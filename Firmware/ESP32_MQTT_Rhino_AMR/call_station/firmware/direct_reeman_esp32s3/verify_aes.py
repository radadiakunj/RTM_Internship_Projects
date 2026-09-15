#!/usr/bin/env python3
"""Compare ESP32 AES-CBC bodies with MQTT/reeman_forklift_client.py.

Usage (from repo root):
  python call_station/firmware/direct_reeman_esp32s3/verify_aes.py
  python call_station/firmware/direct_reeman_esp32s3/verify_aes.py --key a5F6dmfr --pick p2 --drop p3 --home home
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "MQTT"))
import reeman_forklift_client as rfc  # noqa: E402


def map_value(raw: str):
    return raw if raw else None


def calling_plain(map_name, point: str) -> str:
    return json.dumps({"map": map_name, "point": point}, ensure_ascii=False)


def auto_plain(map_name, pick: str, drop: str) -> str:
    body = [{"first": {"map": map_name, "point": pick},
             "second": {"map": map_name, "point": drop}}]
    return json.dumps(body, ensure_ascii=False)


def esp32_calling(map_name, point: str) -> str:
    mapj = "null" if map_name is None else f'"{map_name}"'
    return '{"map": %s, "point": "%s"}' % (mapj, point)


def esp32_auto(map_name, pick: str, drop: str) -> str:
    mapj = "null" if map_name is None else f'"{map_name}"'
    return (
        '[{"first": {"map": %s, "point": "%s"}, '
        '"second": {"map": %s, "point": "%s"}}]'
        % (mapj, pick, mapj, drop)
    )


def check(label: str, python_pt: str, esp32_pt: str, codec: rfc.AesCodec) -> bool:
    py_body = codec.encrypt(python_pt)
    esp_body = codec.encrypt(esp32_pt)
    match_pt = python_pt == esp32_pt
    match_body = py_body == esp_body
    print(f"=== {label} ===")
    print("python plaintext:", python_pt)
    print("esp32  plaintext:", esp32_pt)
    print("plaintext match:", match_pt)
    print("body_b64 python:", py_body)
    print("body_b64 esp32 :", esp_body)
    print("body match:", match_body)
    print("roundtrip:", codec.decrypt(py_body))
    print()
    return match_pt and match_body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="a5F6dmfr")
    ap.add_argument("--map", default="", help="empty => JSON null (elevator off)")
    ap.add_argument("--home", default="home")
    ap.add_argument("--pick", default="p2")
    ap.add_argument("--drop", default="p3")
    args = ap.parse_args()

    map_name = map_value(args.map)
    codec = rfc.AesCodec(args.key)

    print("key_len:", len(args.key.encode("utf-8")), "normalized_key_hex:", codec.key.hex())
    print("iv_hex:", codec.iv.hex())
    print()

    ok_home = check(
        "calling_model home",
        calling_plain(map_name, args.home),
        esp32_calling(map_name, args.home),
        codec,
    )
    ok_auto = check(
        "auto_model pick->place",
        auto_plain(map_name, args.pick, args.drop),
        esp32_auto(map_name, args.pick, args.drop),
        codec,
    )

    print("Topics (hostname example rbot55f-260114-003-001):")
    print("  PUB  reeman/calling/phone/<hostname>/forklift/heartbeat")
    print("  PUB  reeman/calling/phone/<hostname>/forklift/task/auto_model")
    print("  PUB  reeman/calling/phone/<hostname>/forklift/task/calling_model")
    print("  SUB  reeman/calling/robot/<hostname>/forklift/#")
    print()
    if ok_home and ok_auto:
        print("PASS: ESP32 plaintext matches Python json.dumps for home and p2->p3.")
        return 0
    print("FAIL: ESP32 snprintf does not match Python json.dumps — ciphertext will differ.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
