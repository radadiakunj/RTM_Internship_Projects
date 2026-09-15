# Call Station — Plug & Play (ESP32-S3 + AMR)

## Prefer no dashboard? (Task 4 / 5)

**Shareable SOP:** [`SOP_DIRECT_ESP32_AMR.md`](SOP_DIRECT_ESP32_AMR.md)  
**Short guide:** [`DIRECT_ESP32_GUIDE.md`](DIRECT_ESP32_GUIDE.md)  
**Firmware:** `firmware/direct_reeman_esp32s3/` — Serial **A**=home, **S**=p1. Laptop only needs Mosquitto.  
No `call_station_dashboard.py`.

---

Home call box (legacy bridge path): **White button** starts **Home → Point A (pick) → Point D (place) → Home**.  
LEDs: **Green** (→ Point A), **Yellow** (→ Point D), **Red** (→ Home). One White button = full trip.

See **[`REAL_WIFI_MQTT.md`](REAL_WIFI_MQTT.md)** for how ESP32 + laptop Mosquitto + AMR share Wi‑Fi.

```text
call_station/
  README.md
  DIRECT_ESP32_GUIDE.md          ← no-dashboard beginner guide
  CIRCUIT.md
  firmware/direct_reeman_esp32s3/  ← direct Reeman client (no Python bridge)
  firmware/call_station_esp32s3/   ← older floor MQTT + PC bridge
  bridge/call_station_dashboard.py ← PC bridge + web UI (optional legacy)
  wokwi/
```

## Simulation tools (before parts arrive)

| Tool | Use for | Real Wi‑Fi/MQTT? |
|------|---------|------------------|
| **`sim/firmware_visualizer.html`** | **Best:** visualize the real `.ino` (LEDs, buttons, MQTT, Serial, code path) | Simulated bus |
| **[Wokwi.com](https://wokwi.com)** | Hardware-like GPIO in browser | Simulated Wi‑Fi only |
| **Wokwi project in `wokwi/`** | Practice GPIO phases | No real AMR |
| **MQTTX** or mentor `MQTT/dashboard.py` | Practice broker + SOP | Yes, with Mosquitto |
| **This bridge dashboard** | Full job UI without ESP32 | Yes — click **Run job** |

### Open the firmware visualizer (no install)
```powershell
start "" "D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\call_station\sim\firmware_visualizer.html"
```
Or double-click `call_station\sim\firmware_visualizer.html`.

**Recommended practice path this week:**  
1) Firmware visualizer → 2) Mosquitto + bridge dashboard with AMR → 3) When hardware arrives, upload ESP32 and plug wires.

You **cannot** fully simulate Reeman AES Calling API inside free Wokwi; use the **PC bridge** for real AMR commands.

---

## When components arrive (checklist)

### 1. Power
- [ ] Set buck converter to **5.0 V** (multimeter) **before** connecting ESP32  
- [ ] Battery 12V → buck → ESP32 **5V + GND**  
- [ ] Common GND everywhere  

### 2. Wire
- Follow **[CIRCUIT.md](CIRCUIT.md)** pin table  
- Buttons: NO to GPIO and GND  
- 12V LED modules: via **MOSFET**, never 12V into ESP32 GPIO  

### 3. PC broker (mentor SOP)
```powershell
cd D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\SOP_broker
& "E:\mosquitto\mosquitto.exe" -c mosquitto.conf -v
```
Call Mode on AMR: **Server Address = YOUR_PC_IP**, port 1883.

### 4. Edit ESP32 `config.h`
File: `firmware/call_station_esp32s3/config.h`  
Set Wi‑Fi SSID/password, `MQTT_HOST` = PC IP, point names `Home` / `A` / `D` (must match map).

### 5. Upload firmware
Arduino IDE:
- Board: **ESP32S3 Dev Module**
- Libraries: **PubSubClient**, **ArduinoJson**
- Open `call_station_esp32s3.ino` → Upload → Serial 115200

### 6. Start bridge dashboard
```powershell
cd D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR
pip install -r requirements.txt
python call_station\bridge\call_station_dashboard.py `
  --broker YOUR_PC_IP --hostname rbot55f-260114-003-001 `
  --token "YOUR_TOKEN" --key a5F6dmfr `
  --pick A --drop D --home Home `
  --mqtt-user "" --mqtt-pass ""
```
Open **http://localhost:5055**

### 7. Test
1. Dashboard shows AMR battery / e-stop released  
2. Press **Run job** on web (e-stop ready) **or** White button on station  
3. Watch phase LEDs: Green → White → Blue → Yellow  

---

## Architecture (why a bridge?)

ESP32 handles **buttons + LEDs + Wi‑Fi**.  
PC bridge keeps mentor **SOP heartbeat + AES** and talks Reeman topics.  
That matches `MQTT/SOP_BEGINNER_GUIDE.md` and avoids fragile crypto on the MCU for v1.

```text
[Buttons/LEDs]—ESP32—floor MQTT—[Bridge dashboard]—Reeman MQTT—[AMR]
                              Mosquitto on PC
```

## Safety
- Clear path; hand on **physical e-stop** before any job  
- No remote e-stop over MQTT  
- Confirm point names with `--request-points` before first move  

## Share with others
Send them:
1. This `README.md`  
2. `CIRCUIT.md`  
3. Photo of your wired station (when built)  
4. Call Mode MQTT screenshot (host/token/key — don’t publish token publicly)
