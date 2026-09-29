---
title: How it works
nav_order: 4
---

# How it works

You do not need to know all of this to use the plugin. It is here for anyone who wants to know what is going on, and for setting up the geofence, which needs a few steps outside Indigo.

## Checking the controller

Every 60 seconds, or whatever you set in **Update frequency**, the plugin asks the controller for its list of devices, the devices connected to it, its own health report and the neighbouring networks its access points can hear. It brings the controller, access point and UniFi WiFi Client devices up to date from those answers.

It waits up to eight seconds for each answer.

If the plugin cannot sign in — the controller cannot be found, or it turns the username and password away — the controller device shows **Unreachable** and the Event Log has a warning at each check until it can. Once the plugin is signed in, a check that gets no answer, or too slow an answer, gives one warning in the Event Log and the plugin tries again at the next check. If three checks in a row get no answer, the controller device shows **Unreachable**, just as it does when the plugin cannot sign in. While the controller is not answering, the access point and UniFi WiFi Client devices keep what they last showed. When the controller answers again, the log says how many checks were missed.

The plugin only reads from the controller, apart from three things you ask for yourself: restarting an access point, flashing its light, and the **Apply Minimum RSSI** menu item.

## Keeping the list of access points in step

After each check, the plugin creates a device for any access point that does not have one yet, and files it in the **UniFi Health** folder. Each time the plugin starts it also moves all of its devices into that folder, creating the folder if it has gone.

When you remove an access point from UniFi — you forget it, or replace it — the plugin deletes its Indigo device, but only after it has been missing from three checks in a row, so one odd answer from the controller cannot delete anything. An access point that is simply switched off stays in the controller's list, so its device is never deleted.

If a trigger, schedule, action group or control page still uses the device, the plugin leaves it in place instead. The Event Log says once what still uses it, and the device's summary reads **Removed from controller (still referenced)**. Delete it yourself once nothing uses it.

You can turn both of these off in the plugin's settings.

## Restarts and dropouts

The plugin notices an access point has restarted when the time since it started goes down between two checks. It ticks **Recently Rebooted** for one check, notes it in the Event Log, runs the **An Access Point Rebooted** trigger, and sends a Pushover message if you have asked for them.

An access point that stops being connected to the controller is not marked offline at once. Firmware updates restart access points one after another, and each is away for a minute or two. So the device stays on, with its summary showing what the controller says it is doing, until it has been away for the **AP offline grace** time, three minutes to start with. Only then does it go off, which is what a trigger watching for a failed access point sees.

## The settings check

At every check the plugin looks at each access point's Wi-Fi settings and notes anything on this list:

| Problem | Why it matters |
|---|---|
| **2.4 GHz channel 40 MHz wide** | 2.4 GHz only has room for three channels that do not overlap, each 20 MHz wide. A 40 MHz channel overlaps most of the band. |
| **2.4 GHz transmit power on High** | A loud access point pulls in devices from far away that would be better on a nearer one. |
| **2.4 GHz minimum signal level off** | Without it, a device can hang on to a distant access point with a weak signal. UniFi Network 10 and later have no such setting, so there it is not checked. |
| **A 2.4 GHz channel shared by more than two of your access points** | Access points on the same channel take turns, so they slow each other down. |
| **2.4 GHz busier than the utilisation warning level** | On a busy channel every device waits longer to send. The level is set in the plugin's settings, 70% to start with. |
| **5 GHz transmit power on High** | The same reason as for 2.4 GHz. |

6 GHz is not checked. The results show on each access point's **Audit Flags** and **Config OK** states, the total on the controller's **Config Audit Issue Count**, and **Plugins → UniFi Health → Run WiFi Config Audit (log report)** writes them all to the Event Log.

When the check finds a problem on an access point that it had not found before, the Event Log says so and the **Config Audit Found an Issue** trigger runs. When a band has been busier than the warning level on average over the last 15 minutes, the Event Log says so and the **An AP Band Went Over the Utilisation Threshold** trigger runs.

The check only reports. It never changes a setting.

## Phone presence

A UniFi WiFi Client device turns to **home** the moment its device connects to your network. It only turns to **away** once the device has been gone for the **Presence: away after (minutes)** time, ten minutes to start with, because phones leave Wi-Fi for short spells all day to save their battery.

When a device you follow does change between home and away, the Event Log says so and the **A Tracked Client Arrived** or **A Tracked Client Left** trigger runs. The plugin keeps the time it last saw each device, so restarting the plugin does not make everyone leave and come home again.

## Adding the phone's location — the geofence

Wi-Fi alone can only notice that a phone has gone quiet, which is why away takes ten minutes. A phone knows when it has left home much sooner, and Apple Home can pass that on. The plugin puts the two together.

To set it up for one phone:

1. In Indigo, create a **New Device**, set **Type** to **UniFi Health** and pick **Geofence Switch**. Name it after the person, such as "Clive Geofence".
2. Make the switch visible in Apple Home. I use the HomeKitLink-Siri plugin for this.
3. In the Home app on that person's iPhone, create two automations: **when I leave home**, turn the switch off, and **when I arrive home**, turn it on.
4. Open that person's **UniFi WiFi Client** device in Indigo, choose the switch in **Geofence switch (optional)**, and click **Save**.

Any other Indigo on and off device can be chosen instead, if you already have one the phone switches. The plugin's own Geofence Switches are listed first.

From then on, the two work together like this:

| Phone on your Wi-Fi? | Geofence switch | Presence |
|---|---|---|
| Yes | On | **home** |
| Yes | Off | **home** — a location mistake cannot mark someone away while their phone is on your Wi-Fi |
| No | On | **home** — the phone has only dropped off Wi-Fi, and its location says it is still here |
| No | Off | **away**, at once, with no ten-minute wait |

The plugin acts on the switch the moment it changes, rather than at the next check. **Presence Source** shows what decided each verdict.

If the phone's **when I leave home** automation ever fails to run, the switch stays on and the person reads as home until it is put right. I let the geofence win because a phone with Wi-Fi switched off or a flat battery at home is far more common than a failed automation.

## Pushover messages

If you tick **Pushover WiFi alerts**, the plugin sends a message through the Pushover plugin when an access point restarts, and when the controller device changes from **Connected** to **Unreachable**. That way you get one message saying what went wrong, rather than a message for every device that dropped off Wi-Fi because of it.

The message vibrates rather than playing a sound, and the plugin sends at most one message for the same access point, or for the controller, in any half hour.

## Keeping SQL Logger's history small

If you use SQL Logger to keep a history of your devices, it saves a row every time a device changes. Some of this plugin's states change at almost every check and are of no use in a chart, so the plugin adds them to each device's SQL Logger skip list:

- on the controller, the three lists kept as text — **Wi-Fi Generation Mix**, **Worst Clients** and **RF Neighbourhood**
- on each access point, **Uptime**, **Connected Clients** and **Summary**
- on each UniFi WiFi Client, **Last Seen (epoch)**

Anything you had already told SQL Logger to skip stays skipped, and a device you told it to ignore completely stays ignored. The controller's readings also go in together at each check, so SQL Logger saves one row per check rather than one for each reading.
