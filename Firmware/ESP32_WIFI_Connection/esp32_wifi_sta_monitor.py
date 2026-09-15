"""
ESP32 STA WiFi flow in Python

Input:
  WIFI_SSID     = your hotspot / WiFi name
  WIFI_PASSWORD = that WiFi password

Then:
  1) Writes SSID/password into esp32_wifi_firmware.ino
  2) Tries to read ESP32 IPv4 from Serial (115200) if COM port works
  3) Monitors that IP

Output:
  Connected with <ESP32_IP>
  Disconnected with <ESP32_IP>

Run:
  python esp32_wifi_sta_monitor.py
"""

from __future__ import annotations

import ipaddress
import platform
import re
import subprocess
import sys
import time
from pathlib import Path


FIRMWARE_PATH = Path(__file__).with_name("esp32_wifi_firmware") / "esp32_wifi_firmware.ino"
CHECK_INTERVAL_SEC = 1
PING_TIMEOUT_MS = 800
SERIAL_BAUD = 115200
SERIAL_WAIT_SEC = 45


def validate_ipv4(address: str) -> str:
    return str(ipaddress.IPv4Address(address.strip()))


def ping_ok(ip: str) -> bool:
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", str(PING_TIMEOUT_MS), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, PING_TIMEOUT_MS // 1000)), ip]
    try:
        return subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
    except OSError:
        return False


def get_local_ipv4s() -> set[str]:
    found: set[str] = set()
    result = subprocess.run(["ipconfig"], capture_output=True, text=True, check=False)
    for match in re.finditer(r"IPv4 Address[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)", result.stdout):
        found.add(match.group(1))
    return found


def list_com_ports() -> list[str]:
    ports: list[str] = []
    try:
        import winreg
    except ImportError:
        return ports
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
    except OSError:
        return ports
    try:
        i = 0
        while True:
            try:
                _, value, _ = winreg.EnumValue(key, i)
            except OSError:
                break
            if isinstance(value, str) and value.upper().startswith("COM"):
                ports.append(value.upper())
            i += 1
    finally:
        winreg.CloseKey(key)
    return sorted(set(ports))


def update_firmware_credentials(ssid: str, password: str) -> None:
    if not FIRMWARE_PATH.exists():
        raise FileNotFoundError(f"Firmware not found: {FIRMWARE_PATH}")

    text = FIRMWARE_PATH.read_text(encoding="utf-8")

    def repl_ssid(match: re.Match[str]) -> str:
        return f'{match.group(1)}"{ssid}"'

    def repl_pass(match: re.Match[str]) -> str:
        return f'{match.group(1)}"{password}"'

    text2, n1 = re.subn(
        r'(const char\*\s*WIFI_SSID\s*=\s*)"[^"]*"',
        repl_ssid,
        text,
        count=1,
    )
    text2, n2 = re.subn(
        r'(const char\*\s*WIFI_PASSWORD\s*=\s*)"[^"]*"',
        repl_pass,
        text2,
        count=1,
    )
    if n1 != 1 or n2 != 1:
        raise RuntimeError("Could not update WIFI_SSID / WIFI_PASSWORD in firmware.")

    FIRMWARE_PATH.write_text(text2, encoding="utf-8")


def read_ip_from_serial(port: str, wait_sec: int = SERIAL_WAIT_SEC) -> str | None:
    try:
        import serial  # type: ignore
    except ImportError:
        print("pyserial not installed. Install with:  pip install pyserial")
        return None

    pattern = re.compile(
        r"(?:ESP32 IPv4|SoftAP IP|then use IP):\s*(\d+\.\d+\.\d+\.\d+)",
        re.IGNORECASE,
    )
    print(f"Reading Serial on {port} @ {SERIAL_BAUD} for up to {wait_sec}s...")
    print("(Reset the ESP32 once: press EN/RESET button)\n")

    try:
        ser = serial.Serial(port, SERIAL_BAUD, timeout=0.5)
    except Exception as exc:
        print(f"Could not open {port}: {exc}")
        return None

    deadline = time.time() + wait_sec
    buf = ""
    try:
        while time.time() < deadline:
            raw = ser.read(256)
            if raw:
                chunk = raw.decode("utf-8", errors="ignore")
                sys.stdout.write(chunk)
                sys.stdout.flush()
                buf += chunk
                match = pattern.search(buf)
                if match:
                    return match.group(1)
            time.sleep(0.05)
    finally:
        ser.close()
    return None


def monitor_ip(ip: str) -> None:
    local = get_local_ipv4s()
    if ip in local:
        print(
            f"\nWARNING: {ip} is THIS laptop's IP.\n"
            "That will always look Connected. Use the ESP32 IP from Serial.\n"
        )

    print(f"\nMonitoring ESP32 at {ip}")
    print("Power OFF board -> Disconnected | Power ON -> Connected")
    print("Press Ctrl+C to stop.\n")
    print(f"Connecting with {ip}...")

    last = "connecting"
    while True:
        ok = ping_ok(ip)
        if ok and last != "connected":
            print(f"Connected with {ip}")
            last = "connected"
        elif not ok and last == "connected":
            print(f"Disconnected with {ip}")
            print(f"Connecting with {ip}...")
            last = "connecting"
        time.sleep(CHECK_INTERVAL_SEC)


def main() -> int:
    print("=" * 60)
    print("ESP32 WiFi STA monitor (Python)")
    print("=" * 60)
    print(
        "\nLaptop must be on the SAME WiFi as the ESP32 "
        "(e.g. your phone hotspot).\n"
    )

    try:
        ssid = input("Enter WIFI_SSID (hotspot/WiFi name): ").strip()
        password = input("Enter WIFI_PASSWORD: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return 0

    if not ssid:
        print("WIFI_SSID is required.", file=sys.stderr)
        return 1

    try:
        update_firmware_credentials(ssid, password)
    except Exception as exc:
        print(f"Failed to update firmware: {exc}", file=sys.stderr)
        return 1

    print("\nSaved into firmware:")
    print(f"  {FIRMWARE_PATH}")
    print(f"  WIFI_SSID     = {ssid}")
    print(f"  WIFI_PASSWORD = {'*' * len(password)}")

    print("\n" + "-" * 60)
    print("FLASH STEP (needed once, requires COM port / CP210x)")
    print("-" * 60)
    print("1) Open Arduino IDE")
    print("2) Open the file printed above")
    print("3) Board: ESP32 Dev Module")
    print("4) Select COM port -> Upload")
    print("5) Keep laptop on the same hotspot/WiFi")
    print("6) Serial Monitor 115200 should print: ESP32 IPv4: 192.168.x.x")

    ports = list_com_ports()
    print(f"\nCOM ports now: {', '.join(ports) or '(none)'}")

    esp_ip: str | None = None

    if ports:
        try:
            choice = input(
                f"\nRead IP from Serial now? Enter COM port "
                f"[{ports[0]}] or press Enter to skip: "
            ).strip().upper() or ports[0]
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 0
        if choice:
            if not choice.upper().startswith("COM"):
                choice = "COM" + choice
            esp_ip = read_ip_from_serial(choice.upper())
            if esp_ip:
                print(f"\nESP32 IPv4: {esp_ip}")
            else:
                print("\nNo IP found on Serial yet (firmware may not be flashed).")

    if not esp_ip:
        try:
            raw = input(
                "\nEnter ESP32 IPv4 from Serial Monitor "
                "(or leave blank to quit): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 0
        if not raw:
            print(
                "Flash the updated .ino first, read ESP32 IPv4 from Serial, "
                "then run this script again."
            )
            return 1
        try:
            esp_ip = validate_ipv4(raw)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1

    try:
        monitor_ip(esp_ip)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
