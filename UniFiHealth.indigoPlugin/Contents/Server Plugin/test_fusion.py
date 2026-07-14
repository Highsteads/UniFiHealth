#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_fusion.py
# Description: Contract tests for presence_fusion — the pure decision core of
#              UniFi Health's Wi-Fi + geofence fused presence (v0.6.0). Runs
#              under pytest OR standalone: python3 test_fusion.py
# Author:      CliveS & Claude Fable 5
# Date:        14-07-2026
# Version:     1.0

from presence_fusion import fused_presence, presence_source

AWAY_MIN = 10


# ── legacy Wi-Fi-only behaviour (geo_home=None) must be unchanged ──────────

def test_wifi_only_home_while_associated():
    assert fused_presence(True, 0, AWAY_MIN, None) == "home"

def test_wifi_only_patient_during_nap():
    # phone napping 9 minutes — still home (below the debounce)
    assert fused_presence(False, 9, AWAY_MIN, None) == "home"

def test_wifi_only_away_after_debounce():
    assert fused_presence(False, 10, AWAY_MIN, None) == "away"
    assert fused_presence(False, 9999, AWAY_MIN, None) == "away"


# ── fused behaviour (geofence configured) ───────────────────────────────────

def test_both_home():
    assert fused_presence(True, 0, AWAY_MIN, True) == "home"

def test_gps_wobble_cannot_fake_away_while_on_wifi():
    # geofence flaps to away but the phone is on the house Wi-Fi -> home
    assert fused_presence(True, 0, AWAY_MIN, False) == "home"

def test_wifi_nap_covered_by_geofence():
    # phone napped off Wi-Fi for 45 min but geofence says inside -> home
    assert fused_presence(False, 45, AWAY_MIN, True) == "home"

def test_fast_exit_no_debounce_wait():
    # left the geofence, not on Wi-Fi -> away IMMEDIATELY even at minute 0
    assert fused_presence(False, 0, AWAY_MIN, False) == "away"
    assert fused_presence(False, 2, AWAY_MIN, False) == "away"

def test_documented_residual_stuck_geofence_reads_home():
    # leave-automation misfired: geofence stuck ON, phone long gone -> home
    # (deliberate choice; see the module docstring truth table)
    assert fused_presence(False, 600, AWAY_MIN, True) == "home"


# ── provenance labels ───────────────────────────────────────────────────────

def test_source_labels():
    assert presence_source(True, None) == "wifi"
    assert presence_source(False, None) == "wifi"
    assert presence_source(True, True) == "wifi+geofence"
    assert presence_source(True, False) == "wifi"
    assert presence_source(False, True) == "geofence"
    assert presence_source(False, False) == "geofence"


if __name__ == "__main__":
    import sys
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError:
                failures += 1
                print(f"FAIL {name}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
