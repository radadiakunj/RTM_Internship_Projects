# I2C LCD scanner — ESP32-S3

Find the LCD address **before** the main call-station firmware.

## Wiring (LCD only)

| LCD backpack | ESP32-S3 |
|--------------|----------|
| **GND** | **GND** |
| **VCC** | **5V** |
| **SDA** | **GPIO 15** |
| **SCL** | **GPIO 16** |

Match labels on the green PCB (`GND VCC SDA SCL` or `VCC GND SDA SCL`).

Power: USB-C for upload; LCD on ESP **5V**. Or shared buck **5.0 V** to ESP + LCD, common GND. Never 12 V on LCD.

## Run

1. Open `lcd_i2c_scanner.ino`
2. Board **ESP32S3 Dev Module** · Upload
3. Serial **115200** · press **RST**

## Success

LCD:

```text
LCD I2C address
is at 0x27
```

Serial:

```text
RESULT: LCD address = 0x27
Set config.h: LCD_I2C_ADDR = 0x27;
```

## If `none`

1. Swap SDA ↔ SCL  
2. Confirm backlight on (5V/GND)  
3. Turn blue contrast pot  
4. Then use `lcd_keypad_demo` to test A/B messages without AMR  
