#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    unifi_api.py
# Description: Minimal read-mostly UniFi controller API client for the
#              UniFiHealth plugin. Handles UniFi OS (UDM/UDR) and legacy
#              controllers. Read endpoints for health/diagnostics; cmd/devmgr
#              for AP restart / PoE power-cycle / locate.
# Author:      CliveS & Claude Opus 4.8; Claude Opus 5.5 (1.2-1.3)
# Date:        05-10-2026
# Version:     1.3
#
# v1.3 (05-10-2026): set_radio_tx_power -- one radio's transmit power, through
#       upd/device with the whole radio_table, read back after the write.
# v1.2 (27-09-2026): set_radio_min_rssi no longer refuses 2.4GHz outright --
#       the plugin decides by Network version before calling it.
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

TX_POWER_MODES   = ("auto", "low", "medium", "high", "custom")
TX_POWER_MIN_DBM = 1
TX_POWER_MAX_DBM = 30
RADIO_NAMES      = {"ng": "2.4 GHz", "na": "5 GHz", "6e": "6 GHz"}


def describe_tx_power(mode, power=None):
    """'High', 'Auto', 'custom 12 dBm' -- for log lines, never a raw token."""
    if mode == "custom":
        return f"custom {power} dBm"
    return str(mode or "unknown").capitalize()


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
    # DO NOT send per-radio min_rssi writes to Network 10+ without re-testing.
    # The plugin refuses them up front there (plugin.py per_ap_min_rssi_supported).
    # On this controller (Network 10.5.67) they are a dead end, in two ways:
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

        # v1.2: no blanket 2.4GHz refusal here any more. It was right for
        # Network 10 and wrong for 9 and earlier, where the per-radio field is
        # real. The plugin now refuses the whole controller up front on
        # Network 10+ (per_ap_min_rssi_supported), and the read-back below
        # still reports any field a controller silently ignores.
        try:
            doc = self.get_device_config(device_id, site)
        except UniFiError as err:
            return False, (f"this controller has no per-access-point settings route "
                           f"({err}), which is how UniFi Network 10 and later behave. "
                           f"Nothing was changed.")
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

    # ── transmit power (v1.3, 05-10-2026) ──────────────────────────────────
    #
    # Network 10 has no rest/device, but PUT upd/device/<_id> with the WHOLE
    # radio_table stores tx_power_mode (measured 29-09 and 05-10-2026: Dining
    # Room U7-Pro 2.4 GHz auto -> high, stored, AP re-provisioned in under two
    # minutes). The table is taken from stat/device, edited in place and sent
    # back whole, because a list-valued key replaces the stored list.

    def _ap_row(self, device_id, site="default"):
        for row in self.get_devices(site):
            if row.get("_id") == device_id:
                return row
        return None

    def set_radio_tx_power(self, device_id, radio, mode, power=None,
                           site="default", dry_run=False):
        """Set the transmit power of ONE radio on one AP. Returns (ok, message).

        `radio` is "ng" (2.4GHz), "na" (5GHz) or "6e" (6GHz). `mode` is one of
        TX_POWER_MODES; "custom" needs `power` in dBm. A radio that is switched
        off is refused: writing a power mode to it would switch it back on.
        """
        mode = str(mode or "").strip().lower()
        if mode not in TX_POWER_MODES:
            return False, f"power mode {mode!r} is not one of {', '.join(TX_POWER_MODES)}"
        if mode == "custom":
            try:
                power = int(power)
            except (TypeError, ValueError):
                return False, f"custom power {power!r} is not a whole number of dBm"
            if not (TX_POWER_MIN_DBM <= power <= TX_POWER_MAX_DBM):
                return False, f"custom power {power} dBm is outside {TX_POWER_MIN_DBM}-{TX_POWER_MAX_DBM}"

        row = self._ap_row(device_id, site)
        if row is None:
            return False, "access point not found on the controller"
        table = row.get("radio_table")
        if not isinstance(table, list) or not table:
            return False, "access point has no radio table"
        entry = next((e for e in table if e.get("radio") == radio), None)
        if entry is None:
            return False, f"this access point has no {RADIO_NAMES.get(radio, radio)} radio"
        was = entry.get("tx_power_mode")
        if was == "disabled":
            return False, (f"the {RADIO_NAMES.get(radio, radio)} radio is switched off, "
                           f"and setting its power would switch it on. Nothing was changed.")
        was_power = entry.get("tx_power")
        if was == mode and (mode != "custom" or str(was_power) == str(power)):
            return True, f"already {describe_tx_power(mode, power)}, nothing sent"
        if dry_run:
            return True, f"would change {describe_tx_power(was, was_power)} to {describe_tx_power(mode, power)}"

        entry["tx_power_mode"] = mode
        if mode == "custom":
            entry["tx_power"] = power
        if self.session is None:
            self.login()
        url = f"{self.base}{self._prefix}/s/{site}/upd/device/{device_id}"
        try:
            r = self.session.put(url, json={"radio_table": table}, timeout=self.timeout)
            if r.status_code == 401:
                self.login()
                r = self.session.put(url, json={"radio_table": table}, timeout=self.timeout)
        except Exception as err:
            return False, f"PUT connection error: {err}"
        if r.status_code != 200:
            return False, f"PUT -> HTTP {r.status_code} {r.text[:120]}"

        # A 200 is not evidence: this route silently drops some fields.
        check = self._ap_row(device_id, site) or {}
        got = next((e for e in (check.get("radio_table") or []) if e.get("radio") == radio), {})
        if got.get("tx_power_mode") != mode or (mode == "custom" and str(got.get("tx_power")) != str(power)):
            return False, (f"the controller answered OK but holds "
                           f"{describe_tx_power(got.get('tx_power_mode'), got.get('tx_power'))}")
        return True, f"changed from {describe_tx_power(was, was_power)} to {describe_tx_power(mode, power)}"

    def close(self):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None
