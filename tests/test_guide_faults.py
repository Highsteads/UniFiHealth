#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_guide_faults.py
# Description: v0.8.0. Faults found while writing the plain-English guide:
#              the two audit events never fired, the Log level setting was
#              never read, a signed-in controller that stopped answering never
#              showed Unreachable, and the minimum-RSSI audit flag and Apply
#              menu item could not work on UniFi Network 10.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

import importlib.util
import os
import sys
import types
from unittest.mock import MagicMock

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(os.path.dirname(HERE), "UniFiHealth.indigoPlugin", "Contents", "Server Plugin")

for _name in ("requests", "urllib3"):         # CI installs neither; Indigo bundles both
    try:
        __import__(_name)
    except ImportError:
        sys.modules[_name] = MagicMock()

_ind = types.ModuleType("indigo")


class _PB:
    def __init__(self, *a, **k):
        self.logger = MagicMock()
        self.indigo_log_handler = MagicMock()


_ind.PluginBase = _PB
for _a in ("kStateImageSel", "server", "devices", "device", "kProtocol", "variables"):
    setattr(_ind, _a, MagicMock())
sys.modules["indigo"] = _ind
sys.path.insert(0, SERVER)

_spec = importlib.util.spec_from_file_location("unifihealth_plugin_v080", os.path.join(SERVER, "plugin.py"))
MOD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MOD)

from unifi_api import UniFiSession   # noqa: E402

AP_MAC = "aa:bb:cc:00:00:01"


class FakeDev:
    def __init__(self, dev_id=7, type_id="unifiController", name="UniFi Controller", states=None):
        self.id = dev_id
        self.name = name
        self.deviceTypeId = type_id
        self.address = AP_MAC
        self.pluginProps = {"unifi_controller": "7"}
        self.states = dict(states or {})
        self.batches = []

    def updateStatesOnServer(self, states):
        self.batches.append(states)
        for st in states:
            self.states[st["key"]] = st["value"]

    def updateStateOnServer(self, key, value, **k):
        self.states[key] = value

    def updateStateImageOnServer(self, *a):
        pass

    def replaceOnServer(self):
        pass


def plugin():
    p = MOD.Plugin.__new__(MOD.Plugin)
    p.logger = MagicMock()
    p.indigo_log_handler = MagicMock()
    p.pluginPrefs = {"autoCreateAPs": False}
    p.controllers = {}
    p.ap_devices = {}
    p.client_devices = {}
    p.util_warn = 70
    p.sat_warn = 80
    p.ap_offline_grace_secs = 180
    p._reap_removed_aps = lambda *a: None
    p._fire_event = MagicMock()
    p._pushover = MagicMock()
    return p


def fired(p, event_id):
    return sum(1 for c in p._fire_event.call_args_list if c.args == (event_id,))


# ── Log level ────────────────────────────────────────────────────────────────

def test_log_level_is_read_at_start():
    p = MOD.Plugin("id", "UniFi Health", "0.8.0", {"logLevel": "40"})
    p.indigo_log_handler.setLevel.assert_called_with(40)


def test_log_level_follows_the_dialog_and_refuses_junk():
    p = plugin()
    p.closedPrefsConfigUi({"logLevel": "10"}, False)
    p.indigo_log_handler.setLevel.assert_called_with(10)
    assert p._apply_log_level("loud") == 20
    assert p._apply_log_level("15") == 20


# ── Controller dropout ──────────────────────────────────────────────────────

class DeadSession:
    unifi_os = True

    def get_devices(self):
        raise TimeoutError("Read timed out")

    def close(self):
        pass


class LiveSession:
    unifi_os = True

    def get_devices(self):
        return []

    def get_clients(self):
        return []

    def get_health(self):
        return [{"subsystem": "wlan", "status": "ok"}]

    def get_rogue_aps(self):
        return []

    def get_sysinfo(self):
        return {"version": "10.5.67"}

    def close(self):
        pass


def _controller(p, dev, session_box):
    p.controllers[dev.id] = {"session": None, "devices_by_mac": {}, "clients_by_mac": {},
                             "ch24": {}, "ap_uptime": {}, "ap_missing": {}, "rf24": {},
                             "ap_off_since": {}}

    def _session_for(d):
        p.controllers[d.id]["session"] = session_box[0]
        return session_box[0]
    p._session_for = _session_for


def test_a_signed_in_controller_that_stops_answering_goes_unreachable():
    p = plugin()
    dev = FakeDev(states={"status": "Connected"})
    box = [DeadSession()]
    _controller(p, dev, box)
    for _ in range(MOD.CONTROLLER_FAILS_BEFORE_UNREACHABLE - 1):
        p._poll_controller(dev)                      # must not raise
        assert dev.states["status"] == "Connected"   # one blip is not an outage
    assert fired(p, "controllerUnreachable") == 0
    assert p.logger.warning.call_count == 1          # warned once, then quiet
    p._poll_controller(dev)
    assert dev.states["status"] == "Unreachable"
    assert fired(p, "controllerUnreachable") == 1
    p._pushover.assert_called_once()
    p._poll_controller(dev)                          # still down: trigger as before,
    assert fired(p, "controllerUnreachable") == 2    # but no second Pushover
    p._pushover.assert_called_once()
    box[0] = LiveSession()
    p._poll_controller(dev)
    assert dev.states["status"] == "Connected"
    assert p.controllers[dev.id]["fails"] == 0


def test_one_blip_then_an_answer_never_shows_unreachable():
    p = plugin()
    dev = FakeDev(states={"status": "Connected"})
    box = [DeadSession()]
    _controller(p, dev, box)
    p._poll_controller(dev)
    box[0] = LiveSession()
    p._poll_controller(dev)
    assert dev.states["status"] == "Connected"
    assert fired(p, "controllerUnreachable") == 0
    assert any("answered again" in str(c) for c in p.logger.info.call_args_list)


def test_a_failed_check_leaves_its_clients_and_aps_alone(monkeypatch):
    p = plugin()
    p.controllers = {7: {}}
    p.ap_devices = {8: 7}
    p.client_devices = {9: 7}
    p._update_ap = MagicMock()
    p._update_client = MagicMock()
    monkeypatch.setattr(MOD.indigo, "devices", {7: FakeDev(), 8: FakeDev(8), 9: FakeDev(9)})
    p._poll_controller = lambda d: p.controllers[7].update(poll_ok=False)
    p._poll_cycle()
    assert not p._update_ap.called and not p._update_client.called
    p._poll_controller = lambda d: p.controllers[7].update(poll_ok=True)
    p._poll_cycle()
    assert p._update_ap.called and p._update_client.called


# ── The two audit events ────────────────────────────────────────────────────

def _ap_data(ht="20", util=10):
    return {"state": 1, "name": "Hall", "uptime": 1000, "model": "U7PRO",
            "radio_table": [{"radio": "ng", "ht": ht, "tx_power_mode": "auto",
                             "min_rssi_enabled": True}],
            "radio_table_stats": [{"radio": "ng", "channel": 6, "cu_total": util}]}


def _ap_setup(p, data, states=None):
    p.controllers[7] = {"devices_by_mac": {AP_MAC: data}, "clients_by_mac": {}, "ch24": {},
                        "ap_uptime": {}, "rf24": {}, "ap_off_since": {}}
    p.ap_devices = {8: 7}
    return FakeDev(8, "unifiAP", "UniFi AP Hall", states)


def test_a_new_audit_finding_fires_once():
    p = plugin()
    dev = _ap_setup(p, _ap_data(ht="40"), {"auditFlags": ""})
    p._update_ap(dev)
    assert fired(p, "configIssueFound") == 1
    p._update_ap(dev)                                # still there: not new
    assert fired(p, "configIssueFound") == 1


def test_a_restart_does_not_reannounce_a_stored_finding():
    p = plugin()
    dev = _ap_setup(p, _ap_data(ht="40"), {"auditFlags": "2.4GHz width 40MHz (use 20)"})
    p._update_ap(dev)
    assert fired(p, "configIssueFound") == 0


def test_a_moving_count_is_the_same_finding():
    before = "2.4GHz ch6 shared by 3 APs, 2.4GHz util 71%"
    assert MOD.new_config_findings(before, ["2.4GHz ch6 shared by 4 APs"]) == []
    assert MOD.new_config_findings(before, ["2.4GHz ch11 shared by 3 APs"]) == \
        ["2.4GHz ch11 shared by 3 APs"]
    # utilisation has its own event, so it never fires the config one
    assert MOD.new_config_findings("", ["2.4GHz util 90%"]) == []


def _feed(p, dev, data, readings, clock, step=60):
    """One _update_ap per reading, a minute apart on a fake clock."""
    for util in readings:
        data["radio_table_stats"][0]["cu_total"] = util
        p._update_ap(dev)
        clock[0] += step


def _clocked_plugin():
    p = plugin()
    clock = [1_000_000.0]
    p._now = lambda: clock[0]
    return p, clock


def test_a_busy_band_fires_once_per_crossing():
    p, clock = _clocked_plugin()
    data = _ap_data(util=85)
    dev = _ap_setup(p, data, {"auditFlags": "", "band24Utilisation": 0})
    _feed(p, dev, data, [85] * 8, clock)               # under 60% of the window: no verdict yet
    assert fired(p, "apHighUtilisation") == 0
    _feed(p, dev, data, [85] * 3, clock)
    assert fired(p, "apHighUtilisation") == 1
    _feed(p, dev, data, [62] * 20 + [85] * 20, clock)  # 62 is under 70 but not 10 below: no re-arm
    assert fired(p, "apHighUtilisation") == 1
    _feed(p, dev, data, [40] * 20 + [85] * 20, clock)  # cleared, then busy again
    assert fired(p, "apHighUtilisation") == 2
    p.logger.info.assert_any_call(
        "UniFi AP Hall: 2.4 GHz has averaged 85% busy over the last 15 minutes, "
        "over the 70% warning level")


def test_a_swinging_band_fires_once_not_every_swing():
    """The shape measured on the live APs, 29-09-2026: readings jumping between
    the low 60s and the 90s from one minute to the next. 0.8.0 logged a line at
    every climb back over 70."""
    p, clock = _clocked_plugin()
    data = _ap_data(util=62)
    dev = _ap_setup(p, data, {"auditFlags": "", "band24Utilisation": 0})
    _feed(p, dev, data, [62, 95, 64, 88, 61, 97, 63, 90] * 30, clock)
    assert fired(p, "apHighUtilisation") == 1


def test_one_spike_is_not_a_busy_band():
    p, clock = _clocked_plugin()
    data = _ap_data(util=30)
    dev = _ap_setup(p, data, {"auditFlags": "", "band24Utilisation": 0})
    _feed(p, dev, data, [30] * 15 + [99, 99] + [30] * 15, clock)
    assert fired(p, "apHighUtilisation") == 0


def test_the_average_forgets_readings_older_than_the_window():
    samples = []
    assert MOD.utilisation_average(samples, 0, 90, window=900) is None
    assert MOD.utilisation_average(samples, 600, 90, window=900) == 90
    assert MOD.utilisation_average(samples, 1200, 30, window=900) == 60   # the 0 s reading dropped
    assert [t for t, _ in samples] == [600, 1200]


def test_a_restart_does_not_refire_a_band_already_busy():
    p, clock = _clocked_plugin()
    data = _ap_data(util=85)
    dev = _ap_setup(p, data, {"auditFlags": "2.4GHz util 84%", "band24Utilisation": 84})
    _feed(p, dev, data, [85] * 20, clock)
    assert fired(p, "apHighUtilisation") == 0


# ── Minimum RSSI on UniFi Network 10 ────────────────────────────────────────

def test_network_version_parsing():
    assert MOD.network_major_version("10.5.67") == 10
    assert MOD.network_major_version("v9.0.114") == 9
    assert MOD.network_major_version("") is None
    assert MOD.per_ap_min_rssi_supported("10.5.67") is False
    assert MOD.per_ap_min_rssi_supported("9.0.114") is True
    assert MOD.per_ap_min_rssi_supported("") is None


def test_the_audit_skips_min_rssi_on_network_10():
    p = plugin()
    data = _ap_data()
    data["radio_table"][0]["min_rssi_enabled"] = False
    assert "2.4GHz min-RSSI off" not in p._audit_ap(data, {}, "10.5.67")
    assert "2.4GHz min-RSSI off" in p._audit_ap(data, {}, "9.0.114")
    assert "2.4GHz min-RSSI off" in p._audit_ap(data, {}, "")


def test_the_controller_version_is_refreshed_after_an_upgrade():
    p = plugin()
    dev = FakeDev(states={"status": "Connected", "controllerVersion": "9.0.114"})
    _controller(p, dev, [LiveSession()])
    p._poll_controller(dev)
    assert dev.states["controllerVersion"] == "10.5.67"


class RssiSession(LiveSession):
    def __init__(self, version):
        self.version = version
        self.set_radio_min_rssi = MagicMock(return_value=(True, "ng min_rssi -80 -> -70"))
        self.get_devices = MagicMock(return_value=[
            {"type": "uap", "name": "Hall", "_id": "x1", "radio_table": [{"radio": "ng"}]}])

    def get_sysinfo(self):
        return {"version": self.version}


def test_apply_min_rssi_says_plainly_when_network_10_cannot_take_it():
    p = plugin()
    dev = FakeDev()
    session = RssiSession("10.5.67")
    p.controllers = {7: {}}
    p._each_controller = lambda: iter([(dev, session)])
    p.menu_apply_min_rssi({"minRssi": "-70", "band": "ng"})
    assert not session.set_radio_min_rssi.called
    assert not session.get_devices.called
    text = " ".join(str(c) for c in p.logger.warning.call_args_list)
    assert "UniFi Network 10.5.67" in text and "Nothing was sent" in text
    assert not p.logger.error.called


def test_apply_min_rssi_still_writes_on_an_older_controller():
    p = plugin()
    dev = FakeDev()
    session = RssiSession("9.0.114")
    p.controllers = {7: {}}
    p._each_controller = lambda: iter([(dev, session)])
    p.menu_apply_min_rssi({"minRssi": "-70", "band": "ng"})
    assert session.set_radio_min_rssi.called


def test_the_api_no_longer_refuses_2_4ghz_outright():
    s = UniFiSession("192.168.1.1", "u", "p")
    doc = {"radio_table": [{"radio": "ng", "min_rssi": -80, "min_rssi_enabled": False}]}
    stored = {"radio_table": [{"radio": "ng", "min_rssi": -70, "min_rssi_enabled": True}]}
    s.get_device_config = MagicMock(side_effect=[doc, stored])
    s.put_device_config = MagicMock(return_value=(True, "ok"))
    ok, msg = s.set_radio_min_rssi("x1", "ng", -70)
    assert ok, msg
    assert s.put_device_config.called


# ── A radio switched off is not sharing a channel (0.8.1) ───────────────────

def _ap(ch, tx="auto"):
    return {"type": "uap", "is_access_point": True,
            "radio_table": [{"radio": "ng", "ht": "20", "tx_power_mode": tx}],
            "radio_table_stats": [{"radio": "ng", "channel": ch, "cu_total": 20}]}


def test_a_disabled_radio_is_not_counted_on_its_channel():
    """Live 29-09-2026: the Bedroom U6-LR has 2.4 GHz off but still reports
    channel 6 while it scans, so the audit said 'ch6 shared by 3 APs'."""
    devices = [_ap(6), _ap(6), _ap(6, tx="disabled"), _ap(11)]
    assert MOD.count_24ghz_channels(devices) == {"6": 2, "11": 1}


def test_a_disabled_radio_raises_no_findings():
    p = plugin()
    bedroom = _ap(6, tx="disabled")
    bedroom["radio_table"][0]["ht"] = "40"
    assert p._audit_ap(bedroom, {"6": 3}) == []
    assert "2.4GHz ch6 shared by 3 APs" in p._audit_ap(_ap(6), {"6": 3})
