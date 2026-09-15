# SOP — Project 2: Industrial 4×4 Numpad + Cloud Pallet ID

| Field | Value |
|--------|--------|
| **Project** | Project 2 — Industrial numpad + cloud pallet ID only |
| **Folder to share** | `call_station/project2_industrial_numpad_pallet/` (see `WHAT_TO_SHARE.md`) |
| **Firmware** | `firmware/industrial_numpad_demo/` |
| **Cloud** | `cloud/` → `http://LAPTOP_IP:3081` |
| **Revision** | **2.1** — 2026-08-24 |
| **Audience** | Operators, engineers, mentors |
| **Scope** | **Numpad + LCD + cloud only** — no robot / AMR content in this document |

> **Idea in one sentence:** Type a pallet number on the **4×4 telephone keypad**, press **A**, and that ID is stored in the cloud as **warehouse placement validated**. Download the list in **Excel**. Only an **administrator** can void a wrong ID.

Read also: [`SHOWCASE_PALLET_VALIDATION.md`](SHOWCASE_PALLET_VALIDATION.md) · [`WIRING.md`](WIRING.md) · [`../WHAT_TO_SHARE.md`](../WHAT_TO_SHARE.md)

---

## 1. Purpose (warehouse validation)

| Step | What happens | Why it matters |
|------|----------------|----------------|
| 1 | Operator types integer digits on **4×4 Matrix 16-key** keypad | Identifies the physical pallet |
| 2 | Presses **A** | Confirms “this pallet is **placed** / logged in the warehouse” |
| 3 | Cloud stores `palletId` + time + station + status **`placed`** | Digital proof / audit trail |
| 4 | Anyone can **Download Excel** | Mentors / warehouse see the list in Microsoft Excel |
| 5 | Admin **Void** only | Wrong IDs corrected without operators deleting history |

This SOP covers **only** the industrial numpad station and its cloud log.

---

## 2. What folder / code to share

**Share the entire directory:**

`call_station/project2_industrial_numpad_pallet/`

| Must include | Optional |
|--------------|----------|
| `docs/`, `firmware/industrial_numpad_demo/` (with `config.h.example`), `cloud/` (with `config.example.json`), `README.md`, `WHAT_TO_SHARE.md`, `FOLDER_INDEX.md` | `node_modules` (or run `npm install` on the other PC) |

**Do not share** real Wi‑Fi passwords / admin passwords in `config.h` or `cloud/config.json`.

---

## 3. Architecture

```text
[4×4 telephone keypad + I2C LCD]
        │  digits + A
        ▼
   ESP32-S3  ──Wi‑Fi MQTT──►  Mosquitto :1883
                                    │
                                    ▼
                             Project 2 cloud :3081
                                    │
                             pallets.json + Web UI
                                    │
                             Download Excel / CSV / JSON
                                    │
                             Admin Void only
```

Topic: **`callstation/pallet/record`**

---

## 4. Operator procedure

1. Power the station (USB **or** pack **~6.3 V** → buck **5.0 V** → ESP **5V** / **GND**).  
2. Wait LCD: `Enter pallet` (Wi‑Fi + MQTT connected).  
3. Type digits `0–9` (example `1042`). LCD: `ID: 1042`.  
4. `*` = backspace · `#` = clear all.  
5. Press **A**:
   - Empty → `Need pallet ID`.  
   - OK → cloud status **`placed`** · LCD `Placed OK` · meaning: **warehouse placement validated**.  
6. Press **C** → clears local buffer only (**does not** remove the cloud row).

---

## 5. Admin / mentor procedure (cloud)

1. Open `http://LAPTOP_IP:3081`.  
2. See live pallet table (auto-refresh).  
3. **Download Excel** → opens in Microsoft Excel (also CSV / JSON available).  
4. **Login** with admin password → **Void** wrong IDs.  
5. Change `adminPassword` in `cloud/config.json` before real use.

---

## 6. What to change in code (numpad project only)

All settings for this project live in:

`firmware/industrial_numpad_demo/config.h`

| If you need to change… | Edit in `config.h` | Then |
|------------------------|--------------------|------|
| Wi‑Fi name / password | `WIFI_SSID`, `WIFI_PASSWORD` | Re-upload firmware |
| Mosquitto PC IP | `MQTT_HOST`, `MQTT_PORT` | Re-upload |
| Station name shown in cloud | `STATION_ID` | Re-upload |
| MQTT topic | `PALLET_TOPIC` (default `callstation/pallet/record`) | Match cloud `config.json` |
| LCD I2C address | `LCD_I2C_ADDR` (`0x27` or `0x3F`) | Re-upload |
| LCD pins | `LCD_SDA_PIN`, `LCD_SCL_PIN` | Match wiring |
| Max ID length | `PALLET_ID_MAX` | Re-upload |

Cloud side: `cloud/config.json` (copy from `config.example.json`)

| Setting | Meaning |
|---------|---------|
| `httpPort` | Web UI port (default **3081**) |
| `adminPassword` | Admin void login |
| `mqtt.host` / `mqtt.port` | Same broker the ESP uses |
| `palletHistory.topic` | Must match `PALLET_TOPIC` |

If keypad letters are wrong, edit the `keys[][]` map in `industrial_numpad_demo.ino` (not AMR-related).

---

## 7. ESP32-S3 GPIO map (industrial numpad only)

| Function | Component | GPIO / net | Notes |
|----------|-----------|------------|--------|
| Keypad rows 1–4 | 4×4 matrix 16-key panel | **12, 11, 10, 8** | Signal only |
| Keypad cols 1–4 | same | **5, 4, 7, 6** | Library pull-ups |
| LCD SDA | 16×2 I2C | **GPIO 1** | |
| LCD SCL | 16×2 I2C | **GPIO 2** | |
| LCD VCC / GND | backpack | **5 V / GND** | Address often **0x27** |
| Onboard RGB | DevKit | **GPIO 48** | Optional / unused by place logic |
| Common GND | All | **GND** | |

**Keys:** `0–9` digits · `*` backspace · `#` clear · **A** place/validate · **C** clear local.

---

## 8. Components, voltage, and current (estimates)

### 8.1 Battery → 5 V

| Item | Value |
|------|--------|
| Cells | **4 × ~1.57 V** |
| Pack | **~6.3 V** |
| Buck OUT | **5.0 V** (set with multimeter before connecting ESP) |
| Path | Pack → Buck → ESP **5V** + **GND** |

### 8.2 Per component (@ ~5 V rail)

| Component | Qty | Supply | Typical | Notes |
|-----------|-----|--------|---------|--------|
| ESP32-S3 Dev Module | 1 | 5 V | **150–300 mA** | Wi‑Fi TX peaks **~350–500 mA** |
| 16×2 I2C LCD + backlight | 1 | 5 V | **20–50 mA** | Backlight dominates |
| 4×4 keypad | 1 | GPIO | **≪ 1 mA** | Scan / pull-ups only |
| Buck losses | 1 | 6.3→5 V | — | ~85–90% efficiency |

### 8.3 Total budget

| Scenario | ~5 V load | ~6.3 V battery\* | Buck size |
|----------|-----------|------------------|-----------|
| Idle connected | **180–280 mA** | **~170–260 mA** | |
| Typing + MQTT publish burst | **250–450 mA** | **~230–410 mA** | |
| Design / buy | | | **≥ 1 A @ 5 V** |


**Rule of thumb:** plan **~0.4–0.5 A** average on 5 V; use a **≥ 1 A** buck from **~6.3 V**.

---

## 9. Display / timing (this project)

| Item | Behavior |
|------|----------|
| Feedback | **LCD only** (`Placed OK` / `Need pallet ID`) |
| Status LEDs G/Y/R | **Not used** in this project |
| Key debounce | Handled by **Keypad** library (typically tens of ms) |
| After successful **A** | LCD shows success ~**1.2 s**, then back to enter ID |

---

## 10. Cloud data model

File: `cloud/data/pallets.json`

| Field | Example | Meaning |
|-------|---------|---------|
| `palletId` | `"1042"` | Typed on keypad |
| `status` | `"placed"` | Warehouse placement **validated** |
| `purpose` | `"Warehouse placement validated"` | Showcase / audit text |
| `stationId` | `"esp-numpad-1"` | Which box logged it |
| `missionId` | `1` | Local counter on the ESP |
| `createdAt` / `updatedAt` | epoch ms | When logged |
| `voidedBy` / `voidedAt` | admin | Soft delete |

MQTT example:

```json
{
  "palletId": "1042",
  "stationId": "esp-numpad-1",
  "status": "placed",
  "purpose": "Warehouse placement validated",
  "action": "upsert",
  "missionId": 1,
  "notes": "A pressed — warehouse placement validated"
}
```

---

## 11. HTTP API

| Method | Path | Auth | Behavior |
|--------|------|------|----------|
| `GET` | `/api/pallets` | none | List |
| `GET` | `/api/pallets/export.xls` | none | **Excel** (opens in Microsoft Excel) |
| `GET` | `/api/pallets/export.csv` | none | CSV (also opens in Excel) |
| `GET` | `/api/pallets/export.json` | none | JSON |
| `POST` | `/api/admin/login` | password | Admin token |
| `POST` | `/api/pallets/:id/void` | admin | Soft-delete |

Station firmware **must never** call void.

---

## 12. Safety (numpad station)

- Never put **5 V** into keypad GPIO columns as a power feed.  
- ESP32 GPIO logic is **3.3 V**.  
- **C** clears the local ID buffer only — it does **not** delete cloud rows.  
- Change the default admin password before site use.  
- Set buck to **exactly 5.0 V** before connecting the ESP.

---

## 13. Test plan

| # | Test | Pass |
|---|------|------|
| 1 | Type digits on 4×4 | LCD shows ID |
| 2 | A empty | Rejected |
| 3 | A with ID | Cloud row **placed** + purpose text |
| 4 | Download Excel | Opens in Excel with pallet IDs |
| 5 | Void without login | Denied |
| 6 | Admin void | status `void` |
| 7 | C after A | Buffer clear; cloud row remains |

---

## 14. Quick start

```powershell
cd call_station\project2_industrial_numpad_pallet\cloud
copy config.example.json config.json
npm install
npm start
```

Upload `firmware/industrial_numpad_demo/industrial_numpad_demo.ino` (edit `config.h` first).  
Open `http://localhost:3081`.

---

## Revision

| Rev | Date | Notes |
|-----|------|--------|
| 1.0 | 2026-08-23 | Demo firmware + cloud |
| 2.0 | 2026-08-24 | Warehouse **placed**; Excel; GPIO/power |
| **2.1** | **2026-08-24** | SOP scope = **industrial numpad only** (AMR content removed) |
