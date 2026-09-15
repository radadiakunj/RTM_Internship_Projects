#!/usr/bin/env python3
"""
Sync portal/config.json → config.h before Arduino upload (compile-time fallback).

ESP32 also fetches live credentials from the portal at runtime — no re-upload needed
when portal/config.json changes. Run this once before the first upload, or optionally
before each upload to keep config.h in sync.

  python sync_credentials.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_H = HERE / "config.h"
PORTAL_JSON = HERE.parent.parent.parent / "portal" / "config.json"


def read_field(text: str, name: str) -> str:
    m = re.search(rf'static const char\* {name}\s*=\s*"([^"]*)"', text)
    return m.group(1) if m else ""


def replace_cstring(text: str, name: str, value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    pattern = rf'(static const char\* {name}\s*=\s*")[^"]*(";)'
    new_text, n = re.subn(pattern, rf"\1{escaped}\2", text, count=1)
    if n != 1:
        raise RuntimeError(f"Could not find {name} in {CONFIG_H.name}")
    return new_text


def main() -> int:
    if not PORTAL_JSON.is_file():
        print(f"Missing {PORTAL_JSON}", file=sys.stderr)
        print("Start portal once and save credentials in the browser.", file=sys.stderr)
        return 1
    if not CONFIG_H.is_file():
        print(f"Missing {CONFIG_H}", file=sys.stderr)
        return 1

    portal = json.loads(PORTAL_JSON.read_text(encoding="utf-8"))
    hostname = (portal.get("hostname") or "").strip()
    token = (portal.get("token") or "").strip()
    key = (portal.get("encryptKey") or "").strip()

    if not token:
        print("portal/config.json has no token — open http://laptop:3080 and Save credentials.", file=sys.stderr)
        return 2

    text = CONFIG_H.read_text(encoding="utf-8")
    before = (read_field(text, "ROBOT_HOSTNAME"), read_field(text, "ROBOT_TOKEN"), read_field(text, "ROBOT_KEY"))
    after = (hostname, token, key)

    if before == after:
        print("config.h already matches portal/config.json — no changes.")
        return 0

    text = replace_cstring(text, "ROBOT_HOSTNAME", hostname)
    text = replace_cstring(text, "ROBOT_TOKEN", token)
    text = replace_cstring(text, "ROBOT_KEY", key or "a5F6dmfr")
    CONFIG_H.write_text(text, encoding="utf-8")
    print(f"Updated {CONFIG_H.name} from portal/config.json")
    print(f"  hostname = {hostname}")
    print(f"  token    = {token[:8]}...")
    print("Upload direct_reeman_esp32s3.ino (ESP32 will also auto-sync at runtime).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
