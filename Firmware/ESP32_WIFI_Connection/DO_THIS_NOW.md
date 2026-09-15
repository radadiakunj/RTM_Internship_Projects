# FAST TASK COMPLETION (before 6:00 PM)

## Goal
Show: `Connected with 192.168.4.1` / `Disconnected with 192.168.4.1`

## Why SoftAP?
Your laptop is on `10.35.39.x` (office/campus WiFi). ESP32 often cannot join that network.
So the ESP32 creates its own WiFi instead.

## Steps (do in order)

### 1) Fix COM port (MUST — about 5–10 min)
1. Plug ESP32 USB into laptop.
2. Open Device Manager → look for yellow warning / Ports (COM & LPT).
3. Install ONE driver:
   - CP210x: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
   - OR CH340: search "CH340 Windows driver" (WCH)
4. Confirm a COMx port appears.

If board USB driver still fails: use any external USB-TTL adapter on ESP32 pins:
`adapter TX→ESP32 RX0 (GPIO3)`, `RX→TX0 (GPIO1)`, `GND→GND`, then select that COM port.

### 2) Flash SoftAP firmware (3 min)
1. Open Arduino IDE → Board: **ESP32 Dev Module**
2. Open file:
   `esp32_softap_fast/esp32_softap_fast.ino`
3. Select the COM port → Upload
4. Serial Monitor 115200 should show: `ESP32 IP: 192.168.4.1`

### 3) Demo connection (2 min)
1. On laptop, connect WiFi to **ESP32-RTM** / password **12345678**
2. Run:

```powershell
python d:\RTM_Tasks\ESP32_WIFI_Connection\wifi_connection_monitor.py --mode wifi --ip 192.168.4.1
```

3. Expected:
   - `Connected with 192.168.4.1`
4. Unplug ESP32 power:
   - `Disconnected with 192.168.4.1`
5. Power ON + reconnect laptop to ESP32-RTM:
   - `Connected with 192.168.4.1`

Optional browser check: http://192.168.4.1

## Do NOT use
`10.35.39.20` = your laptop IP (always looks Connected, not ESP32)
