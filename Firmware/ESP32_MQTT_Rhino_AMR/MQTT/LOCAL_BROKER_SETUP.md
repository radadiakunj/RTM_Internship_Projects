# Local MQTT broker setup — Reeman forklift

Per Reeman support: **you host the MQTT broker**, the forklift connects to it,
and your controller client connects to it too. This is the confirmed, correct
architecture (NOT connecting to Reeman's `mqtt.rmbot.cn`). For the forklift,
MQTT is the **only** way to make it move — the HTTP `/cmd/nav_name` API does
not work on this model.

```
  ┌──────────────┐        ┌─────────────────────┐        ┌──────────────┐
  │ Your client  │ ─────▶ │  YOUR broker         │ ◀───── │  Forklift    │
  │ (python)     │ ◀───── │  (Mosquitto on PC)   │ ─────▶ │  Android app │
  └──────────────┘        │  192.168.10.123:1883 │        └──────────────┘
                          └─────────────────────┘
```

Your PC's robot-facing IP is **`192.168.10.123`** (the "Ethernet 2" adapter).
That is the broker address you'll type into the forklift.

---

## Step 1 — Install Mosquitto on your PC
- Download from https://mosquitto.org/download/ (Windows installer) **or**
  `winget install EclipseFoundation.Mosquitto`.
- Default install dir: `C:\Program Files\mosquitto\`.

## Step 2 — Open the Windows firewall for port 1883 (CRITICAL)
The forklift connects **inbound** to your PC, so Windows Firewall must allow it.
Run PowerShell **as Administrator**:
```powershell
New-NetFirewallRule -DisplayName "Mosquitto 1883" -Direction Inbound `
  -Protocol TCP -LocalPort 1883 -Action Allow
```
> If you skip this, the forklift simply won't be able to connect and you'll
> see nothing — no error, just silence.

## Step 3 — Start the broker with the provided config
```powershell
cd "D:\Maulik\reeman-forklift-mqtt\broker"
& "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf -v
```
Leave this window open. `-v` (verbose) prints every connection and message —
your live view of what's happening. Stage-1 config allows anonymous access, so
no credentials are needed yet.

## Step 4 — Sanity-check the broker locally
In another window (MQTTX or mosquitto_sub), connect to `localhost:1883` and
subscribe to `#`. Publish a test message; you should see it echo. This proves
the broker runs before you involve the robot.

## Step 5 — Point the forklift at your broker
On the forklift's **MQTT Configuration** screen, set:

| Field | Value |
|---|---|
| Server Address (Host) | `192.168.10.123`  ← your PC's IP |
| Port | `1883` |
| Username | leave blank for Stage 1 (or your chosen user in Stage 2) |
| Password | leave blank for Stage 1 |
| Encryption Key | keep `a5F6dmfr` (this is the AES key; note it for the client) |
| Token | keep the shown token (note it for the client; don't regenerate unless you re-copy it) |

**Save**, then enable/connect the call module. Watch your mosquitto `-v`
window — you should see the forklift connect and a
`reeman/calling/robot/<hostname>/forklift/heartbeat` publish appear.

## Step 6 — Run your controller client against your broker
```powershell
python reeman_forklift_client.py `
  --broker 192.168.10.123 --broker-port 1883 `
  --hostname rbot55f-260114-003-001 `
  --token <TOKEN_FROM_SCREEN> --key a5F6dmfr
```
(Add `--mqtt-user/--mqtt-pass` only once you move to Stage 2 auth.) You should
see the robot's 5-second status heartbeat with live battery %. **That's the
milestone.**

## Step 7 — Then points, then movement
- `--request-points` to fetch points (first thing that needs AES to decode).
- `--pick <point> --drop <point>` to dispatch a real task (robot moves — clear
  the area, hand on the e-stop).

---

## Notes & gotchas
- **`192.168.10.x` subnet warning:** Reeman docs flag the `.10.` subnet as
  problematic for their nav system. MQTT to your broker may be fine, but if the
  forklift won't connect or misbehaves, moving its network off `.10.` is the
  first thing to try.
- **Keep one broker, one source of truth:** the Encryption Key and Token on the
  forklift screen must match exactly what your client uses.
- **AES still applies:** heartbeats need only the token (no encryption), but
  points and task bodies are AES-encrypted with the Encryption Key. If point
  decoding fails, confirm the AES mode/padding with Reeman (see
  `INTEGRATION_SPEC.md` §7).
- **Optional simplification:** the Encryption Key field is editable. Setting it
  to an exact 16-character value removes the key-length guesswork for AES-128
  (you'd update `--key` to match), though mode/padding still need confirming.
