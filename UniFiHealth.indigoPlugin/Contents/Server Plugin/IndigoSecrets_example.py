#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    IndigoSecrets_example.py
# Description: Template for the keys UniFi Health reads from IndigoSecrets.py.
#              Copy the lines you need into
#                  /Library/Application Support/Perceptive Automation/IndigoSecrets.py
#              (create that file if you have none, naming it IndigoSecrets.py,
#              not IndigoSecrets_example.py). Never commit the real file.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0
#
# Every key is optional. A value here wins over the same field on the UniFi
# Controller device; leave a key out, or blank, to use the device field.
# The port and "Verify SSL" are set on the controller device, not here.
# After editing IndigoSecrets.py choose Plugins -> UniFi Health -> Reload.

# UniFi controller (a local account, without two-step verification)
UNIFI_HOST     = ""      # e.g. "192.168.1.1"
UNIFI_USERNAME = ""
UNIFI_PASSWORD = ""

# Pushover (optional) - the user key the WiFi alerts go to
PUSHOVER_USER_TOKEN = ""
