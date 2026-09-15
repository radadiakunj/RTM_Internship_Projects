# Direct ESP32 → AMR — keypad, LCD, mission history

**You do not run `call_station_dashboard.py`.**  
Laptop needs **Mosquitto** plus the **browser portal** for mission history.

## Flow

```text
1) Power ESP32 (USB-C or 5V+GND) or press RST
2) Wi-Fi connects; LCD shows status
3) MQTT connects to Mosquitto on laptop
4) Wait until AMR STATUS appears (Ready on LCD)
5) Use 4x4 keypad A / B / C / D
```

## Keypad map

| Key | Action |
|-----|--------|
| **A** | Full job: pick **p2** → place **p3** → return **home** (forks operate) |
| **B** | Store mission record to browser portal (`callstation/mission/record`) |
| **C** | Cancel **ESP32 workflow state only** (physical e-stop still required) |
| **D** | Navigate **home** only — no fork action |

Serial Monitor at **115200** mirrors the same **A/B/C/D** keys for debug.  
GPIO4 cancel button still clears ESP32 job state.

## LCD messages (16×2 I2C)

| Phase | Line 1 | Line 2 |
|-------|--------|--------|
| Ready | `Ready at home` | `A=job D=home` |
| Job start | `From home` | `Going p2 pick` |
| Pick/place | `Pick/place` or `At p2` | `p2 -> p3` / `Picking pallet` |
| After place | `Place done` | `Return home soon` |
| Return | `Return home` | battery / mission # |
| Complete | `Job complete` | `home p2 p3 done` |
| Store (B) | `Mission #N` | `stored` |

## Wiring (ESP32-S3 DevKit)

### 4×4 matrix keypad (8 pins)

Keypad layout:

```text
1  2  3  A
4  5  6  B
7  8  9  C
*  0  #  D
```

| Keypad pin | ESP32 GPIO | Notes |
|------------|------------|-------|
| Row 1 | GPIO **1** | matrix row |
| Row 2 | GPIO **2** | matrix row |
| Row 3 | GPIO **5** | matrix row |
| Row 4 | GPIO **6** | matrix row |
| Col 1 | GPIO **7** | matrix column (internal pull-up) |
| Col 2 | GPIO **10** | matrix column |
| Col 3 | GPIO **11** | matrix column |
| Col 4 | GPIO **12** | matrix column |

Also connect keypad **VCC** → **3.3 V**, **GND** → **GND**.

### 16×2 I2C LCD (PCF8574 backpack, 4 pins)

| LCD pin | ESP32 | Notes |
|---------|-------|-------|
| GND | GND | common ground |
| VCC | **5 V** (or 3.3 V if module label allows) | do not use 12 V |
| SDA | GPIO **15** | I2C data |
| SCL | GPIO **16** | I2C clock |

Default I2C address: **0x27**. If the display stays blank, change `LCD_I2C_ADDR` in `config.h` to **0x3F** or check Serial I2C scan on boot.

### Existing pins (keep as-is)

| Function | GPIO |
|----------|------|
| Cancel button | **4** (INPUT_PULLUP) |
| Onboard RGB LED | **48** |

**Avoid:** GPIO 0, 3, 43, 44, 45, 46 (strapping / USB serial).

## Mission history (browser “cloud”)

This is **not** internet cloud. Records are stored on the **laptop** and viewed in a browser on the same Wi‑Fi.

1. Start Mosquitto on the laptop.
2. Start portal:

```powershell
cd portal
npm install
npm start
```

3. Open **`http://LAPTOP_IP:3080`** on the laptop or mentor phone/tablet (same Wi‑Fi).
4. After a job (or while in progress), press keypad **B**.
5. LCD shows **`Mission #N stored`**. Portal section **9. Call-station mission history** updates.

Records persist in `portal/data/missions.json` across portal restarts.

## Architecture

```text
ESP32 + keypad + LCD
   |-- encrypted Reeman tasks --> Mosquitto --> AMR Call Mode
   |-- plain mission JSON -----> Mosquitto --> portal (browser at :3080)
```

## Setup once

1. Mosquitto service **Running** / Automatic  
2. Wire keypad + LCD as above  
3. Edit [`firmware/direct_reeman_esp32s3/config.h`](firmware/direct_reeman_esp32s3/config.h):
   - Wi‑Fi, `MQTT_HOST`, token, hostname, points  
   - keypad/LCD pins if your wiring differs  
4. AMR Call Mode Host = laptop IP, port `1883`  
5. Upload `direct_reeman_esp32s3.ino` (PubSubClient + ArduinoJson; no extra LCD library needed)

## Prerequisite (hardware test last)

```powershell
python MQTT\reeman_forklift_client.py --broker LAPTOP_IP --hostname HOST --token "TOKEN" --key a5F6dmfr --pick p2 --drop p3
python MQTT\reeman_forklift_client.py --broker LAPTOP_IP --hostname HOST --token "TOKEN" --key a5F6dmfr --goto home
```

Supervised keypad order:

1. **D** — navigate home only  
2. **A** — full pick → place → home (pallet at p2, path clear, e-stop ready)  
3. **B** — store mission; confirm on browser portal  

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Blank LCD | Check 5 V/GND; try address 0x3F; read Serial I2C scan |
| Wrong keys | Swap row/column wires; verify KEY_MAP matches keypad silkscreen |
| Mission not in portal | Start `npm start` in `portal/`; Mosquitto running; same `MQTT_HOST` |
| Mentor cannot open portal | Windows firewall allow port **3080**; use laptop Wi‑Fi IP |

## Files

- `firmware/direct_reeman_esp32s3/direct_reeman_esp32s3.ino`
- `firmware/direct_reeman_esp32s3/config.h`
- `firmware/direct_reeman_esp32s3/lcd_i2c.h`
- `portal/server.js` + `portal/public/index.html`
- `portal/data/missions.json` (created on first store)
