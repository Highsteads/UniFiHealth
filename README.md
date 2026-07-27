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
a channel, 2.4 GHz over its utilisation threshold.*

## Device types

| Device | What it gives you |
| --- | --- |
| **UniFi Controller** | Connection status, version, AP/client counts, WLAN health, worst-AP utilisation, worst-client satisfaction, total audit issues. **Plus (v0.5.0):** Internet/WAN health — the controller's own ISP speedtest (down/up Mbps + when it last ran), internet latency, drops and public WAN IP, and the gateway's CPU/memory; client roll-ups — wired vs wireless, the Wi-Fi-generation mix (Wi-Fi 7/6/5/4/legacy) and a count of slow legacy a/b/g clients, plus the least-happy clients by satisfaction; a count of APs with firmware updates pending; and the RF neighbourhood — how many neighbouring networks are visible and how they're spread across the 2.4 GHz channels. |
| **UniFi Access Point** | Per band (2.4/5/6 GHz): channel, width, utilisation and client count — plus TX power and satisfaction on 2.4 and 5 GHz only. Uptime + reboot detection, uplink type, and an **audit** (`configOK` + `auditFlags`). Auto-discovered — including Wi-Fi consoles such as the **UDR / UDM** that broadcast their own Wi-Fi. **Plus (v0.5.0):** firmware version + an update-available flag, CPU/memory/load, the wired uplink speed against what the AP is capable of (so a 2.5 GbE AP stuck at 1 Gb is flagged) with the switch and port it's plugged into, live throughput, and how many neighbouring networks share its 2.4 GHz channel. |
| **UniFi WiFi Client** | Opt-in, for the devices you care about (e.g. smart plugs): signal, satisfaction, connected AP, SSID, vendor, online/offline. As of **v0.3.0** every tracked client also gets **presence** — a debounced `home`/`away` state designed for phones. |
| **Geofence Switch** (v0.6.1) | A plain on/off switch with nothing to configure. On means inside the home zone. Flip it from Apple Home — via HomeKitLink-Siri, with *when I leave* and *when I arrive* automations — then name it in a WiFi Client's **Geofence switch** setting, and the client fuses the two witnesses. Create one per phone you track. |

## Features

- **Auto-setup** — on startup it creates a "UniFi Health" device folder, auto-creates
  the Controller (when credentials are present) and a device for every access point,
  all filed into the folder. Delete the lot, restart, and it rebuilds itself. The AP
  list stays in step with the controller: new access points are added automatically,
  and one that's forgotten/un-adopted is removed automatically too — unless a trigger,
  schedule or control page still uses it, in which case it's kept and flagged rather
  than deleted. Both behaviours are on by default and can be turned off in the plugin
  config (*Auto-create / Auto-remove AP devices*).
- **Cause-level Pushover alerts** (opt-in) — pages you *once* with the actual cause
  (an AP reboot, or the controller going unreachable) instead of the flood of
  "device offline" alerts the dropped clients would otherwise generate.
- **Config audit** — on 2.4 GHz it flags 40 MHz width, TX power = High, min-RSSI
  off, a channel shared by more than two APs, and utilisation over your threshold.
  On 5 GHz it flags TX power = High. 6 GHz isn't audited. Run it on demand from the
  plugin menu, or read the result off the device states.
- **Internet, hardware & RF insight (v0.5.0)** — surfaces a lot of what the controller
  already knows but never used to leave the controller: your ISP speedtest result and
  internet latency, which APs need firmware, an AP whose 2.5 GbE uplink has negotiated
  down to 1 Gb, the one ancient legacy client dragging down 2.4 GHz, and how crowded each
  Wi-Fi channel is with the neighbours. All as ordinary device states you can chart,
  trigger on, or show on a dashboard.
- **Triggers** — AP rebooted, config issue found, controller unreachable, WLAN
  degraded. Numeric thresholds (utilisation, satisfaction) use Indigo's built-in
  device-state triggers on the numeric states.
- **AP actions** — restart an AP, locate it (flash the LED), via `cmd/devmgr`.
- **Debounced offline detection** — an access point only flips to *Offline* (and fires
  any "AP down" automation you've built) once it's been off the controller continuously
  for the *AP offline grace* (default 3 minutes), so the routine reboots of a firmware
  upgrade don't trigger a flurry of false alarms — while a genuine outage still alerts.
  During the grace window the device stays up but its state shows the live reason
  (e.g. *Upgrading*). Set the grace to 0 in the plugin config to alert immediately.
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
  address your controller actually shows for the phone (or set the phone's Private
  Wi-Fi Address to Off for your home network and track the hardware address).
- **Geofence fusion (v0.6.0, v0.6.1)** — WiFi alone can only notice an *absence*,
  which is why `away` waits out the quiet period. A WiFi Client device can pair an
  optional **geofence switch** — a switch flipped by the phone's own location.
  Since v0.6.1 the plugin ships its own **Geofence Switch** device type for the job:
  add one, expose it to Apple Home (e.g. via HomeKitLink-Siri), and build the two
  Home-app automations, *when I leave home → off* and *when I arrive → on*. Any
  other on/off Indigo device still works if you already have one you'd rather use.
  The two witnesses then fuse: **home when either says home** (a phone napping off
  WiFi stays home while the geofence vouches for it, and a GPS wobble can't fake
  `away` while the phone is demonstrably on your WiFi), and **away the moment the
  geofence says gone** and the phone isn't associated — seconds, not the 10-minute
  wait. The plugin reacts to the switch flip immediately (no waiting for the next
  poll), a new `presenceSource` state says which witness produced the verdict
  (`wifi` / `geofence` / `wifi+geofence`), and with no switch paired the behaviour
  is exactly the WiFi-only logic above. The decision table lives in
  `presence_fusion.py` with contract tests in `test_fusion.py`.
- **A bad poll no longer stops the plugin (v0.6.2)** — a controller that answered
  slowly could let a timeout escape the poll and kill the loop, so the plugin went
  quiet without saying why. The whole cycle is wrapped now: one failure warns and
  skips that cycle, a continuing outage stays quiet at debug level rather than
  filling the log, and recovery reports how many cycles were missed.
- **Cleaner logs (v0.6.3)** — the shared `plugin_utils.py` moved to v1.3, which
  stops the `[HH:MM:SS.mmm]` stamp being added twice if the filter is installed
  more than once, and keeps a malformed log call's arguments visible instead of
  dropping them.

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

## Acknowledgements

The controller-type detection, dual-URL auth and cookie/CSRF handling
are adapted from [FlyingDiver's MIT-licensed Indigo-miniUniFi](https://github.com/FlyingDiver/Indigo-miniUniFi),
and the AP-command and broad-controller-support ideas are informed by
[kw123's MIT-licensed unifi plugin](https://github.com/kw123/unifi). With thanks to both.

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
