# USB not detecting ESP32 — what actually helps

## Important truth
- I cannot make a CP210x/CH340 driver (must be from Silicon Labs / WCH, Microsoft-signed).
- Reinstalling the driver 1000 times will NOT help if Device Manager never shows a new device.
- USB driver != WiFi. Phone hotspot helps only AFTER WiFi firmware is already on the ESP32.

## Run this test now
```powershell
python d:\RTM_Tasks\ESP32_WIFI_Connection\usb_plug_watcher.py
```
Unplug -> Enter -> plug ESP32. It tells you which case you are in.

### Case A — NEW COM port
Flash `esp32_softap_fast`, then join ESP32 WiFi / or use phone hotspot later.

### Case B — New USB device, no COM
Install the matching vendor driver for that VID (script prints which one).

### Case C — No new USB device (your current situation most likely)
Driver downloads cannot fix this. Hardware path is broken:

1. Try another **data** USB cable (many cables are charge-only).
2. Try another port (USB-A on PC, no hub).
3. Confirm board LED lights when plugged.
4. Best fix before deadline: **external USB-TTL (FTDI/CP2102 dongle)** wires:
   - TTL TX -> ESP32 RX0 (GPIO3)
   - TTL RX -> ESP32 TX0 (GPIO1)
   - TTL GND -> ESP32 GND
   - ESP32 powered by its USB or 5V/GND
   Then a COM port appears from the dongle (not from the board chip).

## After you can flash (SoftAP — fastest demo)
1. Upload `esp32_softap_fast/esp32_softap_fast.ino`
2. Laptop joins WiFi `ESP32-RTM` / `12345678`
   OR leave SoftAP and also use phone hotspot only for laptop internet (not required for demo)
3. Run:
```powershell
python d:\RTM_Tasks\ESP32_WIFI_Connection\wifi_connection_monitor.py --mode wifi --ip 192.168.4.1
```
