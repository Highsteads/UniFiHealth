#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_login_refused.py
# Description: v0.9.2. A refused sign-in is not retried at every check. On
#              17-11-2026 the router was replaced and its password changed;
#              the plugin asked again every minute, which turned the
#              controller's 403 into a 429 lockout that never lapsed.
# Author:      CliveS & Claude Fable 5.2
# Date:        17-11-2026
# Version:     1.0

from unittest.mock import MagicMock

import pytest

import test_outage_presence as base

MOD = base.MOD
API = __import__("unifi_api")
CTRL_ID = base.CTRL_ID


def refuse(p, session, status):
    """Make every sign-in from now on answer `status`; count the tries."""
    tries = []

    def _session_for(d):
        tries.append(p._now())
        if status:
            raise API.UniFiLoginRefused(status)
        p.controllers[d.id]["session"] = session
        return session
    p._session_for = _session_for
    return tries


def warnings(p):
    return [c.args[0] for c in p.logger.warning.call_args_list]


def test_the_wait_doubles_from_five_minutes_to_an_hour():
    assert [MOD.login_hold_seconds(n) for n in (0, 1, 2, 3, 4, 5, 9)] == [0, 300, 600, 1200, 2400, 3600, 3600]


def test_one_minute_is_singular():
    assert MOD.minutes_text(60) == "1 minute"
    assert MOD.minutes_text(300) == "5 minutes"


@pytest.mark.parametrize("status", [401, 403, 429])
def test_a_refusal_is_not_tried_again_at_the_next_check(monkeypatch, status):
    p, session, clock, ctrl, phone, geo = base.setup(monkeypatch)
    tries = refuse(p, session, status)
    for step in range(5):                      # five one-minute checks
        clock[0] = 1000 + 60 * step
        p._poll_cycle()
    assert len(tries) == 1
    assert ctrl.states["status"] == MOD.LOGIN_REFUSED_STATUS
    assert len(warnings(p)) == 1, "the wait must be quiet"


def test_it_tries_again_after_the_wait_and_then_waits_longer(monkeypatch):
    p, session, clock, ctrl, phone, geo = base.setup(monkeypatch)
    tries = refuse(p, session, 403)
    p._poll_cycle()
    clock[0] = 1000 + 301
    p._poll_cycle()
    assert len(tries) == 2
    assert p.controllers[CTRL_ID]["login_hold_until"] == clock[0] + 600
    clock[0] += 599
    p._poll_cycle()
    assert len(tries) == 2


def test_a_refusal_is_reported_at_once_not_after_three_checks(monkeypatch):
    p, session, clock, ctrl, phone, geo = base.setup(monkeypatch)
    refuse(p, session, 403)
    p._poll_cycle()
    assert ctrl.states["status"] == MOD.LOGIN_REFUSED_STATUS
    p._pushover.assert_called_once()
    assert p._fire_event.call_args_list.count((("controllerUnreachable",),)) == 1


def test_the_event_and_pushover_are_not_repeated_while_it_stays_refused(monkeypatch):
    p, session, clock, ctrl, phone, geo = base.setup(monkeypatch)
    refuse(p, session, 403)
    for clock[0] in (1000, 1301, 1902):
        p._poll_cycle()
    assert p._pushover.call_count == 1
    assert p._fire_event.call_args_list.count((("controllerUnreachable",),)) == 1


def test_an_accepted_sign_in_clears_the_wait(monkeypatch):
    p, session, clock, ctrl, phone, geo = base.setup(monkeypatch)
    refuse(p, session, 429)
    p._poll_cycle()
    refuse(p, session, None)
    clock[0] = 1301
    p._poll_cycle()
    cache = p.controllers[CTRL_ID]
    assert (cache["refusals"], cache["login_hold_until"], cache["poll_ok"]) == (0, 0, True)
    assert ctrl.states["status"] == "Connected"
    refuse(p, session, 403)
    clock[0] = 1361
    p._poll_cycle()
    assert cache["login_hold_until"] == 1361 + 300, "a later refusal starts from five minutes"


def test_a_timeout_is_still_tried_at_every_check(monkeypatch):
    p, session, clock, ctrl, phone, geo = base.setup(monkeypatch)
    session.dead = True
    for step in range(4):
        clock[0] = 1000 + 60 * step
        p._poll_cycle()
    assert p.controllers[CTRL_ID]["fails"] == 4
    assert ctrl.states["status"] == "Unreachable"
    assert not p.controllers[CTRL_ID].get("login_hold_until")


@pytest.mark.parametrize("status,word", [(403, "wrong"), (401, "wrong"), (429, "too many")])
def test_the_warning_says_what_to_do_in_plain_words(monkeypatch, status, word):
    p, session, clock, ctrl, phone, geo = base.setup(monkeypatch)
    refuse(p, session, status)
    p._poll_cycle()
    text = warnings(p)[0]
    assert word in text and "IndigoSecrets.py" in text and "5 minutes" in text
    assert text.endswith(".") and "HTTP" not in text and "|" not in text


class _Reply:
    def __init__(self, status):
        self.status_code = status
        self.headers = {}


@pytest.mark.parametrize("status,kind", [(401, API.UniFiLoginRefused), (403, API.UniFiLoginRefused),
                                         (429, API.UniFiLoginRefused), (500, API.UniFiError)])
def test_login_sorts_a_refusal_from_any_other_failure(monkeypatch, status, kind):
    s = API.UniFiSession("192.0.2.1", "u", "p")
    s.unifi_os = True
    fake = MagicMock()
    fake.post.return_value = _Reply(status)
    monkeypatch.setattr(API.requests, "Session", lambda: fake)
    with pytest.raises(API.UniFiError) as err:
        s.login()
    assert type(err.value) is kind
