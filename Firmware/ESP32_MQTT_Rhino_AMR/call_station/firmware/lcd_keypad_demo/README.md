# LCD + keypad DEMO (no AMR)

Use this to check the **16×2 I2C LCD** and keypad messages **without** Wi‑Fi or robot.

## Step 1 — Wire LCD only (find address)

| LCD pin | ESP32-S3 |
|---------|----------|
| **GND** | **GND** |
| **VCC** | **5V** |
| **SDA** | **GPIO 15** |
| **SCL** | **GPIO 16** |

1. Open `call_station/firmware/lcd_i2c_scanner/lcd_i2c_scanner.ino`
2. Board: **ESP32S3 Dev Module** · Upload · Serial **115200** · press **RST**
3. LCD should show `LCD I2C address` / `is at 0x27` (or `0x3F`)
4. Put that value in main `config.h` as `LCD_I2C_ADDR`

If scan says none: swap SDA↔SCL, check 5V backlight, turn blue contrast screw.

## Step 2 — Wire keypad + LCD (demo screens)

Keep LCD as above. Add keypad:

| Keypad | ESP32-S3 |
|--------|----------|
| Rows | GPIO **12, 11, 10, 8** |
| Cols | GPIO **5, 4, 7, 6** |

1. Open `call_station/firmware/lcd_keypad_demo/lcd_keypad_demo.ino`
2. Install library **Keypad** (Mark Stanley) if needed
3. Upload · Serial **115200**

## Step 3 — Press A (AMR can be OFF)

LCD plays the **same story** as a real A job (display only):

1. `A pressed` / `DEMO no AMR`  
2. `From home` / `Going p2 pick`  
3. `At p2` / `Picking pallet`  
4. `Going p3` / `Place pallet`  
5. `Place done` / `Return home`  
6. `Return home` / `calling home`  
7. `Job complete` / `home p2 p3 done`  
8. back to `Ready (DEMO)`

Also try **B** (reverse screens), **C**, **D**, **1**, **2**.

This proves LCD + keypad. It does **not** move the AMR.
