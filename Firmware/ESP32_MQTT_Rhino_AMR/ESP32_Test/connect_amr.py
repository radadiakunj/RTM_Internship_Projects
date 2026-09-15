#!/usr/bin/env python3
"""
Connect / verify Reeman Rhino AMR on the LAN, then open an interactive
MQTT Calling-API shell (topic + JSON in → expected / actual out).

IP often changes daily — pass --ip, or leave it empty to auto-scan the laptop subnet.

Usage (interactive):
  python connect_amr.py

Usage (args):
  python connect_amr.py --hostname rbot55f-260114-003-001 --token YOUR_TOKEN --ip 192.168.5.75
  python connect_amr.py --hostname rbot55f-260114-003-001 --token YOUR_TOKEN

Success print:
  Connected with <token>
  …then MQTT shell for Calling API topics/payloads
"""

from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Missing dependency: paho-mqtt")
    print("Install with:  pip install -r requirements.txt")
    sys.exit(1)


def load_portal_config() -> dict:
    """Optional defaults from portal/config.json (hostname, token, MQTT user/pass)."""
    cfg_path = Path(__file__).resolve().parent / "portal" / "config.json"
    if not cfg_path.is_file():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def print_mqtt_auth_help(username: str, host: str, port: int = 1883) -> None:
    print("\nMQTT broker rejected login (Not authorized).")
    print(f"Tried user '{username or '(anonymous)'}' on {host}:{port}")
    print("Call Mode MQTT Configuration (tablet) is NOT a broker on the robot.")
    print("That screen makes the ROBOT connect TO your broker (Server Address).")
    print("Checklist:")
    print("  1) MQTT broker must be running on the tablet Server Address (e.g. 192.168.5.117:1883)")
    print("  2) Broker user/pass must match Call Mode: Robo / 1234")
    print("  3) connect_amr.py must use THAT broker host — not the AMR nav IP (192.168.5.75)")
    print("  4) On tablet: Save MQTT Configuration, then Test Connection")
    print("  5) Token / encryptKey on that page are for Calling payloads, not broker login")
    print("  6) Example:")
    print("       python connect_amr.py --mqtt-host 192.168.5.117 --mqtt-user Robo --mqtt-pass 1234")

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad

    HAS_AES = True
except ImportError:
    HAS_AES = False


HTTP_TIMEOUT = 1.5
SCAN_WORKERS = 64

# Calling API status codes (v2 + forklift docs)
STATUS_CODES = {
    0: "Success",
    2: "Cannot start task",
    1001: "Failed to get points (data source issue)",
    1002: "Failed to get points (elevator control error)",
    2001: "Task failed (data source issue)",
    2002: "Task failed (data source issue)",
    2003: "Task failed (invalid state: e-stop, low battery, busy, lift not reset, etc.)",
}

CHARGE_STATES = {
    1: "Not charging",
    2: "Dock charging",
    3: "Cable charging",
    8: "Docking",
}

POINT_MODELS = ("calling_model", "normal_model", "route_model", "qrcode_model",
                 "auto_model", "manual_model", "task_model")
TASK_MODELS = ("normal_model", "route_model", "qrcode_model", "charge_model",
                "return_model", "calling_model", "auto_model", "manual_model", "task_model")


# ---------------------------------------------------------------------------
# HTTP discovery (unchanged behaviour)
# ---------------------------------------------------------------------------

def http_get_json(url: str, timeout: float = HTTP_TIMEOUT):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def check_amr(ip: str, expected_hostname: str | None = None) -> dict | None:
    """Return hostname JSON if this IP looks like a Reeman nav host."""
    url = f"http://{ip}/reeman/hostname"
    try:
        data = http_get_json(url)
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
        return None

    hostname = None
    if isinstance(data, dict):
        hostname = data.get("hostname") or data.get("alias")
    if not hostname and isinstance(data, dict) and "raw" in data:
        return None
    if expected_hostname and hostname and hostname != expected_hostname:
        return {
            "ip": ip,
            "hostname": hostname,
            "match": False,
            "data": data,
        }
    return {
        "ip": ip,
        "hostname": hostname,
        "match": (not expected_hostname) or (hostname == expected_hostname),
        "data": data,
    }


def local_ipv4s() -> list[str]:
    found: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                found.append(ip)
    except OSError:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in found and not ip.startswith("127."):
            found.append(ip)
    except OSError:
        pass

    out: list[str] = []
    for ip in found:
        if ip not in out:
            out.append(ip)
    return out


def subnet_hosts(ipv4: str) -> list[str]:
    net = ipaddress.ip_network(f"{ipv4}/24", strict=False)
    return [str(h) for h in net.hosts()]


def discover_amr(expected_hostname: str) -> dict | None:
    locals_ = local_ipv4s()
    if not locals_:
        print("Could not detect laptop IPv4. Connect to the same Wi-Fi as the AMR.")
        return None

    print(f"Laptop IP(s): {', '.join(locals_)}")
    candidates: list[str] = []
    for lip in locals_:
        candidates.extend(subnet_hosts(lip))

    seen = set()
    hosts: list[str] = []
    for h in candidates:
        if h not in seen:
            seen.add(h)
            hosts.append(h)

    print(f"Scanning {len(hosts)} addresses for /reeman/hostname matching '{expected_hostname}' ...")
    matches: list[dict] = []
    near: list[dict] = []

    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        futs = {pool.submit(check_amr, ip, expected_hostname): ip for ip in hosts}
        for fut in as_completed(futs):
            result = fut.result()
            if not result:
                continue
            if result.get("match"):
                matches.append(result)
                print(f"  FOUND match: {result['ip']} hostname={result['hostname']}")
            else:
                near.append(result)
                print(f"  Found other Reeman at {result['ip']} hostname={result['hostname']}")

    if matches:
        return matches[0]
    if near:
        print("No exact hostname match. Using first Reeman device found.")
        return near[0]
    return None


def connect_http(ip: str, hostname: str, token: str) -> bool:
    print(f"\nChecking HTTP http://{ip}/reeman/hostname ...")
    result = check_amr(ip, hostname)
    if not result:
        print(f"FAILED: cannot reach AMR HTTP at {ip}")
        return False

    print(f"HTTP OK: {json.dumps(result['data'], ensure_ascii=False)}")
    if hostname and result.get("hostname") and result["hostname"] != hostname:
        print(f"WARNING: expected hostname '{hostname}', got '{result['hostname']}'")

    for path in ("reeman/base_encode", "reeman/get_mode", "reeman/pose"):
        try:
            data = http_get_json(f"http://{ip}/{path}", timeout=2.5)
            print(f"  {path}: {json.dumps(data, ensure_ascii=False)}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {path}: (skip) {exc}")

    print(f"\nConnected with {token}")
    print(f"AMR IP: {ip}")
    print(f"Hostname: {result.get('hostname') or hostname}")
    return True


# ---------------------------------------------------------------------------
# AES helpers (pairing encryptKey) — optional
# ---------------------------------------------------------------------------

def normalize_aes_key(key: str) -> bytes:
    buf = key.encode("utf-8")
    if len(buf) in (16, 24, 32):
        return buf
    out = bytearray(16)
    out[: min(len(buf), 16)] = buf[:16]
    return bytes(out)


def aes_encrypt(plaintext: str, key: str) -> str:
    if not HAS_AES:
        raise RuntimeError("pycryptodome required for AES. pip install pycryptodome")
    cipher = AES.new(normalize_aes_key(key), AES.MODE_ECB)
    return base64.b64encode(cipher.encrypt(pad(plaintext.encode("utf-8"), 16))).decode("ascii")


def aes_decrypt(ciphertext_b64: str, key: str) -> Any:
    if not HAS_AES:
        raise RuntimeError("pycryptodome required for AES. pip install pycryptodome")
    cipher = AES.new(normalize_aes_key(key), AES.MODE_ECB)
    raw = unpad(cipher.decrypt(base64.b64decode(ciphertext_b64)), 16).decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def try_decrypt_body(body: Any, code: Any, key: str | None) -> dict:
    if body is None or body == "":
        return {"decrypted": None, "raw": body, "error": None}
    should_decrypt = code in (0, 200)
    if not should_decrypt:
        return {"decrypted": body, "raw": body, "error": None, "plaintext_error": True}
    if not key:
        return {"decrypted": None, "raw": body, "error": "encryptKey missing — cannot decrypt body"}
    if not HAS_AES:
        return {"decrypted": None, "raw": body, "error": "pycryptodome not installed"}
    try:
        return {"decrypted": aes_decrypt(str(body), key), "raw": body, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"decrypted": None, "raw": body, "error": str(exc)}


def describe_code(code: Any) -> str:
    try:
        c = int(code)
    except (TypeError, ValueError):
        return f"Unknown code {code}"
    return STATUS_CODES.get(c, f"Unknown code {c}")


# ---------------------------------------------------------------------------
# Topic helpers + expected-output mapping (Calling API)
# ---------------------------------------------------------------------------

def phone_base(hostname: str, style: str) -> str:
    # style: "v2" (CALLING API english) or "forklift" (FORKLIFT CALLING API)
    return f"reeman/calling/phone/{hostname}/{style}"


def robot_base(hostname: str, style: str) -> str:
    return f"reeman/calling/robot/{hostname}/{style}"


def robot_subscribe_topics(hostname: str) -> list[str]:
    topics: list[str] = []
    for style in ("v2", "forklift"):
        r = robot_base(hostname, style)
        topics.append(f"{r}/heartbeat")
        topics.append(f"{r}/task/response")
        for m in POINT_MODELS:
            topics.append(f"{r}/points/response/{m}")
    # catch-all for unexpected robot replies on this hostname
    topics.append(f"reeman/calling/robot/{hostname}/#")
    return topics


def classify_publish(topic: str, hostname: str) -> dict | None:
    """Map a phone publish topic → what robot output to expect."""
    for style in ("v2", "forklift"):
        p = phone_base(hostname, style)
        r = robot_base(hostname, style)

        if topic == f"{p}/heartbeat":
            return {
                "kind": "heartbeat",
                "style": style,
                "expect_topic": f"{r}/heartbeat",
                "expect_hint": (
                    "Robot heartbeat JSON every ~5s after wake: battery, emergencyButton "
                    "(0=pressed / 1=released), chargeState/chargeFlag, isNavigating, "
                    "currentTask, taskList, …"
                ),
                "example_out": {
                    "battery": 55,
                    "emergencyButton": 1,
                    "chargeState": 1,
                    "isNavigating": False,
                    "currentTask": None,
                    "taskList": [],
                },
            }

        m = re.match(rf"^{re.escape(p)}/points/request/([\w]+)$", topic)
        if m:
            model = m.group(1)
            return {
                "kind": "points",
                "style": style,
                "model": model,
                "expect_topic": f"{r}/points/response/{model}",
                "expect_hint": (
                    "code 0 = OK (body AES-encrypted maps/points). "
                    "code 1 / 1001 / 1002 = error (body often plaintext)."
                ),
                "example_out": {
                    "token": "<same token>",
                    "code": 0,
                    "body": "<AES ciphertext base64>",
                },
            }

        m = re.match(rf"^{re.escape(p)}/task/([\w]+)$", topic)
        if m:
            model = m.group(1)
            return {
                "kind": "task",
                "style": style,
                "model": model,
                "expect_topic": f"{r}/task/response",
                "expect_hint": (
                    "code 0 = task started. code 2 = cannot start (forklift doc). "
                    "code 2001–2003 = data/state failure (v2 doc)."
                ),
                "example_out": {"token": "<same token>", "code": 0},
            }

    return None


def print_expected(meta: dict | None, topic: str, payload: Any) -> None:
    print("\n========== EXPECTED OUTPUT (Calling API) ==========")
    print(f"You published : {topic}")
    print(f"Payload       : {json.dumps(payload, ensure_ascii=False)}")
    if not meta:
        print("This topic is not a known Calling phone topic.")
        print("Still listening — any reply will show under ACTUAL MQTT IN.")
        print("=====================================================\n")
        return
    print(f"Kind          : {meta['kind']}  (API style: {meta['style']})")
    print(f"Expect topic  : {meta['expect_topic']}")
    print(f"Meaning       : {meta['expect_hint']}")
    print("Example shape :")
    print(json.dumps(meta["example_out"], indent=2, ensure_ascii=False))
    if meta["kind"] == "heartbeat":
        print("Note: keep publishing heartbeat every <10s or robot may ignore commands.")
    print("Waiting for ACTUAL MQTT IN from the robot…")
    print("=====================================================\n")


def print_actual(topic: str, payload_text: str, encrypt_key: str | None) -> None:
    print("\n========== ACTUAL MQTT IN ==========")
    print(f"topic : {topic}")
    print(f"raw   : {payload_text}")
    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError:
        parsed = None
        print("(non-JSON payload)")

    if parsed is None:
        print("====================================\n")
        return

    if topic.endswith("/heartbeat") and "/robot/" in topic:
        print("kind  : robot heartbeat")
        for key in ("battery", "emergencyButton", "chargeState", "chargeFlag",
                    "isNavigating", "navigating", "currentTask", "taskList", "status"):
            if key in parsed:
                val = parsed[key]
                if key in ("chargeState", "chargeFlag") and isinstance(val, int):
                    extra = CHARGE_STATES.get(val, "")
                    print(f"  {key}: {val}" + (f" ({extra})" if extra else ""))
                else:
                    print(f"  {key}: {val}")
    elif "/points/response/" in topic:
        code = parsed.get("code")
        print(f"kind  : points response → {describe_code(code)}")
        dec = try_decrypt_body(parsed.get("body"), code, encrypt_key)
        if dec.get("decrypted") is not None:
            print("body  :", json.dumps(dec["decrypted"], indent=2, ensure_ascii=False)
                  if not isinstance(dec["decrypted"], str)
                  else dec["decrypted"])
        if dec.get("error"):
            print("decrypt:", dec["error"])
    elif topic.endswith("/task/response"):
        code = parsed.get("code")
        print(f"kind  : task response → {describe_code(code)}")
        if "body" in parsed:
            dec = try_decrypt_body(parsed.get("body"), code, encrypt_key)
            if dec.get("decrypted") is not None:
                print("body  :", dec["decrypted"])
            if dec.get("error"):
                print("decrypt:", dec["error"])
    else:
        print("kind  : other message")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    print("====================================\n")


def print_guide(hostname: str, token: str) -> None:
    print("\n=== Calling API guide (publish → expected reply) ===\n")
    for style, label in (("v2", "CALLING API v2 (english)"), ("forklift", "FORKLIFT CALLING API")):
        p = phone_base(hostname, style)
        r = robot_base(hostname, style)
        print(f"--- {label} ---")
        print(f"PUB  {p}/heartbeat")
        print(f"     {{\"token\":\"{token[:8]}…\"}}")
        print(f"OUT  {r}/heartbeat   ← battery / e-stop / nav / tasks\n")
        print(f"PUB  {p}/points/request/normal_model")
        print(f"     {{\"token\":\"…\"}}")
        print(f"OUT  {r}/points/response/normal_model  ← code 0 + AES body\n")
        print(f"PUB  {p}/task/normal_model")
        print(f"     {{\"token\":\"…\",\"body\":\"<AES({{\\\"map\\\":null,\\\"point\\\":\\\"A\\\"}})>\"}}")
        print(f"OUT  {r}/task/response  ← code 0 started / 2 or 200x fail\n")
    print("Shell commands: help | guide | hb | points [model] | pub | quit")
    print("Or type a full topic, then paste JSON payload when prompted.\n")


# ---------------------------------------------------------------------------
# MQTT interactive shell
# ---------------------------------------------------------------------------

class MqttShell:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        hostname: str,
        token: str,
        encrypt_key: str = "",
        username: str = "",
        password: str = "",
        style: str = "v2",
    ):
        self.host = host
        self.port = port
        self.hostname = hostname
        self.token = token
        self.encrypt_key = encrypt_key
        self.username = username
        self.password = password
        self.style = style  # default shortcuts use v2 or forklift
        self.client: mqtt.Client | None = None
        self.connected = threading.Event()
        self.connect_failed = threading.Event()
        self.connect_fail_reason = ""
        self._lock = threading.Lock()
        self.last_heartbeat: dict | None = None

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties=None):
        # paho v2 callback API
        rc = int(getattr(reason_code, "value", reason_code))
        if rc == 0:
            self.connected.set()
            subs = robot_subscribe_topics(self.hostname)
            client.subscribe([(t, 0) for t in subs])
            print(f"MQTT connected to {self.host}:{self.port} as '{self.username or 'anonymous'}'")
            print(f"Subscribed to robot replies for hostname={self.hostname}")
        else:
            self.connect_fail_reason = str(reason_code)
            print(f"MQTT connect failed, reason_code={reason_code}")
            self.connect_failed.set()
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    def _on_message(self, _client, _userdata, msg):
        text = msg.payload.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
            if msg.topic.endswith("/heartbeat") and "/robot/" in msg.topic and isinstance(parsed, dict):
                with self._lock:
                    self.last_heartbeat = parsed
        except json.JSONDecodeError:
            pass
        print_actual(msg.topic, text, self.encrypt_key or None)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _properties=None):
        # Avoid spam: only note disconnect if we were fully connected
        if self.connected.is_set():
            print(f"MQTT disconnected ({reason_code})")
        self.connected.clear()

    def connect(self) -> bool:
        client_id = f"connect-amr-{int(time.time()) % 100000}"
        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
                protocol=mqtt.MQTTv311,
            )
        except AttributeError:
            # older paho
            self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)

        # Do not auto-retry forever on bad credentials
        self.client.reconnect_delay_set(min_delay=1, max_delay=2)
        try:
            self.client._reconnect_on_failure = False  # noqa: SLF001
        except Exception:  # noqa: BLE001
            pass

        if self.username:
            self.client.username_pw_set(self.username, self.password or "")

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        try:
            self.client.on_disconnect = self._on_disconnect
        except Exception:  # noqa: BLE001
            pass

        print(f"\nConnecting MQTT mqtt://{self.host}:{self.port} ...")
        print(f"Auth: user='{self.username or '(anonymous)'}'")
        try:
            self.client.connect(self.host, self.port, keepalive=30)
        except OSError as exc:
            print(f"FAILED MQTT connect: {exc}")
            print("Tips: same Wi-Fi as AMR; check port 1883; try --mqtt-user / --mqtt-pass")
            return False

        self.client.loop_start()
        deadline = time.time() + 8
        while time.time() < deadline:
            if self.connected.is_set():
                return True
            if self.connect_failed.is_set():
                reason = self.connect_fail_reason.lower()
                if "not authorized" in reason or "bad user" in reason or reason in ("5", "134", "135"):
                    print_mqtt_auth_help(self.username, self.host, self.port)
                else:
                    print(f"FAILED: MQTT connect rejected ({self.connect_fail_reason})")
                self.close()
                return False
            time.sleep(0.05)

        print("FAILED: MQTT connect timeout (no CONNACK)")
        print(f"Is an MQTT broker listening on {self.host}:{self.port}?")
        print("Call Mode Server Address must be YOUR broker (laptop), then both robot + this script join it.")
        self.close()
        return False

    def publish(self, topic: str, payload: Any) -> None:
        assert self.client is not None
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        else:
            body = str(payload)
        meta = classify_publish(topic, self.hostname)
        print_expected(meta, topic, payload if isinstance(payload, (dict, list)) else body)
        self.client.publish(topic, body, qos=0)
        print(f"PUBLISH OK → {topic}")

    def close(self) -> None:
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self.client = None

    def run_interactive(self) -> None:
        print_guide(self.hostname, self.token)
        print("Type 'help' for commands. Empty topic = quit.\n")

        while True:
            try:
                line = input("mqtt> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue
            low = line.lower()

            if low in ("quit", "exit", "q"):
                break
            if low in ("help", "?"):
                print_guide(self.hostname, self.token)
                continue
            if low == "guide":
                print_guide(self.hostname, self.token)
                continue
            if low == "status":
                with self._lock:
                    hb = self.last_heartbeat
                if hb:
                    print(json.dumps(hb, indent=2, ensure_ascii=False))
                else:
                    print("No robot heartbeat received yet. Try: hb")
                continue
            if low == "hb" or low.startswith("hb "):
                topic = f"{phone_base(self.hostname, self.style)}/heartbeat"
                self.publish(topic, {"token": self.token})
                continue
            if low == "points" or low.startswith("points "):
                parts = line.split()
                model = (parts[1] if len(parts) > 1 else "normal_model").strip()
                if not model.endswith("_model"):
                    model = f"{model}_model"
                topic = f"{phone_base(self.hostname, self.style)}/points/request/{model}"
                self.publish(topic, {"token": self.token})
                continue
            if low == "pub" or low.startswith("pub "):
                # pub [topic]  OR just prompts
                parts = line.split(maxsplit=1)
                topic = parts[1].strip() if len(parts) > 1 else ""
                if not topic:
                    topic = input("Topic: ").strip()
                if not topic:
                    print("Cancelled (empty topic).")
                    continue
                raw = input("Payload JSON: ").strip()
                if not raw:
                    print("Cancelled (empty payload).")
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    print(f"Invalid JSON: {exc}")
                    continue
                # auto-fill token if omitted on known calling payloads
                if isinstance(payload, dict) and "token" not in payload:
                    payload["token"] = self.token
                    print("(filled missing token from connect)")
                self.publish(topic, payload)
                continue
            if low.startswith("task "):
                # task normal PointA   | task charge | task return
                parts = line.split()
                kind = parts[1].lower() if len(parts) > 1 else "normal"
                if kind in ("charge", "return"):
                    model = f"{kind}_model"
                    body = None
                else:
                    model = "normal_model" if kind in ("normal", "normal_model") else (
                        kind if kind.endswith("_model") else f"{kind}_model"
                    )
                    point = parts[2] if len(parts) > 2 else ""
                    if not point:
                        print("Usage: task normal <PointName> | task charge | task return")
                        continue
                    if not self.encrypt_key:
                        print("encryptKey required for task body. Pass --key or enter when prompted.")
                        continue
                    if not HAS_AES:
                        print("pip install pycryptodome  (needed to AES-encrypt task body)")
                        continue
                    plain = json.dumps({"map": None, "point": point}, separators=(",", ":"))
                    body = aes_encrypt(plain, self.encrypt_key)
                topic = f"{phone_base(self.hostname, self.style)}/task/{model}"
                self.publish(topic, {"token": self.token, "body": body})
                continue

            # Treat first token as topic if it looks like one
            if "/" in line:
                topic = line
                raw = input("Payload JSON: ").strip()
                if not raw:
                    print("Cancelled (empty payload).")
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    print(f"Invalid JSON: {exc}")
                    continue
                if isinstance(payload, dict) and "token" not in payload:
                    payload["token"] = self.token
                    print("(filled missing token from connect)")
                self.publish(topic, payload)
                continue

            print("Unknown command. Try: help | hb | points | pub | task | quit")

        print("Closing MQTT…")
        self.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Find/verify Reeman AMR, then interactive MQTT Calling shell"
    )
    p.add_argument("--hostname", help="AMR hostname, e.g. rbot55f-260114-003-001")
    p.add_argument("--token", help="Pairing / Calling token")
    p.add_argument("--ip", help="AMR navigation IP (optional; auto-scan if omitted)")
    p.add_argument("--scan", action="store_true", help="Force subnet scan even if --ip is given")
    p.add_argument(
        "--mqtt-host",
        help="MQTT broker host = Call Mode 'Server Address' (NOT AMR nav IP)",
    )
    p.add_argument("--mqtt-port", type=int, default=None, help="MQTT port (default 1883)")
    p.add_argument("--mqtt-user", default="", help="MQTT username (Call Mode Username)")
    p.add_argument("--mqtt-pass", default="", help="MQTT password (Call Mode Password)")
    p.add_argument("--key", default="", help="Call Mode Encryption Key (AES) for task bodies")
    p.add_argument(
        "--style",
        choices=("v2", "forklift"),
        default="v2",
        help="Default Calling topic style for shortcuts (hb/points/task)",
    )
    p.add_argument(
        "--cloud",
        action="store_true",
        help="Use cloud broker mqtt.rmbot.cn instead of Call Mode broker",
    )
    p.add_argument(
        "--amr-broker",
        action="store_true",
        help="Connect MQTT to AMR nav IP:1883 (only if robot hosts a broker)",
    )
    p.add_argument(
        "--no-mqtt",
        action="store_true",
        help="Only do HTTP connect check (skip MQTT shell)",
    )
    return p.parse_args()


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def main() -> int:
    args = parse_args()
    file_cfg = load_portal_config()
    brokers = file_cfg.get("brokers") or {}
    call_broker = brokers.get("callMode") or brokers.get("local") or {}
    amr_broker = brokers.get("amr") or {}

    default_host = file_cfg.get("hostname") or "rbot55f-260114-003-001"
    default_token = file_cfg.get("token") or ""
    default_ip = file_cfg.get("navIp") or ""
    # Call Mode tablet: Server Address = YOUR broker (laptop), not AMR IP
    default_mqtt_host = (
        file_cfg.get("mqttHost")
        or call_broker.get("host")
        or "192.168.5.117"
    )
    default_mqtt_port = int(
        file_cfg.get("mqttPort")
        or call_broker.get("port")
        or 1883
    )
    default_user = (
        file_cfg.get("mqttUsername")
        or call_broker.get("username")
        or "Robo"
    )
    default_pass = (
        file_cfg.get("mqttPassword")
        or call_broker.get("password")
        or "1234"
    )
    default_key = file_cfg.get("encryptKey") or ""

    hostname = args.hostname or prompt("Hostname", default_host)
    token = args.token or prompt("Token", default_token)
    ip = args.ip if args.ip is not None else prompt(
        "AMR IP (leave empty to auto-find on current Wi-Fi)", default_ip
    )

    if not hostname:
        print("Hostname is required")
        return 1
    if not token:
        print("Token is required")
        return 1

    if not ip or args.scan:
        found = discover_amr(hostname)
        if not found:
            print("\nFAILED: AMR not found on this Wi-Fi.")
            print("Connect laptop to the SAME network as the AMR, then retry.")
            return 2
        ip = found["ip"]
        if found.get("hostname"):
            hostname = found["hostname"]
    else:
        print(f"Using provided IP: {ip}")

    ok = connect_http(ip, hostname, token)
    if not ok:
        return 3

    if args.no_mqtt:
        return 0

    if args.cloud:
        mqtt_host = args.mqtt_host or "mqtt.rmbot.cn"
    elif args.amr_broker:
        mqtt_host = args.mqtt_host or amr_broker.get("host") or ip
    else:
        mqtt_host = args.mqtt_host or default_mqtt_host

    mqtt_port = int(args.mqtt_port if args.mqtt_port is not None else default_mqtt_port)
    mqtt_user = args.mqtt_user or default_user
    mqtt_pass = args.mqtt_pass or default_pass
    encrypt_key = args.key or default_key

    print("\nCall Mode MQTT: robot joins YOUR broker (tablet Server Address).")
    print("This script must join the SAME broker — not the AMR nav IP.")
    if not args.mqtt_host and not args.cloud and not args.amr_broker:
        mqtt_host = prompt(
            "MQTT broker host (Call Mode Server Address)",
            mqtt_host,
        )
    if args.mqtt_port is None and not args.cloud:
        port_in = prompt("MQTT broker port", str(mqtt_port))
        try:
            mqtt_port = int(port_in)
        except ValueError:
            mqtt_port = default_mqtt_port
    if not args.mqtt_user:
        mqtt_user = prompt("MQTT username (Call Mode Username)", mqtt_user)
    if mqtt_user and not args.mqtt_pass:
        mqtt_pass = prompt("MQTT password (Call Mode Password)", mqtt_pass)
    if not args.key:
        encrypt_key = prompt("encryptKey (Call Mode Encryption Key)", encrypt_key)

    shell = MqttShell(
        host=mqtt_host,
        port=mqtt_port,
        hostname=hostname,
        token=token,
        encrypt_key=encrypt_key,
        username=mqtt_user,
        password=mqtt_pass,
        style=args.style,
    )
    if not shell.connect():
        print("\nHTTP connect succeeded, but MQTT shell could not start.")
        print("1) Start Mosquitto (or other broker) on the Call Mode Server Address")
        print("2) Create user Robo / 1234 on that broker")
        print("3) On tablet Call Mode → MQTT Configuration → Save → Test Connection")
        print("4) Retry:")
        print(
            f"  python connect_amr.py --mqtt-host {mqtt_host} "
            f"--mqtt-user {mqtt_user or 'Robo'} --mqtt-pass {mqtt_pass or '1234'}"
        )
        return 4

    shell.run_interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
