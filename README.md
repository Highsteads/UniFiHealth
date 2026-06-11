# UniFi Health

An Indigo plugin that monitors **UniFi WiFi health** — not just whether things are
online, but *how well the radios are performing* — and runs a **config audit** that
flags where a network is mis-set or an access point is over-powered.

Works with UniFi OS controllers (UDM / UDR / UDM-Pro) and legacy software
controllers / Cloud Keys. Read-mostly: it never changes radio configuration, with
the exception of opt-in AP commands (restart / locate) via the `cmd/devmgr` endpoint.

## Why this exists

The existing UniFi plugins (FlyingDiver's miniUniFi, kw123's unifi — both excellent)
focus on **presence and online/offline** status. UniFi Health adds the layer they
don't: per-AP channel / width / TX-power / **utilisation** / **satisfaction**,
reboot detection, and a best-practice **audit** so you can see at a glance where the
problem is — e.g. *2.4 GHz running at 40 MHz width, TX power on High, four APs sharing
a channel, a band over its utilisation threshold.*

## Device types

| Device | What it gives you |
| --- | --- |
| **UniFi Controller** | Connection status, version, AP/client counts, WLAN health, worst-AP utilisation, worst-client satisfaction, total audit issues. |
| **UniFi Access Point** | Per band (2.4/5/6 GHz): channel, width, TX power, utilisation, satisfaction, client count; uptime + reboot detection; uplink type; and an **audit** (`configOK` + `auditFlags`). Auto-discovered. |
| **UniFi WiFi Client** | Opt-in, for the devices you care about (e.g. smart plugs): signal, satisfaction, connected AP, SSID, vendor, online/offline. As of **v0.3.0** every tracked client also gets **presence** — a debounced `home`/`away` state designed for phones. |

## Features

- **Auto-setup** — on startup it creates a "UniFi Health" device folder, auto-creates
  the Controller (when credentials are present) and a device for every access point,
  all filed into the folder. Delete the lot, restart, and it rebuilds itself.
- **Cause-level Pushover alerts** (opt-in) — pages you *once* with the actual cause
  (an AP reboot, or the controller going unreachable) instead of the flood of
  "device offline" alerts the dropped clients would otherwise generate.
- **Config audit** — flags 2.4 GHz at 40 MHz width, TX power = High, min-RSSI off,
  channel over-subscription, and bands over a utilisation threshold. Run on demand
  from the plugin menu, or read it off the device states.
- **Triggers** — AP rebooted, config issue found, controller unreachable, WLAN
  degraded. Numeric thresholds (utilisation, satisfaction) use Indigo's built-in
  device-state triggers on the numeric states.
- **AP actions** — restart an AP, locate it (flash the LED), via `cmd/devmgr`.
- **Phone presence (v0.3.0)** — track a phone as a WiFi Client device and it gains a
  `presence` state with proper debounce: connecting marks it `home` instantly, but it
  only flips to `away` after a configurable quiet period (default 10 minutes), because
  phones nap off WiFi constantly and raw connected/disconnected would flap all day.
  Two new trigger events — *client arrived* and *client left* — fire on the debounced
  transitions, `minutesSinceSeen` and a persisted last-seen survive plugin restarts,
  and the away delay lives in the plugin config. One honest caveat: iPhones use a
  private (randomised) WiFi address per network — fine for tracking as long as
  "Rotate WiFi Address" stays off for your home network in iOS settings, but if iOS
  rotates the address the device will look like it never came back. Track by the
  address your controller actually shows for the phone.

## Credentials

Credentials are read from `IndigoSecrets.py` first:

```python
UNIFI_HOST     = "192.168.1.1"
UNIFI_USERNAME = "your-local-unifi-user"
UNIFI_PASSWORD = "your-password"
```

To create `IndigoSecrets.py`, copy `IndigoSecrets_example.py` (shipped with the CliveS
plugins) into `/Library/Application Support/Perceptive Automation/` and rename the copy to
`IndigoSecrets.py`, then fill in your values. If you would rather not use `IndigoSecrets.py`
at all, fill the same values into the plugin's
Configure dialog (or the Controller device). A **local-only UniFi account without
2FA** is recommended — a Viewer-role account is enough for everything except the
optional AP commands.

## Installation

1. Go to the [Releases](../../releases) page and download `UniFiHealth.indigoPlugin.zip`.
2. Unzip it — you'll get `UniFiHealth.indigoPlugin`.
3. Double-click `UniFiHealth.indigoPlugin` — Indigo installs it automatically.

With your credentials in `IndigoSecrets.py` (or the plugin's Configure dialog), the
plugin **creates the Controller and all the AP devices for you** on startup, in a
"UniFi Health" folder. Add **UniFi WiFi Client** devices for any specific clients
(e.g. smart plugs) you want to watch closely, and tick **Pushover WiFi alerts** in
Configure if you want the cause-level alerts.

## Credits & licence

MIT licensed. The controller-type detection, dual-URL auth and cookie/CSRF handling
are adapted from [FlyingDiver's MIT-licensed Indigo-miniUniFi](https://github.com/FlyingDiver/Indigo-miniUniFi),
and the AP-command and broad-controller-support ideas are informed by
[kw123's MIT-licensed unifi plugin](https://github.com/kw123/unifi). With thanks to both.
