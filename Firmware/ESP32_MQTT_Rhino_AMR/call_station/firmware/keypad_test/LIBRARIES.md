# Keypad libraries — what you need

## For `keypad_wire_finder.ino` and `keypad_test.ino`

**No library required.**  
These sketches scan GPIO directly. If nothing appears in Serial, the issue is **wiring**, not a missing library.

Install only:
- **ESP32 board support** (Board Manager: `esp32` by Espressif)
- Serial Monitor at **115200**

---

## Optional library (after you know row/col GPIO pins)

Use this only when row and column pins are mapped and you want cleaner code.

| Item | Value |
|------|--------|
| Library name | **Keypad** |
| Authors | Mark Stanley, Alexander Brevig |
| Install | Arduino IDE → **Sketch → Include Library → Manage Libraries** → search **`Keypad`** → Install |

Example (after mapping):

```cpp
#include <Keypad.h>

const byte ROWS = 4;
const byte COLS = 4;
char keys[ROWS][COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[ROWS] = { /* your 4 row GPIOs */ };
byte colPins[COLS] = { /* your 4 col GPIOs */ };

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);
```

The library **does not discover pins for you**. You must still run the wire finder or multimeter first.

---

## LCD library (only when LCD works)

| Library name | **LiquidCrystal I2C** |
| Author | Frank de Brabander |

Not needed for keypad-only Serial test.

---

## If wire finder still shows nothing

1. Remove **3V3/GND** from keypad (matrix = 8–10 GPIO wires only).  
2. Connect **all 10** ribbon pins per `keypad_wire_finder.ino` header.  
3. Find **pin 1** on PCB back (square pad / triangle).  
4. Hold key firmly 1+ second; watch for `[heartbeat] scanning...`.  
5. Multimeter: continuity beep between two ribbon pins while holding **A**.

Send Serial output (including heartbeat lines) if still stuck.
