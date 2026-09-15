# What to share — Project 2

**Share this whole folder:**

```text
call_station/project2_industrial_numpad_pallet/
```

That is the complete Project 2 package (docs + ESP32 code + cloud).

## Minimum share set (zip for mentors)

| Include | Why |
|---------|-----|
| `README.md` | Quick start + warehouse idea |
| `FOLDER_INDEX.md` | Every file explained |
| `docs/SOP_PROJECT2.md` | Full SOP (GPIO, power, map points, Excel) |
| `docs/WIRING.md` | Pin wiring |
| `docs/SHOWCASE_PALLET_VALIDATION.md` | How to explain “pallet ID = placed in warehouse” |
| `firmware/industrial_numpad_demo/` | Arduino sketch + `config.h.example` (**not** your secret `config.h` with Wi‑Fi password) |
| `cloud/` | Server + UI (`package.json`, `lib/`, `public/`, `config.example.json`) |

## Do **not** share secrets

- `firmware/.../config.h` if it has real Wi‑Fi / MQTT passwords  
- `cloud/config.json` if it has real `adminPassword` / broker credentials  
- Use `*.example` files instead  

## Optional extras inside this folder only

Everything needed is already under `project2_industrial_numpad_pallet/`.  
Do not mix other call_station SOPs into the Project 2 zip unless someone asks.

## One-line pitch

> Operator types a pallet number on a 4×4 telephone keypad, presses **A**, and that ID is stored in the cloud as **warehouse placement validated**. Mentors download an **Excel-friendly** file; only an **admin** can void a wrong ID.
