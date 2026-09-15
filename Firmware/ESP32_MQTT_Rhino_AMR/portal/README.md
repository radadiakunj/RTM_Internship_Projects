# Reeman Calling API Web Portal

Browser portal that replaces MQTTX for **REEMAN CALLING API v2** testing.

## Terminal MQTT (AMR Nav IP :1883)

In one CMD window (listen to everything that comes back):

```bat
cd /d d:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\portal
npm run mqtt -- listen --host 192.168.5.75 --port 1883
```

If broker needs login:

```bat
npm run mqtt -- listen --host 192.168.5.75 --port 1883 --user YOUR_USER --pass YOUR_PASS
```

In a second CMD:

```bat
npm run mqtt -- guide
npm run mqtt -- hb
npm run mqtt -- points normal
npm run mqtt -- task normal PointA
```

Expected replies:
- `hb` → `reeman/calling/robot/{hostname}/v2/heartbeat`
- `points` → `.../points/response/normal_model` (`code` 0 + body)
- `task` → `.../task/response` (`code` 0 / 2003 etc.)

## Portal AMR Local MQTT

1. Profile: **AMR Local MQTT (Nav IP)**
2. Host `192.168.5.75`, Port `1883`
3. Fill MQTT Username/Password only if broker requires auth
4. Fill Calling Token (+ encryptKey for tasks)
5. Connect → Start heartbeat → watch message log / topic guide in section 7


No Mosquitto. No internet. One CMD:

```bat
cd /d d:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\portal
npm install
npm start
```

Open **http://localhost:3080**

1. Broker profile: **Local Embedded (no Wi-Fi)** — Host `127.0.0.1`, Port `2883`  
2. Token / encryptKey are prefilled for the offline demo (`demo-token` / `1234567890123456`)  
3. Click **Connect**  
4. Click **Start heartbeat** → robot status fills from the built-in mock AMR  
5. Request **Normal model** points → send a **Normal** task to `PointA`  
6. Watch the **message log**

`npm start` starts:
- Web UI on port **3080** (auto-falls back if busy)
- Embedded MQTT broker on **127.0.0.1:2883** (no Mosquitto, no Wi-Fi)
- Mock robot that answers Calling topics for offline practice

## Real robot (needs Wi-Fi + Reeman cloud)

1. Select **Cloud Calling** (`mqtt.rmbot.cn`)  
2. Paste real hostname / token / encryptKey (or use UDP pairing)  
3. Connect → Start heartbeat → points → tasks  

## Local Mosquitto (optional)

Select **Local Floor** if you already run Mosquitto on the LAN.

## Notes

- Offline mock ≠ real AMR. Real Calling API still needs cloud + robot pairing key.
- If port 1883 is busy, change `embeddedBroker.port` in `config.json`.
- Do not commit real secrets in `config.json`.
