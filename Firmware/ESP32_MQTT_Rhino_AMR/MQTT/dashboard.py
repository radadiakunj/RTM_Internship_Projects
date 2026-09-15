#!/usr/bin/env python3
"""
Reeman forklift — live web dashboard.

Reuses reeman_forklift_client.ForkliftClient for ALL MQTT + AES work, so there is
one source of truth. This process:
  - holds the MQTT connection and heartbeat to the forklift,
  - remembers the latest status / points / task result,
  - serves a browser page that polls status and posts task commands.

The browser never speaks MQTT or does crypto — it only calls this local server.

Run:
    python dashboard.py --broker 192.168.68.61 --hostname rbot55f-260114-003-001 \
        --token "<TOKEN>" --key a5F6dmfr
Then open http://localhost:5000 in a browser.

Dependencies:  pip install -r requirements.txt   (adds Flask)
"""
from __future__ import annotations

import argparse
import logging
import threading
import time

from flask import Flask, Response, jsonify, request

import reeman_forklift_client as rfc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("dashboard")

app = Flask(__name__)

STATE = {
    "status": {},          # latest robot heartbeat (plain JSON, not encrypted)
    "status_ts": 0.0,      # unix time of last heartbeat
    "points": {},          # mode -> {code, data, ts}
    "last_task_result": None,
    "map": None,           # current map md5 (auto-filled from points if not given)
}
_client: rfc.ForkliftClient | None = None


# ---- MQTT callbacks: just stash the latest data ---------------------------- #
def on_status(s: dict):
    STATE["status"] = s
    STATE["status_ts"] = time.time()


def on_points(mode: str, code: int, data: dict):
    STATE["points"][mode] = {"code": code, "data": data, "ts": time.time()}
    # Auto-discover the map md5 from the first successful points response.
    if code == 0 and not STATE["map"]:
        model = (data or {}).get("model") or {}
        if model:
            STATE["map"] = next(iter(model.keys()))


def on_task_result(code: int, result: str):
    STATE["last_task_result"] = {"code": code, "result": result, "ts": time.time()}


# ---- HTTP API -------------------------------------------------------------- #
@app.route("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/api/status")
def api_status():
    age = (time.time() - STATE["status_ts"]) if STATE["status_ts"] else None
    return jsonify({
        "status": STATE["status"],
        "age": age,
        "online": (age is not None and age < 12),
        "points": STATE["points"],
        "last_task_result": STATE["last_task_result"],
        "map": STATE["map"],
    })


@app.route("/api/points", methods=["POST"])
def api_points():
    mode = (request.json or {}).get("mode", "auto_model")
    _client.request_points(mode)
    return jsonify({"ok": True})


@app.route("/api/goto", methods=["POST"])
def api_goto():
    point = (request.json or {})["point"]
    _client.send_calling_task(STATE["map"], point)
    log.info("WEB goto %s", point)
    return jsonify({"ok": True})


@app.route("/api/auto", methods=["POST"])
def api_auto():
    body = request.json or {}
    pick, drop = body["pick"], body["drop"]
    _client.send_auto_task([({"map": STATE["map"], "point": pick},
                             {"map": STATE["map"], "point": drop})])
    log.info("WEB auto %s -> %s", pick, drop)
    return jsonify({"ok": True})


@app.route("/api/route", methods=["POST"])
def api_route():
    pairs = (request.json or {})["pairs"]   # [[pick,drop], ...]
    pp = [({"map": STATE["map"], "point": a}, {"map": STATE["map"], "point": b})
          for a, b in pairs]
    _client.send_auto_task(pp)
    log.info("WEB route %s", pairs)
    return jsonify({"ok": True})


# ---- the page (single file, inline CSS + JS) ------------------------------- #
INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reeman Forklift — Live Dashboard</title>
<style>
  :root{--bg:#0f1217;--card:#1a1f29;--line:#2b323e;--txt:#e6e9ef;--mut:#8b94a3;
        --ok:#2ecc71;--bad:#e74c3c;--warn:#f1c40f;--accent:#3b8bd4;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 system-ui,Segoe UI,sans-serif}
  header{display:flex;align-items:center;gap:12px;padding:14px 20px;border-bottom:1px solid var(--line)}
  header h1{font-size:18px;margin:0;font-weight:600}
  .dot{width:12px;height:12px;border-radius:50%;background:var(--bad)}
  .dot.on{background:var(--ok)}
  .safety{background:#3a1212;color:#ffb3b3;border:1px solid #7a2a2a;border-radius:8px;
          margin:14px 20px;padding:10px 14px;font-size:13px}
  main{padding:0 20px 40px;max-width:1000px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
  .card .lbl{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
  .card .val{font-size:22px;font-weight:600;margin-top:6px}
  .badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:13px;font-weight:600}
  .b-ok{background:rgba(46,204,113,.15);color:var(--ok)}
  .b-bad{background:rgba(231,76,60,.15);color:var(--bad)}
  .b-mut{background:rgba(139,148,163,.15);color:var(--mut)}
  .b-warn{background:rgba(241,196,15,.15);color:var(--warn)}
  .bar{height:10px;border-radius:6px;background:var(--line);overflow:hidden;margin-top:10px}
  .bar > i{display:block;height:100%;background:var(--ok)}
  section.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}
  section.panel h2{margin:0 0 12px;font-size:15px}
  label{display:block;color:var(--mut);font-size:12px;margin:8px 0 4px}
  select,input{width:100%;padding:8px;background:var(--bg);color:var(--txt);
               border:1px solid var(--line);border-radius:8px;font-size:14px}
  .row{display:flex;gap:12px;flex-wrap:wrap}
  .row > div{flex:1;min-width:140px}
  button{margin-top:12px;padding:10px 16px;border:0;border-radius:8px;background:var(--accent);
         color:#fff;font-size:14px;font-weight:600;cursor:pointer}
  button.ghost{background:transparent;border:1px solid var(--line);color:var(--txt)}
  button:active{transform:translateY(1px)}
  .hint{color:var(--mut);font-size:12px;margin-top:6px}
  #result{margin-top:10px;font-size:13px}
  details{margin:16px 0;color:var(--mut)}
  pre{background:#0b0e13;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:12px}
  .pillrow{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
  .pill{background:var(--bg);border:1px solid var(--line);border-radius:20px;padding:4px 10px;font-size:12px}
</style>
</head>
<body>
<header>
  <span id="dot" class="dot"></span>
  <h1>Reeman Forklift — Live Dashboard</h1>
  <span id="host" class="hint" style="margin-left:auto"></span>
</header>

<div class="safety">⚠ No remote STOP exists over MQTT. Keep a hand on the physical e-stop.
  Every command below physically moves the forklift — clear the area first.</div>

<main>
  <div class="grid" id="cards"></div>

  <section class="panel">
    <h2>Send a pick → drop job</h2>
    <div class="row">
      <div><label>Pick point</label><select id="pick"></select></div>
      <div><label>Drop point</label><select id="drop"></select></div>
    </div>
    <button onclick="sendAuto()">▶ Send pick → drop (auto mode)</button>
    <button class="ghost" onclick="refreshPoints()">⟳ Refresh points</button>
    <div class="hint">Auto mode is the one your robot executes. Points load automatically.</div>
  </section>

  <section class="panel">
    <h2>Build a multi-stop route</h2>
    <div class="row">
      <div><label>Pick</label><select id="rpick"></select></div>
      <div><label>Drop</label><select id="rdrop"></select></div>
      <div style="flex:0"><label>&nbsp;</label><button class="ghost" onclick="addStop()">+ Add</button></div>
    </div>
    <div class="pillrow" id="routePills"></div>
    <button onclick="sendRoute()">▶ Send route</button>
    <button class="ghost" onclick="clearRoute()">Clear</button>
  </section>

  <section class="panel">
    <h2>Go to a single point (calling mode)</h2>
    <div class="row"><div><label>Point</label><select id="goto"></select></div></div>
    <button onclick="sendGoto()">▶ Go to point</button>
    <div class="hint">Note: only works if the robot's call module is switched to calling mode
      (yours is currently Auto mode, so this may be ignored).</div>
  </section>

  <div id="result"></div>

  <details><summary>Raw status JSON (all fields the robot sends)</summary>
    <pre id="raw">—</pre>
  </details>
</main>

<script>
let POINTS = [];        // list of point names
let ROUTE = [];         // [[pick,drop], ...]

function chargeText(c){return ({1:"Not charging",2:"Dock charging",3:"Cable charging",8:"Docking"})[c] || (c>8?"Charge fail":"—");}
function badge(on,tOn,tOff,invert){const cls=(on? (invert?"b-bad":"b-ok"):(invert?"b-ok":"b-mut"));return `<span class="badge ${cls}">${on?tOn:tOff}</span>`;}

async function poll(){
  try{
    const r = await fetch('/api/status'); const d = await r.json();
    document.getElementById('dot').className = 'dot' + (d.online?' on':'');
    document.getElementById('host').textContent =
      (d.map? 'map '+d.map.slice(0,8)+'… · ':'') + (d.online?'online':'offline');
    const s = d.status || {};
    const bat = s.level ?? '—';
    const estop = s.emergencyButton;          // 1 = released (good), 0 = pressed
    const cards = [
      {lbl:'Battery', html:`<div class="val">${bat}%</div><div class="bar"><i style="width:${bat||0}%;background:${bat<20?'var(--bad)':'var(--ok)'}"></i></div>`},
      {lbl:'E-stop', html:`<div class="val">${estop===1?badge(true,'Released ✓','',false):badge(true,'PRESSED','',true)}</div>`},
      {lbl:'Charging', html:`<div class="val" style="font-size:16px">${chargeText(s.chargeState)}</div>`},
      {lbl:'Navigating', html:`<div class="val">${badge(!!s.isNavigating,'Driving','Idle')}</div>`},
      {lbl:'Task running', html:`<div class="val">${badge(!!s.taskExecuting,'Yes','No')}</div>`},
      {lbl:'Forks', html:`<div class="val">${badge(!!s.isLifting,'Lifting','Still')} <span class="hint">${s.liftModelState===1?'high':'low'}</span></div>`},
      {lbl:'Current target', html:`<div class="val" style="font-size:18px">${(s.currentTask&&s.currentTask.targetPoint)||'—'}</div>`},
      {lbl:'Queue', html:`<div class="val">${(s.taskList||[]).length}</div>`},
    ];
    document.getElementById('cards').innerHTML =
      cards.map(c=>`<div class="card"><div class="lbl">${c.lbl}</div>${c.html}</div>`).join('');
    document.getElementById('raw').textContent = JSON.stringify(s, null, 2);

    if(d.last_task_result){
      const t=d.last_task_result;
      document.getElementById('result').innerHTML =
        `<span class="badge ${t.code===0?'b-ok':'b-bad'}">task result code ${t.code}</span> ${t.result||''}`;
    }
    // refresh point dropdowns from auto_model points
    const pm = d.points && d.points.auto_model;
    if(pm && pm.code===0){
      const model = (pm.data&&pm.data.model)||{};
      const names = [];
      for(const k in model){ (model[k]||[]).forEach(p=>names.push(p.name)); }
      if(JSON.stringify(names)!==JSON.stringify(POINTS)){ POINTS=names; fillSelects(); }
    }
  }catch(e){ document.getElementById('dot').className='dot'; }
}

function fillSelects(){
  const opts = POINTS.map(n=>`<option>${n}</option>`).join('');
  ['pick','drop','rpick','rdrop','goto'].forEach(id=>{
    const el=document.getElementById(id); const cur=el.value; el.innerHTML=opts; if(cur)el.value=cur;
  });
}
function renderRoute(){
  document.getElementById('routePills').innerHTML =
    ROUTE.map((p,i)=>`<span class="pill">${p[0]}→${p[1]} <a href="#" onclick="rmStop(${i});return false" style="color:var(--bad)">✕</a></span>`).join('');
}
function addStop(){ROUTE.push([rpick.value,rdrop.value]);renderRoute();}
function rmStop(i){ROUTE.splice(i,1);renderRoute();}
function clearRoute(){ROUTE=[];renderRoute();}

async function post(url,body){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
  return r.json();
}
function confirmMove(msg){return confirm("⚠ This will MOVE the forklift.\n"+msg+"\n\nIs the area clear and is someone on the e-stop?");}

function refreshPoints(){post('/api/points',{mode:'auto_model'});}
function sendAuto(){ if(!confirmMove(pick.value+" → "+drop.value)) return; post('/api/auto',{pick:pick.value,drop:drop.value}); }
function sendGoto(){ if(!confirmMove("go to "+goto.value)) return; post('/api/goto',{point:goto.value}); }
function sendRoute(){ if(ROUTE.length===0){alert("Add at least one stop.");return;} if(!confirmMove(ROUTE.length+" stop(s)")) return; post('/api/route',{pairs:ROUTE}); }

poll(); setInterval(poll, 1000);
</script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser(description="Reeman forklift live dashboard")
    ap.add_argument("--broker", required=True)
    ap.add_argument("--broker-port", type=int, default=1883)
    ap.add_argument("--hostname", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--map", default=None, help="map md5 (auto-discovered from points if omitted)")
    ap.add_argument("--mqtt-user", default="AGV")
    ap.add_argument("--mqtt-pass", default=None)
    ap.add_argument("--http-port", type=int, default=5000)
    args = ap.parse_args()

    STATE["map"] = args.map

    global _client
    ident = rfc.RobotIdentity(args.hostname, args.hostname, args.key, args.token, 9)
    codec = rfc.AesCodec(args.key)
    _client = rfc.ForkliftClient(
        ident, codec, broker=args.broker, broker_port=args.broker_port,
        mqtt_user=args.mqtt_user, mqtt_pass=args.mqtt_pass,
        on_status=on_status, on_points=on_points, on_task_result=on_task_result,
    )
    _client.connect()
    # fetch the point list shortly after connecting so the dropdowns populate
    threading.Timer(2.0, lambda: _client.request_points("auto_model")).start()

    log.info("Dashboard ready -> open http://localhost:%d", args.http_port)
    app.run(host="0.0.0.0", port=args.http_port, threaded=True)


if __name__ == "__main__":
    main()
