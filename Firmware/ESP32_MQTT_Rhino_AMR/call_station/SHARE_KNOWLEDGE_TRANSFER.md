# Knowledge transfer — what to ZIP and share

Use **two separate zips** so mentors get a clean Project 1 package and a clean Project 2 package.

| Zip name (suggested) | Project | Scope |
|----------------------|---------|--------|
| `Project1_Lab_CallStation_KT.zip` | **Project 1** | Lab keypad/LCD/buttons + Task-14 panel + AMR SOP |
| `Project2_Industrial_Numpad_KT.zip` | **Project 2** | Industrial numpad + warehouse pallet cloud only |

---

## Before you zip (both projects)

**Remove / exclude secrets:**

| Do **not** put in the zip | Use instead |
|---------------------------|-------------|
| `config.h` with real Wi‑Fi / token / password | `config.h.example` |
| `cloud/config.json` with real admin password | `config.example.json` |
| `portal/config.json` with real tokens | `config.example.json` |
| Personal photos of passwords / Call Mode token screenshots | Redact first |

**Optional exclude (makes zip smaller):**

- `node_modules/` → recipient runs `npm install`
- `cloud/data/pallets.json` live data (or leave empty sample)
- `.git/` if you zip from a clone

---

# Project 1 — ZIP contents

**Goal of this package:** Lab bring-up + Task-14 panel call station → AMR (SOP + code + circuit sim).

### Include these paths (from repo root)

```text
call_station/
  SOP_DIRECT_ESP32_AMR.md              ← MAIN SOP (share this as the Project 1 SOP)
  FOLDER_INDEX.md
  PROJECTS_KEYPAD_PALLET_CLOUD.md      ← overview (Project 1 + 2 map)
  DIRECT_ESP32_GUIDE.md                ← optional short guide
  REAL_WIFI_MQTT.md                    ← optional network notes

  panel_circuit_sim/
    index.html
    README.md

  firmware/
    direct_reeman_esp32s3/
      direct_reeman_esp32s3.ino
      config.h.example                 ← NOT your secret config.h
      lcd_i2c.h
      verify_aes.py
    panel_latch_led_test/
      panel_latch_led_test.ino
    keypad_test/
      keypad_test.ino
      KEYPAD_10PIN_GUIDE.md
      LIBRARIES.md
    lcd_i2c_scanner/
      lcd_i2c_scanner.ino
      lcd_i2c.h
      README.md
    lcd_keypad_demo/
      lcd_keypad_demo.ino              ← only if you want LCD demo (no secrets)
      lcd_i2c.h
      README.md
    blink_s3_gpio48/
      blink_s3_gpio48.ino

portal/                                ← optional but useful for mission history
  README.md
  package.json
  config.example.json
  server.js
  lib/
  public/
  (exclude node_modules, exclude config.json with secrets)

MQTT/                                  ← optional prove-AMR scripts
  README.md
  reeman_forklift_client.py
  SOP_BEGINNER_GUIDE.md                ← if present
```

### Project 1 — “read these first” (tell recipients)

1. `call_station/SOP_DIRECT_ESP32_AMR.md`  
2. `call_station/panel_circuit_sim/index.html` (open in browser)  
3. `call_station/FOLDER_INDEX.md`  
4. Upload order: blink → `panel_latch_led_test` → `direct_reeman_esp32s3`  

### Project 1 — PowerShell zip example

```powershell
cd D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR

# Create a clean folder then zip (adjust if paths differ)
$out = "$env:TEMP\Project1_Lab_CallStation_KT"
Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $out | Out-Null

Copy-Item call_station\SOP_DIRECT_ESP32_AMR.md $out\
Copy-Item call_station\FOLDER_INDEX.md $out\
Copy-Item call_station\PROJECTS_KEYPAD_PALLET_CLOUD.md $out\
Copy-Item call_station\DIRECT_ESP32_GUIDE.md $out\ -ErrorAction SilentlyContinue
Copy-Item call_station\REAL_WIFI_MQTT.md $out\ -ErrorAction SilentlyContinue
Copy-Item call_station\panel_circuit_sim $out\panel_circuit_sim -Recurse
Copy-Item call_station\firmware\direct_reeman_esp32s3 $out\firmware\direct_reeman_esp32s3 -Recurse
Copy-Item call_station\firmware\panel_latch_led_test $out\firmware\panel_latch_led_test -Recurse
Copy-Item call_station\firmware\keypad_test $out\firmware\keypad_test -Recurse
Copy-Item call_station\firmware\lcd_i2c_scanner $out\firmware\lcd_i2c_scanner -Recurse
Copy-Item call_station\firmware\lcd_keypad_demo $out\firmware\lcd_keypad_demo -Recurse
Copy-Item call_station\firmware\blink_s3_gpio48 $out\firmware\blink_s3_gpio48 -Recurse

# Strip secrets if present
Remove-Item $out\firmware\direct_reeman_esp32s3\config.h -ErrorAction SilentlyContinue

Compress-Archive -Path $out\* -DestinationPath "$PWD\Project1_Lab_CallStation_KT.zip" -Force
Write-Host "Created: $PWD\Project1_Lab_CallStation_KT.zip"
```

---

# Project 2 — ZIP contents

**Goal of this package:** Industrial 4×4 numpad → type pallet ID → press A → cloud **placed** → Excel download. **No AMR.**

### Include this one folder only

```text
call_station/project2_industrial_numpad_pallet/
```

### Inside the zip (keep)

| Path | Why |
|------|-----|
| `README.md` | Quick start |
| `WHAT_TO_SHARE.md` | Share rules |
| `FOLDER_INDEX.md` | File map |
| `docs/SOP_PROJECT2.md` | **MAIN SOP** for Project 2 |
| `docs/WIRING.md` | GPIO / wiring |
| `docs/SHOWCASE_PALLET_VALIDATION.md` | How to explain warehouse validation |
| `firmware/industrial_numpad_demo/*.ino` | ESP32 code |
| `firmware/industrial_numpad_demo/config.h.example` | Template |
| `cloud/package.json` | Dependencies |
| `cloud/server.js` + `lib/` + `public/` | Cloud UI + Excel export |
| `cloud/config.example.json` | Template |

### Exclude from Project 2 zip

| Exclude | Why |
|---------|-----|
| `firmware/.../config.h` | May contain your Wi‑Fi password |
| `cloud/config.json` | May contain admin password |
| `cloud/node_modules/` | Huge; run `npm install` |
| Anything from `SOP_DIRECT_ESP32_AMR.md` / AMR firmware | Not part of Project 2 |

### Project 2 — “read these first”

1. `docs/SOP_PROJECT2.md`  
2. `docs/SHOWCASE_PALLET_VALIDATION.md`  
3. `README.md` → start cloud → upload numpad firmware  

### Project 2 — PowerShell zip example

```powershell
cd D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR

$src = "call_station\project2_industrial_numpad_pallet"
$out = "$env:TEMP\Project2_Industrial_Numpad_KT"
Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item $src $out -Recurse

Remove-Item "$out\firmware\industrial_numpad_demo\config.h" -ErrorAction SilentlyContinue
Remove-Item "$out\cloud\config.json" -ErrorAction SilentlyContinue
Remove-Item "$out\cloud\node_modules" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$out\cloud\data\pallets.json" -ErrorAction SilentlyContinue

Compress-Archive -Path $out\* -DestinationPath "$PWD\Project2_Industrial_Numpad_KT.zip" -Force
Write-Host "Created: $PWD\Project2_Industrial_Numpad_KT.zip"
```

---

## Side-by-side summary

| | **Project 1 zip** | **Project 2 zip** |
|--|-------------------|-------------------|
| **Main SOP** | `SOP_DIRECT_ESP32_AMR.md` | `project2_.../docs/SOP_PROJECT2.md` |
| **Hardware story** | Panel Task-14 / lab keypad → **AMR** | 4×4 numpad → **warehouse pallet ID cloud** |
| **Code focus** | `direct_reeman_esp32s3` + tests | `industrial_numpad_demo` + `cloud/` |
| **Excel pallet log** | No (missions portal optional) | Yes (`:3081` Download Excel) |
| **AMR docs** | Yes | **No** |

---

## One message you can send with the zips

> **Project1_Lab_CallStation_KT.zip** — Lab + Task-14 panel call station SOP and firmware (AMR via Mosquitto). Start with `SOP_DIRECT_ESP32_AMR.md`.  
> **Project2_Industrial_Numpad_KT.zip** — Industrial keypad only: type pallet ID, press A, store as warehouse **placed**, download Excel. Start with `docs/SOP_PROJECT2.md`. No robot code in this zip.
