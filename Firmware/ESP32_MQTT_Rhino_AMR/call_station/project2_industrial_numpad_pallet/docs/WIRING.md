# Project 2 — Industrial numpad + LCD wiring

Board: **ESP32-S3 Dev Module**. Matches `firmware/industrial_numpad_demo/config.h`.

## LCD (16×2 I2C)

| LCD pin | ESP32-S3 |
|---------|----------|
| GND | GND |
| VCC | **5V** |
| SDA | **GPIO 1** |
| SCL | **GPIO 2** |

Address: often **0x27** (or **0x3F**).

## 4×4 telephone / membrane keypad (16 keys, 8 wires)

| Keypad | ESP32-S3 |
|--------|----------|
| Rows 1–4 | GPIO **12, 11, 10, 8** |
| Cols 1–4 | GPIO **5, 4, 7, 6** |

## Power (~6.3 V pack → 5 V)

| Item | Value |
|------|--------|
| Cells | 4 × ~1.57 V ≈ **6.3 V** |
| Buck OUT | **5.0 V** (≥ **1 A** recommended) |
| ESP | Buck OUT+ → **5V**, OUT− → **GND** |

See current budget in **SOP_PROJECT2.md §8**.

## Do not

- Feed 5 V into keypad GPIO as a power switch.  
- Put admin delete on a physical key.
