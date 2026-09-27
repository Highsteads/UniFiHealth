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

The plugin cannot sign in to the controller. The Event Log has a warning at each check that says why.

- **"controller unreachable at ..."** — nothing answered at that address and port. Check the address in **Controller IP / Hostname** or the settings file, and check **Port** — 443 for a UniFi console, usually 8443 for the UniFi Network application on a computer or an older Cloud Key.
- **"login failed"** — the controller turned the username and password away. Check them, and check the account is a local account on the controller, not a Ubiquiti cloud account, and does not use two-step verification.
- **"no credentials"** — the plugin has no address, username or password to use. Fill them in on the controller device or in the settings file.

If you have just changed `IndigoSecrets.py`, choose **Plugins → UniFi Health → Reload** so the plugin reads it again.

## The log says "controller poll failed (will keep retrying quietly)"

A check went wrong part way through, most often because the controller was slow to answer or had gone away for a moment. The plugin keeps trying at each check without filling the log, and the devices keep what they last showed. When a check works again, the log says **controller poll recovered** and how many were missed. If it never recovers, check the controller is running and reachable from the Mac.

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

The settings check reads a minimum signal level setting that UniFi Network 10 no longer uses for 2.4 GHz, so on that version there may be nothing you can change to clear it. The other flags are unaffected.

## Apply Minimum RSSI says every access point failed

On recent versions of UniFi Network the controller does not accept this change, and 2.4 GHz is always refused. [The plugin menu](plugin-menu.md) explains. Nothing on your access points has changed.

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
