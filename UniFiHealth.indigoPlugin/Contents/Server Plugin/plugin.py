#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: UniFi Health — WiFi health, client/presence and a config audit
#              for UniFi controllers (UDM/UDR + legacy). Read-mostly; cmd/devmgr
#              actions for AP restart / locate.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     0.6.4
#
# v0.6.3 (21-07-2026): shared plugin_utils.py refreshed to v1.3 — the
# estate-wide propagation of the four Appliance Monitor deep-review fixes.
# * install_timestamp_filter() is idempotent — a second call used to stack a
#   second filter, so every log line came out with two timestamps.
# * `import indigo` is soft, so the module imports outside the Indigo host and
#   can be exercised by offline tests.
# * A malformed log call keeps its arguments in the log instead of dropping
#   them, so a %-placeholder mismatch is visible.
# * New shared as_bool() — a pref re-serialised as the string "false" is
#   truthy, which is exactly the wrong answer.
#
# v0.6.2: FAILURE ISOLATION in runConcurrentThread — the whole per-tick poll
#         body is now wrapped so one transient failure (live 14-Jul-2026: the
#         controller took >8s and the requests Read-timeout escaped, killing
#         the thread until Indigo's 10s auto-restart) logs-and-skips the
#         cycle. First failure warns, further failures go quiet (debug), and
#         recovery logs an info line with the failed-cycle count.
# v0.6.1: NEW "Geofence Switch" device type (type="relay") — a pure status
#         switch for the fusion (actionControlDevice just sets onOffState).
#         The Virtual Devices plugin's pseudoRelay turned out to be an
#         action-group front, not a dumb switch: bare ones error ("improperly
#         configured - incorrect ON execution type") and never change state,
#         so HomeKit flips silently did nothing. deviceUpdated's geofence
#         fast-path now runs BEFORE the own-plugin guard (the switch is ours
#         now; loop-safe — watched and written device sets are disjoint), and
#         the geofence picker lists our own switches first.
# v0.6.0: GEOFENCE FUSION — a unifiClient may pair an optional on/off device
#         (a virtual switch flipped by the phone's HomeKit leave/arrive
#         automations via HomeKitLink-Siri; ON = inside the home zone).
#         Verdict comes from presence_fusion.fused_presence: home when EITHER
#         witness says home; away the moment the geofence says gone AND the
#         phone isn't on Wi-Fi (no 10-minute wait). subscribeToChanges +
#         deviceUpdated (own-plugin loop guard) applies a geofence flip in
#         seconds. New presenceSource state (wifi/geofence/wifi+geofence);
#         pure logic in presence_fusion.py with contract tests (test_fusion.py).
# v0.5.1: AP offline detection is now debounced — onState only flips to Offline
#         (firing "AP down" automations) after an AP has been continuously
#         non-connected for apOfflineGraceMinutes (default 3). This rides out
#         reboot / firmware-upgrade blips while still catching a genuine outage.
#         During the grace window the AP stays "up" but apState shows the live
#         label (e.g. "Upgrading"). New apOfflineGraceMinutes pref; tidied the
#         state-code labels.
# v0.5.0: surfaces a lot of data the controller already returns. Controller now
#         publishes Internet/WAN health (ISP speedtest down/up, latency, drops,
#         public WAN IP, gateway CPU/mem), client roll-ups (wired/wireless,
#         Wi-Fi generation mix, legacy a/b/g count, worst-clients list), a
#         firmware-updates-pending count, and an RF-neighbourhood analysis
#         (stat/rogueap — neighbour AP count per 2.4GHz channel). Each AP now
#         publishes firmware version + upgradable flag, CPU/mem/load, wired
#         uplink speed vs capability (under-speed flag), uplink switch+port,
#         live throughput and co-channel neighbour count. New unifi_api
#         get_rogue_aps / get_sysinfo. All extras independently guarded.
# v0.4.1: AP online/offline now derived from the controller's 'state' field
#         (1 = connected). An adopted-but-disconnected AP is still listed by the
#         controller (state 0), so the old "missing from list" check reported a
#         dead AP as online. Now reports Offline (with the reason where known).
# v0.4.0: AP discovery now keys off the controller's is_access_point flag (with
#         a legacy 'uap' fallback), so Wi-Fi consoles like the UDR/UDM are found
#         and shown as access points. Forgotten/un-adopted APs are now
#         auto-removed too (dependency-safe, grace period, autoRemoveAPs pref).
# v0.2.0: each AP now publishes its connected wireless clients as a clientsJson
#         state (name/band/signal/satisfaction) for the Dashboards WiFi AP page.
# v0.1.1: AP device name auto-syncs to the UniFi name (handles swaps/renames);
#         online APs now show the green (on) state image regardless of audit flags.
# Engine patterns adapted from FlyingDiver's MIT Indigo-miniUniFi; PoE/locate
# command idea + broad controller support informed by kw123's MIT unifi plugin.

import indigo
import json
import os as _os
import sys as _sys

_sys.path.insert(0, _os.getcwd())
try:
    from plugin_utils import log_startup_banner, install_timestamp_filter
except ImportError:
    log_startup_banner = None
    install_timestamp_filter = None

from unifi_api import UniFiSession, UniFiError

# Credentials: IndigoSecrets.py first, PluginConfig / device fields as fallback.
_sys.path.insert(0, "/Library/Application Support/Perceptive Automation")
try:
    from IndigoSecrets import UNIFI_HOST
except ImportError:
    UNIFI_HOST = ""
try:
    from IndigoSecrets import UNIFI_USERNAME
except ImportError:
    UNIFI_USERNAME = ""
try:
    from IndigoSecrets import UNIFI_PASSWORD
except ImportError:
    UNIFI_PASSWORD = ""
try:
    from IndigoSecrets import PUSHOVER_USER_TOKEN
except ImportError:
    PUSHOVER_USER_TOKEN = ""

from presence_fusion import fused_presence, presence_source

PLUGIN_VERSION = "0.6.4"
FOLDER_NAME = "UniFi Health"


def _as_int(value, default):
    """Coerce to int, returning default on blank/non-numeric config input."""
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default


def _as_float(value, default):
    """Coerce to float, returning default on blank/non-numeric config input."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# UniFi device 'state' codes — 1 = connected/online. Anything else means the AP
# is adopted but not currently serving Wi-Fi; these are the labels we surface.
# Codes vary a little across firmware, so unmapped values fall back to a generic
# label rather than asserting a wrong cause.
_AP_STATE_UI = {0: "Offline", 1: "Connected", 2: "Pending adoption", 4: "Upgrading",
                5: "Provisioning", 6: "Heartbeat missed", 7: "Adopting",
                8: "Deleting", 9: "Adoption failed", 11: "Isolated"}

# UniFi client radio_proto -> Wi-Fi generation bucket (client-mix roll-up).
# a/b/g are the legacy standards that hog 2.4 GHz airtime; 'b' is the worst.
WIFI_GEN = {"be": "7", "ax": "6", "ac": "5", "n": "4", "ng": "4", "na": "4",
            "g": "legacy", "a": "legacy", "b": "legacy"}

# UniFi radio identifiers -> friendly band labels.
RADIO_BAND = {"ng": "24", "na": "5", "6e": "6"}
# Client records report the radio they're on as ng/na/6e — map to a UI band label.
CLIENT_BAND_UI = {"ng": "2.4", "na": "5", "6e": "6"}


def _is_access_point(data):
    """True when this stat/device entry is an access point. Keyed off the
    controller's own is_access_point flag, with a legacy 'uap' fallback. This
    catches Wi-Fi-capable consoles such as the UDR/UDM — controller type 'udm',
    NOT 'uap' — which broadcast Wi-Fi and report is_access_point=True. Pure
    gateways and switches (usw) report is_access_point False/None and are
    correctly excluded."""
    return bool(data.get("is_access_point")) or data.get("type") == "uap"


# Consecutive successful polls an AP must be absent from the controller's device
# list before its Indigo device is auto-removed — guards against a single odd
# controller response deleting a device. Forgotten/un-adopted APs leave the
# list entirely; merely offline APs stay in it (state 0), so are never reaped.
AP_REMOVE_GRACE_POLLS = 3


def secs_to_ui(seconds):
    seconds = int(seconds or 0)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    return f"{d}d {h:02}:{m:02}"


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        if install_timestamp_filter:
            install_timestamp_filter(self, enabled=True)

        self.update_frequency = max(30.0, _as_float(pluginPrefs.get("updateFrequency"), 60.0))
        self.util_warn = _as_int(pluginPrefs.get("utilWarnPct"), 70)
        self.sat_warn = _as_int(pluginPrefs.get("satisfactionWarn"), 80)
        self.pushover_alerts = bool(pluginPrefs.get("pushoverAlerts", False))
        # Presence (v0.3.0): minutes off the network before a tracked client
        # flips to away. Home is instant; away waits this long.
        self.away_minutes = max(2, _as_int(pluginPrefs.get("awayMinutes"), 10))
        # AP offline debounce (v0.5.1): minutes an AP must be continuously
        # non-connected before onState flips to Offline (and any "AP down"
        # automation fires). Rides out reboot / firmware-upgrade blips; a
        # genuine outage still alerts after this long.
        self.ap_offline_grace_secs = max(0, _as_int(pluginPrefs.get("apOfflineGraceMinutes"), 3)) * 60

        self.controllers = {}      # controllerDevId -> cache dict
        self.ap_devices = {}       # apDevId -> controllerDevId
        self.client_devices = {}   # clientDevId -> controllerDevId
        self.client_last_seen = {} # clientDevId -> epoch of last sighting
        # Geofence fusion (v0.6.0): geofenceDevId -> set(clientDevId) so a
        # HomeKit leave/arrive flip re-evaluates presence within seconds
        # rather than waiting for the next controller poll.
        self.geofence_watch = {}
        self.event_triggers = {}   # triggerId -> trigger
        self._alert_times = {}     # alert-key -> last-sent epoch (Pushover debounce)
        self.next_update = 0.0

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def startup(self):
        self.logger.info(f"Starting UniFi Health {PLUGIN_VERSION}")
        # Geofence fusion (v0.6.0): watch for geofence-switch flips so a
        # HomeKit leave/arrive lands in seconds. deviceUpdated has the
        # mandatory own-plugin loop guard.
        indigo.devices.subscribeToChanges()
        folder_id = self._ensure_folder()
        if folder_id:
            for dev in indigo.devices.iter("self"):
                if dev.folderId != folder_id:
                    try:
                        indigo.device.moveToFolder(dev, value=folder_id)
                    except Exception as err:
                        self.logger.error(f"{dev.name}: move to folder failed: {err}")

        # auto-create a controller from stored credentials if there isn't one yet
        controllers = [d for d in indigo.devices.iter("self") if d.deviceTypeId == "unifiController"]
        if not controllers and self._have_creds():
            try:
                indigo.device.create(protocol=indigo.kProtocol.Plugin, name="UniFi Controller",
                                     deviceTypeId="unifiController", folder=folder_id, props={})
                self.logger.info("Auto-created UniFi Controller from stored credentials")
            except Exception as err:
                self.logger.error(f"auto-create controller failed: {err}")
        elif not controllers:
            self.logger.info("No UniFi Controller yet — add one, or set UNIFI_* in IndigoSecrets.py")

    def _have_creds(self):
        """True only when IndigoSecrets.py supplies a complete credential set —
        used to decide whether to auto-create the controller at startup."""
        return bool(UNIFI_HOST and UNIFI_USERNAME and UNIFI_PASSWORD)

    def _ensure_folder(self):
        """Return the 'UniFi Health' device folder id, creating it if needed."""
        try:
            for folder in indigo.devices.folders:
                if folder.name == FOLDER_NAME:
                    return folder.id
            return indigo.devices.folder.create(FOLDER_NAME).id
        except Exception as err:
            self.logger.error(f"device folder '{FOLDER_NAME}' create/find failed: {err}")
            return 0

    def runConcurrentThread(self):
        # Failure isolation (v0.6.2): the WHOLE per-tick body is wrapped so a
        # transient failure (e.g. the controller taking >8s to answer — seen
        # live 14-Jul-2026 as a Read timed out that killed this thread) logs
        # and skips the cycle instead of taking the loop down. First failure
        # warns; a continuing outage stays quiet until recovery is logged.
        poll_failures = 0
        try:
            while True:
                now = self._now()
                if now >= self.next_update:
                    self.next_update = now + self.update_frequency
                    try:
                        for controller_id in list(self.controllers):
                            self._poll_controller(indigo.devices[controller_id])
                        for ap_id in list(self.ap_devices):
                            self._update_ap(indigo.devices[ap_id])
                        for client_id in list(self.client_devices):
                            self._update_client(indigo.devices[client_id])
                        if poll_failures:
                            self.logger.info(
                                f"controller poll recovered after {poll_failures} failed cycle(s)")
                            poll_failures = 0
                    except self.StopThread:
                        raise
                    except Exception as err:
                        poll_failures += 1
                        if poll_failures == 1:
                            self.logger.warning(
                                f"controller poll failed (will keep retrying quietly): {err}")
                        else:
                            self.logger.debug(f"controller poll failed x{poll_failures}: {err}")
                self.sleep(2.0)
        except self.StopThread:
            pass

    @staticmethod
    def _now():
        import time
        return time.time()

    def deviceStartComm(self, device):
        self.logger.debug(f"deviceStartComm: {device.name}")
        if device.deviceTypeId == "unifiController":
            self.controllers[device.id] = {"session": None, "devices_by_mac": {},
                                           "clients_by_mac": {}, "ch24": {}, "ap_uptime": {},
                                           "ap_missing": {}, "rf24": {}, "ap_off_since": {}}
            # Register states added since this controller device was created
            # (e.g. the v0.5.0 WAN / client-mix / RF states) so the next poll
            # can write them on an existing device without delete+recreate.
            try:
                device.stateListOrDisplayStateIdChanged()
            except Exception as err:
                self.logger.debug(f"stateListOrDisplayStateIdChanged({device.name}): {err}")
            self.next_update = 0.0
        elif device.deviceTypeId == "unifiAP":
            self.ap_devices[device.id] = _as_int(device.pluginProps.get("unifi_controller"), 0)
            # Register any states added since this device was created (e.g.
            # clientsJson in 0.2.0) so the next poll can write them.
            try:
                device.stateListOrDisplayStateIdChanged()
            except Exception as err:
                self.logger.debug(f"stateListOrDisplayStateIdChanged({device.name}): {err}")
            self.next_update = 0.0
        elif device.deviceTypeId == "unifiClient":
            self.client_devices[device.id] = _as_int(device.pluginProps.get("unifi_controller"), 0)
            # Register the presence states added in 0.3.0 on devices created
            # earlier, then seed last-seen from the persisted epoch so a
            # restart doesn't flap presence.
            try:
                device.stateListOrDisplayStateIdChanged()
                device = indigo.devices[device.id]   # re-fetch — local copy is stale
            except Exception as err:
                self.logger.debug(f"state refresh ({device.name}): {err}")
            seen = _as_int(device.states.get("lastSeenEpoch"), 0)
            if seen:
                self.client_last_seen[device.id] = float(seen)
            if "presence" in device.states and not device.states.get("presence"):
                device.updateStateOnServer("presence", "away")
            # Geofence fusion (v0.6.0): map the optional geofence switch to
            # this client so deviceUpdated can react to a flip immediately.
            geo_id = _as_int(device.pluginProps.get("geofence_device"), 0)
            if geo_id:
                self.geofence_watch.setdefault(geo_id, set()).add(device.id)
                self.logger.info(f"{device.name}: geofence fusion active (device {geo_id})")
            self.next_update = 0.0

    def deviceStopComm(self, device):
        self.logger.debug(f"deviceStopComm: {device.name}")
        if device.deviceTypeId == "unifiController":
            cache = self.controllers.pop(device.id, None)
            if cache and cache.get("session"):
                cache["session"].close()
        elif device.deviceTypeId == "unifiAP":
            self.ap_devices.pop(device.id, None)
        elif device.deviceTypeId == "unifiClient":
            self.client_devices.pop(device.id, None)
            for watchers in self.geofence_watch.values():
                watchers.discard(device.id)

    @staticmethod
    def didDeviceCommPropertyChange(orig_dev, new_dev):
        # Restart comm only when the controller binding, target MAC or
        # geofence pairing changes.
        keys = ("address", "port", "username", "password", "unifi_controller",
                "geofence_device")
        return any(orig_dev.pluginProps.get(k) != new_dev.pluginProps.get(k) for k in keys)

    # ── Geofence fusion (v0.6.0) ───────────────────────────────────────────
    # A geofence switch is any Indigo on/off device flipped by the phone's
    # HomeKit leave/arrive automations (via HomeKitLink-Siri). ON = inside
    # the home zone. We subscribe to device changes so a flip re-evaluates
    # presence within seconds instead of waiting for the next poll.

    def deviceUpdated(self, orig_dev, new_dev):
        super().deviceUpdated(orig_dev, new_dev)
        # Geofence fast-path BEFORE the own-plugin guard: since v0.6.1 the
        # geofence switch is one of OUR devices (geofenceSwitch type). This is
        # loop-safe because the watched set (geofence switches) and the
        # written set (unifiClient presence devices) are disjoint —
        # _update_client never writes a geofence switch, and client-device
        # updates fall through to the guard below.
        watchers = self.geofence_watch.get(new_dev.id)
        if watchers and bool(getattr(orig_dev, "onState", None)) != bool(getattr(new_dev, "onState", None)):
            for client_id in list(watchers):
                try:
                    self._update_client(indigo.devices[client_id])
                except Exception as err:
                    self.logger.debug(f"geofence fast-path update ({client_id}): {err}")
            return
        if new_dev.pluginId == self.pluginId:   # loop guard — ignore own devices
            return

    def actionControlDevice(self, action, dev):
        """Relay control for geofenceSwitch (v0.6.1): a pure status switch —
        on/off/toggle just set the native onOffState. HomeKit's leave/arrive
        automations land here via HomeKitLink-Siri."""
        if dev.deviceTypeId != "geofenceSwitch":
            return
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            new_state = True
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            new_state = False
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            new_state = not bool(dev.onState)
        else:
            return   # RequestStatus etc. — nothing to ask; state is the truth
        dev.updateStateOnServer("onOffState", new_state)
        dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn if new_state
                                     else indigo.kStateImageSel.PowerOff)
        self.logger.info(f"{dev.name}: {'ON (inside home zone)' if new_state else 'OFF (left home zone)'}")

    def _geo_home_for(self, device):
        """True/False from the paired geofence switch; None when not
        configured or unreadable (fusion then degrades to Wi-Fi-only)."""
        geo_id = _as_int(device.pluginProps.get("geofence_device"), 0)
        if not geo_id:
            return None
        try:
            return bool(indigo.devices[geo_id].onState)
        except Exception:
            return None

    def get_geofence_device_list(self, filter="", valuesDict=None, typeId="", targetId=0):
        """ConfigUI menu: on/off-capable devices that could act as a geofence
        switch — virtuals first (the expected case), then everything else."""
        items = [("0", "- none (Wi-Fi only) -")]
        own_switches, others = [], []
        for dev in indigo.devices:
            if dev.pluginId == self.pluginId:
                # our own Geofence Switch type is the expected choice; every
                # other own-plugin type (clients/APs) must never be pairable.
                if dev.deviceTypeId == "geofenceSwitch":
                    own_switches.append((str(dev.id), dev.name))
                continue
            if getattr(dev, "onState", None) is None:
                continue
            others.append((str(dev.id), dev.name))
        items += sorted(own_switches, key=lambda x: x[1].lower())
        items += sorted(others, key=lambda x: x[1].lower())
        return items

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        """Block saving a Controller until it has host + username + password,
        from IndigoSecrets.py and/or the dialog fields. 'Save without configuring'
        or Cancel let the user out either way, so they're never trapped."""
        if typeId != "unifiController" or valuesDict.get("configure_later", False):
            return (True, valuesDict)
        errors = indigo.Dict()
        if not (UNIFI_HOST or valuesDict.get("address", "").strip()):
            errors["address"] = "Enter the controller IP/hostname — not found in IndigoSecrets.py."
        if not (UNIFI_USERNAME or valuesDict.get("username", "").strip()):
            errors["username"] = "Enter the UniFi username — not found in IndigoSecrets.py."
        if not (UNIFI_PASSWORD or valuesDict.get("password", "").strip()):
            errors["password"] = "Enter the UniFi password — not found in IndigoSecrets.py."
        if errors:
            errors["showAlertText"] = ("UniFi credentials are incomplete. Fill in the missing field(s), "
                                       "or tick 'Save without configuring', or click Cancel to discard.")
            return (False, valuesDict, errors)
        return (True, valuesDict)

    # ── Credential resolution (IndigoSecrets -> device -> PluginConfig) ─────

    def _resolve_creds(self, device):
        p = device.pluginProps
        host = UNIFI_HOST or p.get("address", "")
        user = UNIFI_USERNAME or p.get("username", "")
        pw = UNIFI_PASSWORD or p.get("password", "")
        port = p.get("port") or "443"
        verify = p.get("ssl_verify", False)
        return host, user, pw, port, verify

    def _session_for(self, device):
        cache = self.controllers[device.id]
        if cache["session"] is None:
            host, user, pw, port, verify = self._resolve_creds(device)
            if not host or not user or not pw:
                raise UniFiError("no credentials — set UNIFI_* in IndigoSecrets.py or the controller device")
            cache["session"] = UniFiSession(host, user, pw, port=port, verify=verify, logger=self.logger)
            cache["session"].login()
        return cache["session"]

    # ── Controller poll → cache ────────────────────────────────────────────

    def _poll_controller(self, device):
        cache = self.controllers.get(device.id)
        if cache is None:
            return
        try:
            session = self._session_for(device)
            devices = session.get_devices()
            clients = session.get_clients()
            health = session.get_health()
        except UniFiError as err:
            was_connected = (device.states.get("status") == "Connected")
            self.logger.warning(f"{device.name}: {err}")
            device.updateStateOnServer("status", "Unreachable")
            device.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
            if cache.get("session"):
                cache["session"].close()
                cache["session"] = None
            self._fire_event("controllerUnreachable")
            if was_connected:
                self._pushover("ctrl:" + str(device.id), "WiFi Health", "UniFi controller unreachable")
            return

        cache["devices_by_mac"] = {d.get("mac"): d for d in devices}
        cache["clients_by_mac"] = {c.get("mac"): c for c in clients}

        # cross-AP 2.4 GHz channel reuse map (for the audit)
        ch24 = {}
        aps = [d for d in devices if _is_access_point(d)]
        for ap in aps:
            for radio in ap.get("radio_table_stats", []):   # live channel, not "auto" config
                if radio.get("radio") == "ng" and radio.get("channel"):
                    ch24[str(radio["channel"])] = ch24.get(str(radio["channel"]), 0) + 1
        cache["ch24"] = ch24

        # auto-create an AP device for any access point not yet represented
        if self.pluginPrefs.get("autoCreateAPs", True):
            existing = {d.address for d in indigo.devices.iter("self") if d.deviceTypeId == "unifiAP"}
            folder_id = self._ensure_folder()
            for mac, ap in cache["devices_by_mac"].items():
                if _is_access_point(ap) and mac not in existing:
                    try:
                        indigo.device.create(protocol=indigo.kProtocol.Plugin,
                                             name=f"UniFi AP {ap.get('name', mac)}",
                                             deviceTypeId="unifiAP", folder=folder_id,
                                             props={"unifi_controller": str(device.id), "address": mac})
                        self.logger.info(f"Auto-created AP device: {ap.get('name', mac)}")
                    except Exception as err:
                        self.logger.error(f"auto-create AP {mac}: {err}")

        # auto-remove devices for APs the controller has forgotten (own pref)
        self._reap_removed_aps(device.id, set(cache["devices_by_mac"]))

        # controller roll-up states
        wlan = next((h.get("status") for h in health if h.get("subsystem") == "wlan"), "unknown")
        worst_util = 0
        total_issues = 0
        for ap in aps:
            flags = self._audit_ap(ap, ch24)
            total_issues += len(flags)
            for radio in ap.get("radio_table_stats", []):
                worst_util = max(worst_util, radio.get("cu_total") or 0)
        worst_sat = min([c.get("satisfaction", 100) for c in clients if c.get("satisfaction") is not None] or [100])

        device.updateStateOnServer("status", "Connected")
        device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        device.updateStateOnServer("unifiOS", bool(getattr(cache["session"], "unifi_os", False)))
        device.updateStateOnServer("wlanHealth", wlan)
        device.updateStateOnServer("numAPs", len(aps))
        device.updateStateOnServer("numClients", len(clients))
        device.updateStateOnServer("worstApUtilisation", worst_util)
        device.updateStateOnServer("worstClientSatisfaction", worst_sat)
        device.updateStateOnServer("auditIssues", total_issues)

        if wlan != "ok":
            self._fire_event("wlanDegraded")

        # v0.5.0 extras (Internet/WAN, client mix, firmware count, RF) — wholly
        # isolated so a missing field or a rogueap hiccup can never break the poll.
        try:
            self._update_controller_extras(device, cache, health, clients, aps)
        except Exception as err:
            self.logger.debug(f"{device.name}: controller extras failed: {err}")

    # ── v0.5.0 controller extras — WAN / clients / firmware / RF ────────────

    def _update_controller_extras(self, device, cache, health, clients, aps):
        """Populate the richer controller states. Each block is independently
        guarded: one missing subsystem or field must not blank the others."""
        h = {sub.get("subsystem"): sub for sub in (health or [])}

        # ── Internet / WAN (the controller's own www+wan probe + ISP speedtest) ──
        try:
            www = h.get("www", {})
            wan = h.get("wan", {})
            device.updateStateOnServer("wanStatus", www.get("status") or wan.get("status") or "unknown")
            device.updateStateOnServer("wanIp", wan.get("wan_ip", "") or "")
            device.updateStateOnServer("internetLatencyMs", _as_int(www.get("latency"), 0))
            device.updateStateOnServer("internetDrops", _as_int(www.get("drops"), 0))
            device.updateStateOnServer("speedtestDown", round(_as_float(www.get("xput_down"), 0.0), 1))
            device.updateStateOnServer("speedtestUp", round(_as_float(www.get("xput_up"), 0.0), 1))
            last = _as_int(www.get("speedtest_lastrun"), 0)
            device.updateStateOnServer("speedtestAgeHours",
                                       int((self._now() - last) / 3600) if last else -1)
            gw = wan.get("gw_system-stats") or {}
            device.updateStateOnServer("gatewayCpu", int(round(_as_float(gw.get("cpu"), 0.0))))
            device.updateStateOnServer("gatewayMem", int(round(_as_float(gw.get("mem"), 0.0))))
        except Exception as err:
            self.logger.debug(f"WAN extras: {err}")

        # ── Client intelligence roll-ups ──
        try:
            wired = sum(1 for c in clients if c.get("is_wired"))
            gen = {"7": 0, "6": 0, "5": 0, "4": 0, "legacy": 0}
            legacy = 0
            for c in clients:
                if c.get("is_wired"):
                    continue
                proto = (c.get("radio_proto") or "").lower()
                bucket = WIFI_GEN.get(proto)
                if bucket:
                    gen[bucket] += 1
                if proto in ("a", "b", "g"):
                    legacy += 1
            device.updateStateOnServer("numWired", wired)
            device.updateStateOnServer("numWireless", len(clients) - wired)
            device.updateStateOnServer("numLegacyClients", legacy)
            device.updateStateOnServer("wifiGenJson", json.dumps(gen, separators=(",", ":")))
            worst = sorted(
                (c for c in clients if not c.get("is_wired") and c.get("satisfaction") is not None),
                key=lambda c: c.get("satisfaction") or 0)[:6]
            wj = [{"n": c.get("name") or c.get("hostname") or c.get("oui") or c.get("mac"),
                   "sat": c.get("satisfaction"), "sig": c.get("signal"),
                   "ap": c.get("last_uplink_name") or ""} for c in worst]
            device.updateStateOnServer("worstClientsJson", json.dumps(wj, separators=(",", ":")))
        except Exception as err:
            self.logger.debug(f"client extras: {err}")

        # ── Firmware updates pending ──
        try:
            device.updateStateOnServer("apsNeedingUpdate", sum(1 for ap in aps if ap.get("upgradable")))
        except Exception as err:
            self.logger.debug(f"firmware extras: {err}")

        # ── RF neighbourhood (stat/rogueap) — guarded + non-fatal ──
        try:
            rogue = cache["session"].get_rogue_aps()
        except Exception as err:
            self.logger.debug(f"rogueap fetch: {err}")
            rogue = None
        if rogue is not None:
            try:
                rf24 = {}
                n5 = 0
                for r in rogue:
                    ch = r.get("channel")
                    ch = int(ch) if str(ch).isdigit() else None
                    if ch is None:
                        continue
                    if 1 <= ch <= 14:
                        rf24[str(ch)] = rf24.get(str(ch), 0) + 1
                    else:
                        n5 += 1
                cache["rf24"] = rf24
                device.updateStateOnServer("neighbourApCount", len(rogue))
                device.updateStateOnServer("rfJson", json.dumps(
                    {"total": len(rogue), "ch24": rf24, "n5": n5}, separators=(",", ":")))
            except Exception as err:
                self.logger.debug(f"RF extras: {err}")

        # ── Controller version (sysinfo) — fetch once, it rarely changes ──
        if not device.states.get("controllerVersion"):
            try:
                info = cache["session"].get_sysinfo()
                ver = info.get("version") or info.get("console_display_version") or ""
                if ver:
                    device.updateStateOnServer("controllerVersion", ver)
            except Exception as err:
                self.logger.debug(f"sysinfo: {err}")

    # ── Config audit (the headline feature) ────────────────────────────────

    def _audit_ap(self, ap_data, ch24):
        """Return a list of human-readable config issues for this AP."""
        flags = []
        cfg = {r.get("radio"): r for r in ap_data.get("radio_table", [])}
        stt = {r.get("radio"): r for r in ap_data.get("radio_table_stats", [])}
        ng, ngs = cfg.get("ng", {}), stt.get("ng", {})
        na = cfg.get("na", {})

        if ng:
            if str(ng.get("ht")) == "40":
                flags.append("2.4GHz width 40MHz (use 20)")
            if ng.get("tx_power_mode") == "high":
                flags.append("2.4GHz TX power High")
            if not ng.get("min_rssi_enabled", False):
                flags.append("2.4GHz min-RSSI off")
            chan = ngs.get("channel") or ng.get("channel")   # live assigned channel
            if chan and ch24.get(str(chan), 0) > 2:
                flags.append(f"2.4GHz ch{chan} shared by {ch24[str(chan)]} APs")
            util = ngs.get("cu_total")
            if util is not None and util > self.util_warn:
                flags.append(f"2.4GHz util {util}%")
        if na and na.get("tx_power_mode") == "high":
            flags.append("5GHz TX power High")
        return flags

    # ── Auto-remove forgotten APs ──────────────────────────────────────────

    def _reap_removed_aps(self, controller_id, present_macs):
        """Auto-remove unifiAP devices for APs the controller has forgotten
        (un-adopted / replaced) — distinct from merely offline, where the AP is
        still listed (state 0) and so stays in present_macs. Dependency-safe:
        an AP still referenced by a trigger, schedule, action group or control
        page is kept and flagged once, never deleted. Gated on the
        autoRemoveAPs pref plus a grace period so one odd controller response
        can't delete a device."""
        if not self.pluginPrefs.get("autoRemoveAPs", True):
            return
        cache = self.controllers.get(controller_id)
        if cache is None:
            return
        missing = cache.setdefault("ap_missing", {})
        ap_ids = [ap_id for ap_id, ctrl in self.ap_devices.items() if ctrl == controller_id]
        for ap_id in ap_ids:
            try:
                ap_dev = indigo.devices[ap_id]
            except Exception:
                self.ap_devices.pop(ap_id, None)
                continue
            mac = ap_dev.address
            if mac in present_macs:
                missing.pop(mac, None)
                continue
            # absent from the controller's device list on a successful poll
            missing[mac] = missing.get(mac, 0) + 1
            if missing[mac] < AP_REMOVE_GRACE_POLLS:
                continue
            dependents = self._device_dependents(ap_dev)
            if dependents:
                if missing[mac] == AP_REMOVE_GRACE_POLLS:   # warn once, on first block
                    self.logger.warning(
                        f"{ap_dev.name}: removed from the controller but still used by "
                        f"{dependents} — left in place. Delete it manually once unreferenced.")
                    try:
                        ap_dev.updateStateOnServer("apSummary", "Removed from controller (still referenced)")
                    except Exception:
                        pass
                missing[mac] = AP_REMOVE_GRACE_POLLS   # pin — no unbounded growth, no re-warn
                continue
            try:
                name = ap_dev.name
                indigo.device.delete(ap_dev)
                self.ap_devices.pop(ap_id, None)
                missing.pop(mac, None)
                self.logger.info(f"Auto-removed AP device (forgotten by controller): {name}")
            except Exception as err:
                self.logger.error(f"auto-remove AP {ap_dev.name}: {err}")

    @staticmethod
    def _device_dependents(device):
        """Summarise the triggers / schedules / action groups / control pages
        that reference this device, '' when nothing does. On any error returns
        a non-empty sentinel so a destructive auto-remove errs towards keeping
        the device."""
        try:
            deps = indigo.device.getDependencies(device.id)
        except Exception:
            return "an unknown reference (dependency check failed)"
        parts = []
        for key in ("triggers", "schedules", "actionGroups", "controlPages"):
            try:
                items = deps.get(key) or []
            except Exception:
                items = []
            if items:
                parts.append(f"{len(items)} {key}")
        return ", ".join(parts)

    # ── AP device update ───────────────────────────────────────────────────

    def _update_ap(self, device):
        controller_id = self.ap_devices.get(device.id)
        cache = self.controllers.get(controller_id)
        if not cache:
            return
        data = cache["devices_by_mac"].get(device.address)
        # 'state' 1 = connected. Any other value (or a missing entry) means the
        # AP isn't fully serving Wi-Fi — but a reboot / firmware upgrade /
        # provision is a TRANSIENT non-connected blip. So onState is debounced:
        # it only flips to Offline (firing any "AP down" automation) once the AP
        # has been continuously non-connected for ap_offline_grace_secs. During
        # the grace window we keep it 'up' but surface the live state label, so a
        # dashboard can show "Upgrading" without the AP being marked down.
        state = data.get("state") if data else None
        online_now = (state == 1)
        off_since = cache.setdefault("ap_off_since", {})
        if online_now:
            off_since.pop(device.address, None)
        else:
            off_since.setdefault(device.address, self._now())
        offline_secs = 0 if online_now else (self._now() - off_since.get(device.address, self._now()))
        label = (_AP_STATE_UI.get(state, "Unavailable") if data else "Offline")

        if not online_now and offline_secs >= self.ap_offline_grace_secs:
            # sustained non-connected — genuinely down, alert
            device.updateStateOnServer("onOffState", False, uiValue="Offline")
            device.updateStateOnServer("apSummary", label)
            device.updateStateOnServer("apState", label)
            device.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
            return
        if not online_now:
            # transient blip within the grace window — keep it up, show the
            # live label (e.g. "Upgrading"), don't fire the down-alert.
            device.updateStateOnServer("onOffState", True)
            device.updateStateOnServer("apSummary", f"{label}…")
            device.updateStateOnServer("apState", label)
            device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
            return

        cfg = {r.get("radio"): r for r in data.get("radio_table", [])}
        stt = {r.get("radio"): r for r in data.get("radio_table_stats", [])}

        states = []
        states.append({"key": "onOffState", "value": True})
        states.append({"key": "apModel", "value": data.get("model", "")})
        uptime = data.get("uptime", 0)
        states.append({"key": "uptimeSeconds", "value": uptime})
        states.append({"key": "uplinkType", "value": (data.get("uplink") or {}).get("type", "")})
        states.append({"key": "numClients", "value": data.get("num_sta", 0)})

        # reboot detection (uptime dropped since last poll)
        prev = cache["ap_uptime"].get(device.address)
        rebooted = prev is not None and uptime < prev
        cache["ap_uptime"][device.address] = uptime
        states.append({"key": "rebooted", "value": rebooted})
        if rebooted:
            self.logger.warning(f"{device.name}: rebooted (uptime reset)")
            self._fire_event("apRebooted")
            self._pushover("reboot:" + str(device.address), "WiFi Health",
                           "Access point rebooted: " + device.name.replace("UniFi AP ", ""))

        # per-band curated states
        for radio_id, band in RADIO_BAND.items():
            c = cfg.get(radio_id, {})
            s = stt.get(radio_id, {})
            if not c and not s:
                continue
            states.append({"key": f"band{band}Channel", "value": str(s.get("channel") or c.get("channel", ""))})
            states.append({"key": f"band{band}Width", "value": int(c.get("ht") or 0)})
            states.append({"key": f"band{band}Utilisation", "value": s.get("cu_total") or 0})
            states.append({"key": f"band{band}Clients", "value": s.get("num_sta") or 0})
            if band in ("24", "5"):
                states.append({"key": f"band{band}TxPower", "value": c.get("tx_power_mode", "")})
                states.append({"key": f"band{band}Satisfaction", "value": s.get("satisfaction") or 0})
            if band == "24":
                states.append({"key": "band24MinRssiOn", "value": bool(c.get("min_rssi_enabled", False))})

        # audit
        flags = self._audit_ap(data, cache["ch24"])
        states.append({"key": "configOK", "value": len(flags) == 0})
        states.append({"key": "auditFlags", "value": ", ".join(flags)})

        # summary display
        ng_s = stt.get("ng", {})
        ng_c = cfg.get("ng", {})
        summary = f"2.4: ch{ng_s.get('channel', ng_c.get('channel', '?'))} {ng_c.get('ht', '?')}MHz {ng_s.get('cu_total', '?')}%"
        if flags:
            summary += f"  ⚠ {len(flags)}"
        states.append({"key": "apSummary", "value": summary})

        # v0.5.0 — hardware health, uplink quality, firmware, RF neighbours
        sysst = data.get("system-stats") or {}
        loadst = data.get("sys_stats") or {}
        up = data.get("uplink") or {}
        up_speed = _as_int(up.get("speed"), 0)
        up_max = _as_int(up.get("max_speed"), 0)
        ng_chan = str(ng_s.get("channel") or ng_c.get("channel") or "")
        states.append({"key": "apState", "value": "Connected"})
        states.append({"key": "firmwareVersion", "value": data.get("version", "") or ""})
        states.append({"key": "firmwareUpgradable", "value": bool(data.get("upgradable"))})
        states.append({"key": "cpuPct", "value": int(round(_as_float(sysst.get("cpu"), 0.0)))})
        states.append({"key": "memPct", "value": int(round(_as_float(sysst.get("mem"), 0.0)))})
        states.append({"key": "loadAvg1", "value": _as_float(loadst.get("loadavg_1"), 0.0)})
        states.append({"key": "uplinkSpeedMbps", "value": up_speed})
        states.append({"key": "uplinkMaxMbps", "value": up_max})
        states.append({"key": "uplinkUnderspeed", "value": bool(up_speed and up_max and up_speed < up_max)})
        states.append({"key": "uplinkDevice", "value": up.get("uplink_device_name", "") or ""})
        states.append({"key": "uplinkPort", "value": _as_int(up.get("uplink_remote_port"), 0)})
        states.append({"key": "throughputKbps", "value": int((data.get("bytes-r") or 0) / 1024)})
        states.append({"key": "neighbourCount", "value": (cache.get("rf24") or {}).get(ng_chan, 0)})

        # connected wireless clients on this AP (ap_mac maps to this AP's MAC).
        # Published as compact JSON for the Dashboards WiFi AP detail page.
        ap_clients = []
        for mac, c in cache["clients_by_mac"].items():
            if c.get("ap_mac") != device.address:
                continue
            ap_clients.append({
                "n":   c.get("name") or c.get("hostname") or c.get("oui") or mac,
                "b":   CLIENT_BAND_UI.get(c.get("radio"), ""),
                "sig": c.get("signal"),
                "sat": c.get("satisfaction"),
            })
        # strongest/happiest first: satisfaction, then signal
        ap_clients.sort(
            key=lambda x: (x["sat"] if x["sat"] is not None else -1,
                           x["sig"] if x["sig"] is not None else -999),
            reverse=True,
        )
        states.append({"key": "clientsJson", "value": json.dumps(ap_clients, separators=(",", ":"))})

        device.updateStatesOnServer(states)
        # Green (on) when the AP is up — the audit is shown via configOK / auditFlags /
        # the summary, not the status dot. (Offline path above uses the red tripped image.)
        device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

        # Keep the Indigo device name in step with the UniFi name, so an AP swap or
        # rename in UniFi flows through automatically (no stale names to untangle).
        desired = f"UniFi AP {data.get('name', device.address)}"
        if device.name != desired:
            try:
                device.name = desired
                device.replaceOnServer()
                self.logger.info(f"Renamed to match UniFi: {desired}")
            except Exception as err:
                self.logger.debug(f"name sync deferred -> {desired}: {err}")

    # ── Client device update ───────────────────────────────────────────────

    def _set_presence(self, device, new_presence):
        """Apply a debounced presence transition: update states, fire the
        matching custom event, and log the change once."""
        if device.states.get("presence") == new_presence:
            return
        from datetime import datetime
        device.updateStatesOnServer([
            {"key": "presence", "value": new_presence},
            {"key": "presenceChangedUi", "value": datetime.now().strftime("%H:%M %d-%b")},
        ])
        self.logger.info(f"{device.name}: presence -> {new_presence.upper()}")
        self._fire_event("clientArrived" if new_presence == "home" else "clientLeft")

    def _update_client(self, device):
        controller_id = self.client_devices.get(device.id)
        cache = self.controllers.get(controller_id)
        if not cache:
            return
        now = self._now()
        data = cache["clients_by_mac"].get(device.address)
        geo_home = self._geo_home_for(device)
        if not data:
            # Not on the network right now. Wi-Fi-only presence is patient
            # (phones nap off WiFi constantly); with a geofence paired the
            # verdict comes from the fusion table instead — away lands
            # immediately when the geofence agrees, and a napping phone
            # stays home for as long as the geofence vouches for it.
            last_seen = self.client_last_seen.get(device.id, 0.0)
            minutes = int((now - last_seen) / 60) if last_seen else 9999
            verdict = fused_presence(False, minutes, self.away_minutes, geo_home)
            source = presence_source(False, geo_home)
            if verdict == "away":
                summary = f"AWAY {minutes}m"
            elif geo_home:
                summary = f"HOME (geofence · offline {minutes}m)"
            else:
                summary = f"HOME (offline {minutes}m)"
            device.updateStatesOnServer([
                {"key": "onOffState", "value": False},
                {"key": "minutesSinceSeen", "value": min(minutes, 99999)},
                {"key": "offlineSeconds", "value": min(int(now - last_seen) if last_seen else 0, 9999999)},
                {"key": "presenceSource", "value": source},
                {"key": "clientSummary", "value": summary},
            ])
            if verdict == "away":
                self._set_presence(device, "away")
                device.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
            else:
                self._set_presence(device, "home")
                device.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
            return

        # On the network: home, instantly.
        self.client_last_seen[device.id] = now
        sat = data.get("satisfaction")
        signal = data.get("signal")
        ap_name = ""
        ap_data = cache["devices_by_mac"].get(data.get("ap_mac"))
        if ap_data:
            ap_name = ap_data.get("name", "")
        states = [
            {"key": "onOffState", "value": True},
            {"key": "signal", "value": signal or 0},
            {"key": "satisfaction", "value": sat if sat is not None else 0},
            {"key": "apName", "value": ap_name},
            {"key": "essid", "value": data.get("essid", "")},
            {"key": "channel", "value": str(data.get("channel", ""))},
            {"key": "wired", "value": bool(data.get("is_wired", False))},
            {"key": "vendor", "value": data.get("oui", "")},
            {"key": "offlineSeconds", "value": 0},
            {"key": "minutesSinceSeen", "value": 0},
            {"key": "lastSeenEpoch", "value": int(now)},
            {"key": "presenceSource", "value": presence_source(True, geo_home)},
            {"key": "clientSummary", "value": f"HOME · {signal}dBm sat={sat} @ {ap_name}"},
        ]
        device.updateStatesOnServer(states)
        self._set_presence(device, "home")
        device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        if sat is not None and sat < self.sat_warn:
            self._fire_event("clientLowSatisfaction")

    # ── Custom event firing (canonical trigger pattern) ────────────────────

    def triggerStartProcessing(self, trigger):
        self.event_triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.event_triggers.pop(trigger.id, None)

    def _fire_event(self, event_id):
        for trigger in self.event_triggers.values():
            if trigger.pluginTypeId == event_id:
                indigo.trigger.execute(trigger)

    def _pushover(self, key, title, body, cooldown=1800):
        """Send a Pushover alert (vibrate), debounced per key by cooldown seconds.
        Sends only when 'Pushover WiFi alerts' is enabled in the plugin config —
        the point is to page the CAUSE (an AP reboot / controller down), once,
        rather than the ten symptom alerts the dropped clients would generate."""
        if not self.pushover_alerts:
            return
        now = self._now()
        if now - self._alert_times.get(key, 0) < cooldown:
            return
        self._alert_times[key] = now
        try:
            po = indigo.server.getPlugin("io.thechad.indigoplugin.pushover")
            if not (po and po.isEnabled()):
                self.logger.warning("Pushover plugin not available — WiFi alert skipped")
                return
            props = {"msgTitle": title, "msgBody": body, "msgPriority": "0", "msgSound": "vibrate"}
            if PUSHOVER_USER_TOKEN:
                props["msgUser"] = PUSHOVER_USER_TOKEN
            po.executeAction("send", props=props)
            self.logger.info(f"Pushover WiFi alert sent: {body}")
        except Exception as err:
            self.logger.error(f"Pushover send failed: {err}")

    # ── Device-config list callbacks ───────────────────────────────────────

    def get_controller_list(self, filter="", valuesDict=None, typeId="", targetId=0):
        return [(str(dev_id), indigo.devices[dev_id].name) for dev_id in self.controllers]

    def get_ap_list(self, filter="", valuesDict=None, typeId="", targetId=0):
        try:
            cache = self.controllers[int(valuesDict["unifi_controller"])]
        except (KeyError, ValueError, TypeError):
            return []
        items = [(mac, data.get("name") or f"{data.get('model')} {mac}")
                 for mac, data in cache["devices_by_mac"].items() if _is_access_point(data)]
        items.sort(key=lambda t: str(t[1]).lower())
        return items

    def get_client_list(self, filter="", valuesDict=None, typeId="", targetId=0):
        try:
            cache = self.controllers[int(valuesDict["unifi_controller"])]
        except (KeyError, ValueError):
            return []
        items = [(mac, data.get("name") or data.get("hostname") or data.get("oui") or mac)
                 for mac, data in cache["clients_by_mac"].items()]
        items.sort(key=lambda t: str(t[1]).lower())
        return items

    def menuChanged(self, valuesDict=None, typeId=None, devId=None):
        return valuesDict

    # ── Actions (cmd/devmgr) ───────────────────────────────────────────────

    def _ap_command(self, device, cmd, **extra):
        controller_id = self.ap_devices.get(device.id)
        try:
            controller = indigo.devices[controller_id]
        except Exception:
            self.logger.error(f"{device.name}: no controller bound")
            return
        try:
            session = self._session_for(controller)
            ok, msg = session.command(device.address, cmd, **extra)
        except UniFiError as err:
            ok, msg = False, str(err)
        if ok:
            self.logger.info(f"{device.name}: '{cmd}' sent OK")
        else:
            self.logger.error(f"{device.name}: '{cmd}' failed — {msg}")

    def action_restart_ap(self, action, device):
        self._ap_command(device, "restart")

    def action_locate_ap(self, action, device):
        self._ap_command(device, "set-locate")

    def action_unlocate_ap(self, action, device):
        self._ap_command(device, "unset-locate")

    def actionControlSensor(self, action, dev):
        # unifiAP + unifiClient are type="sensor"; without this a Send Status Request logs
        # "plugin does not define method actionControlSensor". RequestStatus forces a refresh.
        if action.sensorAction == indigo.kSensorAction.RequestStatus:
            self.next_update = 0.0
        else:
            self.logger.warning(f"{dev.name}: unsupported sensor action {action.sensorAction}")

    def action_refresh_now(self, action=None, device=None):
        self.next_update = 0.0
        self.logger.info("UniFi data refresh requested")

    # ── Menu callbacks ─────────────────────────────────────────────────────

    def menu_discover_aps(self, valuesDict=None, typeId=None):
        folder_id = self._ensure_folder()
        existing = {d.address for d in indigo.devices.iter("self") if d.deviceTypeId == "unifiAP"}
        created = 0
        for controller_id, cache in self.controllers.items():
            for mac, data in cache["devices_by_mac"].items():
                if not _is_access_point(data) or mac in existing:
                    continue
                existing.add(mac)
                name = f"UniFi AP {data.get('name', mac)}"
                try:
                    indigo.device.create(
                        protocol=indigo.kProtocol.Plugin,
                        name=name,
                        deviceTypeId="unifiAP",
                        folder=folder_id,
                        props={"unifi_controller": str(controller_id), "address": mac})
                    created += 1
                except Exception as err:
                    self.logger.error(f"create AP {name}: {err}")
        self.logger.info(f"Discover APs: created {created} device(s)")
        return True

    def menu_run_audit(self, valuesDict=None, typeId=None):
        for controller_id, cache in self.controllers.items():
            ch24 = cache.get("ch24", {})
            self.logger.info("===== UniFi WiFi Config Audit =====")
            shared = {ch: n for ch, n in ch24.items() if n > 2}
            if shared:
                self.logger.info(f"2.4GHz channels shared by >2 APs: {shared}")
            for mac, data in cache["devices_by_mac"].items():
                if not _is_access_point(data):
                    continue
                flags = self._audit_ap(data, ch24)
                name = data.get("name", mac)
                if flags:
                    self.logger.warning(f"  {name}: {', '.join(flags)}")
                else:
                    self.logger.info(f"  {name}: OK")
        return True

    def testConnection(self, valuesDict=None, typeId=None):
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion)
        for controller_id in self.controllers:
            device = indigo.devices[controller_id]
            try:
                session = self._session_for(device)
                devices = session.get_devices()
                aps = [d for d in devices if _is_access_point(d)]
                self.logger.info(f"{device.name}: connection OK — {len(aps)} APs, "
                                 f"{len(session.get_clients())} clients")
            except UniFiError as err:
                self.logger.error(f"{device.name}: connection FAILED — {err}")

    def showPluginInfo(self, valuesDict=None, typeId=None):
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion)
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion}")

    # ── Prefs ──────────────────────────────────────────────────────────────

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            # Guarded coercion — a blank/non-numeric field must never crash
            # the prefs save (estate-wide rule, 05-Jun-2026).
            self.update_frequency = max(30.0, _as_float(valuesDict.get("updateFrequency"), 60.0))
            self.util_warn = _as_int(valuesDict.get("utilWarnPct"), 70)
            self.sat_warn = _as_int(valuesDict.get("satisfactionWarn"), 80)
            self.away_minutes = max(2, _as_int(valuesDict.get("awayMinutes"), 10))
            self.ap_offline_grace_secs = max(0, _as_int(valuesDict.get("apOfflineGraceMinutes"), 3)) * 60
            self.pushover_alerts = bool(valuesDict.get("pushoverAlerts", False))
            self.next_update = 0.0
