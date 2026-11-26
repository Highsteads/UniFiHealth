#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_speedtest_status.py
# Description: v0.10.0. The controller reports a speed test that ended in an
#              error as 0 down and 0 up, with speedtest_status "Error" beside
#              them (measured on a UDR7, 26-11-2026). The plugin published the
#              noughts and dropped the word. It now publishes the word as the
#              state speedtestStatus, and says once in the Event Log when a
#              test first fails and when one works again.
# Author:      CliveS & Claude Fable 5.2
# Date:        26-11-2026
# Version:     1.0

import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from unittest.mock import MagicMock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import test_guide_faults as G   # noqa: E402  (loads the plugin with a stub indigo)

MOD = G.MOD
SERVER = os.path.join(os.path.dirname(HERE), "UniFiHealth.indigoPlugin", "Contents", "Server Plugin")

# The www record as the UDR7 sent it on 26-11-2026, addresses left out.
FAILED_WWW = {"subsystem": "www", "status": "ok", "latency": 11, "drops": 1,
              "speedtest_lastrun": 1795672921, "speedtest_ping": 0,
              "speedtest_status": "Error", "xput_down": 0.0, "xput_up": 0.0}
NOW = 1795672921 + 8 * 3600


class Dev:
    name = "UniFi Controller"

    def __init__(self, states=None):
        self.states = dict(states or {})


def _plugin():
    p = MOD.Plugin.__new__(MOD.Plugin)
    p.logger = MagicMock()
    p._now = lambda: NOW
    return p


def _extras(p, dev, www):
    batch = []
    health = [{"subsystem": "wan", "status": "ok"}, dict(www)]
    p._update_controller_extras(dev, {}, health, [], [], batch)
    return {s["key"]: s["value"] for s in batch}


def test_the_state_is_declared_on_the_controller():
    root = ET.parse(os.path.join(SERVER, "Devices.xml")).getroot()
    ids = [s.get("id") for d in root.findall("Device") if d.get("id") == "unifiController"
           for s in d.iter("State")]
    assert "speedtestStatus" in ids
    assert ids.count("speedtestStatus") == 1


def test_the_controllers_word_is_published():
    out = _extras(_plugin(), Dev(), FAILED_WWW)
    assert out["speedtestStatus"] == "Error"
    assert out["speedtestDown"] == 0.0 and out["speedtestUp"] == 0.0
    assert out["speedtestAgeHours"] == 8


def test_a_controller_that_sends_no_word_publishes_a_blank():
    www = {"subsystem": "www", "status": "ok", "xput_down": 512.3, "xput_up": 110.0}
    out = _extras(_plugin(), Dev(), www)
    assert out["speedtestStatus"] == ""
    assert isinstance(out["speedtestStatus"], str)


def test_the_states_after_the_word_are_still_written():
    """The word sits in the same guarded block as the gateway figures."""
    www = dict(FAILED_WWW)
    health_wan = {"subsystem": "wan", "status": "ok", "gw_system-stats": {"cpu": 20, "mem": 70}}
    batch = []
    _plugin()._update_controller_extras(Dev(), {}, [health_wan, www], [], [], batch)
    out = {s["key"]: s["value"] for s in batch}
    assert out["gatewayCpu"] == 20 and out["gatewayMem"] == 70


def test_failed_is_decided_by_the_word_alone():
    assert MOD.speedtest_failed("Error")
    assert MOD.speedtest_failed(" error ")
    assert MOD.speedtest_failed("Failed")
    for word in ("", None, "Success", "Idle", "Running", 0):
        assert not MOD.speedtest_failed(word), word


def test_a_first_failure_is_one_warning_in_plain_words():
    p = _plugin()
    _extras(p, Dev({"speedtestStatus": "Success"}), FAILED_WWW)
    assert p.logger.warning.call_count == 1
    line = p.logger.warning.call_args[0][0]
    assert "speed test failed" in line
    assert "It ran at" in line and "am" in line
    assert line.endswith(".")
    assert "|" not in line and "=" not in line
    assert line.isascii()


def test_a_failure_already_stored_says_nothing():
    """The state on the device is the memory, so a restart is silent."""
    p = _plugin()
    dev = Dev({"speedtestStatus": "Error"})
    for _ in range(3):
        _extras(p, dev, FAILED_WWW)
    assert p.logger.warning.call_count == 0
    assert p.logger.info.call_count == 0


def test_a_device_made_before_the_state_existed_says_it_once():
    p = _plugin()
    _extras(p, Dev(), FAILED_WWW)          # no speedtestStatus state yet
    assert p.logger.warning.call_count == 1


def test_a_test_that_works_again_is_one_line():
    p = _plugin()
    www = dict(FAILED_WWW, speedtest_status="Success", xput_down=512.3, xput_up=110.0)
    _extras(p, Dev({"speedtestStatus": "Error"}), www)
    assert p.logger.warning.call_count == 0
    assert p.logger.info.call_count == 1
    assert "working again" in p.logger.info.call_args[0][0]


def test_a_working_test_that_stays_working_says_nothing():
    p = _plugin()
    www = dict(FAILED_WWW, speedtest_status="Success", xput_down=512.3, xput_up=110.0)
    _extras(p, Dev({"speedtestStatus": "Success"}), www)
    _extras(p, Dev({"speedtestStatus": ""}), www)
    assert p.logger.warning.call_count == 0
    assert p.logger.info.call_count == 0


def test_clock_words_reads_as_a_person_says_it():
    six = datetime(2026, 11, 26, 6, 2).timestamp()
    noon = datetime(2026, 11, 26, 12, 5).timestamp()
    late = datetime(2026, 11, 25, 23, 40).timestamp()
    midnight = datetime(2026, 11, 26, 0, 7).timestamp()
    now = datetime(2026, 11, 26, 14, 0).timestamp()
    assert MOD.clock_words(six, now) == "6:02am today"
    assert MOD.clock_words(noon, now) == "12:05pm today"
    assert MOD.clock_words(midnight, now) == "12:07am today"
    assert MOD.clock_words(late, now) == "11:40pm on 25 November"
    assert MOD.clock_words(0, now) == ""
    assert MOD.clock_words(None, now) == ""
    assert MOD.clock_words("soon", now) == ""
