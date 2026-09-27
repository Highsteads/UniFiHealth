---
title: Your devices
nav_order: 3
---

# Your devices

The plugin has four kinds of device. It creates the controller and access point devices for you, and you add the other two for the things you want to follow. This page explains what each one shows.

A few words come up again and again:

- **Channel utilisation** is how much of the time a Wi-Fi channel is busy, as a percentage. The busier it is, the longer each device waits its turn.
- **Satisfaction** is UniFi's own score for how well a device's connection is working, where 100 is perfect.
- **Signal** is measured in dBm, a negative number where closer to zero is stronger. Around -50 is a strong signal, and below about -75 a device will struggle.

The states below are listed by the names Indigo shows when you build a trigger or a control page.

## UniFi Controller

One for your controller. The device list shows **Connected**, or **Unreachable** when the plugin cannot sign in to it or it turns a request away.

### The whole network

| Shown as | What it means |
|---|---|
| **Controller Status** | **Connected** or **Unreachable**. This is what the device list shows. |
| **Is UniFi OS** | Ticked for a UniFi console such as a Dream Machine or Dream Router, unticked for the older UniFi Network application. |
| **Controller Version** | The version of the UniFi software on the controller. |
| **WLAN Health** | UniFi's own verdict on your Wi-Fi as a whole — **ok** when all is well. |
| **Number of APs** | How many access points the controller has. |
| **Number of Clients** | How many devices are connected, wired and wireless together. |
| **Worst AP Utilisation %** | The busiest channel on any band of any access point. |
| **Worst Client Satisfaction** | The lowest satisfaction score of any connected device. |
| **Config Audit Issue Count** | How many problems the settings check found across all your access points. [How it works](how-it-works.md) lists what it checks. |

### Your internet connection

| Shown as | What it means |
|---|---|
| **WAN/Internet Status** | UniFi's verdict on your internet connection — **ok** when it is working. |
| **Public WAN IP** | The address the rest of the internet sees your home as. |
| **Internet Latency (ms)** | How long, in thousandths of a second, it takes to reach the internet and back. |
| **Internet Drops** | How many times UniFi has counted the internet dropping. |
| **Speedtest Down (Mbps)** and **Speedtest Up (Mbps)** | The result of the last internet speed test your UniFi gateway ran, in megabits a second. The gateway only runs these if speed tests are turned on in UniFi. |
| **Speedtest Age (hours)** | How long ago that speed test ran. It shows -1 if there has never been one. |
| **Gateway CPU %** and **Gateway Memory %** | How hard your UniFi gateway, the box that joins your home to the internet, is working. |

### Connected devices

| Shown as | What it means |
|---|---|
| **Wired Clients** and **Wireless Clients** | How many devices are connected by cable, and by Wi-Fi. |
| **Legacy (a/b/g) Clients** | How many Wi-Fi devices use the oldest standards, 802.11a, b or g. They take far longer to send the same data, which leaves less time on the channel for everything else. |
| **Wi-Fi Generation Mix (JSON)** | How many devices use Wi-Fi 7, 6, 5, 4 and the older standards, as a short list of text for a dashboard or script. |
| **Worst Clients (JSON)** | The six Wi-Fi devices with the lowest satisfaction, with their signal and access point, as a short list of text. |
| **APs Needing Firmware Update** | How many access points have a firmware update waiting. |

### The neighbours

| Shown as | What it means |
|---|---|
| **Neighbour APs Visible** | How many Wi-Fi access points your access points can hear that are not yours — usually the neighbours'. |
| **RF Neighbourhood (JSON)** | How those neighbouring access points are spread across the 2.4 GHz channels, and how many are on 5 GHz, as a short list of text. |

## UniFi Access Point

One for each access point, created by the plugin. Its name is **UniFi AP** followed by the access point's name in UniFi, and it follows that name: if you rename the access point in UniFi, the Indigo device is renamed to match, and if you rename the Indigo device yourself, the plugin puts the UniFi name back at the next check.

The device list shows a short summary of the 2.4 GHz radio, such as `2.4: ch6 20MHz 35%` — the channel, its width and how busy it is — followed by a warning sign and a number when the settings check has found problems on that access point.

The device is on while the access point is connected to the controller, and goes off, showing **Offline**, once it has been away for longer than the **AP offline grace** setting — three minutes to start with. While it is within that grace time, for a restart or a firmware update, the summary shows what the controller says it is doing, such as **Upgrading…**, and the device stays on.

### The access point itself

| Shown as | What it means |
|---|---|
| **Summary** | The line the device list shows, described above. |
| **Model** | The model, such as **U6-LR** or **UAP-AC-Lite**. |
| **Model code (raw UniFi)** | The short code UniFi uses for the model. Some are misleading — UniFi's code for the UAP-AC-Lite is **U7LT**, which has nothing to do with Wi-Fi 7 — so **Model** is the one to read. |
| **Device State** | What the controller says the access point is doing: **Connected**, **Upgrading**, **Provisioning**, **Offline** and so on. |
| **Uptime (s)** | How long since the access point last started, in seconds. |
| **Recently Rebooted** | Ticked for one check after the plugin sees the access point has restarted. |
| **Total Clients** | How many devices are connected to it. |
| **Firmware Version** and **Firmware Update Available** | The firmware it runs, and whether UniFi has a newer one for it. |
| **CPU %**, **Memory %** and **Load Average (1m)** | How hard the access point is working. |
| **Throughput (kB/s)** | How much data it is passing, in kilobytes a second. |

### Its network cable

| Shown as | What it means |
|---|---|
| **Uplink Type** | How it connects to the rest of your network — **wire** for a cable, or **wireless** for an access point that links over Wi-Fi. |
| **Uplink Speed (Mbps)** | The speed its cable is running at. |
| **Uplink Max Speed (Mbps)** | The fastest its network socket can run. |
| **Uplink Below Capability** | Ticked when the cable is running slower than the access point could manage — a 2.5 gigabit access point stuck at 1 gigabit, for instance. A tired cable or a slower switch port is the usual cause. |
| **Uplink Switch** and **Uplink Switch Port** | The switch and port it is plugged into. |

### Each band

The same states appear for 2.4 GHz, 5 GHz and 6 GHz, where the access point has that band.

| Shown as | What it means |
|---|---|
| **Channel** | The channel the radio is using now. |
| **Width (MHz)** | How wide the channel is. |
| **Utilisation %** | How busy the channel is. |
| **Clients** | How many devices are connected on that band. |
| **TX Power** | The transmit power setting, such as **high**, **medium** or **auto**. 2.4 and 5 GHz only. |
| **Satisfaction** | The satisfaction of the devices on that band. 2.4 and 5 GHz only. |
| **2.4GHz Min-RSSI Enabled** | Whether the 2.4 GHz radio is set to drop devices whose signal falls below a set level. |
| **Co-channel Neighbour APs (2.4GHz)** | How many of the neighbours' access points are on the same 2.4 GHz channel as this one. |

### The settings check

| Shown as | What it means |
|---|---|
| **Config OK (audit)** | Ticked when the settings check found nothing wrong with this access point. |
| **Audit Flags** | The problems it found, such as `2.4GHz width 40MHz (use 20)` or `2.4GHz ch6 shared by 3 APs`. Empty when there are none. |
| **Connected Clients (JSON)** | The Wi-Fi devices on this access point, with their band, signal and satisfaction, as a short list of text. My Dashboards plugin shows it as a list. |

## UniFi WiFi Client

One for each device you choose to follow, such as a phone or a smart plug. You add these yourself — [Getting started](getting-started.md) shows how.

The device is on while the device is connected to your network. The device list shows a summary such as `HOME · -48dBm sat=98 @ Hall`, or `HOME (offline 4m)` while a phone that has just dropped off Wi-Fi is still counted as home, or `AWAY 25m`.

| Shown as | What it means |
|---|---|
| **Summary** | The line the device list shows, described above. |
| **Presence (home/away)** | **home** or **away**. It turns to home the moment the device connects, and to away only after it has been off your network for the **Presence: away after (minutes)** setting — ten minutes to start with — because phones drop off Wi-Fi for short spells all day. With a geofence switch paired, away can come much sooner, as [How it works](how-it-works.md) explains. |
| **Presence Changed At** | When it last changed between home and away, such as `14:05 27-Sep`. |
| **Presence Source** | What decided it: **wifi**, **geofence**, or **wifi+geofence** when both agree the device is home. |
| **Minutes Since Seen** | How long since the device was last connected. 0 while it is connected. |
| **Seconds Offline** | The same in seconds. |
| **Last Seen (epoch)** | When the device was last seen, as a count of seconds, for scripts. |
| **Signal (dBm)** | Its signal strength. |
| **Satisfaction** | Its satisfaction score. |
| **Connected AP** | The access point it is using. |
| **SSID** | The name of the Wi-Fi network it is on. |
| **Channel** | The channel it is using. |
| **Wired** | Ticked if it is connected by cable. |
| **Vendor (MAC OUI)** | The maker, as worked out from its hardware address. |

While the device is away, the signal, satisfaction and access point states keep the values they had when it was last seen.

## Geofence Switch

A plain on and off switch with nothing to set up. On means the phone is inside your home area. It does nothing by itself — its only job is to be switched by the phone's own location, through Apple Home, and read by a UniFi WiFi Client device. [How it works](how-it-works.md) explains how to set one up. Make one for each phone you follow.
