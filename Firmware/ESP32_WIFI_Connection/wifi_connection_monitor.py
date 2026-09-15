"""
ESP32 connection monitor — WiFi ping or USB COM detect.

Important:
  In --mode wifi, Connected means THAT IPv4 replies to ping.
  Do NOT enter your laptop IP. Enter the ESP32 IP.

Examples
  python wifi_connection_monitor.py --verify
  python wifi_connection_monitor.py --mode wifi --ip 192.168.x.x
  python wifi_connection_monitor.py --scan
  python wifi_connection_monitor.py --commands
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import platform
import re
import socket
import subprocess
import sys
import time
from pathlib import Path


CHECK_INTERVAL_SEC = 1
PING_TIMEOUT_MS = 800
HINT_AFTER_SEC = 3
FIRMWARE_HINT = Path(__file__).with_name("esp32_wifi_firmware") / "esp32_wifi_firmware.ino"


def validate_ipv4(address: str) -> str:
    try:
        return str(ipaddress.IPv4Address(address.strip()))
    except ipaddress.AddressValueError as exc:
        raise ValueError(f"Invalid IPv4 address: {address!r}") from exc


def ping_ok(ip: str) -> bool:
    system = platform.system().lower()
    if system == "windows":
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


def get_local_ipv4s() -> list[str]:
    found: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass

    if platform.system().lower() == "windows":
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            check=False,
        )
        for match in re.finditer(
            r"IPv4 Address[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)",
            result.stdout,
        ):
            found.add(match.group(1))
    return sorted(found)


def get_wifi_info() -> dict[str, str]:
    info = {"ip": "", "mask": "", "gateway": ""}
    if platform.system().lower() != "windows":
        return info

    result = subprocess.run(
        ["ipconfig"],
        capture_output=True,
        text=True,
        check=False,
    )
    blocks = re.split(r"\r?\n(?=\S)", result.stdout)
    wifi_block = ""
    for block in blocks:
        if re.search(r"Wireless LAN adapter Wi-Fi", block, re.IGNORECASE):
            wifi_block = block
            break
    if not wifi_block:
        return info

    ip_m = re.search(r"IPv4 Address[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)", wifi_block)
    mask_m = re.search(r"Subnet Mask[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)", wifi_block)
    gw_m = re.search(r"Default Gateway[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)", wifi_block)
    if ip_m:
        info["ip"] = ip_m.group(1)
    if mask_m:
        info["mask"] = mask_m.group(1)
    if gw_m:
        info["gateway"] = gw_m.group(1)
    return info


def list_com_ports_fast() -> list[str]:
    if platform.system().lower() != "windows":
        return []
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
        index = 0
        while True:
            try:
                _, value, _ = winreg.EnumValue(key, index)
            except OSError:
                break
            if isinstance(value, str) and value.upper().startswith("COM"):
                ports.append(value.upper())
            index += 1
    finally:
        winreg.CloseKey(key)
    return sorted(set(ports))


def wait_enter(prompt: str) -> bool:
    """Return False if user cancels."""
    try:
        input(prompt)
        return True
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return False


def discover_alive_hosts() -> tuple[list[str], dict[str, str], set[str]] | None:
    wifi = get_wifi_info()
    if not wifi["ip"] or not wifi["mask"]:
        print("Could not detect Wi-Fi IPv4/subnet from ipconfig.", file=sys.stderr)
        return None

    network = ipaddress.IPv4Network(f"{wifi['ip']}/{wifi['mask']}", strict=False)
    local_ips = set(get_local_ipv4s())
    hosts = [str(h) for h in network.hosts()]
    if len(hosts) > 1024:
        print(f"Subnet {network} is too large to scan safely.", file=sys.stderr)
        return None

    print(f"Scanning {network} ({len(hosts)} hosts)... please wait.")
    alive: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        futures = {pool.submit(ping_ok, ip): ip for ip in hosts}
        for fut in concurrent.futures.as_completed(futures):
            ip = futures[fut]
            try:
                ok = fut.result()
            except Exception:
                ok = False
            if ok:
                alive.append(ip)

    alive.sort(key=lambda s: tuple(int(p) for p in s.split(".")))
    return alive, wifi, local_ips


def classify_hosts(
    alive: list[str], wifi: dict[str, str], local_ips: set[str]
) -> tuple[list[str], list[str]]:
    """Return (tagged display lines logic via candidates, ignored)."""
    candidates: list[str] = []
    for ip in alive:
        if ip in local_ips or ip == wifi["ip"]:
            continue
        if wifi.get("gateway") and ip == wifi["gateway"]:
            continue
        candidates.append(ip)
    return candidates, alive


def print_alive_report(alive: list[str], wifi: dict[str, str], local_ips: set[str]) -> None:
    if not alive:
        print("  (no hosts replied)")
        return
    for ip in alive:
        tags = []
        if ip in local_ips or ip == wifi["ip"]:
            tags.append("THIS PC - not ESP32")
        if wifi.get("gateway") and ip == wifi["gateway"]:
            tags.append("router/gateway")
        suffix = f"  <- {', '.join(tags)}" if tags else ""
        print(f"  {ip}{suffix}")


def print_plug_and_play_commands() -> None:
    wifi = get_wifi_info()
    pc_ip = wifi["ip"] or "(unknown)"
    gateway = wifi["gateway"] or "(unknown)"

    print(
        f"""
Plug-and-play commands (PowerShell / CMD)
Your laptop Wi-Fi IP right now: {pc_ip}
Router/gateway:                 {gateway}

1) Guided proof that ESP32 is on WiFi
   python wifi_connection_monitor.py --verify

2) Show your PC Wi-Fi details
   ipconfig

3) Ping ESP32 IP (NOT {pc_ip})
   ping -n 4 192.168.x.x

4) See recent LAN devices
   arp -a

5) Scan subnet once
   python wifi_connection_monitor.py --scan

6) Monitor one IP
   python wifi_connection_monitor.py --mode wifi --ip 192.168.x.x

7) Show this laptop's own IPs
   python wifi_connection_monitor.py --whoami

8) USB COM ports (needs CP210x/CH340 or external USB-UART)
   mode
"""
    )


def scan_subnet() -> int:
    result = discover_alive_hosts()
    if result is None:
        return 1
    alive, wifi, local_ips = result
    print(f"Your PC: {wifi['ip']}   Gateway: {wifi['gateway'] or 'unknown'}\n")
    print("Hosts that replied to ping:")
    print_alive_report(alive, wifi, local_ips)
    candidates, _ = classify_hosts(alive, wifi, local_ips)
    print()
    if candidates:
        print("Possible ESP32 / other device IPs:")
        for ip in candidates:
            print(f"  {ip}")
        print("\nTip: run --verify for guided OFF/ON discovery + proof.")
    else:
        print(
            "Only your PC/gateway replied. No other Wi-Fi device is reachable.\n"
            "ESP32 is probably not on WiFi yet (flash WiFi firmware first)."
        )
    return 0


def print_whoami() -> int:
    wifi = get_wifi_info()
    local = get_local_ipv4s()
    print("Addresses belonging to THIS laptop:")
    for ip in local:
        mark = " (Wi-Fi)" if ip == wifi.get("ip") else ""
        print(f"  {ip}{mark}")
    if wifi.get("gateway"):
        print(f"Wi-Fi gateway/router: {wifi['gateway']}")
    print(
        "\nIf you pass any of the laptop addresses to --mode wifi, "
        "it will always say Connected even with no ESP32."
    )
    return 0


def print_io_options() -> None:
    print(
        """
Other inputs / outputs for ESP32-WROOM-32UE:

1) WiFi ping/HTTP     input: ESP32 IPv4         output: Connected/Disconnected
2) Bluetooth          input: BT name/MAC        output: paired/connected
3) External USB-UART  input: TX/RX/GND + COM    output: serial/flash
4) Board USB bridge   input: USB cable          output: COM (needs CP210x/CH340)
"""
    )


def run_status_loop(ip: str, is_connected_fn, mode_label: str) -> None:
    print(f"Mode: {mode_label}")
    print(f"Target: {ip}")
    print(f"Checking every {CHECK_INTERVAL_SEC}s. Press Ctrl+C to stop.\n")
    print(f"Connecting with {ip}...")

    last_state = "connecting"
    waiting_since = time.monotonic()
    hinted = False

    while True:
        connected = is_connected_fn()

        if connected and last_state != "connected":
            print(f"Connected with {ip}")
            last_state = "connected"
            hinted = False
        elif not connected and last_state == "connected":
            print(f"Disconnected with {ip}")
            print(f"Connecting with {ip}...")
            last_state = "connecting"
            waiting_since = time.monotonic()
            hinted = False
        elif not connected and last_state == "connecting" and not hinted:
            if time.monotonic() - waiting_since >= HINT_AFTER_SEC:
                if mode_label.startswith("usb"):
                    print(
                        "Still waiting: no new COM port.\n"
                        "  Try --verify, --mode wifi, --scan, or --commands."
                    )
                else:
                    print(
                        "Still waiting: that IPv4 is not reachable.\n"
                        "  Run: python wifi_connection_monitor.py --verify"
                    )
                hinted = True

        time.sleep(CHECK_INTERVAL_SEC)


def monitor_wifi(ip: str) -> None:
    local_ips = set(get_local_ipv4s())
    if ip in local_ips:
        print(
            f"WARNING: {ip} is THIS laptop's own address.\n"
            f"Connected here does NOT mean ESP32 is on WiFi.\n"
            f"Run --verify to find and prove the ESP32 IP.\n"
        )
    else:
        print(
            "WiFi mode: Connected only while this IPv4 replies to ping.\n"
            "Prove it is the ESP32 by powering the board OFF/ON.\n"
        )
    run_status_loop(ip, lambda: ping_ok(ip), "wifi (ping IPv4)")


def monitor_usb(ip: str) -> None:
    baseline = set(list_com_ports_fast())
    print(f"USB mode baseline COM ports: {', '.join(baseline) or '(none)'}")
    print("Connected when a NEW COM port appears after plug-in.\n")

    def is_connected() -> bool:
        return bool(set(list_com_ports_fast()) - baseline)

    run_status_loop(ip, is_connected, "usb (COM port detect)")


def wait_until(ip: str, want_connected: bool, timeout_sec: float) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        ok = ping_ok(ip)
        if ok == want_connected:
            return True
        time.sleep(CHECK_INTERVAL_SEC)
    return False


def verify_esp32_on_wifi() -> int:
    """
    Guided flow:
      1) WiFi firmware reminder
      2) Find ESP32 IP via OFF/ON subnet scan
      3) Prove with power OFF -> Disconnected, ON -> Connected
    """
    print("=" * 60)
    print("VERIFY: Is the ESP32 really on WiFi?")
    print("=" * 60)

    # ----- Step 1 -----
    print("\nSTEP 1/3 - WiFi firmware (needed once)")
    print("-" * 60)
    print("The ESP32 must already run WiFi firmware that joins your network")
    print("(or creates a SoftAP). Flashing needs serial once:")
    print("  - Working CP210x/CH340 driver, OR")
    print("  - External USB-UART on TX/RX/GND pins")
    if FIRMWARE_HINT.exists():
        print(f"\nArduino sketch ready at:\n  {FIRMWARE_HINT}")
        print("Edit WIFI_SSID / WIFI_PASSWORD, then Upload from Arduino IDE.")
    ports = list_com_ports_fast()
    print(f"\nCOM ports now: {', '.join(ports) or '(none - serial flash not available yet)'}")

    if not wait_enter(
        "\nPress Enter when firmware is already on the ESP32 "
        "(or Enter to continue anyway)... "
    ):
        return 0

    # ----- Step 2 -----
    print("\nSTEP 2/3 - Find the ESP32's own IP (not your laptop IP)")
    print("-" * 60)
    wifi = get_wifi_info()
    print(f"Your laptop Wi-Fi IP: {wifi.get('ip') or '(unknown)'}  <- do NOT use this")
    print(f"Router/gateway:       {wifi.get('gateway') or '(unknown)'}")

    print("\nA) Power OFF the ESP32 now (unplug USB / remove power).")
    if not wait_enter("Press Enter when ESP32 is powered OFF... "):
        return 0

    off_result = discover_alive_hosts()
    if off_result is None:
        return 1
    alive_off, wifi, local_ips = off_result
    print("Hosts while ESP32 is OFF:")
    print_alive_report(alive_off, wifi, local_ips)

    print("\nB) Power ON the ESP32 and wait ~10-20 seconds for WiFi join.")
    if not wait_enter("Press Enter when ESP32 is powered ON and ready... "):
        return 0

    on_result = discover_alive_hosts()
    if on_result is None:
        return 1
    alive_on, wifi, local_ips = on_result
    print("Hosts while ESP32 is ON:")
    print_alive_report(alive_on, wifi, local_ips)

    new_ips = sorted(
        set(alive_on) - set(alive_off),
        key=lambda s: tuple(int(p) for p in s.split(".")),
    )
    # Ignore PC / gateway if they somehow differ between scans
    new_ips = [
        ip
        for ip in new_ips
        if ip not in local_ips
        and ip != wifi.get("ip")
        and ip != wifi.get("gateway")
    ]

    print()
    if new_ips:
        print("NEW IP(s) that appeared after power ON (likely ESP32):")
        for ip in new_ips:
            print(f"  {ip}")
        esp_ip = new_ips[0]
        if len(new_ips) > 1:
            choice = input(
                f"\nEnter ESP32 IP to use [{esp_ip}]: "
            ).strip() or esp_ip
            try:
                esp_ip = validate_ipv4(choice)
            except ValueError as exc:
                print(exc, file=sys.stderr)
                return 1
        else:
            print(f"\nUsing {esp_ip}")
    else:
        candidates, _ = classify_hosts(alive_on, wifi, local_ips)
        print("No brand-new IP appeared between OFF and ON scans.")
        if candidates:
            print("Other non-PC hosts currently online:")
            for ip in candidates:
                print(f"  {ip}")
            choice = input(
                "\nIf you know the ESP32 IP, type it (or press Enter to abort): "
            ).strip()
            if not choice:
                print(
                    "Could not identify ESP32 IP.\n"
                    "Flash WiFi firmware first, then run --verify again."
                )
                return 1
            try:
                esp_ip = validate_ipv4(choice)
            except ValueError as exc:
                print(exc, file=sys.stderr)
                return 1
        else:
            print(
                "No candidate device found on WiFi.\n"
                "Flash the sketch in esp32_wifi_firmware/, join WiFi, then retry --verify."
            )
            return 1

    if esp_ip in local_ips or esp_ip == wifi.get("ip"):
        print(f"ERROR: {esp_ip} is your laptop IP. That cannot prove ESP32 WiFi.")
        return 1

    # ----- Step 3 -----
    print("\nSTEP 3/3 - Prove it: OFF -> Disconnected, ON -> Connected")
    print("-" * 60)
    print(f"Monitoring {esp_ip}")

    print("\nWaiting for Connected...")
    if wait_until(esp_ip, True, timeout_sec=45):
        print(f"Connected with {esp_ip}")
    else:
        print(f"Timed out waiting for Connected with {esp_ip}")
        print("ESP32 may not be on WiFi, or ICMP ping is blocked.")
        return 1

    print("\nNow POWER OFF the ESP32.")
    print("Waiting for Disconnected...")
    if wait_until(esp_ip, False, timeout_sec=60):
        print(f"Disconnected with {esp_ip}")
    else:
        print(
            f"Still reachable after waiting. {esp_ip} is probably NOT the ESP32 "
            "(another always-on device)."
        )
        return 1

    print("\nNow POWER ON the ESP32 again.")
    print("Waiting for Connected...")
    if wait_until(esp_ip, True, timeout_sec=90):
        print(f"Connected with {esp_ip}")
    else:
        print("Timed out waiting for reconnect.")
        return 1

    print("\n" + "=" * 60)
    print("PROOF OK: ESP32 WiFi is working.")
    print(f"ESP32 IPv4: {esp_ip}")
    print("Keep monitoring? (Ctrl+C to stop)")
    print("=" * 60 + "\n")
    run_status_loop(esp_ip, lambda: ping_ok(esp_ip), "wifi verify (proven ESP32)")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor / verify ESP32 over WiFi ping or USB COM port."
    )
    parser.add_argument(
        "--mode",
        choices=("wifi", "usb"),
        default="wifi",
        help="wifi=ping IPv4 (default). usb=COM detect.",
    )
    parser.add_argument("--ip", help="IPv4 for wifi mode / status text.")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Guided flow: firmware check, find ESP32 IP, prove OFF/ON.",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan Wi-Fi subnet for live IPs.",
    )
    parser.add_argument(
        "--whoami",
        action="store_true",
        help="Show this laptop's own IPv4 addresses.",
    )
    parser.add_argument(
        "--commands",
        action="store_true",
        help="Print plug-and-play diagnostic commands.",
    )
    parser.add_argument(
        "--list-io",
        action="store_true",
        help="Print other input/output options.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_io:
        print_io_options()
        return 0
    if args.commands:
        print_plug_and_play_commands()
        return 0
    if args.whoami:
        return print_whoami()
    if args.scan:
        return scan_subnet()
    if args.verify:
        try:
            return verify_esp32_on_wifi()
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            return 0

    try:
        raw = args.ip or input("Enter ESP32 IPv4 address (not your PC IP): ").strip()
        ip = validate_ipv4(raw)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return 0

    try:
        if args.mode == "usb":
            if platform.system().lower() != "windows":
                print("USB mode supports Windows only.", file=sys.stderr)
                return 1
            monitor_usb(ip)
        else:
            monitor_wifi(ip)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
