#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_speedtest_status.py
# Description: v0.10.0. The controller reports a speed test that ended in an
#              error as 0 down and 0 up, with speedtest_status "Error" beside
#              them (measured on a UDR7, 26-11-2026). The plugin published the
#              noughts and dropped the word. It now publishes the word as the
#              state speedtestStatus, and says once in the Event Log when a
#              test first fails and when one works again.
#              v0.10.1. That "failed test" was the gateway's second internet
#              port, which has no cable: the 6am run tests the line in use and
#              then the spare port, and stat/health keeps only the newest test.
#              Where the newest test failed, the plugin now looks through the
#              gateway's stored tests for one that measured a speed in the
#              same run, and reports that.
# Author:      CliveS & Claude Fable 5.2
# Date:        26-11-2026
# Version:     1.1

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


# ── 0.10.1: the failed test was the spare internet port's ────────────────────
# The gateway's stored tests as the UDR7 sent them on 26-11-2026 (ids left
# out). Each morning's run tests WAN, the line in use, then WAN2, a port with
# no cable.
def _ms(y, mo, d, h, mi, s):
    return int(datetime(y, mo, d, h, mi, s).timestamp() * 1000)


STORED = [
    {"time": _ms(2026, 11, 24, 6, 0, 57), "wan_networkgroup": "WAN", "interface_name": "ppp0",
     "download_mbps": 935, "upload_mbps": 111, "latency_ms": 13},
    {"time": _ms(2026, 11, 24, 6, 1, 17), "wan_networkgroup": "WAN2", "interface_name": "eth4",
     "download_mbps": 0, "upload_mbps": 0, "latency_ms": 0},
    {"time": _ms(2026, 11, 25, 6, 0, 35), "wan_networkgroup": "WAN", "interface_name": "ppp0",
     "download_mbps": 938, "upload_mbps": 111, "latency_ms": 12},
    {"time": _ms(2026, 11, 25, 6, 1, 46), "wan_networkgroup": "WAN2", "interface_name": "eth4",
     "download_mbps": 0, "upload_mbps": 0, "latency_ms": 0},
    {"time": _ms(2026, 11, 26, 6, 1, 26), "wan_networkgroup": "WAN", "interface_name": "ppp0",
     "download_mbps": 822, "upload_mbps": 113, "latency_ms": 11},
]
FAILED_AT = int(datetime(2026, 11, 26, 6, 2, 1).timestamp())    # the spare port's test
LINE_AT = int(datetime(2026, 11, 26, 6, 1, 26).timestamp())     # the line's, 35 s earlier


class Stored:
    """Stands in for the controller session: counts how often it is asked."""

    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.asked = rows, error, 0

    def get_speedtests(self):
        self.asked += 1
        if self.error:
            raise self.error
        return self.rows


def _morning(session, states=None, www=None, now=None):
    p = _plugin()
    if now:
        p._now = lambda: now
    cache = {"session": session}
    dev = Dev(states or {"speedtestStatus": "Success"})
    batch = []
    record = dict(FAILED_WWW, speedtest_lastrun=FAILED_AT) if www is None else www
    p._update_controller_extras(dev, cache, [{"subsystem": "wan", "status": "ok"}, record], [], [], batch)
    return p, cache, {s["key"]: s["value"] for s in batch}


def test_the_lines_own_test_is_reported_when_the_spare_ports_failed():
    p, cache, out = _morning(Stored(STORED), now=FAILED_AT + 8 * 3600)
    assert out["speedtestStatus"] == "Success"
    assert out["speedtestDown"] == 822.0 and out["speedtestUp"] == 113.0
    assert out["speedtestAgeHours"] == 8
    assert p.logger.warning.call_count == 0
    assert p.logger.info.call_count == 0


def test_the_gateway_is_asked_once_for_each_failed_test_not_at_every_check():
    session = Stored(STORED)
    p = _plugin()
    cache = {"session": session}
    record = dict(FAILED_WWW, speedtest_lastrun=FAILED_AT)
    for _ in range(5):
        p._update_controller_extras(Dev({"speedtestStatus": "Success"}), cache,
                                    [{"subsystem": "wan"}, dict(record)], [], [], [])
    assert session.asked == 1
    p._update_controller_extras(Dev({"speedtestStatus": "Success"}), cache,
                                [{"subsystem": "wan"}, dict(record, speedtest_lastrun=FAILED_AT + 86400)], [], [], [])
    assert session.asked == 2          # a newer failed test is a new question


def test_a_failed_test_with_no_working_neighbour_is_still_a_failure():
    """The line's own test failed: nothing measured a speed in that run."""
    rows = [r for r in STORED if r["time"] < _ms(2026, 11, 26, 0, 0, 0)]   # yesterday's only
    p, cache, out = _morning(Stored(rows))
    assert out["speedtestStatus"] == "Error"
    assert out["speedtestDown"] == 0.0 and out["speedtestUp"] == 0.0
    assert p.logger.warning.call_count == 1
    assert "no other internet port" in p.logger.warning.call_args[0][0]


def test_a_stored_failure_on_the_line_itself_does_not_count_as_working():
    rows = STORED[:-1] + [dict(STORED[-1], download_mbps=0, upload_mbps=0, latency_ms=0)]
    assert MOD.working_speedtest(rows, FAILED_AT) is None


def test_a_test_run_after_the_failed_one_is_reported():
    later = dict(STORED[-1], time=_ms(2026, 11, 26, 15, 1, 15), download_mbps=920, upload_mbps=112)
    found = MOD.working_speedtest(STORED + [later], FAILED_AT)
    assert found["down"] == 920 and found["time"] == int(datetime(2026, 11, 26, 15, 1, 15).timestamp())


def test_the_window_is_wider_than_any_gap_seen_and_shorter_than_a_day():
    assert 74 * 4 < MOD.SPEEDTEST_SAME_RUN_SECONDS < 3600
    edge = FAILED_AT - MOD.SPEEDTEST_SAME_RUN_SECONDS
    inside = [dict(STORED[-1], time=(edge + 1) * 1000)]
    outside = [dict(STORED[-1], time=(edge - 1) * 1000)]
    assert MOD.working_speedtest(inside, FAILED_AT) is not None
    assert MOD.working_speedtest(outside, FAILED_AT) is None


def test_working_speedtest_survives_rubbish_rows():
    rows = [None, "x", {}, {"time": "soon", "download_mbps": 5}, {"time": None, "download_mbps": "fast"},
            {"download_mbps": 900, "upload_mbps": 100}]
    assert MOD.working_speedtest(rows, FAILED_AT) is None
    assert MOD.working_speedtest(None, FAILED_AT) is None
    assert MOD.working_speedtest([], FAILED_AT) is None


def test_a_controller_without_stored_tests_reports_the_failure_as_before():
    for session in (Stored([]), Stored(error=RuntimeError("HTTP 404")), None, object()):
        p, cache, out = _morning(session)
        assert out["speedtestStatus"] == "Error", session
        assert out["gatewayCpu"] == 0            # the rest of the block still ran


def test_a_read_that_goes_wrong_is_asked_again_at_the_next_check():
    session = Stored(error=RuntimeError("timed out"))
    p = _plugin()
    cache = {"session": session}
    record = dict(FAILED_WWW, speedtest_lastrun=FAILED_AT)
    for _ in range(3):
        p._update_controller_extras(Dev({"speedtestStatus": "Error"}), cache,
                                    [{"subsystem": "wan"}, dict(record)], [], [], [])
    assert session.asked == 3


def test_a_working_newest_test_never_asks_for_the_stored_ones():
    session = Stored(STORED)
    www = dict(FAILED_WWW, speedtest_status="Success", xput_down=920.0, xput_up=112.0)
    p, cache, out = _morning(session, www=www)
    assert session.asked == 0
    assert out["speedtestDown"] == 920.0 and out["speedtestStatus"] == "Success"


def test_get_speedtests_reads_the_v2_list_and_is_empty_where_there_is_none():
    class R:
        def __init__(self, code, body):
            self.status_code, self._body = code, body

        def json(self):
            if isinstance(self._body, Exception):
                raise self._body
            return self._body

    class S:
        def __init__(self, reply):
            self.reply, self.urls = reply, []

        def get(self, url, timeout=None, **k):
            self.urls.append(url)
            return self.reply

    def session(reply, unifi_os=True):
        s = MOD.UniFiSession("controller.example", "user", "pw")
        s.unifi_os, s.base, s.session = unifi_os, "https://controller.example", S(reply)
        return s

    s = session(R(200, {"data": STORED}))
    assert s.get_speedtests() == STORED
    assert s.session.urls == ["https://controller.example/proxy/network/v2/api/site/default/speedtest"]
    assert session(R(200, STORED)).get_speedtests() == STORED          # a bare list
    assert session(R(404, {})).get_speedtests() == []
    assert session(R(200, {"data": "no"})).get_speedtests() == []
    assert session(R(200, ValueError("not json"))).get_speedtests() == []
    legacy = session(R(200, {"data": STORED}), unifi_os=False)
    assert legacy.get_speedtests() == [] and legacy.session.urls == []
