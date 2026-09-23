#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_sql_logger_churn.py
# Description: v0.7.3. The controller poll set ~25 states one call at a time, and
#              SQL Logger stores a row for every state write that changes
#              something: up to six rows in the same second, every minute. The
#              poll now makes ONE updateStatesOnServer call, and the three JSON
#              states join the controller's sqlLoggerIgnoreStates shared prop.
# Author:      CliveS & Claude Opus 5.5
# Date:        23-09-2026
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
        pass


_ind.PluginBase = _PB
for _a in ("kStateImageSel", "server", "devices", "device", "kProtocol", "variables"):
    setattr(_ind, _a, MagicMock())
sys.modules["indigo"] = _ind
sys.path.insert(0, SERVER)

_spec = importlib.util.spec_from_file_location("unifihealth_plugin", os.path.join(SERVER, "plugin.py"))
MOD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MOD)


class FakeDev:
    def __init__(self, shared=None):
        self.id = 7
        self.name = "UniFi Controller"
        self.deviceTypeId = "unifiController"
        self.states = {"status": "Connected"}
        self.sharedProps = dict(shared or {})
        self.shared_writes = 0
        self.batches = []
        self.singles = []

    def replaceSharedPropsOnServer(self, props):
        self.sharedProps = dict(props)
        self.shared_writes += 1

    def updateStatesOnServer(self, states):
        self.batches.append(states)

    def updateStateOnServer(self, *a, **k):
        self.singles.append(a)

    def updateStateImageOnServer(self, *a):
        pass

    def stateListOrDisplayStateIdChanged(self):
        pass


class FakeSession:
    unifi_os = True

    def get_devices(self):
        return []

    def get_clients(self):
        return [{"mac": "aa", "is_wired": False, "radio_proto": "ax", "satisfaction": 80,
                 "name": "Phone", "signal": -60}]

    def get_health(self):
        return [{"subsystem": "wlan", "status": "ok"},
                {"subsystem": "www", "status": "ok", "latency": 9},
                {"subsystem": "wan", "wan_ip": "", "gw_system-stats": {"cpu": 20, "mem": 70}}]

    def get_rogue_aps(self):
        return [{"channel": 6}, {"channel": 36}]

    def get_sysinfo(self):
        return {"version": "9.0"}


def plugin():
    p = MOD.Plugin.__new__(MOD.Plugin)
    p.logger = MagicMock()
    p.pluginPrefs = {"autoCreateAPs": False}
    p.controllers = {}
    p.ap_devices = {}
    p._reap_removed_aps = lambda *a: None
    p._fire_event = MagicMock()
    return p


def test_one_poll_is_one_state_write():
    p = plugin()
    dev = FakeDev()
    p.deviceStartComm(dev)
    session = FakeSession()

    def _session_for(d):          # the real one caches the session here too
        p.controllers[d.id]["session"] = session
        return session
    p._session_for = _session_for
    p._poll_controller(dev)
    assert dev.singles == []
    assert len(dev.batches) == 1
    keys = {s["key"] for s in dev.batches[0]}
    for k in ("status", "numClients", "gatewayCpu", "worstClientsJson", "rfJson", "controllerVersion"):
        assert k in keys


def test_the_json_states_are_kept_out_of_sql_logger_once():
    p = plugin()
    dev = FakeDev({"sqlLoggerIgnoreStates": "speedtestUp"})
    p.deviceStartComm(dev)
    p.deviceStartComm(dev)
    assert dev.sharedProps["sqlLoggerIgnoreStates"] == \
        "speedtestUp, wifiGenJson, worstClientsJson, rfJson"
    assert dev.shared_writes == 1


def test_ignore_everything_is_never_narrowed():
    assert MOD.merge_sql_logger_ignore("*") is None
    assert MOD.merge_sql_logger_ignore("RFJSON, wifigenjson, WorstClientsJson") is None
