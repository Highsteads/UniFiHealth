---
title: Settings
nav_order: 6
---

# Settings

## The plugin's settings

Open these with **Plugins → UniFi Health → Configure**. They apply to everything the plugin does. The controller's address and sign-in details are not here — they go in the controller device or in a settings file, both explained below.

| Setting | What it does |
|---|---|
| **Update frequency (seconds)** | How often the plugin checks the controller. It starts at 60, and anything below 30 is treated as 30. |
| **Utilisation warning threshold (%)** | How busy a 2.4 GHz channel can get before the settings check reports it, and how busy any band can get, on average over 15 minutes, before the Event Log says so and the **An AP Band Went Over the Utilisation Threshold** trigger runs. It starts at 70. |
| **Satisfaction warning threshold** | The satisfaction score below which a UniFi WiFi Client device runs the **A Client Dropped Below the Satisfaction Threshold** trigger. It starts at 80. |
| **Presence: away after (minutes)** | How long a device you follow must be off your network before it counts as away. It starts at 10, and anything below 2 is treated as 2. Arriving home always counts at once. |
| **Auto-create AP devices** | Ticked, the plugin creates a device for every access point it finds, including a console with its own Wi-Fi such as a Dream Router. It is ticked to start with. |
| **Auto-remove AP devices** | Ticked, the plugin deletes an access point's device once you remove the access point from UniFi, unless a trigger, schedule, action group or control page still uses it. It is ticked to start with. [How it works](how-it-works.md) explains the safeguards. |
| **AP offline grace (minutes)** | How long an access point must be away from the controller before its device goes off. It starts at 3, which rides out the restarts of a firmware update. Set it to 0 to mark an access point offline at once. |
| **Pushover WiFi alerts** | Ticked, the plugin sends a Pushover message when an access point restarts or the controller device becomes **Unreachable**. You need the Pushover plugin installed and turned on. It is unticked to start with. |
| **Log level** | How much the plugin writes to the Event Log. **Info**, to start with, shows what changes. **Debug** adds every step, which helps when asking for help. **Warning** and **Error** keep the log to problems only. |

A change takes effect as soon as you click **Save**.

### Keeping the controller's details in one file

You can keep the controller's address and sign-in details in a shared file instead of typing them into Indigo. The file is called `IndigoSecrets.py` and lives in `/Library/Application Support/Perceptive Automation/`. If you run other plugins of mine you may have one already — add these lines to it. If not, create a plain text file with that name holding them:

```python
UNIFI_HOST     = "192.168.1.1"
UNIFI_USERNAME = "your-local-unifi-user"
UNIFI_PASSWORD = "your-password"
```

Change the three values to your own. The plugin comes with `IndigoSecrets_example.py`, inside the plugin, which lists every name it reads. If you use Pushover and want the messages to go to a particular Pushover user, add that user's key too:

```python
PUSHOVER_USER_TOKEN = "your-pushover-user-key"
```

When the file has a value, it is used, whatever the controller device says. With all three of the controller's details in the file, the plugin creates the controller device by itself when it starts and finds none. After changing the file, choose **Plugins → UniFi Health → Reload** so the plugin reads it again.

## The controller device's settings

Open these by double-clicking the **UniFi Controller** device.

| Setting | What it does |
|---|---|
| **Controller IP / Hostname** | The controller's network address, such as `192.168.1.1`, or its name. Leave it blank if the settings file has it. |
| **Port** | 443 for a UniFi console such as a Dream Machine or Dream Router, which is how it starts. For the UniFi Network application on a computer, or an older Cloud Key, use the port you reach it on, usually 8443. |
| **Username** and **Password** | The local account the plugin signs in with. Leave them blank if the settings file has them. |
| **Verify SSL** | Leave this unticked unless your controller has a proper security certificate. Most home controllers use one they made themselves, and with this ticked the plugin would refuse to connect to it. It is unticked to start with. A change takes effect when you click **Save**. |
| **Save without configuring** | Tick this to save the device before you have the sign-in details. It stays idle until you add them. |

The dialog will not save until it has an address, a username and a password, from these boxes or the settings file, unless **Save without configuring** is ticked.

## An access point device's settings

You rarely need these, because the plugin fills them in when it creates the device.

| Setting | What it does |
|---|---|
| **UniFi Controller** | The controller the access point belongs to. |
| **Access Point** | The access point, chosen from those the controller has. The list fills in once the controller has connected. |

## A UniFi WiFi Client device's settings

| Setting | What it does |
|---|---|
| **UniFi Controller** | The controller the device connects through. |
| **Client** | The device to follow, chosen from those connected to your network at that moment. |
| **Geofence switch (optional)** | An on and off switch the phone's own location turns on when it arrives home and off when it leaves. Leave it at none to use Wi-Fi alone. [How it works](how-it-works.md) explains how to set one up. |

## Geofence Switch

It has no settings.
