# Project 1 & Project 2 — Keypad / LCD Testing, Breadboard AMR Buttons, Industrial Numpad & Cloud Pallet IDs

| Field | Value |
|--------|--------|
| **Document** | Dual-project plan + test SOP |
| **Location** | `call_station/PROJECTS_KEYPAD_PALLET_CLOUD.md` |
| **Related SOP** | [`SOP_DIRECT_ESP32_AMR.md`](SOP_DIRECT_ESP32_AMR.md) (panel Task-14 production) |
| **Folder map** | [`FOLDER_INDEX.md`](FOLDER_INDEX.md) |
| **Revision** | **1.0** — 2026-08-23 |
| **Audience** | Engineers (bring-up), operators (numpad), administrators (pallet cloud) |

> **Two projects share one ESP32-S3 + Mosquitto + portal idea.**  
> **Project 1** = lab bring-up (prove keypad, LCD, colored buttons, AMR).  
> **Project 2** = industrial numpad + **pallet ID typed on keypad → cloud store / download / admin-only delete**.

> **Project 2 lives in its own folder:**  
> [`project2_industrial_numpad_pallet/`](project2_industrial_numpad_pallet/) — docs, ESP32 demo firmware, and cloud server.  
> This file remains the **dual overview** (Project 1 + Project 2).

---

## Big picture

```text
┌──────────────── PROJECT 1 (lab) ────────────────┐
│  Breadboard colored buttons  OR  4×4 keypad     │
│  + I2C LCD                                      │
│  → Test wiring → Test AMR jobs (A/B/C/D/1/2)    │
└─────────────────────────────────────────────────┘
                      │ same broker / same robot
                      ▼
┌──────────────── PROJECT 2 (industrial) ─────────┐
│  Industrial numpad + LCD (or status LEDs)        │
│  Type pallet number → press A                    │
│  → MQTT → Portal cloud → download CSV/JSON       │
│  → Delete pallet ID = administrator only         │
└─────────────────────────────────────────────────┘
```

| | **Project 1 — Lab bring-up** | **Project 2 — Industrial + pallet cloud** |
|--|------------------------------|-------------------------------------------|
| **Goal** | Prove hardware + AMR moves | Operator enters **pallet ID**; cloud keeps history |
| **UI** | Colored tactiles **or** membrane 4×4 + LCD | Industrial numpad (or sealed 4×4) + LCD / panel |
| **Firmware** | `UI_MODE=0` lab path + test sketches | [`project2_industrial_numpad_pallet/firmware/`](project2_industrial_numpad_pallet/firmware/) |
| **Cloud** | Optional mission records only | [`project2_industrial_numpad_pallet/cloud/`](project2_industrial_numpad_pallet/cloud/) (port **3081**) |
| **When** | First (this week) | After Project 1 works |

---

# PROJECT 1 — Lab: Keypad + I2C LCD + Colored Buttons → AMR

## 1.1 What you build

| Track | Hardware | Purpose |
|-------|----------|---------|
| **1A — LCD + keypad test** | 16×2 I2C LCD + 4×4 keypad | No AMR required; prove display + keys |
| **1B — Breadboard colored buttons** | Colored tactiles → GPIO | Same jobs as keypad A/B/C/D/1/2 without matrix |
| **1C — Live AMR** | Track 1A or 1B + Wi‑Fi + Mosquitto + Call Mode | Real pick/place / home / cancel |

## 1.2 Firmware & docs already in this folder

| Step | Sketch / doc | AMR? |
|------|--------------|------|
| Blink board | `firmware/blink_s3_gpio48/` | No |
| Find LCD address | `firmware/lcd_i2c_scanner/` | No |
| Keypad only (Serial) | `firmware/keypad_test/keypad_test.ino` | No |
| LCD + keypad demo screens | `firmware/lcd_keypad_demo/` (see its README) | No |
| Wire finder | `firmware/keypad_wire_finder/` | No |
| Full Call Mode lab UI | `firmware/direct_reeman_esp32s3/` with **`UI_MODE 0`** | Yes |

## 1.3 Track 1A — Keypad + I2C LCD test (checklist)

### Wiring (match working `keypad_test` + current lab `config.h`)

**LCD (I2C backpack)**

| LCD pin | ESP32-S3 |
|---------|----------|
| GND | GND |
| VCC | **5V** |
| SDA | **GPIO 1** (lab `config.h`) — older demos may use 15; **use whatever matches your uploaded sketch** |
| SCL | **GPIO 2** (lab `config.h`) — older demos may use 16 |

1. Upload `lcd_i2c_scanner` → Serial **115200** → note address **0x27** or **0x3F**.  
2. Set `LCD_I2C_ADDR` in `config.h`.  
3. LCD should show address / “Ready”.

**4×4 keypad (8 signal pins — typical production lab pins)**

| Keypad | ESP32-S3 |
|--------|----------|
| Rows 1–4 | GPIO **12, 11, 10, 8** |
| Cols 1–4 | GPIO **5, 4, 7, 6** |

Upload `keypad_test.ino` → press every key → Serial prints the character.  
Then upload `lcd_keypad_demo` (or lab `UI_MODE=0` firmware) so LCD mirrors A/B/C/D/1/2 stories.

### Expected key meanings (lab)

| Key | Meaning (Project 1 / lab firmware) |
|-----|-------------------------------------|
| **A** | Forward job: home → pick **p2** → place **p3** → home |
| **B** | Reverse job: pick **p3** → place **p2** → home *(or store, depending on sketch — always check Serial help)* |
| **C** | Cancel ESP32 job state only (e-stop still required) |
| **D** | Store mission / or navigate home *(confirm on Serial banner)* |
| **1** | Navigate **home** only (when idle) |
| **2** | Navigate **charge** only (when idle) |
| **0–9 * #** | Digits for Project 2 pallet entry (not required in Project 1) |

> If keys print wrong letters, fix `keys[][]` map in the sketch (see `keypad_test`) — do not guess robot commands until Serial shows the right letter.

## 1.4 Track 1B — Breadboard colored buttons → AMR

Use **one tactile per job**, same firmware keys as Serial `A/B/C/D/1/2`.

### Suggested color → job map (lab `config.h` UI_MODE=0)

| Wire color (example) | Job | GPIO (lab config) | Firmware key |
|----------------------|-----|-------------------|--------------|
| Black | Store / D | **5** | `D` |
| White | Home only / 1 | **4** | `1` |
| Green | Forward A | **6** | `A` |
| Red | Cancel C | **7** | `C` |
| Yellow | Reverse B | **8** | `B` |
| Green (2nd) | Charge / 2 | **10** | `2` |

**Wiring rule (safe):** each switch = **GPIO ↔ GND** with `INPUT_PULLUP`.  
**Never** put 5V across the switch contacts.

### Test order (breadboard)

1. Power ESP32 (USB or buck 5.0 V).  
2. Mosquitto running; Call Mode Host = laptop IP.  
3. Upload `direct_reeman_esp32s3` with **`UI_MODE 0`**.  
4. Wait Serial/LCD **Ready**.  
5. Press **Green (A)** with path clear → watch AMR + LCD phases.  
6. Press **Red (C)** only to clear ESP state; use **physical e-stop** if robot is moving.  
7. When idle: **White (1)** home, **Green-2 (2)** charge.  
8. **Black (D)** store mission to portal if portal is running.

## 1.5 Track 1C — Pass criteria (Project 1 done)

- [ ] Every keypad key (or every colored button) matches Serial letter  
- [ ] LCD shows Ready / job phases (lab mode)  
- [ ] **A** moves AMR p2→p3→home (or demo screens if AMR off)  
- [ ] **C** clears ESP state without confusing “robot stopped”  
- [ ] Missions appear in portal when **D**/store is used (`portal/` + topic `callstation/mission/record`)  
- [ ] No 5V on GPIO inputs  

**Then start Project 2.**

---

# PROJECT 2 — Industrial Numpad + Pallet ID Cloud

## 2.1 What you build

An **industrial call / numpad station** where the operator:

1. Types a **pallet number** on the keypad (digits).  
2. Presses **A** to **start the job** and **register that pallet ID**.  
3. Cloud (portal) **stores** the pallet ID with time, station, mission, status.  
4. Anyone with portal access can **download** the list (CSV/JSON).  
5. **Only an administrator** can **remove / void** a pallet ID from the cloud.

```text
[Industrial numpad] --Wi-Fi MQTT--> [Mosquitto] --listener--> [Portal cloud]
        |                                                      |
        +-- Call Mode tasks --> [AMR]                          +-- Download
                                                               +-- Admin delete
```

## 2.2 Operator UX (numpad)

| Step | Operator action | LCD / feedback |
|------|-----------------|----------------|
| 1 | Idle | `Enter pallet` / `then press A` |
| 2 | Type digits `0–9` | Shows `ID: 12345` (max length e.g. 8–12) |
| 3 | `*` = clear / backspace | Clears last digit or whole ID |
| 4 | `#` = confirm ID only (optional) | `ID locked` without starting job |
| 5 | **A** | Requires non-empty ID → publish pallet to cloud → start forward job |
| 6 | **C** | Cancel ESP job state (does **not** delete cloud pallet ID) |
| 7 | **B** | Reverse job (optional; may require ID or reuse last ID) |
| 8 | **1** / **2** | Home / charge when idle (no new pallet create) |

**Rules**

- Pressing **A** with empty ID → reject: `Need pallet ID`.  
- Same pallet ID sent twice → cloud **updates** same record or creates a new “trip” with same `palletId` + new `missionId` (choose one policy below).  
- Job cancel (**C**) does **not** erase the cloud row — only admin can delete.

## 2.3 Cloud data model (pallet registry)

Extend portal (today: `portal/data/missions.json`) with a **pallet store**, e.g. `portal/data/pallets.json`.

### Record fields (suggested)

| Field | Example | Who sets it |
|-------|---------|-------------|
| `palletId` | `"P-1042"` or `"1042"` | Operator keypad |
| `missionId` | `17` | ESP32 |
| `stationId` | `esp-panel-1` | `config.h` |
| `status` | `registered` → `running` → `complete` / `error` / `void` | ESP + admin |
| `pick` / `drop` / `home` | `p2` / `p3` / `home` | Firmware |
| `createdAt` | ISO time | Portal |
| `updatedAt` | ISO time | Portal |
| `notes` | free text | ESP / admin |
| `createdBy` | `station` | Portal |
| `voidedBy` | `admin@…` | Admin only |
| `voidedAt` | ISO time | Admin only |

### MQTT (ESP → portal)

Reuse / extend topic, e.g.:

| Topic | Payload idea |
|-------|----------------|
| `callstation/mission/record` | Existing mission state machine (**keep**) |
| `callstation/pallet/record` | **New** — `{ "palletId", "missionId", "stationId", "status", "action": "upsert" }` |

On **A** (Project 2):

1. Publish `callstation/pallet/record` with `status: "registered"` (or `"running"`).  
2. Start AMR forward job as today.  
3. Later mission updates can also attach `palletId` on `mission/record` for the live table.

### HTTP API (portal — to implement)

| Method | Path | Who | Behavior |
|--------|------|-----|----------|
| `GET` | `/api/pallets?limit=100` | Any logged-in viewer | List pallets |
| `GET` | `/api/pallets/export.csv` | Viewer | **Download** CSV |
| `GET` | `/api/pallets/export.json` | Viewer | **Download** JSON |
| `POST` | `/api/pallets` | Station (MQTT preferred) or internal | Upsert (optional) |
| `DELETE` | `/api/pallets/:palletId` | **Admin only** | Soft-delete / void |
| `POST` | `/api/admin/login` | Admin | Issue session / token |

**Administrator-only delete**

- Portal UI shows **Delete / Void** only after admin login (password or token in `portal/config.json`).  
- Soft-delete recommended: set `status: "void"`, keep history; hard delete only if policy requires.  
- Station firmware **must not** expose a “delete pallet” key for operators.

## 2.4 Industrial numpad hardware

| Item | Notes |
|------|--------|
| Sealed **4×4 membrane / metal keypad** | Same matrix idea as lab; mount in panel enclosure |
| **16×2 I2C LCD** (or OLED) | Show typed pallet ID + Ready / job phase |
| Optional status LEDs | Can share Task-14 G/Y/R meanings from panel SOP |
| Power | Buck **5.0 V** → ESP32; common GND |
| Keys | Rows/cols → ESP32 GPIOs (same as Project 1 once proven) |

**Do not** mix Project 2 numpad with White battery latch pins until wiring is documented in one place (`config.h` + this doc).

## 2.5 Firmware behavior (Project 2 — design target)

In `direct_reeman_esp32s3` (lab keypad mode or dedicated `UI_MODE`):

1. Buffer digits into `palletIdBuf[]`.  
2. On **A**: if buffer empty → LCD error; else publish pallet upsert → `startFullJob()` with `palletId` in mission JSON.  
3. On `*` → backspace.  
4. On timeout / Ready → keep last ID on screen or clear (configurable).  
5. Never publish `action: "delete"` from the station.

## 2.6 Admin portal UX (design target)

| Screen | Actions |
|--------|---------|
| **Pallets table** | Filter by ID, status, date; open mission link |
| **Download** | Button → CSV / JSON export |
| **Admin login** | Password from `config.json` (change from default) |
| **Void / Delete** | Visible only when admin session active; confirm dialog |

---

# Shared rules (both projects)

## Safety

- Clear path; hand on **physical e-stop**.  
- **C** / cancel = ESP memory only, not motor stop.  
- Switch inputs = **GPIO ↔ GND** only (no 5V through contacts).  
- Confirm FMS points: **`home`**, **`charge`**, **`p2`**, **`p3`**.

## Network

- Laptop Mosquitto `:1883`.  
- Call Mode Host = **laptop IP** = `MQTT_HOST`.  
- Portal (optional Project 1 / required Project 2 download UI): `http://LAPTOP_IP:3080`.

## What exists today vs what to build

| Feature | Status |
|---------|--------|
| Keypad Serial test | **Exists** — `keypad_test` |
| LCD I2C scan / demo | **Exists** — `lcd_i2c_scanner`, `lcd_keypad_demo` |
| Colored button GPIOs (lab) | **Exists** — `UI_MODE 0` in `config.h` |
| AMR A/B/C/D/1/2 | **Exists** — `direct_reeman_esp32s3` |
| Mission live status in portal | **Exists** — `callstation/mission/record` |
| Type pallet ID then A | **To build** (Project 2 firmware) |
| Pallet cloud store + CSV download | **To build** (portal API + UI) |
| Admin-only delete | **To build** (auth + DELETE API) |

---

# Test plans

## Project 1 test plan

| # | Test | Pass |
|---|------|------|
| P1-1 | LCD scanner shows address | LCD text visible |
| P1-2 | Every keypad key → correct Serial char | 16 keys OK |
| P1-3 | LCD demo A sequence | Screens advance without AMR |
| P1-4 | Colored Green = A on Ready | AMR starts forward job |
| P1-5 | Red = C | ESP Ready again; e-stop if needed |
| P1-6 | Portal mission row updates | Status running → complete |

## Project 2 test plan

| # | Test | Pass |
|---|------|------|
| P2-1 | Type `1042`, LCD shows `ID: 1042` | Digits buffer |
| P2-2 | A with empty ID | Rejected, no job |
| P2-3 | A with ID | Pallet row in cloud + AMR job |
| P2-4 | Download CSV | File opens with palletId |
| P2-5 | Operator has no delete button | Cannot void |
| P2-6 | Admin login → Void | Row voided / removed per policy |
| P2-7 | C during job | Job cancel; pallet row **not** auto-deleted |

---

# Implementation roadmap (suggested)

| Phase | Work | Project |
|-------|------|---------|
| **A** | Finish Tracks 1A–1C on breadboard / lab keypad | 1 |
| **B** | Mount industrial numpad; reuse proven GPIO map | 2 hardware |
| **C** | Firmware: digit buffer + send `palletId` on A | 2 firmware |
| **D** | Portal: `pallets.json`, MQTT listener, list UI | 2 cloud |
| **E** | Export CSV/JSON download | 2 cloud |
| **F** | Admin password + DELETE/void only | 2 security |

---

# Quick links

| Need | Path |
|------|------|
| Main AMR SOP (panel Task-14) | `SOP_DIRECT_ESP32_AMR.md` |
| Folder inventory | `FOLDER_INDEX.md` |
| Keypad Serial test | `firmware/keypad_test/keypad_test.ino` |
| LCD + keypad demo | `firmware/lcd_keypad_demo/` |
| Production / lab firmware | `firmware/direct_reeman_esp32s3/` |
| Mission portal | `../portal/` |
| Panel circuit sim (Task-14) | `panel_circuit_sim/index.html` |

---

## Revision history

| Rev | Date | Notes |
|-----|------|--------|
| **1.0** | **2026-08-23** | Initial dual-project doc: lab keypad/LCD/buttons + industrial numpad + cloud pallet ID (download / admin-only delete) |

---

**Made for RTM / Rhino AMR call-station work.** Keep this file when sharing Project 1 vs Project 2 scope with mentors.
