# BenchWire

Personal beginner dashboard for laying out **your real electronics parts**, wiring them on a virtual canvas, and catching voltage / polarity / ground / current mistakes **before soldering**.

## Run

```bash
npm install
npm run dev
```

Open the local URL Vite prints (usually `http://localhost:5173`).

## What’s in MVP (Manual mode)

- Inventory of your actual parts (Zero PCBs, ESP32, sensors, BTS7960s, bucks, battery, XT60, etc.) with quantities
- Drag components onto a freeform canvas
- Draw wires pin → pin
- Live validation:
  - Over / under voltage
  - Reversed polarity
  - Missing common GND
  - Solar → buck / solar → battery blocked (needs charge controller)
  - ESP32 GPIO over-voltage + ACS712 ADC warning
  - Rail current budget (3.3V / 5V / 12V / BAT / SOLAR)
- Power-rail view with draw vs supply
- **Load starter power chain** — Battery → switch → PDB → XL4016 → 4015 → rails → ESP32 + sensors + solar via charge controller
- Export markdown wiring guide + BOM

## Modes

| Mode | Status |
|------|--------|
| Manual | MVP — use this |
| Guided | Phase 2 placeholder |
| Learn | Phase 2 preview (Ohm’s Law playground + concept cards) |

## Stack

Vite · React · TypeScript · React Flow · Zustand

## Notes

Simulation is **rule-based** (not SPICE). That covers most beginner fry-risk. Analog/transient simulation can come later.
