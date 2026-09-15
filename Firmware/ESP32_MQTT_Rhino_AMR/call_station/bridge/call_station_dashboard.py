#!/usr/bin/env python3
"""
Call-station bridge + web dashboard
===================================
Listens for ESP32 floor MQTT commands and drives the Reeman forklift using
the mentor SOP client (AES + heartbeat in MQTT/reeman_forklift_client.py).

Flow (White button on ESP32):
  run_job → auto_model pick(POINT A) → drop(POINT D)
  then calling_model → HOME
  LEDs updated from robot heartbeat phases.

Flow (Blue button):
  go_home → calling_model HOME

Run (from repo root or this folder):
  pip install -r requirements.txt
  python call_station_dashboard.py \\
    --broker 192.168.5.117 --hostname rbot55f-260114-003-001 \\
    --token "YOUR_TOKEN" --key a5F6dmfr \\
    --pick A --drop D --home Home \\
    --mqtt-user "" --mqtt-pass ""

Open http://localhost:5055
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request
import paho.mqtt.client as mqtt

# Import mentor SOP client from ../MQTT/
ROOT = Path(__file__).resolve().parents[2]
MQTT_DIR = ROOT / "MQTT"
sys.path.insert(0, str(MQTT_DIR))
import reeman_forklift_client as rfc  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("call_station")

app = Flask(__name__)

STATE = {
    "phase": "idle",
    "robot": {},
    "robot_ts": 0.0,
    "station": {},
    "station_ts": 0.0,
    "last_cmd": None,
    "last_task": None,
    "map": None,
    "elevator_mode": False,  # if False, task payloads must use map=null
    "online": False,
    "job_active": False,
}

_cfg = {}
_forklift: rfc.ForkliftClient | None = None
_floor: mqtt.Client | None = None
_lock = threading.Lock()


def station_topic(kind: str) -> str:
    return f"floor/callstation/{_cfg['station_id']}/{kind}"


def set_phase(phase: str, reason: str = ""):
    with _lock:
        STATE["phase"] = phase
    payload = json.dumps({"phase": phase, "reason": reason})
    if _floor:
        _floor.publish(station_topic("leds"), payload, qos=0)
    log.info("PHASE %s (%s)", phase, reason)


def on_robot_status(status: dict):
    with _lock:
        STATE["robot"] = status
        STATE["robot_ts"] = time.time()
        STATE["online"] = True
        job = STATE["job_active"]

    if not job:
        return

    cur = status.get("currentTask") or {}
    target = (cur or {}).get("targetPoint")
    navigating = bool(status.get("isNavigating"))
    lifting = bool(status.get("isLifting"))
    executing = bool(status.get("taskExecuting"))
    estop = status.get("emergencyButton")

    if estop == 0:
        set_phase("error", "e-stop pressed")
        return

    pick = _cfg["pick"]
    drop = _cfg["drop"]
    home = _cfg["home"]

    if lifting:
        set_phase("lifting", "forks moving / docking")
    elif target == pick or (navigating and target == pick):
        set_phase("to_pick", f"nav→{pick}")
    elif target == drop:
        set_phase("to_drop", f"nav→{drop}")
    elif target == home:
        set_phase("to_home", f"nav→{home}")
    elif not executing and not navigating and job:
        # idle while job flagged — may be between tasks
        pass


def on_points(mode: str, code: int, data: dict):
    if code != 0:
        return
    data = data or {}
    STATE["elevator_mode"] = bool(data.get("elevatorModeSwitch"))
    model = data.get("model") or {}
    if model and not STATE["map"]:
        STATE["map"] = next(iter(model.keys()))
        log.info("Map auto-discovered: %s", STATE["map"])
    log.info(
        "Points mode=%s elevator=%s map_for_tasks=%s",
        mode, STATE["elevator_mode"], task_map(),
    )


def task_map():
    """Reeman wants map=null when elevator/floor mode is OFF."""
    if STATE.get("elevator_mode"):
        return STATE["map"] or _cfg.get("map")
    return None


def on_task_result(code: int, result: str):
    with _lock:
        STATE["last_task"] = {"code": code, "result": result, "ts": time.time()}
    if code != 0:
        set_phase("error", f"task code={code} {result}")
        with _lock:
            STATE["job_active"] = False


def start_job():
    pick, drop, home = _cfg["pick"], _cfg["drop"], _cfg["home"]
    map_name = task_map()
    with _lock:
        STATE["job_active"] = True
        STATE["last_cmd"] = {"cmd": "run_job", "ts": time.time()}
    set_phase("to_pick", f"dispatch {pick}→{drop}")
    log.info("Dispatch AUTO %s → %s (map=%s elevator=%s)",
             pick, drop, map_name, STATE.get("elevator_mode"))
    _forklift.send_auto_task([
        ({"map": map_name, "point": pick}, {"map": map_name, "point": drop}),
    ])
    # After auto task, queue return home as calling task once robot finishes.
    threading.Thread(target=_finish_with_home, args=(home, map_name), daemon=True).start()


def _finish_with_home(home: str, map_name):
    """Wait until auto task finishes, then send go-home + LED blue."""
    deadline = time.time() + 900  # 15 min safety
    saw_exec = False
    while time.time() < deadline:
        with _lock:
            s = dict(STATE["robot"])
            active = STATE["job_active"]
        if not active:
            return
        executing = bool(s.get("taskExecuting"))
        navigating = bool(s.get("isNavigating"))
        lifting = bool(s.get("isLifting"))
        if executing or navigating or lifting:
            saw_exec = True
        if saw_exec and not executing and not navigating and not lifting:
            break
        time.sleep(1.0)
    else:
        set_phase("error", "job timeout")
        with _lock:
            STATE["job_active"] = False
        return

    set_phase("to_home", f"return {home}")
    _forklift.send_calling_task(map_name, home)

    # Wait for home arrival
    deadline = time.time() + 600
    saw = False
    while time.time() < deadline:
        with _lock:
            s = dict(STATE["robot"])
        executing = bool(s.get("taskExecuting"))
        navigating = bool(s.get("isNavigating"))
        cur = (s.get("currentTask") or {}).get("targetPoint")
        if navigating or executing or cur == home:
            saw = True
        if saw and not navigating and not executing:
            break
        time.sleep(1.0)

    set_phase("done", "home reached")
    time.sleep(2.0)
    set_phase("idle", "ready")
    with _lock:
        STATE["job_active"] = False


def go_home():
    home = _cfg["home"]
    map_name = task_map()
    with _lock:
        STATE["job_active"] = True
        STATE["last_cmd"] = {"cmd": "go_home", "ts": time.time()}
    set_phase("to_home", f"calling {home}")
    _forklift.send_calling_task(map_name, home)
    threading.Thread(target=_wait_idle_then_ready, daemon=True).start()


def _wait_idle_then_ready():
    time.sleep(2)
    deadline = time.time() + 600
    saw = False
    while time.time() < deadline:
        with _lock:
            s = dict(STATE["robot"])
        if s.get("isNavigating") or s.get("taskExecuting"):
            saw = True
        if saw and not s.get("isNavigating") and not s.get("taskExecuting"):
            break
        time.sleep(1)
    set_phase("done", "home")
    time.sleep(1.5)
    set_phase("idle", "ready")
    with _lock:
        STATE["job_active"] = False


def on_floor_message(_client, _userdata, msg):
    topic = msg.topic
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return

    if topic.endswith("/status") or topic.endswith("/hb"):
        with _lock:
            STATE["station"] = data
            STATE["station_ts"] = time.time()
        return

    if not topic.endswith("/cmd"):
        return

    cmd = data.get("cmd")
    log.info("Station CMD: %s %s", cmd, data)
    with _lock:
        STATE["last_cmd"] = data
        busy = STATE["job_active"]

    if busy and cmd in ("run_job", "go_home"):
        log.warning("Ignored %s — job already active", cmd)
        return

    # Allow ESP32 to override point names from payload
    if data.get("pick"):
        _cfg["pick"] = data["pick"]
    if data.get("drop"):
        _cfg["drop"] = data["drop"]
    if data.get("home"):
        _cfg["home"] = data["home"]

    if cmd == "run_job":
        start_job()
    elif cmd == "go_home":
        go_home()
    else:
        log.warning("Unknown cmd %s", cmd)


def connect_floor(broker: str, port: int, user: str, password: str):
    global _floor
    _floor = mqtt.Client(client_id=f"call-bridge-{int(time.time())}")
    if user:
        _floor.username_pw_set(user, password or "")
    _floor.on_message = on_floor_message
    _floor.connect(broker, port, keepalive=30)
    _floor.subscribe(station_topic("cmd"))
    _floor.subscribe(station_topic("status"))
    _floor.subscribe(station_topic("hb"))
    _floor.loop_start()
    set_phase("idle", "bridge online")
    log.info("Floor MQTT ready; listening %s", station_topic("cmd"))


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Call Station — AMR</title>
<style>
  :root { --bg:#0f1419; --card:#1a2332; --text:#e7eef8; --muted:#8b9bb4; --ok:#3ddc97; --warn:#f4c95f; --err:#ff6b6b; --accent:#5b8cff; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: "Segoe UI", system-ui, sans-serif; background:linear-gradient(160deg,#0f1419,#162033); color:var(--text); }
  header { padding:1.25rem 1.5rem; border-bottom:1px solid #243044; }
  h1 { margin:0; font-size:1.35rem; letter-spacing:.02em; }
  .sub { color:var(--muted); font-size:.9rem; margin-top:.35rem; }
  main { display:grid; gap:1rem; padding:1.25rem; grid-template-columns: repeat(auto-fit,minmax(280px,1fr)); }
  .card { background:var(--card); border:1px solid #2a3a55; border-radius:14px; padding:1rem 1.1rem; }
  .phase { font-size:1.8rem; font-weight:700; text-transform:uppercase; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:.4rem .8rem; font-size:.92rem; }
  .k { color:var(--muted); } .v { font-weight:600; }
  .leds { display:flex; gap:.5rem; flex-wrap:wrap; margin-top:.8rem; }
  .led { width:28px; height:28px; border-radius:50%; background:#333; border:2px solid #555; }
  .led.on-r { background:var(--err); box-shadow:0 0 12px var(--err); }
  .led.on-y { background:var(--warn); box-shadow:0 0 12px var(--warn); }
  .led.on-g { background:var(--ok); box-shadow:0 0 12px var(--ok); }
  button { cursor:pointer; border:0; border-radius:10px; padding:.7rem 1rem; font-weight:600; margin:.25rem .25rem 0 0; }
  .go { background:var(--ok); color:#062; }
  .home { background:#4da3ff; color:#032; }
  .pts { background:#334; color:var(--text); }
  pre { background:#0c1118; padding:.75rem; border-radius:8px; overflow:auto; font-size:.78rem; max-height:220px; }
</style>
</head>
<body>
<header>
  <h1>Call Station Dashboard</h1>
  <div class="sub">ESP32 buttons → floor MQTT → Reeman SOP bridge → AMR</div>
</header>
<main>
  <section class="card">
    <div class="k">Phase</div>
    <div class="phase" id="phase">—</div>
    <div class="leds">
      <div class="led" id="ly" title="Yellow idle"></div>
      <div class="led" id="lg" title="Green job"></div>
      <div class="led" id="lr" title="Red error"></div>
    </div>
    <div style="margin-top:1rem">
      <button class="go" onclick="send('run_job')">▶ Run job (A→D→Home)</button>
      <button class="pts" onclick="fetch('/api/points',{method:'POST'})">Refresh points</button>
    </div>
  </section>
  <section class="card">
    <h3 style="margin-top:0">AMR status</h3>
    <div class="grid">
      <div class="k">Online</div><div class="v" id="online">—</div>
      <div class="k">Battery</div><div class="v" id="bat">—</div>
      <div class="k">E-stop</div><div class="v" id="estop">—</div>
      <div class="k">Navigating</div><div class="v" id="nav">—</div>
      <div class="k">Lifting</div><div class="v" id="lift">—</div>
      <div class="k">Target</div><div class="v" id="tgt">—</div>
      <div class="k">Map</div><div class="v" id="map">—</div>
    </div>
  </section>
  <section class="card">
    <h3 style="margin-top:0">Station / last events</h3>
    <pre id="log">waiting…</pre>
  </section>
</main>
<script>
const phaseLeds = {
  idle:[], connecting:[],
  to_pick:['g'], lifting:['g'],
  to_drop:['y'], placing:['y'],
  to_home:['r'], done:['r'],
  error:['r','y','g']
};
function paint(phase){
  ['lr','ly','lg'].forEach(id=>document.getElementById(id).className='led');
  const m={r:'lr',y:'ly',g:'lg'};
  (phaseLeds[phase]||[]).forEach(c=>document.getElementById(m[c]).classList.add('on-'+c));
}
async function poll(){
  const r = await fetch('/api/state'); const d = await r.json();
  document.getElementById('phase').textContent = d.phase;
  paint(d.phase);
  const s = d.robot || {};
  document.getElementById('online').textContent = d.online ? 'YES' : 'NO';
  document.getElementById('bat').textContent = (s.level ?? '—') + '%';
  document.getElementById('estop').textContent = s.emergencyButton===1 ? 'released' : (s.emergencyButton===0?'PRESSED':'—');
  document.getElementById('nav').textContent = String(!!s.isNavigating);
  document.getElementById('lift').textContent = String(!!s.isLifting);
  document.getElementById('tgt').textContent = (s.currentTask&&s.currentTask.targetPoint) || '—';
  document.getElementById('map').textContent = d.map || '—';
  document.getElementById('log').textContent = JSON.stringify({station:d.station,last_cmd:d.last_cmd,last_task:d.last_task},null,2);
}
async function send(cmd){
  if(!confirm('This can MOVE the forklift. Area clear + e-stop ready?')) return;
  await fetch('/api/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd})});
}
poll(); setInterval(poll, 1000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/api/state")
def api_state():
    with _lock:
        age = (time.time() - STATE["robot_ts"]) if STATE["robot_ts"] else None
        return jsonify({
            "phase": STATE["phase"],
            "robot": STATE["robot"],
            "station": STATE["station"],
            "last_cmd": STATE["last_cmd"],
            "last_task": STATE["last_task"],
            "map": STATE["map"],
            "online": bool(age is not None and age < 12),
            "job_active": STATE["job_active"],
            "cfg": {
                "pick": _cfg.get("pick"),
                "drop": _cfg.get("drop"),
                "home": _cfg.get("home"),
                "station_id": _cfg.get("station_id"),
            },
        })


@app.route("/api/cmd", methods=["POST"])
def api_cmd():
    cmd = (request.json or {}).get("cmd")
    if cmd == "run_job":
        start_job()
    elif cmd == "go_home":
        go_home()
    else:
        return jsonify({"ok": False, "error": "unknown cmd"}), 400
    return jsonify({"ok": True})


@app.route("/api/points", methods=["POST"])
def api_points():
    _forklift.request_points("auto_model")
    return jsonify({"ok": True})


def main():
    global _forklift, _cfg
    ap = argparse.ArgumentParser(description="Call-station bridge dashboard")
    ap.add_argument("--broker", required=True, help="PC Mosquitto IP")
    ap.add_argument("--broker-port", type=int, default=1883)
    ap.add_argument("--hostname", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--map", default=None)
    ap.add_argument("--pick", default="p1")
    ap.add_argument("--drop", default="p2")
    ap.add_argument("--home", default="home")
    ap.add_argument("--station-id", default="home1")
    ap.add_argument("--mqtt-user", default="")
    ap.add_argument("--mqtt-pass", default="")
    ap.add_argument("--http-port", type=int, default=5055)
    args = ap.parse_args()

    _cfg = {
        "pick": args.pick,
        "drop": args.drop,
        "home": args.home,
        "map": args.map,
        "station_id": args.station_id,
    }
    STATE["map"] = args.map

    ident = rfc.RobotIdentity(args.hostname, args.hostname, args.key, args.token, 9)
    codec = rfc.AesCodec(args.key)
    user = args.mqtt_user or None
    _forklift = rfc.ForkliftClient(
        ident, codec,
        broker=args.broker, broker_port=args.broker_port,
        mqtt_user=user, mqtt_pass=args.mqtt_pass or None,
        on_status=on_robot_status, on_points=on_points, on_task_result=on_task_result,
    )
    _forklift.connect()
    connect_floor(args.broker, args.broker_port, args.mqtt_user, args.mqtt_pass)
    time.sleep(1.5)
    _forklift.request_points("auto_model")

    log.info("Dashboard http://localhost:%d", args.http_port)
    app.run(host="0.0.0.0", port=args.http_port, threaded=True)


if __name__ == "__main__":
    main()
