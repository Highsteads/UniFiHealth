#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_tx_power.py
# Description: v0.9.0. Set Access Point Transmit Power: the write sends the
#              WHOLE radio table, refuses a radio that is switched off, reads
#              back, and the action dialog refuses a nonsense custom dBm.
# Author:      CliveS & Claude Opus 5.5
# Date:        05-10-2026
# Version:     1.0

import copy
import os
import sys
from unittest.mock import MagicMock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import test_guide_faults as base   # noqa: E402  (stubs indigo and loads the plugin)
from unifi_api import UniFiSession   # noqa: E402

AP_ID = "ap0001"
TABLE = [
    {"radio": "ng", "channel": 6, "ht": 20, "tx_power_mode": "auto"},
    {"radio": "na", "channel": 36, "ht": 80, "tx_power_mode": "medium"},
    {"radio": "6e", "channel": 5, "ht": 160, "tx_power_mode": "disabled"},
]


class FakeResponse:
    def __init__(self, status=200, text="{}"):
        self.status_code = status
        self.text = text


class FakeController:
    """Holds a stored radio table; PUT replaces it unless told to ignore."""

    def __init__(self, ignore_writes=False):
        self.table = copy.deepcopy(TABLE)
        self.puts = []
        self.ignore = ignore_writes

    def rows(self):
        return [{"_id": AP_ID, "radio_table": copy.deepcopy(self.table)}]

    def put(self, url, json=None, timeout=None):
        self.puts.append((url, copy.deepcopy(json)))
        if not self.ignore:
            self.table = copy.deepcopy(json["radio_table"])
        return FakeResponse()


def session(ctrl):
    s = UniFiSession("host", "u", "p")
    s.unifi_os = True
    s.base = "https://host"
    s.session = MagicMock()
    s.session.put = ctrl.put
    s.get_devices = lambda site="default": ctrl.rows()
    return s


def test_high_is_written_with_the_whole_table_and_read_back():
    ctrl = FakeController()
    ok, msg = session(ctrl).set_radio_tx_power(AP_ID, "ng", "high")
    assert ok, msg
    assert msg == "changed from Auto to High"
    url, body = ctrl.puts[0]
    assert url.endswith(f"/upd/device/{AP_ID}")
    assert [e["radio"] for e in body["radio_table"]] == ["ng", "na", "6e"]
    assert body["radio_table"][1]["tx_power_mode"] == "medium"     # other radios untouched
    assert body["radio_table"][2]["tx_power_mode"] == "disabled"


def test_custom_sets_the_dbm():
    ctrl = FakeController()
    ok, msg = session(ctrl).set_radio_tx_power(AP_ID, "na", "custom", "14")
    assert ok, msg
    assert ctrl.table[1]["tx_power_mode"] == "custom" and ctrl.table[1]["tx_power"] == 14


def test_a_switched_off_radio_is_refused():
    ctrl = FakeController()
    ok, msg = session(ctrl).set_radio_tx_power(AP_ID, "6e", "high")
    assert not ok and "switched off" in msg
    assert ctrl.puts == []


def test_a_write_the_controller_ignores_is_a_failure():
    ctrl = FakeController(ignore_writes=True)
    ok, msg = session(ctrl).set_radio_tx_power(AP_ID, "ng", "high")
    assert not ok and "holds Auto" in msg


def test_no_change_sends_nothing():
    ctrl = FakeController()
    ok, msg = session(ctrl).set_radio_tx_power(AP_ID, "ng", "auto")
    assert ok and "nothing sent" in msg
    assert ctrl.puts == []


def test_bad_inputs_are_refused_before_any_request():
    ctrl = FakeController()
    s = session(ctrl)
    for args in (("ng", "loud"), ("ng", "custom", "abc"), ("ng", "custom", "99"), ("xx", "high")):
        ok, _ = s.set_radio_tx_power(AP_ID, *args)
        assert not ok, args
    assert ctrl.puts == []


def test_dialog_refuses_a_bad_custom_dbm():
    p = base.plugin()
    ok, _, errors = p.validateActionConfigUi({"powerMode": "custom", "customDbm": "40"}, "setApTxPower", 1)
    assert not ok and "customDbm" in errors
    assert p.validateActionConfigUi({"powerMode": "custom", "customDbm": "12"}, "setApTxPower", 1)[0]
    assert p.validateActionConfigUi({"powerMode": "high", "customDbm": ""}, "setApTxPower", 1)[0]
