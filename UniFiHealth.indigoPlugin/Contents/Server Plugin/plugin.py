#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: UniFi Health — WiFi health, client/presence and a config audit
#              for UniFi controllers (UDM/UDR + legacy). Read-mostly; cmd/devmgr
#              actions for AP restart / locate.
# Author:      CliveS & Claude Opus 4.8
# Date:        31-05-2026
# Version:     0.2.1
#
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
from datetime import datetime

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

PLUGIN_VERSION = "0.2.1"
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

# UniFi radio identifiers -> friendly band labels.
RADIO_BAND = {"ng": "24", "na": "5", "6e": "6"}
# Client records report the radio they're on as ng/na/6e — map to a UI band label.
CLIENT_BAND_UI = {"ng": "2.4", "na": "5", "6e": "6"}


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

        self.controllers = {}      # controllerDevId -> cache dict
        self.ap_devices = {}       # apDevId -> controllerDevId
        self.client_devices = {}   # clientDevId -> controllerDevId
        self.event_triggers = {}   # triggerId -> trigger
        self._alert_times = {}     # alert-key -> last-sent epoch (Pushover debounce)
        self.next_update = 0.0

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def startup(self):
        self.logger.info(f"Starting UniFi Health {PLUGIN_VERSION}")
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
        try:
            while True:
                now = self._now()
                if now >= self.next_update:
                    self.next_update = now + self.update_frequency
                    for controller_id in list(self.controllers):
                        self._poll_controller(indigo.devices[controller_id])
                    for ap_id in list(self.ap_devices):
                        self._update_ap(indigo.devices[ap_id])
                    for client_id in list(self.client_devices):
                        self._update_client(indigo.devices[client_id])
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
                                           "clients_by_mac": {}, "ch24": {}, "ap_uptime": {}}
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

    @staticmethod
    def didDeviceCommPropertyChange(orig_dev, new_dev):
        # Restart comm only when the controller binding or target MAC changes.
        keys = ("address", "port", "username", "password", "unifi_controller")
        return any(orig_dev.pluginProps.get(k) != new_dev.pluginProps.get(k) for k in keys)

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
        aps = [d for d in devices if d.get("type") == "uap"]
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
                if ap.get("type") == "uap" and mac not in existing:
                    try:
                        indigo.device.create(protocol=indigo.kProtocol.Plugin,
                                             name=f"UniFi AP {ap.get('name', mac)}",
                                             deviceTypeId="unifiAP", folder=folder_id,
                                             props={"unifi_controller": str(device.id), "address": mac})
                        self.logger.info(f"Auto-created AP device: {ap.get('name', mac)}")
                    except Exception as err:
                        self.logger.error(f"auto-create AP {mac}: {err}")

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

    # ── AP device update ───────────────────────────────────────────────────

    def _update_ap(self, device):
        controller_id = self.ap_devices.get(device.id)
        cache = self.controllers.get(controller_id)
        if not cache:
            return
        data = cache["devices_by_mac"].get(device.address)
        if not data:
            device.updateStateOnServer("onOffState", False, uiValue="Offline")
            device.updateStateOnServer("apSummary", "Offline")
            device.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
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

    def _update_client(self, device):
        controller_id = self.client_devices.get(device.id)
        cache = self.controllers.get(controller_id)
        if not cache:
            return
        data = cache["clients_by_mac"].get(device.address)
        if not data:
            device.updateStateOnServer("onOffState", False, uiValue="Offline")
            device.updateStateOnServer("clientSummary", "Offline")
            device.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
            return

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
            {"key": "clientSummary", "value": f"{signal}dBm sat={sat} @ {ap_name}"},
        ]
        device.updateStatesOnServer(states)
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
        return self._device_picker(valuesDict, "uap")

    def get_client_list(self, filter="", valuesDict=None, typeId="", targetId=0):
        try:
            cache = self.controllers[int(valuesDict["unifi_controller"])]
        except (KeyError, ValueError):
            return []
        items = [(mac, data.get("name") or data.get("hostname") or data.get("oui") or mac)
                 for mac, data in cache["clients_by_mac"].items()]
        items.sort(key=lambda t: str(t[1]).lower())
        return items

    def _device_picker(self, valuesDict, dev_type):
        try:
            cache = self.controllers[int(valuesDict["unifi_controller"])]
        except (KeyError, ValueError, TypeError):
            return []
        items = [(mac, data.get("name") or f"{data.get('model')} {mac}")
                 for mac, data in cache["devices_by_mac"].items() if data.get("type") == dev_type]
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
                if data.get("type") != "uap" or mac in existing:
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
                if data.get("type") != "uap":
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
                aps = [d for d in devices if d.get("type") == "uap"]
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
            self.update_frequency = max(30.0, float(valuesDict.get("updateFrequency", 60)))
            self.util_warn = int(valuesDict.get("utilWarnPct", 70))
            self.sat_warn = int(valuesDict.get("satisfactionWarn", 80))
            self.pushover_alerts = bool(valuesDict.get("pushoverAlerts", False))
            self.next_update = 0.0
