"""
Flash ESP32 WiFi firmware WITHOUT Arduino IDE (uses arduino-cli).

Prerequisites:
  1) COM port must exist (CP210x/CH340 working)
  2) arduino-cli installed (winget install ArduinoSA.CLI)

Usage:
  python flash_esp32_cli.py
  python flash_esp32_cli.py --port COM3
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKETCH = ROOT / "esp32_wifi_firmware"
FQBN = "esp32:esp32:esp32"


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


def find_arduino_cli() -> str | None:
    found = shutil.which("arduino-cli")
    if found:
        return found
    candidates = [
        ROOT / "tools" / "arduino-cli.exe",
        Path(r"C:\Program Files\Arduino CLI\arduino-cli.exe"),
        Path.home() / "AppData/Local/Programs/Arduino CLI/arduino-cli.exe",
        Path.home() / "scoop/shims/arduino-cli.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def run(cmd: list[str]) -> int:
    print(">", " ".join(cmd))
    return subprocess.run(cmd, check=False).returncode


def ensure_esp32_core(cli: str) -> int:
    run([cli, "config", "init", "--overwrite"])
    run(
        [
            cli,
            "config",
            "add",
            "board_manager.additional_urls",
            "https://espressif.github.io/arduino-esp32/package_esp32_index.json",
        ]
    )
    code = run([cli, "core", "update-index"])
    if code != 0:
        return code
    # Check if already installed
    result = subprocess.run(
        [cli, "core", "list", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            cores = json.loads(result.stdout)
            for core in cores if isinstance(cores, list) else []:
                if str(core.get("id", "")).startswith("esp32:esp32"):
                    print("ESP32 core already installed.")
                    return 0
        except json.JSONDecodeError:
            pass
    print("Installing esp32:esp32 core (download can take several minutes)...")
    return run([cli, "core", "install", "esp32:esp32"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Flash ESP32 WiFi firmware via arduino-cli")
    parser.add_argument("--port", help="COM port, e.g. COM3")
    parser.add_argument("--skip-install-core", action="store_true")
    args = parser.parse_args()

    cli = find_arduino_cli()
    if not cli:
        print("arduino-cli not found.")
        print("Install with:")
        print("  winget install --id ArduinoSA.CLI -e")
        print("Then reopen the terminal and run this script again.")
        return 1

    print(f"Using: {cli}")
    if not SKETCH.exists():
        print(f"Sketch folder missing: {SKETCH}")
        return 1

    ports = list_com_ports()
    print(f"COM ports: {', '.join(ports) or '(none)'}")
    port = (args.port or (ports[0] if ports else "")).upper()
    if not port:
        print(
            "\nNo COM port detected. Cannot flash.\n"
            "Fix USB/CP210x first (or use external USB-TTL), then retry.\n"
            "Arduino IDE is optional — the blocker is the missing COM port."
        )
        return 1
    if not port.startswith("COM"):
        port = "COM" + port

    if not args.skip_install_core:
        code = ensure_esp32_core(cli)
        if code != 0:
            print("Failed to install ESP32 core.")
            return code

    print(f"\nCompiling {SKETCH} ...")
    code = run([cli, "compile", "--fqbn", FQBN, str(SKETCH)])
    if code != 0:
        print("Compile failed.")
        return code

    print(f"\nUploading to {port} ...")
    print("If upload fails, hold BOOT on the ESP32, start upload, then release.")
    code = run([cli, "upload", "-p", port, "--fqbn", FQBN, str(SKETCH)])
    if code != 0:
        print("Upload failed.")
        return code

    print("\nFlash OK.")
    print("Next:")
    print("  1) Join laptop to the same WiFi/hotspot as in the sketch")
    print("  2) python esp32_wifi_sta_monitor.py")
    print("     (or read ESP32 IPv4 from serial, then monitor that IP)")
    time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
