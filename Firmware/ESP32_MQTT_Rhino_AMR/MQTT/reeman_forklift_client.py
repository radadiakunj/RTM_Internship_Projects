#!/usr/bin/env python3
"""
Reeman Forklift AMR — MQTT integration reference client
========================================================

A self-contained reference implementation of Reeman's "Forklift Calling API"
(MQTT). It demonstrates the full happy path:

    1. Pairing       — discover a robot via UDP multicast and grab its
                       hostname / token / encryptKey.
    2. Connect       — connect to the MQTT broker and subscribe to the
                       robot's status/response topics.
    3. Heartbeat     — keep the robot "awake" by publishing a phone heartbeat
                       (the robot ignores all commands if it hasn't heard one
                       for >10 s).
    4. Query points  — ask the robot for the available map points per mode.
    5. Dispatch task — send an "auto mode" pallet task: a list of
                       (pick-point -> drop-point) pairs.
    6. Monitor       — decode the robot's 5 s status heartbeat and task
                       responses.

------------------------------------------------------------------------------
!! IMPORTANT — THINGS TO CONFIRM WITH REEMAN BEFORE PRODUCTION USE !!
------------------------------------------------------------------------------
The vendor PDF says message bodies are "AES encrypted" but does NOT specify:
    - cipher mode (ECB? CBC?),  - padding (PKCS7?),  - IV (none/transmitted?),
    - key derivation (the sample key "12345678" is 8 bytes, which is NOT a
      valid AES key length — AES needs 16/24/32 bytes).
    - output encoding (Base64? hex?).

CONFIRMED against a live Reeman forklift (2026-06): the body cipher is
AES-128 / CBC / PKCS7 / Base64, where the 8-char Encryption Key is UTF-8
zero-padded to 16 bytes AND that same 16-byte value is reused as the IV.
This is the default below; all parts remain overridable via the AesCodec
constructor and CLI flags.

Dependencies:  pip install paho-mqtt pycryptodome
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import paho.mqtt.client as mqtt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

log = logging.getLogger("reeman")

# --- Constants straight from the vendor doc -------------------------------- #
DEFAULT_MULTICAST_IP = "239.0.0.1"
DEFAULT_MULTICAST_PORT = 7979
DEFAULT_BROKER = "mqtt.rmbot.cn"
DEFAULT_BROKER_PORT = 1883

# Phone->robot heartbeat cadence. Robot drops you after 10 s of silence, so we
# send comfortably inside that window.
PHONE_HEARTBEAT_INTERVAL_S = 4.0

# Task / points modes (the {mode} segment of the topics).
MODE_CALLING = "calling_model"
MODE_AUTO = "auto_model"
MODE_MANUAL = "manual_model"
MODE_TASK = "task_model"   # locally-saved named routes

# Response codes (see doc "Code Description" table).
CODE_OK = 0
CODE_POINTS_FAILED = 1
CODE_TASK_FAILED = 2


# --------------------------------------------------------------------------- #
# AES body codec  (see the big WARNING block above)
# --------------------------------------------------------------------------- #
class AesCodec:
    def __init__(
        self,
        key: str,
        mode: str = "CBC",
        iv: Optional[bytes] = None,
        encoding: str = "base64",
    ):
        self.raw_key = key
        self.key = self._normalize_key(key)
        self.mode = mode.upper()
        # Confirmed against the live forklift: IV is the key itself
        # (zero-padded to 16 bytes), not a zero/random IV.
        self.iv = iv if iv is not None else self.key[:16]
        self.encoding = encoding.lower()

    @staticmethod
    def _normalize_key(key: str) -> bytes:
        """AES needs 16/24/32 bytes. Pad/truncate the UTF-8 key to 16."""
        kb = key.encode("utf-8")
        if len(kb) in (16, 24, 32):
            return kb
        if len(kb) < 16:
            return kb.ljust(16, b"\x00")
        if len(kb) < 24:
            return kb[:16]
        if len(kb) < 32:
            return kb[:24]
        return kb[:32]

    def _cipher(self):
        if self.mode == "ECB":
            return AES.new(self.key, AES.MODE_ECB)
        if self.mode == "CBC":
            return AES.new(self.key, AES.MODE_CBC, self.iv)
        raise ValueError(f"Unsupported AES mode: {self.mode}")

    def encrypt(self, plaintext: str) -> str:
        ct = self._cipher().encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
        return base64.b64encode(ct).decode() if self.encoding == "base64" else ct.hex()

    def decrypt(self, body: str) -> str:
        raw = base64.b64decode(body) if self.encoding == "base64" else bytes.fromhex(body)
        pt = unpad(self._cipher().decrypt(raw), AES.block_size)
        return pt.decode("utf-8")


# --------------------------------------------------------------------------- #
# Pairing credentials
# --------------------------------------------------------------------------- #
@dataclass
class RobotIdentity:
    hostname: str
    alias: str
    key: str          # == encryptKey used for AES
    token: str
    robot_type: int   # 9 == forklift

    @classmethod
    def from_multicast_json(cls, data: dict) -> "RobotIdentity":
        rt = data.get("robotType")
        if isinstance(rt, str):            # can be a description string, e.g. "forkhigh2"
            rt = 9 if ("叉" in rt or "fork" in rt.lower()) else -1
        return cls(
            hostname=data["hostname"],
            alias=data.get("alias", data["hostname"]),
            key=data["key"],
            token=data["token"],
            robot_type=rt if isinstance(rt, int) else -1,
        )


def discover_robot(
    multicast_ip: str = DEFAULT_MULTICAST_IP,
    port: int = DEFAULT_MULTICAST_PORT,
    timeout_s: float = 30.0,
) -> RobotIdentity:
    """Listen on the multicast group for a robot in pairing mode.

    Put the robot into pairing mode first (per its UI); it then broadcasts its
    {hostname, alias, key, token, robotType} JSON on 239.0.0.1:7979.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", port))
    mreq = struct.pack("4sl", socket.inet_aton(multicast_ip), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(timeout_s)

    log.info("Listening for robot pairing broadcast on %s:%d ...", multicast_ip, port)
    try:
        while True:
            raw, addr = sock.recvfrom(4096)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if "hostname" in data and "token" in data:
                ident = RobotIdentity.from_multicast_json(data)
                log.info("Discovered robot %s (alias=%s, type=%s) from %s",
                         ident.hostname, ident.alias, ident.robot_type, addr[0])
                return ident
    finally:
        sock.close()


# --------------------------------------------------------------------------- #
# MQTT client
# --------------------------------------------------------------------------- #
class ForkliftClient:
    def __init__(
        self,
        identity: RobotIdentity,
        codec: AesCodec,
        broker: str = DEFAULT_BROKER,
        broker_port: int = DEFAULT_BROKER_PORT,
        mqtt_user: Optional[str] = None,
        mqtt_pass: Optional[str] = None,
        on_status: Optional[Callable[[dict], None]] = None,
        on_task_result: Optional[Callable[[int, str], None]] = None,
        on_points: Optional[Callable[[str, int, dict], None]] = None,
    ):
        self.id = identity
        self.codec = codec
        self.broker = broker
        self.broker_port = broker_port
        self.on_status = on_status or self._default_status
        self.on_task_result = on_task_result or self._default_task_result
        self.on_points = on_points or self._default_points

        self._hb_stop = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None

        self.client = mqtt.Client(client_id=f"phone-{identity.hostname}-{int(time.time())}")
        if mqtt_user:
            self.client.username_pw_set(mqtt_user, mqtt_pass)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # ---- topic helpers ---------------------------------------------------- #
    def _phone(self, suffix: str) -> str:
        return f"reeman/calling/phone/{self.id.hostname}/forklift/{suffix}"

    def _robot(self, suffix: str) -> str:
        return f"reeman/calling/robot/{self.id.hostname}/forklift/{suffix}"

    # ---- lifecycle -------------------------------------------------------- #
    def connect(self):
        log.info("Connecting to broker %s:%d ...", self.broker, self.broker_port)
        self.client.connect(self.broker, self.broker_port, keepalive=30)
        self.client.loop_start()

    def disconnect(self):
        self.stop_heartbeat()
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            log.error("MQTT connect failed rc=%s", rc)
            return
        # Subscribe to everything the robot publishes for this hostname.
        client.subscribe(self._robot("#"), qos=1)
        log.info("Connected & subscribed to %s", self._robot("#"))
        self.start_heartbeat()

    # ---- heartbeat -------------------------------------------------------- #
    def start_heartbeat(self):
        if self._hb_thread and self._hb_thread.is_alive():
            return
        self._hb_stop.clear()
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()

    def stop_heartbeat(self):
        self._hb_stop.set()

    def _heartbeat_loop(self):
        payload = json.dumps({"token": self.id.token})
        topic = self._phone("heartbeat")
        while not self._hb_stop.is_set():
            self.client.publish(topic, payload, qos=0)
            self._hb_stop.wait(PHONE_HEARTBEAT_INTERVAL_S)

    # ---- outbound commands ------------------------------------------------ #
    def request_points(self, mode: str):
        """Ask for the map points available in a given mode."""
        self.client.publish(
            self._phone(f"points/request/{mode}"),
            json.dumps({"token": self.id.token}),
            qos=1,
        )
        log.info("Requested points for mode=%s", mode)

    def send_auto_task(self, pairs: List[Tuple[dict, dict]]):
        """Auto mode: a list of (pick, drop) point pairs.

        Each point is {"map": <name or None>, "point": <name>}. `map` is only
        required when elevator/floor-control mode is enabled; otherwise pass
        None (or omit).
        """
        body = [{"first": p, "second": d} for (p, d) in pairs]
        self._publish_task(MODE_AUTO, json.dumps(body, ensure_ascii=False))

    def send_calling_task(self, map_name: Optional[str], point: str):
        body = {"map": map_name, "point": point}
        self._publish_task(MODE_CALLING, json.dumps(body, ensure_ascii=False))

    def send_manual_task(self, drop_point: str, floor: Optional[str] = None):
        body = {"first": floor, "second": drop_point}
        self._publish_task(MODE_MANUAL, json.dumps(body, ensure_ascii=False))

    def send_named_route_task(self, route_name: str):
        # task_model body is just the route name string.
        self._publish_task(MODE_TASK, route_name)

    def _publish_task(self, mode: str, plaintext_body: str):
        payload = json.dumps({
            "token": self.id.token,
            "body": self.codec.encrypt(plaintext_body),
        })
        self.client.publish(self._phone(f"task/{mode}"), payload, qos=1)
        log.info("Dispatched %s task: %s", mode, plaintext_body)

    # ---- inbound dispatch ------------------------------------------------- #
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            log.warning("Non-JSON message on %s", msg.topic)
            return

        topic = msg.topic
        if topic.endswith("/heartbeat"):
            self.on_status(payload)
        elif "/points/response/" in topic:
            mode = topic.rsplit("/", 1)[-1]
            self._handle_points(mode, payload)
        elif topic.endswith("/task/response"):
            self._handle_task_response(payload)
        else:
            log.info("RX (unhandled) %s: %s", topic, payload)

    def _handle_points(self, mode: str, payload: dict):
        code = payload.get("code", -1)
        body = payload.get("body", "")
        if code == CODE_OK:
            try:
                decoded = json.loads(self.codec.decrypt(body))
            except Exception as e:  # noqa: BLE001
                log.error("Failed to decrypt/parse points body (%s). "
                          "Check AES params! err=%s", mode, e)
                log.error("RAW ENCRYPTED body (copy this whole string for analysis): %s", body)
                return
            self.on_points(mode, code, decoded)
        else:
            # code=1 -> body is a plaintext error string (do NOT decrypt).
            log.warning("points/%s failed code=%s body=%s", mode, code, body)
            self.on_points(mode, code, {"error": body})

    def _handle_task_response(self, payload: dict):
        code = payload.get("code", -1)
        body = payload.get("body", "")
        result = body
        if code == CODE_OK:  # task started; body is AES-encrypted result string
            try:
                result = self.codec.decrypt(body)
            except Exception as e:  # noqa: BLE001
                log.error("Failed to decrypt task result. Check AES params! err=%s", e)
        self.on_task_result(code, result)

    # ---- default handlers ------------------------------------------------- #
    @staticmethod
    def _default_status(status: dict):
        cur = status.get("currentTask")
        queue = status.get("taskList") or []
        log.info(
            "STATUS  battery=%s%% eStop=%s charge=%s nav=%s exec=%s lifting=%s liftPos=%s task=%s queue=%s",
            status.get("level"),
            status.get("emergencyButton"), status.get("chargeState"),
            status.get("isNavigating"), status.get("taskExecuting"),
            status.get("isLifting"), status.get("liftModelState"),
            (cur or {}).get("targetPoint") if cur else None,
            len(queue),
        )

    @staticmethod
    def _default_task_result(code: int, result: str):
        log.info("TASK RESULT code=%s -> %s", code, result)

    @staticmethod
    def _default_points(mode: str, code: int, data: dict):
        log.info("POINTS[%s] code=%s -> %s", mode, code, data)


# --------------------------------------------------------------------------- #
# CLI demo
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Reeman Forklift MQTT reference client")
    ap.add_argument("--broker", default=DEFAULT_BROKER)
    ap.add_argument("--broker-port", type=int, default=DEFAULT_BROKER_PORT)
    ap.add_argument("--mqtt-user", default="AGV",
                    help="MQTT broker username (Reeman default: AGV)")
    ap.add_argument("--mqtt-pass", default=None, help="MQTT broker password")

    # Pairing: either auto-discover via multicast, or pass creds manually.
    ap.add_argument("--discover", action="store_true",
                    help="Discover the robot via UDP multicast (robot must be in pairing mode).")
    ap.add_argument("--hostname")
    ap.add_argument("--token")
    ap.add_argument("--key", help="encryptKey (AES key)")
    ap.add_argument("--alias", default="")

    # AES tuning knobs (see warning block).
    ap.add_argument("--aes-mode", default="CBC", choices=["ECB", "CBC"])
    ap.add_argument("--aes-encoding", default="base64", choices=["base64", "hex"])

    # Demo action.
    ap.add_argument("--pick", help="pick-up point name (auto-mode demo)")
    ap.add_argument("--drop", help="drop point name (auto-mode demo)")
    ap.add_argument("--goto", help="single-point calling-mode move (gentle first-motion test)")
    ap.add_argument("--route", help="multi-stop auto task: comma-separated pick:drop pairs, "
                                    "e.g. 'mon1:mon21,fri01:fri11' (queued in one dispatch)")
    ap.add_argument("--map", default=None, help="map name (only with elevator/floor mode)")
    ap.add_argument("--request-points", action="store_true")
    ap.add_argument("--points-mode", default="auto_model",
                    choices=["calling_model", "auto_model", "manual_model", "task_model"],
                    help="which mode's points --request-points should fetch")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    if args.discover:
        ident = discover_robot(timeout_s=60)
    else:
        if not (args.hostname and args.token and args.key):
            ap.error("Without --discover you must pass --hostname --token --key")
        ident = RobotIdentity(args.hostname, args.alias or args.hostname,
                              args.key, args.token, robot_type=9)

    codec = AesCodec(ident.key, mode=args.aes_mode, encoding=args.aes_encoding)
    fc = ForkliftClient(ident, codec, broker=args.broker, broker_port=args.broker_port,
                        mqtt_user=args.mqtt_user, mqtt_pass=args.mqtt_pass)
    fc.connect()

    try:
        time.sleep(2)  # let connect + first heartbeat settle
        if args.request_points:
            fc.request_points(args.points_mode)
        if args.goto:
            fc.send_calling_task(args.map, args.goto)
        if args.route:
            pairs = []
            for seg in args.route.split(","):
                pk, _, dr = seg.partition(":")
                pairs.append(({"map": args.map, "point": pk.strip()},
                              {"map": args.map, "point": dr.strip()}))
            fc.send_auto_task(pairs)
        if args.pick and args.drop:
            fc.send_auto_task([
                ({"map": args.map, "point": args.pick},
                 {"map": args.map, "point": args.drop}),
            ])
        # Keep alive to observe status heartbeats & responses.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down ...")
    finally:
        fc.disconnect()


if __name__ == "__main__":
    main()
