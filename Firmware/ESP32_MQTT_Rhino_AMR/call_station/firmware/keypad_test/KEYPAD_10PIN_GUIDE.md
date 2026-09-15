# Keypad wire finder — 10-pin connector with no labels

Your keypad has **10 pins on one ribbon** but no `1`/`A` marks on the wires. That is normal.

## What the 10 pins usually are

| Typical layout | Count |
|----------------|-------|
| Matrix rows + columns | **8 pins** (4 rows + 4 cols) |
| Extra / unused / spacer | **2 pins** (may be NC — not connected) |

You **do not** connect the keypad to **3V3** or **GND** unless a datasheet says so.  
Most 4×4 panels are a **passive matrix** — only 8 wires matter.

---

## Step 1 — Find "Pin 1" on the keypad PCB

Flip the keypad over. At the **10-pin header** on the green PCB:

- **Pin 1** is often marked **`1`**, a **triangle**, or a **square** solder pad (others are round)
- Count **1 → 10** in one direction along the header — do not reverse mid-count

If there is no mark, pick one end as pin 1 and stay consistent.

---

## Step 2 — Connect all 10 pins to ESP32 (test harness)

| Keypad ribbon pin | ESP32 GPIO |
|-------------------|------------|
| **1** | **GPIO 1** |
| **2** | **GPIO 2** |
| **3** | **GPIO 3** |
| **4** | **GPIO 4** |
| **5** | **GPIO 5** |
| **6** | **GPIO 6** |
| **7** | **GPIO 7** |
| **8** | **GPIO 10** |
| **9** | **GPIO 11** |
| **10** | **GPIO 12** |

Power ESP32 via **USB-C** for Serial Monitor.

---

## Step 3 — Upload wire finder

Open and upload:

`call_station/firmware/keypad_test/keypad_wire_finder.ino`

Serial Monitor **115200** → press and **hold** key **A** for about 1 second.

Example output:

```text
Key detected (hold steady):
  Ribbon pin 3 (GPIO 3)  <->  Ribbon pin 9 (GPIO 11)
```

That means key **A** connects ribbon pin 3 and ribbon pin 9.

---

## Step 4 — Map rows and columns

Press every key in the **top row**: `1`, `2`, `3`, `A`.  
They should all share **one** ribbon pin (the **row** for that row).

Press every key in the **right column**: `A`, `B`, `C`, `D`.  
They should all share **one** ribbon pin (the **column**).

Write a table:

| Key | Ribbon pin A | Ribbon pin B |
|-----|--------------|--------------|
| 1 | ? | ? |
| A | ? | ? |
| ... | | |

Group pins that repeat → you get **4 row GPIOs** and **4 col GPIOs**.

---

## Step 5 — Multimeter method (no code)

If the sketch still shows nothing:

1. Set multimeter to **continuity (beep)**
2. Press and hold key **A**
3. Beep **between ribbon pin pairs** until you find the pair that connects
4. That pair is row+col for key A

---

## Step 6 — Update `keypad_test.ino`

Once you know which **4 GPIOs are rows** and which **4 are cols**, edit:

```cpp
const int ROW_PINS[4] = { /* your 4 row GPIOs */ };
const int COL_PINS[4] = { /* your 4 col GPIOs */ };
```

Then upload `keypad_test.ino` again — pressing **A** should print:

```text
A pressed
Task: home -> p2 (pick) -> p3 (place) -> home
```

---

## Why your current test shows nothing

1. **10 pins wired as 8** — two ribbon pins may be the ones you skipped  
2. **Pin 1 counted from wrong end** — whole map shifted  
3. **3V3/GND on matrix pins** — breaks scanning (remove those wires)  
4. **Loose jumper** — press key and wiggle wires while watching Serial

Start with **keypad_wire_finder.ino** and tell me what ribbon pin numbers appear when you hold **A**.
