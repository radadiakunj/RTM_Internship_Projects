# Call Station — Folder Index

Complete map of everything under `call_station/`.  
**Production path today:** panel **Task-14** → `firmware/direct_reeman_esp32s3/` + `SOP_DIRECT_ESP32_AMR.md`.

| Field | Value |
|--------|--------|
| **Root** | `call_station/` |
| **Updated** | 2026-08-23 |
| **Related (outside this folder)** | `portal/` (mission web UI), `MQTT/` (PC test client), `SOP_Broker/` (Mosquitto) |

---

## Start here (by role)

| Role | Read / use |
|------|------------|
| **Operator (panel)** | [`SOP_DIRECT_ESP32_AMR.md`](SOP_DIRECT_ESP32_AMR.md) § Quick start → Task-14 |
| **Engineer (upload)** | `firmware/direct_reeman_esp32s3/config.h` → upload `direct_reeman_esp32s3.ino` |
| **Wiring / mentor** | [`panel_circuit_sim/index.html`](panel_circuit_sim/index.html) + [`SOP_DIRECT_ESP32_AMR.md`](SOP_DIRECT_ESP32_AMR.md) §5.6 |
| **Hardware test (no AMR)** | `firmware/panel_latch_led_test/panel_latch_led_test.ino` |
| **Lab (keypad + LCD)** | `firmware/lcd_keypad_demo/` + set `UI_MODE 0` in `config.h` |

---

## Folder tree

```text
call_station/
├── project2_industrial_numpad_pallet/  ← Project 2: numpad + cloud pallet ID
├── FOLDER_INDEX.md              ← this file
├── PROJECTS_KEYPAD_PALLET_CLOUD.md ← Project 1 + Project 2 overview
├── README.md                    ← legacy overview + bridge path
├── SOP_DIRECT_ESP32_AMR.md      ← main SOP (Task-14 panel + lab keypad)
├── DIRECT_ESP32_GUIDE.md        ← short direct-ESP32 guide (older keypad notes)
├── CIRCUIT.md                   ← legacy circuit (bridge + old point names)
├── REAL_WIFI_MQTT.md            ← Wi-Fi + Mosquitto + AMR topology
├── How_to_Use_MQTT_with_ESP32_Step_by_Step.ino  ← beginner MQTT sketch (root)
│
├── panel_circuit_sim/           ← interactive Task-14 schematic (browser)
├── firmware/                    ← all Arduino sketches
├── sim/                         ← HTML firmware visualizers + open scripts
├── bridge/                      ← optional Python PC bridge (legacy)
└── wokwi/                       ← Wokwi browser sim project
```

---

## Top-level documents

| File | Purpose | Status |
|------|---------|--------|
| **SOP_DIRECT_ESP32_AMR.md** | Full site SOP: Task-14 panel, lab keypad, wiring, safety, troubleshooting, revision history | **Current production doc** |
| **PROJECTS_KEYPAD_PALLET_CLOUD.md** | Project 1 + Project 2 overview | Dual-project plan |
| **SHARE_KNOWLEDGE_TRANSFER.md** | Exact zip lists for Project 1 vs Project 2 knowledge transfer | **Use this to share** |
| **project2_industrial_numpad_pallet/** | Project 2 code + SOP: industrial numpad firmware + pallet cloud (3081) | **Project 2 home** |
| **FOLDER_INDEX.md** | Inventory of everything in `call_station/` | This file |
| **README.md** | Project intro; mentions bridge dashboard and older “White button” job | Partially legacy — use SOP for panel |
| **DIRECT_ESP32_GUIDE.md** | Short guide for direct ESP32→AMR (keypad/LCD era) | Supplement; keypad pins may differ from current `config.h` |
| **CIRCUIT.md** | Block diagram + GPIO for bridge-era station (points A/D, MOSFET LEDs) | **Legacy** — panel wiring is in SOP §5.6 + `panel_circuit_sim/` |
| **REAL_WIFI_MQTT.md** | How ESP32, laptop Mosquitto, and AMR share the network | Still useful |
| **How_to_Use_MQTT_with_ESP32_Step_by_Step.ino** | Standalone MQTT learning sketch at repo root of `call_station/` | Tutorial only |

---

## `project2_industrial_numpad_pallet/` — Project 2 home

| Path | Purpose |
|------|---------|
| **README.md** | Quick start |
| **docs/SOP_PROJECT2.md** | Full Project 2 SOP |
| **docs/WIRING.md** | Numpad + LCD pins |
| **firmware/industrial_numpad_demo/** | ESP32-S3: type ID → A → MQTT `callstation/pallet/record` |
| **cloud/** | Node server port **3081**: list, CSV/JSON download, admin void |

---

## `panel_circuit_sim/` — Task-14 circuit teaching tool

| File | Purpose |
|------|---------|
| **index.html** | Interactive schematic: White = power latch, Blue = GPIO7 Task-14 latch, G/Y/R status LEDs, wire open/closed animation |
| **README.md** | How to open the sim, Task-14 LED sequence, net list, mentor notes (no 10k series on blue GPIO path) |

**No upload required.** Open `index.html` in a browser.

---

## `firmware/` — Arduino projects

### Production — `direct_reeman_esp32s3/`

| File | Purpose |
|------|---------|
| **direct_reeman_esp32s3.ino** | Main firmware: MQTT Call Mode, AES tasks, mission portal events, **UI_MODE 1 = Task-14 panel**, UI_MODE 0 = lab tactile+LCD |
| **config.h** | Wi-Fi, Mosquitto, robot token, map points (`home`, `charge`, `p2`, `p3`), panel GPIO pins, `UI_MODE` |
| **config.h.example** | Template without secrets — copy to `config.h` |
| **lcd_i2c.h** | I2C LCD helper (used when `UI_MODE=0`) |
| **verify_aes.py** | Verify AES encryption matches Python client |
| **sync_credentials.py** / **sync_credentials.bat** | Helper to sync credentials into `config.h` |

**Panel Task-14 (`UI_MODE=1`):**

| Control | GPIO / net |
|---------|------------|
| White power latch | Battery B+ ↔ Buck IN+ (not GPIO; `LATCH_START_PIN=-1`) |
| Blue Task-14 latch | **GPIO7** ↔ GND |
| White / Blue ring LED+ | **GPIO13** / **GPIO14** |
| Green / Yellow / Red IN | **GPIO10** / **11** / **12** |
| Status module VCC | common GND |

**Task-14 LEDs:** Green (start home) → Yellow (p2 pick) → Red (return home) → all OFF (done).

---

### Panel hardware test — `panel_latch_led_test/`

| File | Purpose |
|------|---------|
| **panel_latch_led_test.ino** | Standalone test: no Wi-Fi, no AMR. Blue latch + status LEDs + ring GPIO. Upload before main firmware to verify wiring. |

---

### Lab / bring-up sketches

| Folder / file | Purpose |
|---------------|---------|
| **lcd_keypad_demo/** | Working LCD + keypad demo (user reference — do not overwrite) |
| **lcd_keypad_demo/lcd_keypad_demo.ino** | Demo sketch |
| **lcd_keypad_demo/lcd_i2c.h** | Shared LCD driver |
| **lcd_keypad_demo/README.md** | Demo notes |
| **lcd_i2c_scanner/** | I2C bus scan + LCD probe |
| **lcd_i2c_scanner/lcd_i2c_scanner.ino** | Scanner sketch |
| **lcd_i2c_scanner/lcd_i2c.h** | LCD driver |
| **lcd_i2c_scanner/README.md** | Scanner instructions |
| **keypad_test/** | 4×4 keypad → Serial keys |
| **keypad_test/keypad_test.ino** | Keypad test |
| **keypad_test/KEYPAD_10PIN_GUIDE.md** | 10-pin keypad wiring |
| **keypad_test/LIBRARIES.md** | Required Arduino libraries |
| **keypad_wire_finder/** | Find row/col wires on unknown keypad |
| **keypad_wire_finder/keypad_wire_finder.ino** | Wire-finder sketch |
| **Keypad4_4/** | Minimal 4×4 keypad example |
| **MembraneKeypad1_4/** | Membrane keypad example |
| **blink_s3_gpio48/** | Blink onboard RGB (GPIO48) sanity check |

---

### Legacy / alternate firmware paths

| Folder | Purpose | Notes |
|--------|---------|-------|
| **call_station_esp32s3/** | Older floor MQTT + PC bridge client | Uses `bridge/call_station_dashboard.py`; not Task-14 panel |
| **config.h.example** (under `firmware/`) | Generic config template at firmware root | May predate `direct_reeman_esp32s3/` layout |

---

## `sim/` — Browser visualizers

| File | Purpose |
|------|---------|
| **firmware_visualizer.html** | Simulated firmware flow: buttons, LEDs, MQTT phases, Serial log |
| **howto_mqtt_visualizer.html** | MQTT how-to visual |
| **open_visualizer.py** | Opens firmware visualizer in default browser |
| **open_howto_sim.py** | Opens MQTT how-to sim |

Use before hardware arrives or to explain flow to mentors. **Does not replace** `panel_circuit_sim/` for real panel wiring.

---

## `bridge/` — Python PC bridge (optional legacy)

| File | Purpose |
|------|---------|
| **call_station_dashboard.py** | Web dashboard + AES Reeman client; ESP talks “floor MQTT” to PC |
| **requirements.txt** | Python deps for bridge |

**Not used** for current direct Task-14 path (`direct_reeman_esp32s3`). Documented in root `README.md` for older architecture.

---

## `wokwi/` — Wokwi online simulator

| File | Purpose |
|------|---------|
| **diagram.json** | Wokwi project diagram |
| **sketch/sketch.ino** | Wokwi sketch |

Practice GPIO in browser; no real Wi-Fi or Reeman AES on free tier.

---

## Related folders outside `call_station/`

These are **not** inside `call_station/` but are part of the same system:

| Path | Role |
|------|------|
| **`portal/`** | Node.js mission history UI (`http://LAPTOP_IP:3080`); listens to `callstation/mission/record` |
| **`MQTT/`** | `reeman_forklift_client.py` — prove AMR pick/place from PC |
| **`SOP_Broker/`** | Mosquitto start scripts / broker SOP |

---

## UI modes (main firmware)

Set in `firmware/direct_reeman_esp32s3/config.h`:

| `UI_MODE` | Hardware | Start job | Cancel |
|-----------|----------|-----------|--------|
| **1** (default) | White power + Blue latch + G/Y/R modules | Blue latch **CLOSED** | Blue latch **OPEN** |
| **0** | Tactile buttons + I2C LCD | Key **A** / Serial `A` | Key **C** / Serial `C` |

Serial Monitor **115200** always accepts `A` `B` `C` `D` `1` `2` for debug.

---

## Recommended upload order (new panel build)

1. `blink_s3_gpio48` — board alive  
2. `panel_latch_led_test` — switches + status LEDs wired  
3. `direct_reeman_esp32s3` — full AMR + Task-14  
4. Optional: `portal/` on laptop for mission history  

---

## Document map (which doc when)

| Question | Document |
|----------|----------|
| How do I operate the panel? | `SOP_DIRECT_ESP32_AMR.md` |
| Project 1 keypad/LCD vs Project 2 pallet cloud? | `PROJECTS_KEYPAD_PALLET_CLOUD.md` |
| Project 2 code + cloud server? | `project2_industrial_numpad_pallet/` (see `WHAT_TO_SHARE.md`) |
| What is every file here? | `FOLDER_INDEX.md` (this file) |
| Is my wiring safe / correct? | `panel_circuit_sim/index.html` + SOP §5.6 |
| What GPIO is what? | `config.h` comments + SOP panel GPIO cheat |
| Old bridge + dashboard path? | `README.md` + `CIRCUIT.md` + `bridge/` |
| Network / Mosquitto setup? | `REAL_WIFI_MQTT.md` + SOP §5 |

---

## Revision

| Date | Change |
|------|--------|
| 2026-08-23 | Initial folder index; Task-14 panel as production path |
