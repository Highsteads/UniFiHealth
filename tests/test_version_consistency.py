#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_version_consistency.py
# Description: Fails when the version signals disagree — the bundle's
#              Info.plist, the README header line, and the README changelog.
# Author:      CliveS & Claude Opus 5
# Date:        29-08-2026
# Version:     1.0
#
# Drift here is silent: nothing breaks when a README advertises a version the
# plugin no longer is, so it accumulates until somebody trips over it.
# ClaudeBridge's header sat six releases behind with its changelog correct the
# whole time, and Ecowitt and ShellyGen1 were each one release behind, all
# found on the same day in Aug-2026. ~/bin/estate-check sweeps for this daily;
# this file is the same check at push time, where CI can refuse it.
#
# Generic on purpose — it finds the bundle by glob, so it can be dropped into
# any Highsteads plugin repo unchanged.

import glob
import os
import plistlib
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(REPO, "README.md")

_PLISTS = sorted(glob.glob(os.path.join(REPO, "*.indigoPlugin", "Contents", "Info.plist")))
PLIST = _PLISTS[0] if len(_PLISTS) == 1 else None

pytestmark = pytest.mark.skipif(
    PLIST is None or not os.path.isfile(README),
    reason="not a single-bundle plugin repo with a README",
)


def _plugin_version():
    with open(PLIST, "rb") as fh:
        return plistlib.load(fh)["PluginVersion"]


def _readme():
    with open(README, encoding="utf-8") as fh:
        return fh.read()


def test_plugin_version_is_digits_and_dots():
    """Indigo's own docs call '1.0.5b2' invalid — a beta is a GitHub pre-release."""
    assert re.fullmatch(r"\d+(\.\d+)*", _plugin_version())


def test_readme_header_matches_info_plist():
    """The version a reader sees at the top of the page.

    NOT anchored to end-of-line: ShellyDirect writes
    "**Version:** 3.16.3 | **Author:** ..." on one line, and an end-anchored
    pattern matched nothing there — a check that skips silently is no check.
    Genuinely absent headers still skip, because a repo that never adopted the
    convention has nothing to drift.
    """
    match = re.search(r"\*\*Version:\*\*\s*v?(\d[\w.\-]*)", _readme())
    if not match:
        pytest.skip("README carries no **Version:** header line")
    assert match.group(1) == _plugin_version()


# The estate writes its release notes three ways, so all three are recognised
# rather than skipped past: "### v1.9.1 — ...", "**2.84.4** (date) — ..." and
# "**v2.7.1** — ...". Anchored to the line start so a version mentioned mid
# sentence cannot be mistaken for an entry.
_ENTRY_RE = re.compile(r"^(?:#+ +v?|\*\*v?)(\d+(?:\.\d+)+)", re.M)
_SECTION_RE = re.compile(
    r"^##+ *(?:Changelog|Version [Hh]istory|Release [Nn]otes|What.s [Nn]ew)\b", re.M)


def _sections(text):
    """Every release-notes section, each bounded at the next heading of the
    same level or higher.

    Plural, and bounded, because both mistakes produce a confident wrong
    answer: a README may carry a short "What's new" summary AND a full
    changelog table below it, and an unbounded read swept a "Historical bug
    fixes (v1.1 - v1.4)" section into a plugin that ships 5.78.1.
    """
    out = []
    for m in _SECTION_RE.finditer(text):
        level = len(m.group(0)) - len(m.group(0).lstrip("#"))
        rest = text[m.end():]
        nxt = re.search(r"^#{1,%d} +\S" % level, rest, re.M)
        out.append(rest[:nxt.start()] if nxt else rest)
    return out


def _documents(block, version):
    """True if this block presents `version` as its newest release."""
    entries = _ENTRY_RE.findall(block)
    if entries:
        return entries[0] == version
    # A table-style history has no stamped entries; a word-bounded substring
    # is all that shape supports.
    return re.search(r"(?<![\d.])v?" + re.escape(version) + r"(?![\d.])", block) is not None


def test_readme_release_notes_document_this_version():
    """Every bump appends an entry, so the newest one is the shipped version."""
    text, version = _readme(), _plugin_version()
    sections = _sections(text)
    if sections:
        assert any(_documents(b, version) for b in sections), (
            f"no release-notes section documents {version} as the newest release")
        return
    entries = _ENTRY_RE.findall(text)
    if not entries:
        pytest.skip("README carries no version-stamped release notes")
    assert entries[0] == version, (
        f"newest README entry is {entries[0]}, Info.plist says {version}")


def test_cfbundleversion_is_the_bundle_layout_not_the_release():
    """Jay: CFBundleVersion describes the bundle LAYOUT and stays at 1.0.0."""
    with open(PLIST, "rb") as fh:
        assert plistlib.load(fh).get("CFBundleVersion") == "1.0.0"


def test_required_info_plist_keys_are_present():
    """Six required keys, per Indigo's Developer's Guide.

    CFBundleURLTypes is the one repeatedly missed — it becomes the plugin's
    "About [PLUGIN]" menu item, and the Plugin Store expects it.
    """
    with open(PLIST, "rb") as fh:
        keys = set(plistlib.load(fh))
    required = {"PluginVersion", "ServerApiVersion", "CFBundleDisplayName",
                "CFBundleIdentifier", "CFBundleVersion", "CFBundleURLTypes"}
    assert required <= keys, f"missing: {sorted(required - keys)}"


def test_cfbundleurltypes_has_the_shape_indigo_accepts():
    """Presence is not enough — the SHAPE is what Indigo validates.

    CFBundleURLTypes must be an array of dicts keyed CFBundleURLName. Written as a
    bare string the plist still parses, still contains the key, and still passes a
    presence check — but Indigo refuses the bundle at install with

        InstallPlugin() caught exception: LowLevelBadParameterError

    which names neither the key nor the file. Cost a failed install on 01-09-2026.
    """
    with open(PLIST, "rb") as handle:
        plist = plistlib.load(handle)
    entry = plist.get("CFBundleURLTypes")
    assert isinstance(entry, list), (
        f"CFBundleURLTypes must be an array, got {type(entry).__name__}")
    assert entry, "CFBundleURLTypes must not be empty"
    for item in entry:
        assert isinstance(item, dict), (
            f"each CFBundleURLTypes entry must be a dict, got {type(item).__name__}")
        assert item.get("CFBundleURLName"), "each entry needs a non-empty CFBundleURLName"
