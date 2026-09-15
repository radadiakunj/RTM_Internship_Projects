# RTM Internship — Month 1 (`RTM_Internship_1_Mon`)

Internship deliverables for **RoboTechMech (RTM)** — Rhino AMR / ESP32 call-station work (Orcha & StowProof related tasks).

## Repository structure

```text
RTM_Internship_1_Mon/
├── Documentation/          # Reports, BOM, circuits, test sheets
├── Architecture_Design/    # System diagrams & hardware sketches
├── CAD_Design/             # All mechanical / 3D design assets
│   ├── Fusion360/          # Native Fusion designs (.f3d / .f3z)
│   ├── STL_Files/          # 3D-print meshes (.stl)
│   ├── STEP_Files/         # Interchange CAD (.step / .stp)
│   ├── SolidWorks/         # SolidWorks parts (if any at root)
│   ├── Component_Libraries/# Vendor / GrabCAD component packs
│   └── Scripts/            # Fusion 360 automation scripts
├── Electronics_Systems/    # Electronics systems web app (source)
├── Firmware/               # Embedded & IoT projects
│   ├── ESP32_MQTT_Rhino_AMR/
│   ├── ESP32_WIFI_Connection/
│   └── Industrial_Numpad/
├── Software/               # PC utilities (e.g. drive diagnostics)
└── AMR_Resources/          # Product manuals & SDK reference
```

## What lives where

| File type | Folder |
|-----------|--------|
| `.stl` | `CAD_Design/STL_Files/` (+ component packs when part of a library) |
| `.step` / `.stp` | `CAD_Design/STEP_Files/` |
| `.f3d` / `.f3z` | `CAD_Design/Fusion360/` |
| `.SLDPRT` / `.SLDASM` | `CAD_Design/SolidWorks/` or inside `Component_Libraries/` |
| Fusion Python scripts | `CAD_Design/Scripts/` |
| `.ino` / firmware | `Firmware/` |
| Draw.io / architecture PDFs | `Architecture_Design/` |
| BOM / reports / circuit PDFs | `Documentation/` |

## Setup notes

- Run `npm install` inside any Node project (`Electronics_Systems`, `Firmware/**/portal`, etc.) — `node_modules` is not committed.
- Copy `config.example.json` → `config.json` where needed (local secrets are gitignored).
- Large installers, duplicate ZIPs, incomplete downloads, and personal HR/invoice files were excluded on purpose.

## Original remote note

> Create a project named "Orcha" and "StowProof" during an internship
