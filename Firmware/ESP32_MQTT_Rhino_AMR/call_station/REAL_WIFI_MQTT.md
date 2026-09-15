# Real Wi‑Fi + MQTT picture (ESP32 between laptop and AMR)

## Who talks to whom?

```text
                 SAME Wi‑Fi: RTM_Speed / 1234
  ┌──────────────┐         ┌─────────────────────┐         ┌──────────────┐
  │ ESP32-S3     │         │  YOUR LAPTOP          │         │ Reeman AMR   │
  │ call station │◄──MQTT─►│  Mosquitto :1883      │◄──MQTT─►│ Call Mode    │
  │ White button │         │  IP e.g. 192.168.5.117│         │ (forklift)   │
  │ Y / G / R    │         │  + bridge / client     │         └──────────────┘
  └──────────────┘         └─────────────────────┘
```

Important:
- ESP32 and AMR both join **`RTM_Speed`**.
- MQTT broker is the **laptop** (Mosquitto), **not** the AMR IP.
- On AMR Call Mode → MQTT Configuration → **Server Address = laptop IP**.
- ESP32 `config.h` → `MQTT_HOST` = **same laptop IP**.

ESP32 never sends AES Reeman task bodies. It only publishes:

```json
{"cmd":"run_job","station":"home1","home":"Home","pick":"A","drop":"D"}
```

to `floor/callstation/home1/cmd`.  
The **bridge** turns that into mentor SOP `task/auto_model` + go Home.

---

## Terminal order (with ESP32 plugged in)

### Window 1 — broker
```powershell
cd "D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\SOP_broker"
& "E:\mosquitto\mosquitto.exe" -c "mosquitto.conf" -v
```
Leave open. You should later see ESP32 and AMR connect.

### Window 2 — bridge (preferred with ESP32)
```powershell
cd "D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR"
python call_station\bridge\call_station_dashboard.py `
  --broker 192.168.5.117 --hostname rbot55f-260114-003-001 `
  --token "YOUR_TOKEN" --key a5F6dmfr `
  --pick A --drop D --home Home `
  --mqtt-user "" --mqtt-pass ""
```
Open http://localhost:5055

Your old steps 2–3 (`reeman_forklift_client.py` status / `--request-points`) are still useful for **manual** testing **without** ESP32. With ESP32, use the **bridge** so button presses become AMR jobs.

### ESP32 (Arduino IDE)
1. Edit `firmware/call_station_esp32s3/config.h`:
   - `WIFI_SSID` = `RTM_Speed`
   - `WIFI_PASSWORD` = `1234`
   - `MQTT_HOST` = laptop IP (from `ipconfig`)
2. Board: **ESP32S3 Dev Module**
3. Libraries: **PubSubClient**, **ArduinoJson**
4. Upload `call_station_esp32s3.ino`
5. Serial Monitor 115200 → should show WiFi + MQTT connected, Yellow LED on (idle)

### Press White button
1. ESP32 publishes `run_job` (one press = full trip)
2. Bridge sends Reeman auto task **A → D**, then **Home**
3. LEDs during that single operation:
   - **Green** while going to Point A / picking  
   - **Yellow** while going to / at Point D  
   - **Red** while returning Home  
   - all off when idle again

---

## Hardware (updated)

| Part | GPIO |
|------|------|
| White START button (to GND) | **4** |
| Yellow LED module drive | **7** |
| Green LED module drive | **8** |
| Red LED module drive | **6** |

No blue button. No white/blue signal lamps — only **Y / G / R**.
