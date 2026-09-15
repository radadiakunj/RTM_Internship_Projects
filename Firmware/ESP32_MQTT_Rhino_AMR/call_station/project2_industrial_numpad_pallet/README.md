# Project 2 — Industrial Numpad + Cloud Pallet ID

| Field | Value |
|--------|--------|
| **Folder to share** | **`call_station/project2_industrial_numpad_pallet/`** ← share this |
| **Revision** | 2.0 — 2026-08-24 |
| **SOP** | [`docs/SOP_PROJECT2.md`](docs/SOP_PROJECT2.md) |
| **What to zip** | [`WHAT_TO_SHARE.md`](WHAT_TO_SHARE.md) |
| **File list** | [`FOLDER_INDEX.md`](FOLDER_INDEX.md) |

## Showcase idea

1. Type any integer on the **4×4 Matrix 16-key telephone keypad**.  
2. Press **A**.  
3. Cloud stores that ID with status **`placed`** = **warehouse placement validated**.  
4. Download **Excel** (`.xls`) or CSV — opens in Microsoft Excel.  
5. Only an **administrator** can **Void** a wrong ID.

Explain to mentors: [`docs/SHOWCASE_PALLET_VALIDATION.md`](docs/SHOWCASE_PALLET_VALIDATION.md)  
Full SOP (numpad only): [`docs/SOP_PROJECT2.md`](docs/SOP_PROJECT2.md)

## Quick start

### Cloud
```powershell
cd D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\call_station\project2_industrial_numpad_pallet\cloud
copy config.example.json config.json
npm install
npm start
```
Open **http://localhost:3081** → **Download Excel**

### Firmware
Upload `firmware/industrial_numpad_demo/industrial_numpad_demo.ino`  
(edit Wi‑Fi / `MQTT_HOST` in `config.h` first)

## Keys

| Key | Action |
|-----|--------|
| `0–9` | Pallet ID digits |
| `*` / `#` | Backspace / clear |
| **A** | Save as **placed** (warehouse validated) |
| **C** | Clear local buffer only (cloud unchanged) |

## Related (this folder only)

- SOP: `docs/SOP_PROJECT2.md`  
- Wiring: `docs/WIRING.md`  
- Share checklist: `WHAT_TO_SHARE.md`  
- File list: `FOLDER_INDEX.md`
