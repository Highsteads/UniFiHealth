#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_outage_presence.py
# Description: v0.9.1. Presence while the controller is not answering. A
#              geofence flip used to re-read the last cached Wi-Fi row, so a
#              phone that left during a controller outage was written HOME
#              with a fresh last-seen time. Also: one bad trigger must not
#              stop the others, and a changed Verify SSL setting must rebuild
#              the controller session.
# Author:      CliveS & Claude Opus 5.5
# Date:        05-10-2026
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

    def deviceUpdated(self, orig_dev, new_dev):
        pass


_ind.PluginBase = _PB
for _a in ("kStateImageSel", "server", "devices", "device", "kProtocol", "variables", "trigger"):
    setattr(_ind, _a, MagicMock())
sys.modules["indigo"] = _ind
sys.path.insert(0, SERVER)

_spec = importlib.util.spec_from_file_location("unifihealth_plugin_v091", os.path.join(SERVER, "plugin.py"))
MOD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MOD)

CTRL_ID = 7
PHONE_ID = 9
GEO_ID = 50
PHONE_MAC = "aa:bb:cc:00:00:09"
AP_MAC = "aa:bb:cc:00:00:01"


class FakeDev:
    def __init__(self, dev_id, type_id, name, address="", props=None, states=None, on=None):
        self.id = dev_id
        self.name = name
        self.deviceTypeId = type_id
        self.pluginId = "com.clives.indigoplugin.unifihealth"
        self.address = address
        self.pluginProps = dict(props or {})
        self.states = dict(states or {})
        self.onState = on

    def updateStatesOnServer(self, states, **k):
        for st in states:
            self.states[st["key"]] = st["value"]

    def updateStateOnServer(self, key, value, **k):
        self.states[key] = value

    def updateStateImageOnServer(self, *a):
        pass


class Session:
    """A controller session that answers with whatever `clients` holds, or
    raises when `dead` is set."""
    unifi_os = True

    def __init__(self):
        self.dead = False
        self.clients = []

    def _check(self):
        if self.dead:
            raise TimeoutError("Read timed out")

    def get_devices(self):
        self._check()
        return [{"mac": AP_MAC, "name": "Hall", "type": "uap", "state": 1}]

    def get_clients(self):
        self._check()
        return list(self.clients)

    def get_health(self):
        self._check()
        return [{"subsystem": "wlan", "status": "ok"}]

    def get_rogue_aps(self):
        return []

    def get_sysinfo(self):
        return {"version": "10.5.67"}

    def close(self):
        pass


def setup(monkeypatch, geofence=True, presence="home", geo_on=True):
    p = MOD.Plugin.__new__(MOD.Plugin)
    p.logger = MagicMock()
    p.indigo_log_handler = MagicMock()
    p.pluginId = "com.clives.indigoplugin.unifihealth"
    p.pluginPrefs = {"autoCreateAPs": False, "autoRemoveAPs": False}
    p.util_warn = 70
    p.sat_warn = 80
    p.away_minutes = 10
    p.ap_offline_grace_secs = 180
    p.ap_devices = {}
    p.client_devices = {PHONE_ID: CTRL_ID}
    p.client_last_seen = {}
    p.geofence_watch = {GEO_ID: {PHONE_ID}} if geofence else {}
    p.event_triggers = {}
    p._alert_times = {}
    p._fire_event = MagicMock()
    p._pushover = MagicMock()
    p.controllers = {CTRL_ID: {"session": None, "devices_by_mac": {}, "clients_by_mac": {},
                               "ch24": {}, "ap_uptime": {}, "ap_missing": {}, "rf24": {},
                               "ap_off_since": {}}}
    clock = [1000.0]
    p._now = lambda: clock[0]
    session = Session()

    def _session_for(d):
        p.controllers[d.id]["session"] = session
        return session
    p._session_for = _session_for

    ctrl = FakeDev(CTRL_ID, "unifiController", "UniFi Controller", states={"status": "Connected"})
    props = {"unifi_controller": str(CTRL_ID)}
    if geofence:
        props["geofence_device"] = str(GEO_ID)
    phone = FakeDev(PHONE_ID, "unifiClient", "Clive iPhone", PHONE_MAC, props,
                    states={"presence": presence, "lastSeenEpoch": 0})
    geo = FakeDev(GEO_ID, "geofenceSwitch", "Clive Geofence", on=geo_on)
    devices = {CTRL_ID: ctrl, PHONE_ID: phone, GEO_ID: geo}
    monkeypatch.setattr(MOD.indigo, "devices", devices)
    return p, session, clock, ctrl, phone, geo


def connected_row():
    return {"mac": PHONE_MAC, "ap_mac": AP_MAC, "signal": -50, "satisfaction": 98, "essid": "Home"}


def flip_geofence(p, geo, on):
    before = FakeDev(geo.id, geo.deviceTypeId, geo.name, on=geo.onState)
    geo.onState = on
    p.deviceUpdated(before, geo)


def answered_connected(p, session, ctrl):
    """One full poll cycle in which the controller lists the phone."""
    session.clients = [connected_row()]
    p._poll_cycle()
    assert p.controllers[CTRL_ID]["poll_ok"]


# ── MON-04: a geofence flip during an outage ────────────────────────────────

def test_leaving_during_an_outage_is_away_and_last_seen_does_not_move(monkeypatch):
    p, session, clock, ctrl, phone, geo = setup(monkeypatch)
    answered_connected(p, session, ctrl)
    assert phone.states["presence"] == "home"
    assert phone.states["lastSeenEpoch"] == 1000
    clock[0] = 1060
    session.dead = True
    p._poll_cycle()                                  # controller stops answering
    assert not p.controllers[CTRL_ID]["poll_ok"]
    clock[0] = 1070
    flip_geofence(p, geo, False)                     # HomeKit "left home"
    assert phone.states["presence"] == "away"
    assert phone.states["lastSeenEpoch"] == 1000     # never a fresh sighting
    assert p.client_last_seen[PHONE_ID] == 1000
    assert phone.states["presenceSource"] == "geofence"


def test_arriving_during_an_outage_is_home_without_a_wifi_sighting(monkeypatch):
    p, session, clock, ctrl, phone, geo = setup(monkeypatch, presence="away", geo_on=False)
    session.clients = []
    p._poll_cycle()                                  # answered, phone not there
    assert phone.states["presence"] == "away"
    clock[0] = 1060
    session.dead = True
    p._poll_cycle()
    clock[0] = 1070
    flip_geofence(p, geo, True)                      # HomeKit "arrived"
    assert phone.states["presence"] == "home"
    assert phone.states["lastSeenEpoch"] == 0
    assert PHONE_ID not in p.client_last_seen
    assert phone.states["presenceSource"] == "geofence"


def test_recovery_after_an_outage(monkeypatch):
    p, session, clock, ctrl, phone, geo = setup(monkeypatch)
    answered_connected(p, session, ctrl)
    clock[0] = 1060
    session.dead = True
    p._poll_cycle()
    clock[0] = 1070
    flip_geofence(p, geo, False)
    assert phone.states["presence"] == "away"
    # the controller answers again; the phone is not on the Wi-Fi
    clock[0] = 1300
    session.dead = False
    session.clients = []
    p._poll_cycle()
    assert phone.states["presence"] == "away"
    assert phone.states["minutesSinceSeen"] == 5     # from the real sighting at 1000
    # and when the phone does come back it is home with a fresh sighting
    clock[0] = 1360
    answered_connected(p, session, ctrl)
    assert phone.states["presence"] == "home"
    assert phone.states["lastSeenEpoch"] == 1360


def test_wifi_only_away_is_not_delayed_by_an_outage(monkeypatch):
    p, session, clock, ctrl, phone, geo = setup(monkeypatch, geofence=False)
    answered_connected(p, session, ctrl)
    clock[0] = 1060
    session.dead = True
    p._poll_cycle()
    clock[0] = 1000 + 11 * 60                        # outage over, phone long gone
    session.dead = False
    session.clients = []
    p._poll_cycle()
    assert phone.states["presence"] == "away"


# ── MON-04: the fusion rules with a healthy controller are unchanged ────────

def test_healthy_controller_wifi_still_outvotes_a_geofence_wobble(monkeypatch):
    p, session, clock, ctrl, phone, geo = setup(monkeypatch)
    answered_connected(p, session, ctrl)
    clock[0] = 1040
    flip_geofence(p, geo, False)                     # GPS wobble, phone on Wi-Fi
    assert phone.states["presence"] == "home"
    assert phone.states["lastSeenEpoch"] == 1000     # the poll's time, not the flip's
    assert p.client_last_seen[PHONE_ID] == 1000


def test_healthy_controller_geofence_leave_with_no_wifi_is_away_at_once(monkeypatch):
    p, session, clock, ctrl, phone, geo = setup(monkeypatch)
    session.clients = []
    p._poll_cycle()                                  # answered, phone off Wi-Fi (napping)
    assert phone.states["presence"] == "home"        # geofence vouches
    clock[0] = 1030
    flip_geofence(p, geo, False)
    assert phone.states["presence"] == "away"


def test_a_poll_records_the_time_of_the_answer(monkeypatch):
    p, session, clock, ctrl, phone, geo = setup(monkeypatch)
    answered_connected(p, session, ctrl)
    assert p.controllers[CTRL_ID]["poll_epoch"] == 1000


# ── MON-12: one bad trigger must not stop the rest ──────────────────────────

class _Trig:
    def __init__(self, tid, type_id):
        self.id = tid
        self.pluginTypeId = type_id


def test_one_failing_trigger_does_not_skip_the_others(monkeypatch):
    p, *_ = setup(monkeypatch)
    p._fire_event = MOD.Plugin._fire_event.__get__(p)
    p.event_triggers = {1: _Trig(1, "clientLeft"), 2: _Trig(2, "clientLeft"),
                        3: _Trig(3, "clientArrived")}
    ran = []

    def execute(trigger):
        ran.append(trigger.id)
        if trigger.id == 1:
            raise RuntimeError("trigger deleted under us")
    monkeypatch.setattr(MOD.indigo, "trigger", types.SimpleNamespace(execute=execute))
    p._fire_event("clientLeft")                      # must not raise
    assert ran == [1, 2]


def test_a_trigger_stopping_while_events_fire_does_not_break_the_loop(monkeypatch):
    p, *_ = setup(monkeypatch)
    p._fire_event = MOD.Plugin._fire_event.__get__(p)
    p.event_triggers = {1: _Trig(1, "clientLeft"), 2: _Trig(2, "clientLeft")}
    ran = []

    def execute(trigger):
        ran.append(trigger.id)
        p.triggerStopProcessing(trigger)             # dict changes mid-loop
    monkeypatch.setattr(MOD.indigo, "trigger", types.SimpleNamespace(execute=execute))
    p._fire_event("clientLeft")
    assert ran == [1, 2]


# ── MON-11: Verify SSL change rebuilds the session ──────────────────────────

def test_changing_verify_ssl_restarts_the_controller():
    a = FakeDev(CTRL_ID, "unifiController", "c", props={"ssl_verify": False})
    b = FakeDev(CTRL_ID, "unifiController", "c", props={"ssl_verify": True})
    assert MOD.Plugin.didDeviceCommPropertyChange(a, b) is True
    assert MOD.Plugin.didDeviceCommPropertyChange(a, a) is False
