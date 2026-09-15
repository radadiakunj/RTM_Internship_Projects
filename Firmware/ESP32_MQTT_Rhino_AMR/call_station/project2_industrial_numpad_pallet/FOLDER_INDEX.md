# Project 2 — Folder index

Complete map of files under `call_station/project2_industrial_numpad_pallet/`.

| Updated | 2026-08-24 |

## What to share with others

See **[`WHAT_TO_SHARE.md`](WHAT_TO_SHARE.md)** — zip this whole folder (without secrets).

## Tree

```text
project2_industrial_numpad_pallet/
├── README.md
├── WHAT_TO_SHARE.md                 ← which files to give mentors
├── FOLDER_INDEX.md                  ← this file
├── docs/
│   ├── SOP_PROJECT2.md              ← main SOP (GPIO, power, map points, Excel)
│   ├── WIRING.md                    ← keypad + LCD pins
│   └── SHOWCASE_PALLET_VALIDATION.md← explain “ID = placed in warehouse”
├── firmware/
│   └── industrial_numpad_demo/
│       ├── industrial_numpad_demo.ino
│       ├── config.h                 ← local secrets (do not share)
│       └── config.h.example
└── cloud/
    ├── package.json
    ├── server.js
    ├── config.example.json
    ├── config.json                  ← local secrets (do not share)
    ├── .gitignore
    ├── lib/pallets.js
    ├── lib/palletListener.js
    ├── data/pallets.json
    ├── public/index.html
    └── node_modules/                ← from npm install (optional to zip)
```

## File purposes

| File | Purpose |
|------|---------|
| `README.md` | Quick start |
| `WHAT_TO_SHARE.md` | Share checklist |
| `FOLDER_INDEX.md` | Inventory |
| `docs/SOP_PROJECT2.md` | Full SOP for operators + engineers |
| `docs/WIRING.md` | Hardware pins |
| `docs/SHOWCASE_PALLET_VALIDATION.md` | Mentor / demo explanation |
| `firmware/industrial_numpad_demo/*.ino` | ESP32: type ID → A → MQTT `placed` |
| `firmware/.../config.h.example` | Template Wi‑Fi / MQTT |
| `cloud/server.js` | HTTP + MQTT listener :3081 |
| `cloud/lib/pallets.js` | Store + CSV/Excel export |
| `cloud/lib/palletListener.js` | Subscribe `callstation/pallet/record` |
| `cloud/public/index.html` | Web UI list / download / admin void |
| `cloud/data/pallets.json` | Runtime database |

## Related outside this folder

*(None required for Project 2. This folder is self-contained for industrial numpad + cloud.)*

