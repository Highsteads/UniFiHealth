#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    presence_fusion.py
# Description: Pure presence-fusion decision logic for UniFi Health — combines
#              the Wi-Fi witness (client associated with the network) with an
#              optional geofence witness (a switch flipped by a phone's
#              HomeKit leave/arrive automation). No indigo import, so it is
#              contract-testable outside the plugin host (see test_fusion.py).
# Author:      CliveS & Claude Fable 5
# Date:        14-07-2026
# Version:     1.0

# Fusion truth table (geofence configured, geo_home is True/False):
#
#   Wi-Fi assoc | geofence | verdict | why
#   ------------+----------+---------+------------------------------------------
#   yes         | home     | home    | both witnesses agree
#   yes         | away     | home    | GPS wobble can't fake "away" while the
#               |          |         | phone is demonstrably on the house Wi-Fi
#   no          | home     | home    | phone napping its Wi-Fi / Wi-Fi off at
#               |          |         | home — the geofence vouches for it
#   no          | away     | AWAY    | immediately — no away_minutes wait; this
#               |          |         | is the fast exit path
#
# Known residual failure mode (documented, accepted): if a phone's "leave"
# automation fails to fire, the geofence switch sticks ON and the person reads
# home until it corrects. We deliberately let the geofence win the sustained
# conflict because the opposite case (Wi-Fi off / flat battery while genuinely
# at home) is far more common than a HomeKit automation misfire.
#
# With NO geofence configured (geo_home is None) the behaviour is exactly the
# pre-0.6 Wi-Fi-only logic: home instantly while associated, away only after
# away_minutes of silence.


def fused_presence(wifi_on_network, minutes_since_seen, away_minutes, geo_home):
    """Return 'home' or 'away'.

    wifi_on_network    -- bool: client is in the controller's connected list now
    minutes_since_seen -- int: minutes since the client was last seen (ignored
                          while wifi_on_network is True)
    away_minutes       -- int: the Wi-Fi-only debounce window
    geo_home           -- True/False when a geofence switch is configured
                          (ON = inside the home zone), None when not configured
    """
    if wifi_on_network:
        return "home"
    if geo_home is None:
        # Wi-Fi-only legacy behaviour: patient away.
        return "away" if minutes_since_seen >= away_minutes else "home"
    return "home" if geo_home else "away"


def presence_source(wifi_on_network, geo_home):
    """Human-readable provenance for the verdict, for the presenceSource state
    and the clientSummary line."""
    if geo_home is None:
        return "wifi"
    if wifi_on_network and geo_home:
        return "wifi+geofence"
    if wifi_on_network:
        return "wifi"
    return "geofence"
