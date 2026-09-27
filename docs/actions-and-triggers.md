---
title: Actions and triggers
nav_order: 5
---

# Actions and triggers

## Actions

Add these to an action group, a schedule or a trigger. They are under **Device Actions** in the UniFi Health section of the action list.

| Action | What it does |
|---|---|
| **Restart Access Point** | Tells the controller to restart the access point you choose. Devices on it drop off for a minute or two and reconnect. |
| **Locate Access Point (flash LED)** | Makes the access point's light flash so you can pick it out, which helps when several look the same. |
| **Stop Locating Access Point** | Stops the flashing. |
| **Refresh UniFi Data Now** | Checks the controller straight away rather than waiting for the next check. |

These three access point actions change something on the controller, so the account the plugin signs in with must be allowed to manage devices. The Event Log says whether each one was sent, and gives the controller's reply if it was turned away.

**Send Status Request** on an access point or a UniFi WiFi Client also checks the controller straight away.

A **Geofence Switch** answers Indigo's standard **Turn On**, **Turn Off** and **Toggle**, which is how Apple Home switches it. It only changes its own state.

## Triggers

To use one, create a new trigger, set its type to **UniFi Health**, and choose the event. Then add whatever you want to happen.

| Trigger | When it runs |
|---|---|
| **An Access Point Rebooted** | Once, when the plugin sees an access point has restarted. |
| **The UniFi Controller Became Unreachable** | At each check while the controller device shows **Unreachable**. |
| **WLAN Subsystem Health Not OK** | At each check while UniFi's own verdict on your Wi-Fi is anything other than **ok**. |
| **A Tracked Client Arrived (presence became home)** | When a UniFi WiFi Client device changes from away to home. |
| **A Tracked Client Left (presence became away)** | When a UniFi WiFi Client device changes from home to away. |
| **A Client Dropped Below the Satisfaction Threshold** | At each check while a UniFi WiFi Client device is connected with a satisfaction score below the **Satisfaction warning threshold** setting. |

These triggers do not say which device caused them. Where that matters, use one of Indigo's own device state triggers instead, which you can point at a single device — for example a trigger on an access point's **Device State**, or on a client's **Presence (home/away)** becoming **away**.

The trigger list also shows **Config Audit Found an Issue** and **An AP Band Went Over the Utilisation Threshold**. This version of the plugin never runs them. For the same result, use a device state trigger on an access point's **Config OK (audit)** becoming false, or on one of its **Utilisation %** states going above the level you want.

## Other useful device state triggers

Every state on the [Your devices](devices.md) page can be used in an Indigo device state trigger. A few that are handy:

- an access point's device turning off, which happens once it has been away for longer than the **AP offline grace** setting
- the controller's **APs Needing Firmware Update** going above zero
- an access point's **Uplink Below Capability** becoming true
- the controller's **WAN/Internet Status** changing from **ok**
