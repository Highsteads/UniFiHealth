# UniFi Health for Indigo

**See how well your UniFi Wi-Fi is working from Indigo, and which settings are holding it back.**

**Version:** 0.8.1 | **Author:** CliveS & Claude | **Needs:** Indigo 2022.1 or later and a UniFi controller

**[Read the full guide](https://highsteads.github.io/UniFiHealth/)** — setting up, what everything means, and what to do when something goes wrong.

---

## What it does

This plugin lets [Indigo](https://www.indigodomo.com) keep an eye on a UniFi Wi-Fi network — not just whether each access point is up, but how well its radios are working. It talks straight to your UniFi controller over your home network, signing in with a local account, so no Ubiquiti cloud account is involved.

- **Sets itself up.** It creates a device for your controller and one for every access point, in a **UniFi Health** folder, and keeps the list in step as you add or remove access points.
- **Shows how each access point is doing** on 2.4, 5 and 6 GHz — its channel, how wide and how busy the channel is, how many devices are connected, and UniFi's own score for how well those connections are working.
- **Checks your Wi-Fi settings** for the common mistakes, such as a 40 MHz wide channel on 2.4 GHz, a radio set to full power, or a 2.4 GHz channel shared by more than two of your access points, and says which access point has which problem.
- **Notices when an access point restarts or drops off**, waiting out the short gaps of a firmware update so they do not raise false alarms.
- **Shows your internet connection's health** as UniFi sees it — the gateway's own speed test result, the delay to the internet, dropouts and your public internet address.
- **Spots slow spots** — an access point whose network cable runs slower than it could, devices on the oldest Wi-Fi standards, firmware updates waiting, and how many of the neighbours' networks share each channel.
- **Tells you who is home.** A phone you choose has a home or away state, and with Apple Home passing on the phone's location it can say "away" within seconds of leaving.
- **Sends one Pushover message with the cause** when an access point restarts or the controller shows **Unreachable**, if you use the Pushover plugin.
- **Restarts an access point, or flashes its light** so you can find it, from an Indigo action.

## What it works with

The UniFi Network controller, on a UniFi console such as a Dream Machine or Dream Router, on a Cloud Key, or running on a computer. A console with its own Wi-Fi, such as the Dream Router, counts as an access point and gets a device of its own. I run it against a Dream Router.

## Installing

1. Go to the [Releases page](https://github.com/Highsteads/UniFiHealth/releases/latest) and download `UniFiHealth.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `UniFiHealth.indigoPlugin`
3. Double-click `UniFiHealth.indigoPlugin` — Indigo will install it automatically

## Setting it up

1. Make a local account on your UniFi controller for the plugin, without two-step verification.
2. Create a **New Device**, choose **UniFi Health** and **UniFi Controller**, and fill in the controller's network address — the four numbers, such as `192.168.1.1`, that you type into a browser to reach it — with the account's username and password. You can keep these in a settings file instead, and the guide shows how.
3. Within a minute the controller shows **Connected**, and a device appears for each access point in the **UniFi Health** folder.
4. To follow a phone, create a **UniFi WiFi Client** device and pick the phone from the list.

The [full guide](https://highsteads.github.io/UniFiHealth/) goes through each step, explains every setting, and covers what to do if something does not work.

## What's new

**v0.8.1** — Far fewer "busy" lines in the Event Log. An access point's band is now judged on how busy it has been over the last 15 minutes, not on one reading, and has to calm down to 10 points below your warning level before it can warn again. A busy 2.4 GHz radio jumps up and down from one minute to the next, so the old rule warned hundreds of times a day for the same thing.

**v0.8.0** — The **Config Audit Found an Issue** and **An AP Band Went Over the Utilisation Threshold** triggers now run, once for each new problem. The **Log level** setting now works. A controller that stops answering now shows **Unreachable** after three failed checks, with its trigger and Pushover message. On UniFi Network 10 the settings check no longer reports a minimum signal level you cannot change, and **Apply Minimum RSSI** says plainly that the controller cannot take it.

**v0.7.4** — The access points and the UniFi WiFi Client devices stop filling SQL Logger's history. Uptime, each access point's summary and list of connected devices, and each client's last-seen time changed at most checks and added about 16,000 rows a day. The plugin now tells SQL Logger to skip them. Everything else is kept exactly as before, and existing history is untouched.

Every version is listed in the [version history](https://highsteads.github.io/UniFiHealth/changelog.html).

## Acknowledgements

The way the plugin recognises the type of controller, signs in and keeps its session is adapted from [FlyingDiver's Indigo-miniUniFi](https://github.com/FlyingDiver/Indigo-miniUniFi), and the access point commands and support for a wide range of controllers were informed by [kw123's unifi plugin](https://github.com/kw123/unifi). Both are MIT-licensed. With thanks to both.

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
