---
title: When something goes wrong
nav_order: 8
---

# When something goes wrong

Each section starts with what you see, then what it means and what to do.

## No controller device appears

The plugin only creates the controller device by itself when the settings file holds all three of the controller's details. The Event Log says **No UniFi Controller yet** when it starts without them.

- Either add the three lines to `IndigoSecrets.py`, as [Settings](settings.md) shows, and choose **Plugins → UniFi Health → Reload**,
- or create the device yourself with **New Device → UniFi Health → UniFi Controller**.

## The controller device will not save

The dialog needs an address, a username and a password, from its own boxes or the settings file. Fill in the boxes it marks, or tick **Save without configuring** to save it and come back later.

## The controller shows "Unreachable"

The plugin cannot sign in to the controller, or the controller has not answered three checks in a row. The Event Log has a warning at each check that says why.

- **"controller unreachable at ..."** — nothing answered at that address and port. Check the address in **Controller IP / Hostname** or the settings file, and check **Port** — 443 for a UniFi console, usually 8443 for the UniFi Network application on a computer or an older Cloud Key.
- **"login failed"** — the controller turned the username and password away. Check them, and check the account is a local account on the controller, not a Ubiquiti cloud account, and does not use two-step verification.
- **"no credentials"** — the plugin has no address, username or password to use. Fill them in on the controller device or in the settings file.

If you have just changed `IndigoSecrets.py`, choose **Plugins → UniFi Health → Reload** so the plugin reads it again.

## The log says "no answer from the controller"

The controller was slow to answer or had gone away for a moment. The plugin tries again at the next check, and the devices keep what they last showed. When it answers again, the log says so and how many checks were missed. If three checks in a row fail, the controller shows **Unreachable** and the section above applies.

## No access point devices appear

- Check the controller device shows **Connected** first.
- Check **Auto-create AP devices** is ticked in **Plugins → UniFi Health → Configure**, or choose **Plugins → UniFi Health → Discover / Create AP Devices**.
- Only access points are made into devices. Switches and a gateway without Wi-Fi are left out on purpose.

## An access point shows "Upgrading…" or another word with dots after it

The access point is not connected to the controller at the moment, and the word is what the controller says it is doing. The device stays on while this lasts up to the **AP offline grace** time, three minutes to start with, because firmware updates and restarts cause short gaps. If it lasts longer, the device goes off and shows **Offline**.

## An access point shows "Removed from controller (still referenced)"

You have removed this access point from UniFi, but a trigger, schedule, action group or control page still uses its Indigo device, so the plugin has not deleted it. The Event Log names what uses it. Change those to use another device, then delete this one yourself.

## I renamed an access point in Indigo and the name changed back

The plugin keeps each access point's name in step with its name in UniFi. Rename it in UniFi instead, and the Indigo device follows at the next check.

## The Audit Flags say "2.4GHz min-RSSI off" on every access point

Turn on the minimum signal level for 2.4 GHz on each access point, in the UniFi app or with **Apply Minimum RSSI**. On UniFi Network 10 and later the plugin does not check this, because there is no such setting. If the flag still shows there, check **Controller Version** on the controller device has a version in it.

## Apply Minimum RSSI says the controller has no minimum RSSI on each access point

Your controller runs UniFi Network 10 or later, which moved this setting off the access points. The plugin sends nothing. [The plugin menu](plugin-menu.md) explains.

## A phone I want to follow is not in the Client list

The list only shows devices connected to your network at that moment. Wake the phone, make sure it is on your Wi-Fi, then open the dialog again.

## A phone stays "away", or shows as a new device

An iPhone can show itself to each network with a made-up hardware address that changes from time to time. On the phone, open **Settings → Wi-Fi**, tap your home network, set **Private Wi-Fi Address** to **Off** or **Fixed**, and then choose the phone again in its UniFi WiFi Client device, because its address will have changed.

## A phone takes ten minutes to show "away"

That is the **Presence: away after (minutes)** setting at work. You can shorten it, down to two minutes, but phones drop off Wi-Fi to save battery, so a short setting will mark people away while they are at home. For a quick and reliable away, add a geofence switch, as [How it works](how-it-works.md) explains.

## Pushover messages do not arrive

- Check **Pushover WiFi alerts** is ticked in **Plugins → UniFi Health → Configure**.
- Check the Pushover plugin is installed and turned on. The Event Log says **Pushover plugin not available** if it is not.
- The plugin sends at most one message for the same access point, or for the controller, in any half hour.

## The log says "could not set the SQL Logger ignore list"

The plugin could not add its busiest states to SQL Logger's skip list for that device. Everything else works as normal, and SQL Logger simply keeps a history of those states as well.

## Still stuck?

Choose **Plugins → UniFi Health → Test Connection**, copy the lines it writes to the Event Log, and post them on the [Indigo forum](https://forums.indigodomo.com) with a description of what you see. You can also [raise an issue on GitHub](https://github.com/Highsteads/UniFiHealth/issues).
