---
title: Version history
nav_order: 9
---

# Version history

The newest version is at the top.

## 0.9.0 — 5 October 2026

**Set Access Point Transmit Power**, a new action. Choose an access point, a band (2.4, 5 or 6 GHz) and a power: Auto, Low, Medium, High, or Custom with a figure in dBm from 1 to 30.

- The plugin changes only that band and leaves the access point's other settings alone.
- It reads the setting back afterwards and says in the Event Log whether the controller kept it. The controller sometimes accepts a change and quietly ignores it, so the plugin checks.
- A band you have switched off is left off. Setting its power would switch it back on, so the action says so and changes nothing.
- The access point restarts that radio to apply the change, so the devices on it reconnect within a minute or two.
- On some access points Auto already runs at full power. On a U7 Pro, for example, Auto and High both transmit at 16 dBm on 2.4 GHz, so High gains nothing there.

## 0.8.2 — 29 September 2026

A radio that is switched off no longer counts. An access point keeps reporting a 2.4 GHz channel while its 2.4 GHz radio is off, because it still listens, so the settings check counted it as sharing that channel and could report "shared by 3 APs" when only two were using it. It also checked the switched-off radio's width and power. The check now skips any radio you have turned off.

## 0.8.1 — 29 September 2026

Far fewer "busy" lines in the Event Log.

- **A band is judged on the last 15 minutes, not one reading.** A busy 2.4 GHz radio jumps between about 60% and 99% from one minute to the next, so 0.8.0 warned every time it climbed back over your warning level: about 280 lines a day on a house with six access points. The line and the **An AP Band Went Over the Utilisation Threshold** trigger now look at the average over the last 15 minutes. The same fortnight replayed under the new rule gives about seven a day.
- **It has to calm down properly before it can warn again.** The average must drop 10 points below your warning level, up from 5.
- After the plugin starts, a band needs about ten minutes of readings before it can warn.

## 0.8.0 — 27 September 2026

A tidy-up of the things I found wrong while writing this guide.

- **Two triggers now work.** **Config Audit Found an Issue** runs when the settings check finds a new problem on an access point, and **An AP Band Went Over the Utilisation Threshold** runs when a band gets busier than your warning level. Each runs once when the problem appears, not at every check, and restarting the plugin does not run them again for problems it already knew about. A band has to drop five points below the level before it can run the trigger again, so one sitting right on the line does not keep setting it off.
- **The Log level setting now does something.** Choose Debug to see everything, or Warning or Error for a quieter log.
- **A controller that stops answering now shows Unreachable.** Before, once the plugin had signed in, a controller that went quiet kept showing **Connected** and nothing told you. Now three failed checks in a row mark it **Unreachable**, which runs its trigger and sends the Pushover message if you use them. One slow answer on its own still only puts a line in the log. While the controller is down, the access points and phones keep what they last showed, rather than being worked out again from its last answer.
- **Minimum signal level on UniFi Network 10.** UniFi Network 10 no longer has a minimum signal level on each access point. The settings check no longer reports **2.4GHz min-RSSI off** there, since there is nothing you could change to clear it, and **Apply Minimum RSSI** now says so in one line and sends nothing, rather than listing every access point as failed. On older versions it works as before, and 2.4 GHz is no longer turned away.
- **Controller Version** is read again each time the plugin starts, so it shows the new version after you update the controller.
- The plugin now comes with an example settings file, `IndigoSecrets_example.py`, holding the names of the settings it reads.

## 0.7.4 — 23 September 2026

The access points and the UniFi WiFi Client devices stop filling SQL Logger's history. Each access point reports its uptime at every check and rewrites its summary and its list of connected devices at most, and each client records the moment it was last seen, so SQL Logger was saving about 16,000 rows a day for them. The plugin now tells SQL Logger to skip those. Presence, device counts, channel use, CPU and signal are kept exactly as before, anything you had already told SQL Logger to skip is kept, and existing history is untouched.

## 0.7.3 — 23 September 2026

The controller's history is one row per check, not up to six. Each check updated the controller's readings one at a time, and SQL Logger saved a separate row for each one that had changed. The readings now go in together. The plugin also tells SQL Logger to skip the three lists the controller keeps as text — the Wi-Fi generation mix, the worst clients and the nearby networks — which change at most checks and cannot be charted. Every number is kept exactly as before.

## 0.7.2 — 11 September 2026

The plugin carries a note of where its code lives on GitHub, the same way other Indigo plugins do. Nothing else changed.

## 0.7.1 — 7 September 2026

The help text in the settings dialog was cut off mid-sentence, because the dialog was stretched wider than its own window. The two long pieces of help now sit where they wrap properly. No setting or behaviour changed.

## 0.7.0 — 29 August 2026

- **Access point models have their proper names.** UniFi's short model codes can mislead — its code for the UAP-AC-Lite is U7LT, which has nothing to do with Wi-Fi 7 — so **Model** now shows the name, such as **UAP-AC-Lite** or **U6-LR**, and a new **Model code** state keeps UniFi's code. A code the plugin does not know is shown as it is.
- **New Preview Minimum RSSI and Apply Minimum RSSI menu items.** The preview lists every device a minimum signal level would cut off, and changes nothing. Apply reads each change back, so a change the controller ignores is reported as a failure rather than a success.

## 0.6.4 — 2 August 2026

The **About** item in the Plugins menu opens this project's page. It went nowhere before.

## 0.6.3 — 21 July 2026

Log lines no longer come out with the time printed twice, and a log line with a mistake in it keeps its details rather than losing them.

## 0.6.2 — 14 July 2026

One failed check no longer stops the plugin. A controller that was slow to answer could stop the plugin's checking, leaving a gap until Indigo restarted it. Now a failed check gives one warning and the next check carries on, further failures stay out of the log, and the log says how many checks were missed once the controller answers again.

## 0.6.1 — 14 July 2026

New **Geofence Switch** device, a plain on and off switch for Apple Home to turn on and off as a phone arrives and leaves. It is listed first when you choose a UniFi WiFi Client's geofence switch.

## 0.6.0 — 14 July 2026

A UniFi WiFi Client device can be paired with a **geofence switch** that the phone's own location turns on and off. Home when either Wi-Fi or the switch says home, and away the moment the switch says the phone has left and it is off your Wi-Fi, with no ten-minute wait. The plugin acts on the switch as soon as it changes, and a new **Presence Source** state shows what decided each verdict.

## 0.5.1 — 29 June 2026

An access point is only marked offline once it has been away from the controller for the new **AP offline grace** time, three minutes to start with, so the restarts of a firmware update no longer set off alarms. While it is away for less than that, its summary shows what the controller says it is doing, such as **Upgrading**.

## 0.5.0 — 29 June 2026

The plugin shows much more of what the controller already knows.

- On the controller: internet status, delay and dropouts, the gateway's speed test result and how old it is, your public internet address, the gateway's CPU and memory, wired and wireless device counts, the mix of Wi-Fi generations, a count of devices on the oldest Wi-Fi standards, the least satisfied devices, how many access points need a firmware update, and how many neighbouring networks can be heard on each 2.4 GHz channel.
- On each access point: firmware version and whether an update is waiting, CPU, memory and load, the speed of its network cable against what it could manage, the switch and port it is plugged into, how much data it is passing, and how many neighbouring networks share its 2.4 GHz channel.
- **Controller Version** is filled in. It was always empty before.

## 0.4.1 — 29 June 2026

An access point that the controller still lists but which is not connected now shows as offline, with the reason where the controller gives one. Before, it showed as online.

## 0.4.0 — 29 June 2026

- A UniFi console with its own Wi-Fi, such as a Dream Router or Dream Machine, is found and shown as an access point.
- An access point you remove from UniFi has its Indigo device removed too, after three checks, unless a trigger, schedule, action group or control page still uses it. A new **Auto-remove AP devices** setting turns this off.

## 0.3.0 — 11 June 2026

UniFi WiFi Client devices gain **Presence** — home the moment the device connects, away only after it has been gone for the new **Presence: away after (minutes)** setting — with new **A Tracked Client Arrived** and **A Tracked Client Left** triggers. The time a device was last seen is kept through a restart of the plugin.

## 0.2.2 — 10 June 2026

A tidy-up of the code with no change you would notice.

## 0.2.1 — 5 June 2026

**Send Status Request** works on access point and client devices. It used to do nothing but write an error to the log. A blank or mistyped number in the settings no longer stops the plugin starting.

## 0.2.0 — 31 May 2026

Each access point lists the Wi-Fi devices connected to it, with their band, signal and satisfaction, for use on a dashboard.

## 0.1.1 — 30 May 2026

An access point that is online shows green whatever the settings check found, and each access point device keeps its name in step with the name in UniFi.

## 0.1.0 — 30 May 2026

First release.
