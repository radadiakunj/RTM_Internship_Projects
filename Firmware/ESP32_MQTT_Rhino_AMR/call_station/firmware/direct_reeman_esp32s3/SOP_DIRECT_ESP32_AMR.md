# SOP — Direct ESP32-S3 Call Station → Reeman Rhino AMR

| Field | Value |
|--------|--------|
| **Document owner** | **Kunj Radadiya** |
| **Author / made by** | **Kunj Radadiya** |
| **Document type** | Standard Operating Procedure (site shareable) |
| **Project** | ESP32 MQTT Rhino AMR — Call Station |
| **Firmware folder** | `call_station/firmware/direct_reeman_esp32s3/` |
| **Main sketch** | `direct_reeman_esp32s3.ino` |
| **Config** | `config.h` |
| **Revision** | **2.3** — 2026-08-24 |
| **Audience** | Operators (keypad only) and engineers (setup / token / Wi‑Fi) |
| **Product name (suggested)** | **RhinoCall Point** (see §17) |

> **Ownership notice (do not remove)**  
> This SOP was written and maintained by **Kunj Radadiya** for the RTM / Rhino AMR call-station project.  
> When you share or copy this file, **keep the author name, revision table, and ownership notice**.  
> Do not strip attribution or replace “Made by Kunj Radadiya” with another name.

---

## Quick start (read this first)

| Who | What to do |
|-----|------------|
| **Operator (panel Task-14)** | Latch **White ON** (power) → wait Serial **Ready** → latch **Blue CLOSED** to start job → LEDs Green→Yellow→Red→OFF |
| **Operator (lab keypad)** | Power box → wait LCD **Ready** → use keypad below |
| **Engineer (once)** | Same Wi‑Fi · Mosquitto · Call Mode Host = laptop IP · token in `config.h` · upload sketch |

### Panel Task-14 map (UI_MODE=1 — production)

| Control | What happens |
|---------|----------------|
| **White latch** | **Power only** — Pack **~6.3 V** (4×~1.57 V) B+ → White switch → Buck **5.0 V** → ESP32. Not a GPIO start button. |
| **Blue latch CLOSED** | **Task-14 start** — forward job: leave home → **pick p2** → place p3 → **return home** |
| **Blue latch OPEN** | Cancel **ESP32 job state** only (robot may still move — use **physical e-stop**) |
| **Serial A/B/C/D/1/2** | Same keys as lab mode for debug |

### Status LEDs (Task-14)

| LED | When ON |
|-----|---------|
| **Green** | Job just started / starting from home |
| **Yellow** | Go to **p2** pick / pick-place running |
| **Red** | Returning **home** |
| **All OFF** | Idle / job complete / waiting (not an error) |

Circuit teaching sim: `call_station/panel_circuit_sim/index.html`

### Keypad map (UI_MODE=0 — lab)

| Key | What happens |
|-----|----------------|
| **A** | Forward job: **pick p2 → place p3 → return home** (forks + auto then calling home) |
| **B** | Reverse job: **pick p3 → place p2 → return home** |
| **C** | Cancel **ESP32 job state** only (robot may still be moving — use **physical e-stop**) |
| **D** | Store **mission record** to laptop portal (`callstation/mission/record`) |
| **1** | Navigate to **home** only — **blocked** while A/B job is running |
| **2** | Navigate to **charge** only — **blocked** while A/B job is running |

Map point names (must match FMS exactly): **`home`**, **`charge`**, **`p2`**, **`p3`**.  
If the AMR map names change → edit `POINT_*` in `config.h` — see **§9**.

**Also read:** **§10** GPIO · **§11** battery (~6.3 V→5 V) & current · **§12** LED timing · **§14** MQTTX topics · **§17** product name.

---

## 1. Purpose

Run an ESP32-S3 **call box** that talks to the Reeman Rhino forklift AMR over **MQTT Call Mode**, without the Python dashboard (`call_station_dashboard.py`).

Two UI modes (`config.h` → `UI_MODE`):

| Mode | Hardware | Typical day |
|------|----------|-------------|
| **1 (panel Task-14)** | White power latch + Blue Task-14 latch + Green/Yellow/Red status LEDs | Latch White ON → wait Ready → Blue CLOSED → watch G→Y→R→OFF |
| **0 (lab)** | Tactile buttons + I2C LCD | Power → Ready on LCD → **A**/**B** jobs; **1**/**2** nav; **D** store; **C** clear |

**Mission history (optional for mentors):** run `portal/` and open `http://LAPTOP_IP:3080`.

---

## 2. System overview

```text
┌─────────────────┐      Wi‑Fi MQTT       ┌──────────────────────────┐      MQTT      ┌─────────────────┐
│  ESP32-S3       │ ───────────────────► │  LAPTOP                  │ ◄──────────── │ Reeman Rhino    │
│  Panel Task-14  │                      │  Mosquitto :1883         │               │ Call Mode ON    │
│  or Keypad+LCD  │                      │  Portal :3080 (optional) │               │ FMS :75 (nav)   │
└─────────────────┘                      └──────────────────────────┘               └─────────────────┘
```

| Component | Role |
|-----------|------|
| **Mosquitto on laptop** | MQTT broker — laptop, ESP, and AMR must all join it |
| **ESP32-S3** | Call box: panel Task-14 **or** keypad+LCD; AES Calling tasks; phone heartbeat |
| **AMR Call Mode** | Robot MQTT client; Server Address = **laptop IP**, port **1883** |
| **FMS** `http://AMR_NAV_IP/` (e.g. `http://192.168.5.75/`) | Map / points / dispatch UI — **not** used for Calling token auto-sync |
| **Browser portal** | Mission list at `http://LAPTOP_IP:3080` |
| **Python dashboard** | **Not used** in this SOP |

**Rule:** Mosquitto runs on the **laptop**, not on the ESP32 and not as “Call Mode Server = AMR nav IP”.

---

## 3. Safety

- Clear the path before **Blue CLOSED** (panel) or **A** / **B** / **1** / **2** (lab).
- Keep a hand on the **physical e-stop**.
- Do **not** start a job until Serial/LCD shows **Ready** and STATUS is healthy.
- Before Task-14 / **A**: pallet ready at **p2**; **p3** clear. Before **B**: pallet ready at **p3**; **p2** clear.
- **Blue OPEN** / **C** does **not** stop the robot motors — only clears ESP32 workflow memory. Use e-stop if moving.
- **1** / **2** do **not** command forks (navigate only).
- **Never** put **5V** on blue switch → GPIO (ESP32-S3 GPIO is **3.3V only**). Blue = GPIO7 ↔ GND only.
- First prove pick/place on PC with `MQTT/reeman_forklift_client.py` if the robot ever ignores ESP tasks.

---

## 4. Prerequisites checklist

### Hardware

- [ ] ESP32-S3 Dev Module, USB-C data cable and/or regulated **5.0 V** on **5V** + **GND** (via buck)
- [ ] **Panel (Task-14):** White power latch + Blue Task-14 latch + Green/Yellow/Red status modules  
  **or** lab: 4×4 keypad / tactiles + 16×2 I2C LCD
- [ ] Laptop with Mosquitto
- [ ] AMR powered, mapped, localized
- [ ] FMS points exist: **`home`**, **`charge`**, **`p2`**, **`p3`** (pallet types as required)

### Software (laptop)

- [ ] Mosquitto service **Running** + **Automatic**
- [ ] Arduino IDE — board **ESP32S3 Dev Module**
- [ ] Libraries: **PubSubClient**, **ArduinoJson** (lab also: **Keypad**, **LiquidCrystal_I2C**)

### Network

- [ ] Laptop, ESP32, and AMR on the **same Wi‑Fi** (or equivalent LAN path to Mosquitto)
- [ ] Laptop IPv4 written down → **YOUR_PC_IP** (`ipconfig`)
- [ ] Prefer **2.4 GHz** capable AP for ESP32

### Credentials (Call Mode tablet)

- [ ] `ROBOT_HOSTNAME` (example: `rbot55f-260114-003-001`)
- [ ] `ROBOT_TOKEN` — copy **exactly** from Call Mode (do **not** press Generate Token unless you will update `config.h` and re-upload)
- [ ] `ROBOT_KEY` / encrypt key (example: `a5F6dmfr`)

**Token note (important):** Official Calling docs only deliver a new token via **pairing multicast** (`239.0.0.1:7979`). Site apps (aging-ros3 / forkliftnew) may have **no Pairing UI**. FMS HTTP does **not** expose Calling token. Practical rule: **one stable token** in `config.h` → upload once → operators never touch tokens.

---

## 5. One-time engineer setup

### 5.1 Mosquitto

```powershell
Get-Service mosquitto
Start-Service mosquitto
Set-Service mosquitto -StartupType Automatic
Get-NetTCPConnection -LocalPort 1883 | Select LocalAddress, RemoteAddress, State
```

### 5.2 Laptop IP

```powershell
ipconfig
```

Use the IPv4 of the adapter on the **same network as the AMR** → **YOUR_PC_IP**.

### 5.3 `config.h`

Path: `call_station/firmware/direct_reeman_esp32s3/config.h`

| Setting | Meaning |
|---------|---------|
| `WIFI_SSID` / `WIFI_PASSWORD` | ESP Wi‑Fi |
| `MQTT_HOST` | **YOUR_PC_IP** |
| `MQTT_PORT` | `1883` |
| `ROBOT_HOSTNAME` | Tablet hostname |
| `ROBOT_TOKEN` | Call Mode token |
| `ROBOT_KEY` | Encryption key |
| `POINT_HOME` | `home` |
| `POINT_CHARGE` | `charge` |
| `POINT_PICK` | `p2` |
| `POINT_DROP` | `p3` |

Upload **`direct_reeman_esp32s3.ino`**. Serial Monitor **115200**.

### 5.4 AMR Call Mode

| Field | Value |
|--------|--------|
| Server / Host | **YOUR_PC_IP** (same as `MQTT_HOST`) |
| Port | `1883` |
| Token / Key | Same as `config.h` |

Save → MQTT **Off → On** until **Connected**.

### 5.5 Prove robot (optional but recommended)

```powershell
cd D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\MQTT
python reeman_forklift_client.py --broker YOUR_PC_IP --broker-port 1883 --hostname YOUR_HOSTNAME --token "YOUR_TOKEN" --key YOUR_KEY --pick p2 --drop p3
python reeman_forklift_client.py --broker YOUR_PC_IP --broker-port 1883 --hostname YOUR_HOSTNAME --token "YOUR_TOKEN" --key YOUR_KEY --goto home
```

AES check only:

```powershell
python call_station\firmware\direct_reeman_esp32s3\verify_aes.py --pick p2 --drop p3 --home home
```

### 5.6 Wiring

#### Panel Task-14 (`UI_MODE=1`) — current production

| Net | Connection |
|-----|------------|
| White power switch | Battery **B+** ↔ Buck **IN+** (not a GPIO) |
| Battery B− | Buck **IN−** |
| Buck OUT+ / OUT− | ESP32 **5V** / **GND** |
| Blue Task-14 switch | **GPIO7** ↔ common **GND** |
| White / Blue ring LED+ | **GPIO13** / **GPIO14** (LED− → GND) |
| Green / Yellow / Red **IN** | **GPIO10** / **11** / **12** |
| Status module **VCC** | common **GND** |
| Onboard RGB | GPIO **48** |

Full pin / power tables: **§9** (map points), **§10** (GPIO), **§11** (voltage/current), **§12** (LED delays).  
Interactive diagram: `call_station/panel_circuit_sim/index.html`

#### Lab keypad + LCD (`UI_MODE=0`)

| Device | Connection |
|--------|------------|
| Keypad rows 1–4 | GPIO **12, 11, 10, 8** |
| Keypad cols 1–4 | GPIO **5, 4, 7, 6** |
| LCD SDA / SCL | GPIO **1 / 2** (see `config.h`) |
| LCD VCC / GND | **5 V / GND** |
| Onboard RGB | GPIO **48** |

Standalone tests: `lcd_i2c_scanner/`, `keypad_test/`.

### 5.7 Mission portal (mentor view)

```powershell
cd D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\portal
npm install
npm start
```

Open **`http://YOUR_PC_IP:3080`**. Allow firewall **3080** if needed.  
Missions publish on topic **`callstation/mission/record`**.

---

## 6. Daily operator procedure

### 6.1 Power-on order

1. Laptop on → Mosquitto running  
2. (Optional) `cd portal && npm start`  
3. AMR on → Call Mode **Connected** to laptop IP  
4. Power ESP32 or press **RST**  
5. Wait LCD **Ready** (or Serial Ready help)

### 6.2 Expected Serial (115200)

```text
Wi-Fi ... IP: ...
MQTT ok (broker connected)
Subscribed reeman/calling/robot/<hostname>/forklift/#
STATUS battery=xx% eStop=1 ...
3) Ready
  A = home -> p2 pick -> p3 place -> home
  B = p3 pick -> p2 place -> home (reverse)
  C = cancel current task
  D = store mission record to portal
  1 = go home only (after job is idle)
  2 = go charge only (after job is idle)
```

### 6.3 Job details

| Key | MQTT | Detail |
|-----|------|--------|
| **A** | `task/auto_model` then `task/calling_model` | Pick **p2** → place **p3** → navigate **home**. Mission may auto-store when complete. |
| **B** | same pattern (points swapped) | Pick **p3** → place **p2** → **home**. |
| **C** | — | Clears ESP32 state; LCD “Job cancelled”. E-stop if robot still moving. |
| **D** | `callstation/mission/record` | Stores mission snapshot; LCD “Mission #N stored”. |
| **1** | `task/calling_model` → `home` | Only if **not** mid A/B job. Else LCD “Job running”. |
| **2** | `task/calling_model` → `charge` | Same idle rule as **1**. |

Supervised first-run suggestion: **1** (home) → **A** (full job) → **D** (store) → **2** (charge) when safe.

### 6.4 After unplug

Plug power / USB → **RST** → wait **Ready** → operate keypad.

---

## 7. IP roles (do not mix)

| Address | Who | Used where |
|---------|-----|------------|
| **YOUR_PC_IP** | Laptop broker | `MQTT_HOST` **and** Call Mode Host |
| ESP32 IP (Serial) | ESP only | Display — **never** Call Mode Host |
| AMR nav IP (e.g. `.75`) | FMS web | Browser FMS / HTTP status — **not** Mosquitto Host for Calling |
| AMR MQTT peer | Robot on :1883 | Confirmed via Mosquitto peer list |

If laptop Wi‑Fi IP changes: update Call Mode Host + `MQTT_HOST`, re-upload ESP32.

---

## 8. LED meanings

### 8.1 Panel status LEDs (Task-14 — UI_MODE=1)

| LED | Meaning |
|-----|---------|
| **Green** | Starting from home / job dispatched |
| **Yellow** | Go to **p2** pick / pick-place running |
| **Red** | Returning **home** (or Error fault) |
| **All OFF** | Idle / complete / waiting for Ready |

Boot self-test flashes **Green → Yellow → Red** once (**350 ms** each — see §15).

**Important:** During a real Blue-button job, Green / Yellow / Red do **not** use fixed `delay()` times between colors. They follow **AMR mission phases**. Timing buffers in `config.h` are listed in **§15**.

### 8.2 On-board RGB (ESP32 pin 48)

| Color | Meaning |
|--------|---------|
| Blue | Wi‑Fi / MQTT connecting |
| Magenta | Waiting AMR STATUS |
| Dim green | Ready |
| Yellow | Auto pick/place running |
| Bright green | Going home / nav-only |
| Red | Error |

---

## 9. If you change map points on the AMR — what to edit in code

Point names in firmware **must match FMS / map names exactly** (spelling and case).

### 9.0 Coordinates vs names (important)

| What changed on the AMR | Edit ESP32 code? | Where |
|-------------------------|------------------|--------|
| Only **X/Y coordinates** of `home` / `p2` / `p3` (same names) | **No** | Fix map in FMS / tablet only. ESP sends **names**, not meters. |
| **Renamed** points (e.g. `p2` → `stationA`) | **Yes** | Edit **`config.h`** only (`POINT_*` strings) |
| New points added with new names | **Yes** | `config.h` → `POINT_PICK` / `POINT_DROP` / `POINT_HOME` / `POINT_CHARGE` |

**Do not put coordinates into `direct_reeman_esp32s3.ino` or `config.h`.**  
Call Mode tasks look like “go to point named `p2`”. The robot already knows that name’s position from its map.

### 9.1 File to edit (names only)

`call_station/firmware/direct_reeman_esp32s3/config.h`  
(**not** the `.ino` for map names — the sketch already uses `POINT_*` from `config.h`)

```c
static const char* POINT_HOME   = "home";    // return / park point
static const char* POINT_CHARGE = "charge";  // charge dock (key 2 / Serial 2)
static const char* POINT_PICK   = "p2";      // pick pallet (forward job first stop)
static const char* POINT_DROP   = "p3";      // place pallet (forward job second stop)
```

| If AMR / FMS renames… | Change this in `config.h` | Also used by |
|------------------------|---------------------------|--------------|
| Home / park point | `POINT_HOME` | Return after job; Serial/key **1** |
| Charge point | `POINT_CHARGE` | Serial/key **2** |
| Pick point (forward) | `POINT_PICK` | Blue CLOSED / **A** first auto point |
| Place point (forward) | `POINT_DROP` | Blue CLOSED / **A** second auto point |
| Map / floor name (elevator) | `TASK_MAP` (`""` = JSON `null`) | Only if your site uses a named map |

### 9.2 After changing points

1. Save `config.h`.  
2. **Upload** `direct_reeman_esp32s3.ino` again.  
3. Confirm on FMS that the robot can navigate to the **same** names.  
4. Optional PC prove:

```powershell
python MQTT\reeman_forklift_client.py --broker YOUR_PC_IP --broker-port 1883 --hostname YOUR_HOSTNAME --token "YOUR_TOKEN" --key YOUR_KEY --pick NEW_PICK --drop NEW_DROP
```

### 9.3 What you usually do **not** need to change

| Leave alone | Why |
|-------------|-----|
| GPIO numbers | Hardware wiring unchanged |
| Wi‑Fi / MQTT / token | Unless network or Call Mode token changed |
| LED colors / Task-14 meaning | Still Green→Yellow→Red by **phase**, not by point name |
| `direct_reeman_esp32s3.ino` job logic | It already reads `POINT_*` from `config.h` |

### 9.4 Optional cleanup (LCD / Serial text only)

Some LCD strings still say `"p2"` / `"p3"` in English. Behavior still uses `POINT_PICK` / `POINT_DROP`. If mentors want the display to show the new names, update those string literals in `direct_reeman_esp32s3.ino` (search for `p2` / `p3`).

Example: rename pick `p2` → `stationA`, place `p3` → `stationB`:

```c
static const char* POINT_PICK = "stationA";
static const char* POINT_DROP = "stationB";
```

Then re-upload. Blue button job becomes: leave home → pick **stationA** → place **stationB** → return **home**.

---

## 10. ESP32-S3 GPIO map (panel Task-14 — `UI_MODE=1`)

| Function | Component | ESP32-S3 GPIO / net | Notes |
|----------|-----------|---------------------|--------|
| Power ON/OFF | White latch (LANBOO R165046) | **Not GPIO** — B+ → switch → Buck IN+ | Power latch only |
| Task-14 start/cancel | Blue latch (LANBOO R165054) switch | **GPIO 7** ↔ GND | `INPUT_PULLUP`; CLOSED=LOW=start |
| Green status IN | Module R228873 | **GPIO 10** | VCC of module → common GND |
| Yellow status IN | Module R228872 | **GPIO 11** | VCC → common GND |
| Red status IN | Module R228871 | **GPIO 12** | VCC → common GND |
| White ring LED+ | White button ring | **GPIO 13** | LED− → GND (dim on GPIO; later NPN+5V) |
| Blue ring LED+ | Blue button ring | **GPIO 14** | LED− → GND |
| Onboard RGB | ESP32-S3 DevKit LED | **GPIO 48** | Firmware status colors |
| Common ground | All returns | **GND** | ESP GND = buck OUT− = LED− = switch GND = status VCC |

**Lab mode (`UI_MODE=0`) extra GPIOs:** tactiles on **4,5,6,7,8,10**; LCD SDA/SCL **1 / 2**. See cheat table at end of this SOP.

---

## 11. Components, voltage, and current (estimates)

Use these as **engineering estimates** for sizing the buck and battery. Measure with a multimeter for final sign-off.

### 11.1 Battery → 5 V rail (your pack)

| Item | Value |
|------|--------|
| Cells | **4 × ~1.57 V** (alkaline / similar) |
| Pack open-circuit (your reading) | **~6.3 V** |
| Converter | Buck (step-down) **OUT = 5.0 V** (set with multimeter **before** connecting ESP) |
| Path | Battery B+ → **White latch** → Buck **IN+** · B− → Buck **IN−** · Buck OUT → ESP **5V** + **GND** |

```text
  [4 cells ≈ 6.3 V] --White ON--> [Buck] --5.0 V--> [ESP32-S3 + LEDs]
```

### 11.2 Per-component budget (at ~5 V side unless noted)

| Component | Qty | Supply | Typical current | Peak / notes |
|-----------|-----|--------|-----------------|--------------|
| ESP32-S3 Dev Module (Wi‑Fi on) | 1 | **5 V** (VIN/5V pin) | **150–300 mA** | TX spikes **~350–500 mA** — design headroom |
| Green status module | 1 | GPIO **3.3 V** drive on IN | **~10–20 mA** | Only when Green ON |
| Yellow status module | 1 | GPIO 3.3 V IN | **~10–20 mA** | Only when Yellow ON |
| Red status module | 1 | GPIO 3.3 V IN | **~10–20 mA** | Only when Red ON |
| White ring LED | 1 | GPIO 3.3 V (test) or **5 V** via NPN later | **~10–20 mA** @ 5 V | Rated **5–24 V** ring |
| Blue ring LED | 1 | same | **~10–20 mA** @ 5 V | |
| White / Blue switch contacts | 2 | Signal only | **≪ 1 mA** | Pull-up microamps — not a load |
| Buck converter losses | 1 | 6.3 V in → 5 V out | — | Efficiency often **~85–90%** |

**GPIO rule:** ESP32-S3 logic is **3.3 V**. Do not feed battery or 5 V into GPIO7 / status sense pins.

### 11.3 Total current (how to read this)

Only **one** status LED is ON at a time in Task-14 (Green **or** Yellow **or** Red). Rings may also be ON.

| Scenario | Approx. load on **5 V** rail | Approx. from **6.3 V** battery\* |
|----------|------------------------------|----------------------------------|
| Idle Ready (Wi‑Fi, LEDs off) | **~150–250 mA** | **~140–230 mA** |
| Job running (ESP + 1 status + both rings) | **~220–400 mA** | **~200–370 mA** |
| Wi‑Fi TX spike (short) | **~500–650 mA** | **~460–600 mA** |
| **Recommended buck rating** | **≥ 1 A** @ 5 V continuous | Comfortable margin |


**Rule of thumb for your station:** plan **~0.5–0.6 A** average on 5 V during a job, and choose a buck that can deliver **at least 1 A** at 5.0 V from a **~6.3 V** pack.

---

## 12. LED timing / buffer delays (Green → Yellow → Red)

### 12.1 Boot self-test (fixed delays in code)

On power-up (`LED_BOOT_SELFTEST = true` in `config.h`):

| Step | LED | `delay` in firmware |
|------|-----|---------------------|
| 1 | Green ON | **350 ms** |
| 2 | Yellow ON | **350 ms** |
| 3 | Red ON | **350 ms** |
| Then | All OFF | Idle / wait Ready |

So boot flash total ≈ **1.05 s** of LED stepping (plus short gaps off between steps).

### 12.2 After Blue CLOSED (real job) — **not** fixed 350 ms

Status LEDs follow **mission phase**, not a timer between colors:

| LED | Firmware phase | How long it stays ON |
|-----|----------------|----------------------|
| **Green** | `AutoSent` | Until AMR accepts / starts moving → then **Yellow** |
| **Yellow** | `AutoRun` | Whole pick/place run (p2→p3) — **depends on robot travel** (seconds to minutes) |
| **Red** | `AutoIdle` / `HomeSent` / `HomeRun` | After place done, through return **home** — **depends on robot** |
| **All OFF** | `Ready` / complete | Job finished or idle |

### 12.3 Buffer times in `config.h` (job logic)

| Constant | Default | Meaning |
|----------|---------|---------|
| `BTN_DEBOUNCE_MS` | **50 ms** | Ignore bounce on Blue latch |
| `IDLE_HOLD_MS` | **2500 ms** (2.5 s) | Robot must look **idle** this long before ESP treats a stage as complete |
| `HOME_DWELL_MS` | **2500 ms** (2.5 s) | After pick/place finishes, **wait 2.5 s** before sending “go home” (buffer before Red return phase starts commanding home) |
| `NO_MOTION_TIMEOUT_MS` | **45000 ms** (45 s) | If robot never starts after Blue, error |

**Teaching sim** (`panel_circuit_sim/index.html`) uses ~1.8 s steps for demo only — **production firmware does not use those demo delays**.

To change buffers: edit `HOME_DWELL_MS` / `IDLE_HOLD_MS` in `config.h`, re-upload.

---

## 13. Troubleshooting


| Symptom | Likely cause | Action |
|---------|--------------|--------|
| MQTT fail | Mosquitto stopped / wrong IP | Start Mosquitto; fix `MQTT_HOST` |
| No STATUS | Call Mode not Connected / wrong Host | Set Host = laptop IP; Off→On |
| A presses but no move; `Publish ok` | Wrong **token** vs tablet | Paste current Call Mode token into `config.h`; upload |
| `TASK RESULT` missing | Robot ignored task | Same as PC client; check token / Call Mode / localization |
| `Job running` on 1 or 2 | A/B still active | Wait for job complete or **C** + e-stop if needed |
| Blank LCD | Power / SDA-SCL / address | 5 V; try swap SDA/SCL; 0x27 vs 0x3F |
| Keypad wrong letters | Pin / keymap | Use pins in §5.6; verify with `keypad_test` |
| Mission missing in browser | Portal not running | `npm start` in `portal/`; port 3080 |
| Token “auto” from FMS | Not supported | FMS has no Calling token API (see docs) |
| Wrong point / robot goes elsewhere | FMS name ≠ `config.h` | Edit `POINT_*` (§9), re-upload |
| Blue CLOSED but LEDs never change | Not Ready / no STATUS | Wait Ready; check MQTT |
| Buck hot / ESP brownout | Underrated supply | Use ≥1 A @ 5 V from ~6.3 V pack (§11) |

Peer check:

```powershell
Get-NetTCPConnection -LocalPort 1883 | Select RemoteAddress, State
```

Expect **ESP32** and **AMR** both connected.

---

## 14. MQTT topics for MQTTX (test `direct_reeman_esp32s3.ino`)

Use these with **MQTTX** (or any MQTT client) connected to the **same Mosquitto** as the ESP32 (`MQTT_HOST` in `config.h`, port **1883**).

Replace `<HOSTNAME>` with your `ROBOT_HOSTNAME` from `config.h`  
(example: `rbot55f-260114-003-001`).

### 14.1 Who publishes / who subscribes

| Role | Device | Direction |
|------|--------|-----------|
| **Call box (ESP32)** | This firmware | **Publishes** phone heartbeat + tasks + mission records; **subscribes** robot tree |
| **AMR (Call Mode)** | Reeman robot | **Publishes** STATUS heartbeat + task responses; **subscribes** phone tasks |
| **You (MQTTX)** | Laptop | Subscribe to watch traffic; optional publish for experiments |
| **Portal** (optional) | `portal/` on laptop | Subscribes `callstation/mission/record` |

```text
                    MQTTX  (subscribe to watch)
                       │
ESP32 ──publish──► Mosquitto ◄──publish── AMR
ESP32 ◄─subscribe──┘         └──subscribe── AMR
```

### 14.2 Topic table (exact strings used in firmware)

| Topic | Publisher | Subscriber | Payload (summary) | When you see it |
|-------|-----------|------------|-------------------|-----------------|
| `reeman/calling/phone/<HOSTNAME>/forklift/heartbeat` | **ESP32** | AMR Call Mode | `{"token":"<ROBOT_TOKEN>"}` | Every ~4 s (`PHONE_HB_INTERVAL_MS`) while MQTT up |
| `reeman/calling/phone/<HOSTNAME>/forklift/task/auto_model` | **ESP32** | AMR | `{"token":"...","body":"<AES base64>"}` | Blue CLOSED / **A** or **B** (pick→place auto) |
| `reeman/calling/phone/<HOSTNAME>/forklift/task/calling_model` | **ESP32** | AMR | `{"token":"...","body":"<AES base64>"}` | Return **home**, or **1** / **2** nav-only |
| `reeman/calling/robot/<HOSTNAME>/forklift/#` | — | **ESP32** (wildcard sub) | many | ESP listens to whole robot tree |
| `reeman/calling/robot/<HOSTNAME>/forklift/heartbeat` | **AMR** | ESP32 (+ MQTTX) | JSON STATUS (`level`, `emergencyButton`, `isNavigating`, …) | Robot alive / status |
| `reeman/calling/robot/<HOSTNAME>/forklift/task/response` | **AMR** | ESP32 (+ MQTTX) | Task accept / reject JSON | After ESP sends a task |
| `callstation/mission/record` | **ESP32** | Portal / MQTTX | Mission state JSON (`running`, `pausing`, `complete`, `stored`, `error`) | Job start / cancel / done / **D** store |

### 14.3 MQTTX setup (watch ESP32 traffic)

1. New connection → Host = **YOUR_PC_IP** (same as `MQTT_HOST`), Port **1883**, no TLS (local Mosquitto).  
2. Connect.  
3. Add subscriptions (QoS 0 or 1):

| Name | Topic | Why |
|------|-------|-----|
| All phone (ESP out) | `reeman/calling/phone/<HOSTNAME>/forklift/#` | Heartbeat + tasks from ESP |
| All robot (AMR out) | `reeman/calling/robot/<HOSTNAME>/forklift/#` | STATUS + responses |
| Missions | `callstation/mission/record` | Portal / mission state machine |

4. Power ESP → upload firmware → White ON → wait Serial **Ready**.  
5. In MQTTX you should see ESP **heartbeat** about every 4 seconds.  
6. Latch **Blue CLOSED** (or Serial **A**) → look for **`task/auto_model`** from ESP, then robot **heartbeat** / **task/response**.  
7. Mission updates on **`callstation/mission/record`**.

### 14.4 Example topic strings (copy-paste)

With hostname `rbot55f-260114-003-001`:

```text
reeman/calling/phone/rbot55f-260114-003-001/forklift/#
reeman/calling/phone/rbot55f-260114-003-001/forklift/heartbeat
reeman/calling/phone/rbot55f-260114-003-001/forklift/task/auto_model
reeman/calling/phone/rbot55f-260114-003-001/forklift/task/calling_model
reeman/calling/robot/rbot55f-260114-003-001/forklift/#
reeman/calling/robot/rbot55f-260114-003-001/forklift/heartbeat
reeman/calling/robot/rbot55f-260114-003-001/forklift/task/response
callstation/mission/record
```

### 14.5 What MQTTX will show (readable vs encrypted)

| Message | Readable in MQTTX? | Notes |
|---------|-------------------|--------|
| Phone **heartbeat** | Yes | Plain JSON with token (treat as secret — don’t paste publicly) |
| **auto_model** / **calling_model** | Partially | Outer JSON has `token` + `body`; **`body` is AES-encrypted Base64** — you confirm publish happened, not the plaintext points |
| Robot **heartbeat** | Yes | Battery, e-stop, navigating flags |
| **task/response** | Yes | Accept / reject fields |
| **mission/record** | Yes | `status`, `pick`, `drop`, `home`, `missionId`, … |

To prove plaintext points offline, use `verify_aes.py` / PC client — not by reading `body` in MQTTX.

### 14.6 Quick checks

| Check | MQTTX expect |
|-------|----------------|
| ESP online | Messages on `.../phone/.../heartbeat` |
| AMR online | Messages on `.../robot/.../heartbeat` |
| Job start (Blue / A) | Publish on `.../task/auto_model` then mission `running` |
| Cancel (Blue OPEN / C) | Mission `pausing` (ESP state clear) |
| Job done | Mission `complete` |
| Store (D / Serial) | Mission `stored` |

**Do not** publish fake Call Mode tasks from MQTTX unless you know the AES format — you can break robot state. Prefer **subscribe-only** for testing.

---

## 15. Files reference

| Path | Description |
|------|-------------|
| `call_station/firmware/direct_reeman_esp32s3/direct_reeman_esp32s3.ino` | Production firmware |
| `call_station/firmware/direct_reeman_esp32s3/config.h` | Wi‑Fi, broker, token, points, pins |
| `call_station/firmware/direct_reeman_esp32s3/lcd_i2c.h` | I2C LCD helper |
| `call_station/firmware/direct_reeman_esp32s3/verify_aes.py` | AES verify vs Python |
| `call_station/firmware/keypad_test/` | Keypad-only Serial test |
| `call_station/firmware/lcd_i2c_scanner/` | LCD I2C address test |
| `call_station/DIRECT_ESP32_GUIDE.md` | Short companion notes |
| `call_station/firmware/direct_reeman_esp32s3/SOP_DIRECT_ESP32_AMR.md` | **This SOP** (Kunj Radadiya) · product **RhinoCall Point** |
| `MQTT/reeman_forklift_client.py` | PC prove client |
| `portal/` | Mission history web UI |

---

## 16. Simple training script

The ESP32 is a remote.  
The laptop runs the chat room (Mosquitto).  
The robot joins Call Mode on that chat room.

**Panel Task-14:** White = power (~6.3 V → buck 5 V). When Ready, latch **Blue CLOSED** — Green (start) → Yellow (p2 pick) → Red (return home) → OFF. Blue OPEN / **C** only resets box memory — e-stop stops the robot.

**Lab keypad:** **A** / **B** move pallets; **1** / **2** home / charge when idle; **D** stores a mission; **C** clears ESP memory.

Use **MQTTX** (§14) to watch the same traffic the ESP and AMR exchange.

---

## 17. Product naming (your panel)

Your enclosure (two metal latch buttons + Red / Yellow / Green LEDs) is a wall/desk **call point** for the Reeman Rhino.

### Recommended name

| Name | Why |
|------|-----|
| **RhinoCall Point** | Clear: calls the Rhino AMR; “Point” = industrial call-point panel |

**Tagline:** *Press to dispatch · LEDs show the trip.*

### Other good options

| Name | Tone |
|------|------|
| **RTM CallPoint** | Site / company branded |
| **Rhino Dispatch Pad** | Emphasizes job start |
| **CallBox RYG** | Emphasizes Red/Yellow/Green status |
| **StationLink Panel** | Generic industrial IoT |
| **ForgeCall Station** | Strong product feel |

**Model line example:** `RhinoCall Point T14` (Task-14 panel) · firmware folder stays `direct_reeman_esp32s3`.

Pick one name and use it on the enclosure label, SOP title line, and mentor slides.

---

## 18. Revision history

| Rev | Date | Author | Notes |
|-----|------|--------|--------|
| 1.0 | 2026-08-16 | Project | Direct ESP32 SOP baseline |
| 1.1 | 2026-08-17 | Project | A = auto p2→p3 then home |
| 1.2 | 2026-08-17 | Project | Keypad A/B/C/D, LCD, portal missions |
| 2.0 | 2026-08-20 | Kunj Radadiya | Full rewrite: A/B/C/D/1/2; ownership notice |
| 2.1 | 2026-08-23 | Kunj Radadiya | Task-14 panel: Blue start/cancel, G→Y→R→OFF |
| 2.2 | 2026-08-24 | Kunj Radadiya | Map-point change guide; GPIO; 6.3 V→5 V; LED timings |
| **2.3** | **2026-08-24** | **Kunj Radadiya** | MQTTX topic/pub/sub table (§14); product name **RhinoCall Point** (§17) |

**Site robot example (replace if your unit differs):**  
Hostname `rbot55f-260114-003-001` · Points `home`, `charge`, `p2`, `p3`

---

## MADE BY KUNJ RADADIYA

**Document:** `call_station/firmware/direct_reeman_esp32s3/SOP_DIRECT_ESP32_AMR.md`  
**Product (suggested):** **RhinoCall Point**  
**Keep this signature when sharing.** Do not erase or overwrite the author line.

### Panel Task-14 GPIO cheat (`UI_MODE=1`)

| Net | GPIO / connection |
|-----|-------------------|
| White power | B+ ↔ Buck IN+ (not GPIO) · pack **~6.3 V** → buck **5.0 V** |
| Blue Task-14 | **GPIO7** ↔ GND |
| White / Blue ring+ | **GPIO13** / **GPIO14** |
| Green / Yellow / Red IN | **GPIO10** / **11** / **12** |
| Status VCC | common GND |

### Lab breadboard GPIO cheat (`UI_MODE=0` only)

| Color | Job | GPIO |
|-------|-----|------|
| Black | D store | 5 |
| White | 1 home | 4 |
| Green | A forward | 6 |
| Red | C cancel | 7 |
| Yellow | B reverse | 8 |
| Green | 2 charge | 10 |
