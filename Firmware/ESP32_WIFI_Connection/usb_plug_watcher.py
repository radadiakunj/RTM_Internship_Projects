"""
Watch for ANY new USB device when you plug the ESP32.

Usage:
  1) UNPLUG the ESP32
  2) python usb_plug_watcher.py
  3) Plug the ESP32 in
  4) Read the result
"""

from __future__ import annotations

import csv
import subprocess
import sys
import time
from io import StringIO


def list_usb() -> dict[str, str]:
    ps = r"""
$ErrorActionPreference='SilentlyContinue'
Get-PnpDevice -PresentOnly |
  Where-Object { $_.InstanceId -like 'USB\VID_*' } |
  Select-Object FriendlyName, InstanceId, Status, Class |
  ConvertTo-Csv -NoTypeInformation
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        check=False,
    )
    devices: dict[str, str] = {}
    if result.returncode != 0 or not result.stdout.strip():
        return devices
    reader = csv.DictReader(StringIO(result.stdout))
    for row in reader:
        instance = (row.get("InstanceId") or "").strip()
        name = (row.get("FriendlyName") or "Unknown").strip()
        status = (row.get("Status") or "").strip()
        clas = (row.get("Class") or "").strip()
        if instance:
            devices[instance] = f"{name} | {status} | {clas}"
    return devices


def list_com() -> list[str]:
    try:
        import winreg
    except ImportError:
        return []
    ports: list[str] = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
    except OSError:
        return []
    try:
        i = 0
        while True:
            try:
                _, value, _ = winreg.EnumValue(key, i)
            except OSError:
                break
            if isinstance(value, str):
                ports.append(value)
            i += 1
    finally:
        winreg.CloseKey(key)
    return sorted(set(ports))


def main() -> int:
    print("USB plug watcher for ESP32")
    print("=" * 50)
    print("1) Make sure ESP32 is UNPLUGGED now.")
    try:
        input("Press Enter when unplugged... ")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return 0

    before = list_usb()
    before_com = set(list_com())
    print(f"Baseline USB devices: {len(before)}")
    print(f"Baseline COM ports: {', '.join(sorted(before_com)) or '(none)'}")
    print("\n2) Now PLUG the ESP32 into the laptop USB port.")
    print("   Watching for 45 seconds...\n")

    seen_new: dict[str, str] = {}
    deadline = time.time() + 45
    while time.time() < deadline:
        now = list_usb()
        for instance, info in now.items():
            if instance not in before and instance not in seen_new:
                seen_new[instance] = info
                print(f"NEW USB DEVICE:\n  {info}\n  {instance}\n")
        time.sleep(1)

    after_com = set(list_com())
    new_com = sorted(after_com - before_com)

    print("=" * 50)
    if new_com:
        print(f"SUCCESS: new COM port(s): {', '.join(new_com)}")
        print("You can flash SoftAP firmware from Arduino IDE now.")
        return 0

    if seen_new:
        print("Windows SEES a new USB device, but NO COM port yet.")
        print("That means install/update the driver for THIS device:")
        for instance, info in seen_new.items():
            print(f"  {info}")
            print(f"  {instance}")
            upper = instance.upper()
            if "VID_10C4" in upper:
                print("  -> This is Silicon Labs CP210x. Install CP210x VCP driver.")
            elif "VID_1A86" in upper:
                print("  -> This is CH340/CH9102. Install WCH CH340 driver.")
            elif "VID_0403" in upper:
                print("  -> This is FTDI. Install FTDI VCP driver.")
            elif "VID_303A" in upper:
                print("  -> Espressif USB. Try Windows Update driver / esp32 usb driver.")
            else:
                print("  -> Unknown chip. In Device Manager: Update driver -> Search automatically.")
        return 0

    print("FAIL: Windows detected NO new USB device at all.")
    print("A driver CANNOT fix this. Try in order:")
    print("  1) Different USB cable (must be data+power, not charge-only)")
    print("  2) Different USB port (try USB-A directly, avoid hub)")
    print("  3) Check ESP32 power LED is ON when plugged")
    print("  4) Hold BOOT button while plugging in, then release")
    print("  5) External USB-TTL adapter on TX0/RX0/GND (best workaround)")
    print()
    print("Note: USB drivers do NOT connect ESP32 to phone hotspot WiFi.")
    print("USB is only for flashing. WiFi works AFTER firmware is uploaded.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
