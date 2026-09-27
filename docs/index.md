---
title: Home
nav_order: 1
---

# UniFi Health for Indigo

This plugin lets [Indigo](https://www.indigodomo.com) keep an eye on a UniFi Wi-Fi network — not just whether each access point is up, but how well its radios are working — and checks the Wi-Fi settings for the mistakes that most often make Wi-Fi worse.

It talks straight to your UniFi **controller**, the UniFi Network application that looks after your access points. That usually runs on a UniFi console such as a Dream Machine or Dream Router, and can also run on a Cloud Key or on a computer. The plugin signs in to it over your home network with a local account, so no Ubiquiti cloud account is involved. I run it against a UniFi Dream Router.

## What it does for you

- **Sets itself up.** It creates a device for your controller and one for every access point, all in a folder called **UniFi Health**, and keeps the list in step as you add or remove access points.
- **Shows how each access point is doing** on 2.4, 5 and 6 GHz — its channel, how wide the channel is, how busy it is, how many devices are connected, and how well those connections are working.
- **Checks your Wi-Fi settings** against a short list of good practice and tells you which access point has which problem, such as a 2.4 GHz channel shared by too many of your access points or a radio set to full power.
- **Notices when an access point restarts or drops off**, and waits out the short gaps of a firmware update so they do not raise false alarms.
- **Shows the health of your internet connection** as UniFi sees it — the result of your gateway's own speed test, the delay to the internet, dropouts, your public internet address, and how hard the gateway is working.
- **Spots slow spots** — an access point whose network cable is running below the speed it could manage, how many devices still use the oldest and slowest Wi-Fi standards, and how many of the neighbours' networks share each channel.
- **Tells you who is home.** Any device you choose, such as a phone, can have a home or away state, and a phone can combine Wi-Fi with its own location to say "away" within seconds of leaving.
- **Sends one Pushover message with the cause** — an access point restarted, or the controller stopped answering — if you use the Pushover plugin.
- **Restarts an access point, or flashes its light** so you can find it, from an Indigo action.

## Where to go next

| If you want to... | Read |
|---|---|
| Install the plugin and connect it to your controller | [Getting started](getting-started.md) |
| Know what each device shows in Indigo | [Your devices](devices.md) |
| Understand what the plugin does behind the scenes | [How it works](how-it-works.md) |
| Use its actions and triggers | [Actions and triggers](actions-and-triggers.md) |
| Know what every setting does | [Settings](settings.md) |
| Know what each item in the Plugins menu does | [The plugin menu](plugin-menu.md) |
| Sort out a problem | [When something goes wrong](troubleshooting.md) |
| See what changed in each version | [Version history](changelog.md) |

## Download

The latest version is always on the [Releases page](https://github.com/Highsteads/UniFiHealth/releases/latest).
