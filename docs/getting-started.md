---
title: Getting started
nav_order: 2
---

# Getting started

This takes about ten minutes, and you only do it once.

## What you need

- Indigo 2022.1 or later, on a Mac on the same home network as your UniFi controller.
- A UniFi controller — a UniFi console such as a Dream Machine or Dream Router, a Cloud Key, or the UniFi Network application running on a computer.
- The controller's **network address** — the four numbers separated by dots, such as `192.168.1.1`, that you type into a web browser to reach it. A name such as `unifi.local` works too.
- A **local account** on the controller for the plugin to sign in with — a username and password kept on the controller itself, not your Ubiquiti cloud account. It must not use two-step verification, because the plugin cannot type in a code.

The plugin reads the controller's default site, which is the only site most homes have.

## 1. Install the plugin

1. Go to the [Releases page](https://github.com/Highsteads/UniFiHealth/releases/latest) and download `UniFiHealth.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `UniFiHealth.indigoPlugin`
3. Double-click `UniFiHealth.indigoPlugin` — Indigo will install it automatically

Indigo asks whether to enable the plugin. Say yes.

## 2. Tell the plugin about your controller

There are two ways. Use whichever suits you.

### The quickest way — a settings file

If you keep the controller's details in a file called `IndigoSecrets.py`, the plugin creates the controller device by itself every time it starts and finds none.

1. In Finder, open the folder `/Library/Application Support/Perceptive Automation/`.
2. If there is no file called `IndigoSecrets.py` there, create a plain text file with that name. If one is there already from another of my plugins, open it.
3. Add these three lines, with your own details between the quotes:

```python
UNIFI_HOST     = "192.168.1.1"
UNIFI_USERNAME = "your-local-unifi-user"
UNIFI_PASSWORD = "your-password"
```

4. Save the file, then choose **Plugins → UniFi Health → Reload** so the plugin reads it.

A device called **UniFi Controller** appears in a new **UniFi Health** folder in your device list.

### The other way — a device

1. In Indigo, choose **New Device**.
2. Set **Type** to **UniFi Health**, then pick **UniFi Controller**.
3. Fill in **Controller IP / Hostname**, **Username** and **Password**.
4. Leave **Port** at 443 for a UniFi console. For a UniFi Network application on a computer, or an older Cloud Key, use the port you reach it on, usually 8443.
5. Click **Save**.

The dialog will not save until it has an address, a username and a password, from the file or the boxes. If you do not have them to hand, tick **Save without configuring**, and the controller device waits until you come back and fill them in.

## 3. Check it has connected

Within a minute or so:

- The controller device shows **Connected** in the device list.
- A device appears for every access point, named **UniFi AP** followed by the name it has in UniFi, all in the **UniFi Health** folder. A console that has its own Wi-Fi, such as a Dream Router, counts as an access point and gets a device too.

To be sure, choose **Plugins → UniFi Health → Test Connection**. The Event Log shows a line saying the connection is OK, with the number of access points and connected devices it found.

If the controller shows **Unreachable**, the [When something goes wrong](troubleshooting.md) page goes through the usual causes.

## 4. Look at the settings

Open **Plugins → UniFi Health → Configure**. Everything works as it comes, so you only need to change something if you want to. The two things most people look at are:

- **Pushover WiFi alerts** — tick it if you use the Pushover plugin and want a message on your phone when an access point restarts or the controller stops answering.
- **Presence: away after (minutes)** — how long a phone must be off your Wi-Fi before it counts as away. It starts at 10.

Every setting is explained on the [Settings](settings.md) page.

## 5. Track a phone or other device (optional)

To know whether a phone is at home, or to watch a device that matters to you, such as a smart plug:

1. Make sure the device is connected to your Wi-Fi right now, because the list in the next step only shows connected devices.
2. Choose **New Device**, set **Type** to **UniFi Health**, and pick **UniFi WiFi Client**.
3. Choose your controller in **UniFi Controller**, then the device in **Client**.
4. Leave **Geofence switch (optional)** at none for now. The [How it works](how-it-works.md) page explains how to add one.
5. Click **Save**.

The new device shows **HOME**, with its signal and the access point it is using.

If it is an iPhone, open **Settings → Wi-Fi** on the phone, tap your home network, and set **Private Wi-Fi Address** to **Off** or **Fixed**, not **Rotating**. The plugin knows a device by its hardware address — the number it shows itself to the network with — and a rotating one makes the phone look like a new device each time it changes.
