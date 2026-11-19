#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_slow_answers.py
# Description: v0.9.3. The UDR7 sometimes takes far longer than 8 s to answer
#              stat/device (26.05 s and 11.49 s in 150 checks over 75 minutes,
#              19-11-2026, about half an hour apart). The reads now wait
#              longer than that, and one check that gets no answer is silent:
#              the warning comes only when a second check in a row fails.
# Author:      CliveS & Claude Opus 5.5
# Date:        19-11-2026
# Version:     1.0

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import test_guide_faults as G   # noqa: E402  (loads the plugin with a stub indigo)

MOD = G.MOD
SLOWEST_SEEN = 26.05             # seconds, stat/device on the UDR7, 19-11-2026


class _Recorder:
    """Stands in for requests.Session: records each call's timeout."""

    def __init__(self):
        self.timeouts = []

    def get(self, url, timeout=None, **kwargs):
        self.timeouts.append(timeout)

        class _R:
            status_code = 200

            @staticmethod
            def json():
                return {"data": []}
        return _R()


def _session(**kwargs):
    s = MOD.UniFiSession("controller.example", "user", "pw", **kwargs)
    s.unifi_os = True
    s.base = "https://controller.example"
    s.session = _Recorder()
    return s


def _read_timeout(timeout):
    return timeout[1] if isinstance(timeout, tuple) else timeout


def _connect_timeout(timeout):
    return timeout[0] if isinstance(timeout, tuple) else timeout


def test_the_plugin_waits_longer_than_the_slowest_answer_seen():
    assert MOD.CONTROLLER_READ_TIMEOUT > SLOWEST_SEEN * 1.5


def test_the_reads_wait_for_the_read_timeout_and_connect_stays_short():
    s = _session(read_timeout=MOD.CONTROLLER_READ_TIMEOUT)
    s.get_devices()
    s.get_clients()
    s.get_health()
    assert len(s.session.timeouts) == 3
    for t in s.session.timeouts:
        assert _read_timeout(t) == MOD.CONTROLLER_READ_TIMEOUT
        assert _connect_timeout(t) == 8.0


def test_a_session_made_without_a_read_timeout_keeps_its_old_wait():
    s = _session()
    s.get_devices()
    assert _read_timeout(s.session.timeouts[0]) == 8.0


def test_the_plugin_makes_its_session_with_the_read_timeout(monkeypatch):
    made = {}

    class _Fake:
        def __init__(self, *args, **kwargs):
            made.update(kwargs)

        def login(self):
            pass

    p = G.plugin()
    dev = G.FakeDev(states={"status": "Connected"})
    p.controllers[dev.id] = {"session": None}
    p._resolve_creds = lambda d: ("controller.example", "user", "pw", 443, False)
    monkeypatch.setattr(MOD, "UniFiSession", _Fake)
    p._session_for(dev)
    assert made.get("read_timeout") == MOD.CONTROLLER_READ_TIMEOUT


def _connected():
    p = G.plugin()
    dev = G.FakeDev(states={"status": "Connected"})
    box = [G.DeadSession()]
    G._controller(p, dev, box)
    return p, dev, box


def test_one_check_with_no_answer_says_nothing():
    p, dev, box = _connected()
    p._poll_controller(dev)
    assert p.logger.warning.call_count == 0
    assert p.logger.error.call_count == 0
    assert dev.states["status"] == "Connected"
    assert p.controllers[dev.id]["fails"] == 1


def test_a_second_check_in_a_row_with_no_answer_warns_once():
    p, dev, box = _connected()
    p._poll_controller(dev)
    p._poll_controller(dev)
    assert p.logger.warning.call_count == 1
    text = str(p.logger.warning.call_args)
    assert "twice in a row" in text
    assert dev.states["status"] == "Connected"


def test_an_answer_after_one_silent_miss_says_nothing_either():
    p, dev, box = _connected()
    p._poll_controller(dev)
    box[0] = G.LiveSession()
    p._poll_controller(dev)
    assert p.logger.warning.call_count == 0
    assert not any("answered again" in str(c) for c in p.logger.info.call_args_list)
    assert p.controllers[dev.id]["fails"] == 0


def test_an_answer_after_a_warned_miss_is_logged():
    p, dev, box = _connected()
    p._poll_controller(dev)
    p._poll_controller(dev)
    box[0] = G.LiveSession()
    p._poll_controller(dev)
    assert any("answered again" in str(c) for c in p.logger.info.call_args_list)
    assert p.controllers[dev.id]["fails"] == 0


def test_two_silent_misses_apart_never_warn():
    p, dev, box = _connected()
    for _ in range(3):
        box[0] = G.DeadSession()
        p._poll_controller(dev)
        box[0] = G.LiveSession()
        p._poll_controller(dev)
    assert p.logger.warning.call_count == 0
    assert G.fired(p, "controllerUnreachable") == 0
