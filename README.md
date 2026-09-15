# RTM Internship — Month 1

**Repository:** `RTM_Internship_1_Mon`  
**Organization:** RoboTechMech (RTM)  
**Focus:** Rhino AMR integration, ESP32 call-station development, CAD, and internship deliverables related to **Orcha** and **StowProof**

---

## Overview

This repository contains Month-1 internship work covering documentation, system architecture, mechanical CAD, embedded firmware, supporting software tools, reference AMR materials, and project media (photos and videos).

---

## Repository Structure

```text
RTM_Internship_1_Mon/
│
├── Documentation/                 # Project documents and records
│   ├── Reports/                   # Progress reports and summaries
│   ├── BOM/                       # Bills of materials
│   ├── Circuits/                  # Circuit design PDFs
│   └── Testing/                   # Test logs and sheets
│
├── Architecture_Design/           # System and hardware design visuals
│   ├── Diagrams/                  # Architecture diagrams (Draw.io, PDF, HTML, JPG)
│   └── References/                # Sketches and reference images
│
├── CAD_Design/                    # All mechanical / 3D design assets
│   ├── Fusion360/                 # Native Fusion 360 designs (.f3d, .f3z)
│   ├── STL_Files/                 # 3D-print ready meshes (.stl)
│   ├── STEP_Files/                # CAD interchange files (.step, .stp)
│   ├── Component_Libraries/       # Vendor / GrabCAD component packs
│   └── Scripts/                   # Fusion 360 automation scripts
│
├── Firmware/                      # Embedded and IoT firmware projects
│   ├── ESP32_MQTT_Rhino_AMR/      # MQTT call-station and Rhino AMR integration
│   ├── ESP32_WIFI_Connection/     # ESP32 Wi-Fi setup and monitoring tools
│   └── Industrial_Numpad/         # Industrial numpad firmware, cloud, and simulation
│
├── Software/                      # Desktop / utility applications
│   └── Drive_Diagnostics_Cleaning/
│
├── AMR_Resources/                 # Product manuals and SDK references
│   ├── Manuals/
│   └── SDK/
│
├── Photos/                        # Project photographs and site / hardware captures
├── Videos/                        # Project demonstration and process videos
│
├── .gitignore
└── README.md
```

---

## File Placement Guide

| Asset type | Location |
|------------|----------|
| Reports, BOM, circuit PDFs, test sheets | `Documentation/` |
| Architecture diagrams and sketches | `Architecture_Design/` |
| `.stl` files | `CAD_Design/STL_Files/` |
| `.step` / `.stp` files | `CAD_Design/STEP_Files/` |
| `.f3d` / `.f3z` Fusion designs | `CAD_Design/Fusion360/` |
| SolidWorks / vendor component packs | `CAD_Design/Component_Libraries/` |
| Fusion 360 Python scripts | `CAD_Design/Scripts/` |
| Arduino / ESP32 firmware (`.ino`) | `Firmware/` |
| PC utilities | `Software/` |
| AMR manuals and SDK material | `AMR_Resources/` |
| Project photos (`.jpg`, `.jpeg`, `.png`) | `Photos/` |
| Project videos (`.mp4`, etc.) | `Videos/` |

---

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/radadiakunj/RTM_Internship_1_Mon.git
   cd RTM_Internship_1_Mon
   ```
2. For Node.js apps under `Firmware/` (for example `portal` or Testing Server):
   ```bash
   npm install
   ```
3. Where a `config.example.json` exists, copy it to `config.json` and fill in local values.  
   `config.json` is gitignored and must not be committed.

---

## Notes

- `node_modules`, build outputs, local secrets, installers, and duplicate archives are excluded via `.gitignore`.
- CAD assets are grouped by file type so meshes, interchange files, and native designs stay easy to find.
- Photos and videos for the internship are kept at the repository root under `Photos/` and `Videos/`.

---

## Maintainer

Internship repository for RoboTechMech Month-1 deliverables.
