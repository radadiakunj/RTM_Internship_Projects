# Reeman Forklift AMR — MQTT integration

Deliverables for integrating with a Reeman forklift AMR (robot type 9) over the
**Forklift Calling API (MQTT)**.

> **Architecture (confirmed by Reeman support):** you **self-host the MQTT
> broker**; the forklift connects to *you*. You do NOT use Reeman's cloud
> `mqtt.rmbot.cn`. For this forklift model, MQTT is the **only** way to make it
> move (the HTTP `/cmd/nav_name` API does not work on forklifts). Start with
> **[`LOCAL_BROKER_SETUP.md`](LOCAL_BROKER_SETUP.md)**.

| File | What it is |
|---|---|
| [`SOP_BEGINNER_GUIDE.md`](SOP_BEGINNER_GUIDE.md) | **Zero-to-moving for total beginners.** Plain-English, every step from installing Python to driving the forklift, written so a 15-year-old can follow it. Use this to hand the setup to someone else. |
| [`LOCAL_BROKER_SETUP.md`](LOCAL_BROKER_SETUP.md) | Faster setup reference for someone already comfortable with a terminal. |
| [`broker/mosquitto.conf`](broker/mosquitto.conf) | Ready-to-run broker config (anonymous for first test; password instructions inline). |
| [`INTEGRATION_SPEC.md`](INTEGRATION_SPEC.md) | English spec: connection params, security rules, topic map, payloads, a Mermaid **sequence diagram**, and the internal pick/drop choreography reference. |
| [`reeman_forklift_client.py`](reeman_forklift_client.py) | Runnable reference client: connect → heartbeat → query points → dispatch an auto-mode pallet task → monitor status. (`--discover` multicast pairing is optional; with a self-hosted broker you read creds off the forklift screen.) |
| [`dashboard.py`](dashboard.py) | **Live web dashboard.** Reuses the client; shows battery/e-stop/charge/nav/forks/queue in real time with buttons to send pick→drop jobs, multi-stop routes, and single-point moves. Open `http://localhost:5000`. |
| `requirements.txt` | `paho-mqtt`, `pycryptodome`, `Flask`. |

## Run the dashboard

```bash
pip install -r requirements.txt   # make sure the broker is running first
python dashboard.py --broker 192.168.68.61 --hostname rbot55f-260114-003-001 \
    --token "<TOKEN>" --key a5F6dmfr
# then open http://localhost:5000
```
The browser only talks to this local server — all MQTT + AES stays in Python. Every
"send" button asks for confirmation first (the forklift moves). There is no remote
stop over MQTT, so keep the physical e-stop in reach.

## Quick start

```bash
pip install -r requirements.txt

# Option A: auto-discover (put the robot in pairing mode first; you must be on
# the same LAN segment for the UDP multicast to arrive):
python reeman_forklift_client.py --discover --request-points --pick point1 --drop point2

# Option B: you already have the credentials from a previous pairing:
python reeman_forklift_client.py \
    --hostname reeman-test-001 --token <TOKEN> --key <ENCRYPT_KEY> \
    --request-points --pick point1 --drop point2
```

You'll see the robot's 5 s status heartbeats logged, plus the points response
and task-acceptance result.

## ⚠️ Before this works against a real robot

The vendor PDF does **not** specify the exact AES parameters for message
bodies. The client defaults to **AES-128/ECB/PKCS7/Base64** with the key
padded to 16 bytes — tune with `--aes-mode` / `--aes-encoding` (and the
`AesCodec` constructor) once Reeman confirms the real scheme. See
**§7 Open questions** in the spec. If the points response logs a
"Failed to decrypt" error, that's the parameter you need to fix.
