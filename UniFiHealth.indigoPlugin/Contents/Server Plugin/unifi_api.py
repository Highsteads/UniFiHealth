#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    unifi_api.py
# Description: Minimal read-mostly UniFi controller API client for the
#              UniFiHealth plugin. Handles UniFi OS (UDM/UDR) and legacy
#              controllers. Read endpoints for health/diagnostics; cmd/devmgr
#              for AP restart / PoE power-cycle / locate.
# Author:      CliveS & Claude Opus 4.8
# Date:        29-06-2026
# Version:     1.1
#
# v1.1: added get_rogue_aps (stat/rogueap, RF-neighbour analysis) and
#       get_sysinfo (stat/sysinfo, controller version).
#
# Credits: the controller-type detection, dual-URL templates and cookie/CSRF
# handling are adapted from FlyingDiver's MIT-licensed Indigo-miniUniFi
# (https://github.com/FlyingDiver/Indigo-miniUniFi), and informed by kw123's
# MIT-licensed unifi plugin (Protect / Cloud Key handling). Endpoints validated
# against a UniFi OS 4 / Network 9 UDR on 30-May-2026.

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class UniFiError(Exception):
    """Any controller connection / auth / request failure."""
    pass


class UniFiSession:
    """One controller connection: detects the controller type, logs in, holds
    the session cookie + CSRF token, and exposes the read endpoints we need
    plus cmd/devmgr commands (restart / power-cycle / locate)."""

    def __init__(self, host, username, password, port=443, verify=False,
                 timeout=8.0, logger=None):
        self.host     = host
        self.username = username
        self.password = password
        self.port     = int(port) if port else 443
        self.verify   = verify
        self.timeout  = float(timeout)
        self.logger   = logger
        self.unifi_os = None          # True (UDM/UDR) / False (legacy), set by detect()
        self.session  = None
        self.base     = None

    def _log(self, message, level="debug"):
        if self.logger:
            getattr(self.logger, level, self.logger.debug)(f"[unifi_api] {message}")

    # ── controller-type detection ──────────────────────────────────────────
    def detect(self):
        """HEAD the root: 200 => UniFi OS (UDM/UDR), 302 => legacy controller."""
        url = f"https://{self.host}:{self.port}"
        try:
            r = requests.head(url, verify=self.verify, timeout=self.timeout, allow_redirects=False)
        except Exception as err:
            raise UniFiError(f"controller unreachable at {url}: {err}")
        self.unifi_os = (r.status_code == 200)
        self._log(f"detected {'UniFi OS' if self.unifi_os else 'legacy'} controller (HEAD {r.status_code})")
        return self.unifi_os

    # ── URL helpers ────────────────────────────────────────────────────────
    @property
    def _prefix(self):
        return "/proxy/network/api" if self.unifi_os else "/api"

    def _login_url(self):
        return f"{self.base}/api/auth/login" if self.unifi_os else f"{self.base}/api/login"

    def _api(self, path, site="default"):
        return f"{self.base}{self._prefix}/s/{site}/{path}"

    # ── login ──────────────────────────────────────────────────────────────
    def login(self):
        if self.unifi_os is None:
            self.detect()
        # UniFi OS always serves on 443 via its proxy; legacy uses the given port.
        self.base = f"https://{self.host}" if self.unifi_os else f"https://{self.host}:{self.port}"
        self.session = requests.Session()
        self.session.verify = self.verify
        headers = {"Accept": "application/json", "Content-Type": "application/json", "referer": "/login"}
        body = {"username": self.username, "password": self.password, "strict": True}
        try:
            r = self.session.post(self._login_url(), json=body, headers=headers, timeout=self.timeout)
        except Exception as err:
            raise UniFiError(f"login connection error: {err}")
        if r.status_code != 200:
            raise UniFiError(f"login failed: HTTP {r.status_code}")
        csrf = r.headers.get("x-csrf-token") or r.headers.get("X-CSRF-Token")
        if csrf:
            self.session.headers["X-CSRF-Token"] = csrf
        self._log("login OK")
        return True

    # ── raw GET (re-login once on 401) ─────────────────────────────────────
    def _get(self, path, site="default"):
        if self.session is None:
            self.login()
        url = self._api(path, site)
        r = self.session.get(url, timeout=self.timeout)
        if r.status_code == 401:
            self._log("session expired (401) — re-login")
            self.login()
            r = self.session.get(url, timeout=self.timeout)
        if r.status_code != 200:
            raise UniFiError(f"GET {path} -> HTTP {r.status_code}")
        return r.json().get("data", [])

    # ── read endpoints ─────────────────────────────────────────────────────
    def get_sites(self):
        if self.session is None:
            self.login()
        r = self.session.get(f"{self.base}{self._prefix}/self/sites", timeout=self.timeout)
        if r.status_code != 200:
            raise UniFiError(f"get_sites -> HTTP {r.status_code}")
        return r.json().get("data", [])

    def get_devices(self, site="default"):
        """stat/device — APs, switches, gateway, with radio_table (+ _stats)."""
        return self._get("stat/device", site)

    def get_clients(self, site="default"):
        """stat/sta — connected clients with signal / satisfaction / ap_mac."""
        return self._get("stat/sta", site)

    def get_health(self, site="default"):
        """stat/health — per-subsystem (wlan / wan / www / lan) status, incl.
        the controller's periodic ISP speedtest result and internet latency."""
        return self._get("stat/health", site)

    def get_rogue_aps(self, site="default"):
        """stat/rogueap — neighbouring / rogue BSSIDs the APs can hear. Powers
        the RF-neighbourhood (co-channel congestion) analysis."""
        return self._get("stat/rogueap", site)

    def get_sysinfo(self, site="default"):
        """stat/sysinfo — one row of controller/console build info. Returns the
        single row (or {}); the caller wants version, not a list."""
        rows = self._get("stat/sysinfo", site)
        return rows[0] if rows else {}

    # ── commands (cmd/devmgr) — restart / power-cycle / locate ─────────────
    def command(self, mac, cmd, site="default", **extra):
        """Issue a devmgr command. Returns (ok: bool, message: str). Uses the
        CSRF token captured at login. cmd/devmgr is a command endpoint (distinct
        from the config-REST endpoint that 404s on some firmware)."""
        if self.session is None:
            self.login()
        url = f"{self.base}{self._prefix}/s/{site}/cmd/devmgr"
        body = {"cmd": cmd, "mac": mac}
        body.update(extra)
        try:
            r = self.session.post(url, json=body, timeout=self.timeout)
        except Exception as err:
            return False, f"command connection error: {err}"
        if r.status_code != 200:
            return False, f"command '{cmd}' -> HTTP {r.status_code}"
        return True, "ok"

    def close(self):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None
