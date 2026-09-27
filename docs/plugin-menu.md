---
title: The plugin menu
nav_order: 7
---

# The plugin menu

These are under **Plugins → UniFi Health**.

| Menu item | What it does |
|---|---|
| **Discover / Create AP Devices** | Creates a device for any access point that does not have one yet, and says in the Event Log how many it made. It works even when **Auto-create AP devices** is unticked, so you can leave that off and add new access points when you choose. |
| **Run WiFi Config Audit (log report)** | Writes the results of the settings check to the Event Log — one line per access point, either **OK** or the problems found, and any 2.4 GHz channel shared by more than two of your access points. [How it works](how-it-works.md) lists what it checks. It uses the results of the last check, so it takes no time. |
| **Preview Minimum RSSI...** | Shows which devices would be cut off if you set a minimum signal level. It changes nothing. See below. |
| **Apply Minimum RSSI...** | Asks the controller to set a minimum signal level on every access point. See below. |
| **Test Connection** | Writes the plugin's version and details of your Mac and Indigo to the Event Log, then asks each controller for its devices and says whether that worked, with how many access points and connected devices it found. |
| **Show Plugin Info** | Writes the plugin's version and details of your Mac and Indigo to the Event Log, which is useful to include if you ask for help on the Indigo forum. |

## Minimum RSSI

**RSSI** is the signal level a device reaches an access point with, measured in dBm, where -50 is strong and -80 is weak. An access point with a **minimum RSSI** cuts off any device whose signal falls below that level.

It does not move a device to a nearer access point. It just cuts it off, and if the access point that cut it off is already the nearest one, the device reconnects and is cut off again. That is why the preview comes first.

### Preview Minimum RSSI

Choose the **Band** — 2.4, 5 or 6 GHz — and the **Minimum RSSI (dBm)**, which starts at -70. The Event Log then lists every Wi-Fi device on that band whose signal is at or below that level, weakest first, with the access point it is on, and how many there are. If there are none, it says it would be safe to apply. Nothing is sent to the controller.

### Apply Minimum RSSI

Choose the **Band** and the **Minimum RSSI (dBm)**, which must be between -94 and -60. Two tick boxes finish it off:

- **Enable the threshold** — ticked, the level is switched on. Unticked, the value is stored and switched off.
- **Dry run** — ticked, the Event Log says what would change on each access point and nothing is sent.

For each access point, the plugin reads its settings, changes only the one value, sends them back, and reads them again to check the controller really kept the change. The Event Log gives a line per access point and a total of those changed, those already right and those that failed. An access point the controller did not change is reported as a failure, never as a success.

UniFi Network 10 and later have no minimum signal level on each access point. 2.4 GHz has none at all, and for 5 and 6 GHz it is set on each Wi-Fi network in the UniFi Network app. On those versions the plugin checks the controller's version first, says so in one line, and sends nothing. The preview still works, and adds the same note. On older versions all three bands can be set.
