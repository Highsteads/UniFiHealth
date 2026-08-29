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

    # ── config WRITE (rest/device) ─────────────────────────────────────────
    # Added 29-08-2026. Everything above this line is read-only; everything
    # below can change the controller's stored configuration, so it is kept
    # together and every method here reads before it writes.

    def get_device_config(self, device_id, site="default"):
        """The full stored config document for one device, by its Mongo _id.

        This is the document rest/device PUT edits, and it is NOT the same shape
        as the stat/device row get_devices() returns — that one is stats plus
        config merged. Always start an edit from this.
        """
        rows = self._get(f"rest/device/{device_id}", site)
        return rows[0] if rows else {}

    def put_device_config(self, device_id, payload, site="default"):
        """PUT a partial config document. Returns (ok: bool, message: str).

        DANGER, and the whole reason the helpers below exist: a list-valued key
        REPLACES the stored list wholesale. Sending a radio_table that holds
        only the radio you meant to edit DELETES every other radio's settings on
        that AP. Never hand-build a list for this — read the current document,
        edit the copy in place, and send the entire list back.
        """
        if self.session is None:
            self.login()
        url = f"{self.base}{self._prefix}/s/{site}/rest/device/{device_id}"
        try:
            r = self.session.put(url, json=payload, timeout=self.timeout)
            if r.status_code == 401:
                self._log("session expired (401) on PUT — re-login")
                self.login()
                r = self.session.put(url, json=payload, timeout=self.timeout)
        except Exception as err:
            return False, f"PUT connection error: {err}"
        if r.status_code != 200:
            body = ""
            try:
                body = str(r.json().get("meta", {}).get("msg", ""))
            except Exception:
                body = r.text[:160]
            return False, f"PUT -> HTTP {r.status_code} {body}".strip()
        return True, "ok"

    # ── what min-RSSI actually is on Network 10 (measured 29-08-2026) ──────
    #
    # DO NOT reinstate per-radio min_rssi writes without re-testing. On this
    # controller (Network 10.5.67) they are a dead end, in two separate ways:
    #
    #   * `rest/device` — the classic device-config endpoint — is GONE. Every
    #     shape of it (by _id, by mac, the bare collection) returns
    #     api.err.NotFound.
    #   * The older `upd/device/<id>` route DOES still work for radio_table —
    #     but only for some fields, which is the trap. Measured on this
    #     controller: `channel` writes STORE (Living Room In-Wall ng went
    #     auto -> 11 and read back 11), while `min_rssi` on the same PUT, in the
    #     same table, through the same route, is SILENTLY DISCARDED (Bedroom AP:
    #     sent -70, got HTTP 200, read back -80 unchanged).
    #
    #     So the rule is not "this endpoint is dead" — it is "min_rssi is a dead
    #     FIELD and the endpoint will not tell you". A caller trusting the 200
    #     would report six APs configured having changed nothing. This is why
    #     every write in this module reads back: a 200 is not evidence, and the
    #     same request can be half-honoured.
    #
    # The min_rssi / min_rssi_enabled fields still PRESENT in stat/device output
    # are vestigial. They describe what an older controller once stored.
    #
    # Steering now lives per-SSID in `rest/wlanconf`, which does work (PUT
    # stores and reads back correctly — proven by writing -76 and restoring
    # -75 on an inert field). But the only bands offered are `na` (5GHz) and
    # `6e`: **there is no roaming_assistant_ng_*, so 2.4GHz has no min-RSSI at
    # all on this version.** For a 2.4-only SSID the available levers are
    # `bss_transition` (802.11v — the AP suggests a better AP instead of
    # kicking) and `minrate_ng_data_rate_kbps` (a floor that distant clients
    # cannot hold, which sheds them without a hard disconnect).

    def get_wlans(self, site="default"):
        """Every WLAN's full config document. This IS editable — see put_wlan."""
        if self.session is None:
            self.login()
        url = f"{self.base}{self._prefix}/s/{site}/rest/wlanconf"
        r = self.session.get(url, timeout=self.timeout)
        if r.status_code == 401:
            self.login()
            r = self.session.get(url, timeout=self.timeout)
        if r.status_code != 200:
            raise UniFiError(f"GET rest/wlanconf -> HTTP {r.status_code}")
        return r.json().get("data", [])

    def set_wlan_fields(self, wlan_id, fields, site="default", dry_run=False):
        """Set named fields on one WLAN, verifying each one landed.

        Returns (ok, message). Partial writes are reported as failures naming
        the fields that did not stick, because the controller returns 200 for a
        field it chose to ignore just as readily as for one it stored.
        """
        if not isinstance(fields, dict) or not fields:
            return False, "no fields given"
        current = {w["_id"]: w for w in self.get_wlans(site)}
        wlan = current.get(wlan_id)
        if wlan is None:
            return False, f"WLAN {wlan_id} not found"
        deltas = {k: v for k, v in fields.items() if wlan.get(k) != v}
        if not deltas:
            return True, "already set — nothing sent"
        if dry_run:
            return True, "would set " + ", ".join(
                f"{k}: {wlan.get(k)!r} -> {v!r}" for k, v in sorted(deltas.items()))

        url = f"{self.base}{self._prefix}/s/{site}/rest/wlanconf/{wlan_id}"
        try:
            r = self.session.put(url, json=deltas, timeout=self.timeout)
        except Exception as err:
            return False, f"PUT connection error: {err}"
        if r.status_code != 200:
            return False, f"PUT -> HTTP {r.status_code} {r.text[:120]}"

        after = {w["_id"]: w for w in self.get_wlans(site)}.get(wlan_id) or {}
        ignored = [k for k, v in deltas.items() if after.get(k) != v]
        if ignored:
            return False, ("controller accepted the PUT but did not store: "
                           + ", ".join(sorted(ignored)))
        return True, "set " + ", ".join(
            f"{k}: {wlan.get(k)!r} -> {v!r}" for k, v in sorted(deltas.items()))

    def set_radio_min_rssi(self, device_id, radio, value, enabled=True,
                           site="default", dry_run=False):
        """Set min-RSSI on ONE radio of one AP, preserving every other setting.

        `radio` is UniFi's band name: "ng" = 2.4GHz, "na" = 5GHz, "6e" = 6GHz.
        Returns (ok, message). With dry_run the change is described and nothing
        is sent, which is how the caller previews a fleet-wide edit.

        min_rssi is stored as a NEGATIVE integer. A positive number here would
        be accepted by some firmware and silently mean something absurd, so it
        is normalised and range-checked rather than trusted.
        """
        try:
            value = int(value)
        except (TypeError, ValueError):
            return False, f"min_rssi {value!r} is not a number"
        if value > 0:
            value = -value
        if not (-94 <= value <= -60):
            return False, f"min_rssi {value} outside the sane range -94..-60"

        if radio == "ng":
            return False, ("2.4GHz has no min-RSSI on this controller — the field "
                           "is vestigial and writes are silently ignored. Use "
                           "bss_transition or minrate_ng_data_rate_kbps instead.")
        try:
            doc = self.get_device_config(device_id, site)
        except UniFiError as err:
            return False, (f"per-radio config write is unavailable on this controller "
                           f"({err}). See the note above set_radio_min_rssi.")
        if not doc:
            return False, "device config not found"
        table = doc.get("radio_table")
        if not isinstance(table, list) or not table:
            return False, "device has no radio_table (not an AP?)"

        found = None
        for entry in table:
            if entry.get("radio") == radio:
                found = entry
                break
        if found is None:
            return False, f"no {radio} radio on this device"

        was = (found.get("min_rssi_enabled"), found.get("min_rssi"))
        if was == (bool(enabled), value):
            return True, f"already {value} ({'on' if enabled else 'off'}) — nothing sent"
        if dry_run:
            return True, f"would set {radio} min_rssi {was[1]} -> {value}, enabled {was[0]} -> {bool(enabled)}"

        found["min_rssi_enabled"] = bool(enabled)
        found["min_rssi"] = value
        ok, msg = self.put_device_config(device_id, {"radio_table": table}, site)
        if not ok:
            return False, msg

        # Read back. A 200 means the controller accepted the document, not that
        # it stored what we meant — and a silently-ignored field would look
        # exactly like success.
        check = self.get_device_config(device_id, site)
        for entry in (check.get("radio_table") or []):
            if entry.get("radio") == radio:
                if entry.get("min_rssi") == value and bool(entry.get("min_rssi_enabled")) == bool(enabled):
                    return True, f"{radio} min_rssi {was[1]} -> {value}, enabled {was[0]} -> {bool(enabled)}"
                return False, (f"write not reflected: asked {value}/{enabled}, "
                               f"controller holds {entry.get('min_rssi')}/{entry.get('min_rssi_enabled')}")
        return False, "read-back could not find the radio"

    def close(self):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None
