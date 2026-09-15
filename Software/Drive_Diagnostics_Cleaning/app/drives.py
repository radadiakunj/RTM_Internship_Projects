"""Detect and report available Windows drives."""

from __future__ import annotations

import os
import string
import ctypes
from ctypes import wintypes

from .models import DriveInfo, format_bytes

# Drive type constants (GetDriveTypeW)
DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6

_DRIVE_TYPE_NAMES = {
    DRIVE_UNKNOWN: "Unknown",
    DRIVE_NO_ROOT_DIR: "Unavailable",
    DRIVE_REMOVABLE: "Removable",
    DRIVE_FIXED: "Fixed",
    DRIVE_REMOTE: "Network",
    DRIVE_CDROM: "CD/DVD",
    DRIVE_RAMDISK: "RAM Disk",
}


def _get_drive_type(root: str) -> int:
    return ctypes.windll.kernel32.GetDriveTypeW(root)


def _get_volume_label(root: str) -> tuple[str, str]:
    volume_name = ctypes.create_unicode_buffer(261)
    fs_name = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    max_comp = wintypes.DWORD()
    flags = wintypes.DWORD()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        root,
        volume_name,
        ctypes.sizeof(volume_name),
        ctypes.byref(serial),
        ctypes.byref(max_comp),
        ctypes.byref(flags),
        fs_name,
        ctypes.sizeof(fs_name),
    )
    if not ok:
        return "", ""
    return volume_name.value, fs_name.value


def _get_space(root: str) -> tuple[int, int, int]:
    free_bytes_available = ctypes.c_ulonglong(0)
    total_bytes = ctypes.c_ulonglong(0)
    total_free = ctypes.c_ulonglong(0)
    ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(root),
        ctypes.byref(free_bytes_available),
        ctypes.byref(total_bytes),
        ctypes.byref(total_free),
    )
    if not ok:
        return 0, 0, 0
    total = int(total_bytes.value)
    free = int(total_free.value)
    used = max(0, total - free)
    return total, used, free


def list_drives(include_removable: bool = True, include_network: bool = False) -> list[DriveInfo]:
    """Return ready-to-use drives (fixed by default; optional removable/network)."""
    drives: list[DriveInfo] = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        dtype = _get_drive_type(root)
        if dtype in (DRIVE_UNKNOWN, DRIVE_NO_ROOT_DIR, DRIVE_CDROM):
            continue
        if dtype == DRIVE_REMOVABLE and not include_removable:
            continue
        if dtype == DRIVE_REMOTE and not include_network:
            continue

        label, fs = _get_volume_label(root)
        total, used, free = _get_space(root)
        if total <= 0:
            continue

        drives.append(
            DriveInfo(
                letter=f"{letter}:",
                label=label,
                file_system=fs or "Unknown",
                total_bytes=total,
                used_bytes=used,
                free_bytes=free,
                drive_type=_DRIVE_TYPE_NAMES.get(dtype, "Unknown"),
            )
        )
    return drives


def drive_space_summary(drive: DriveInfo) -> str:
    return (
        f"{drive.display_name}  |  "
        f"Free: {format_bytes(drive.free_bytes)} / "
        f"Total: {format_bytes(drive.total_bytes)}  |  "
        f"Used: {drive.used_percent:.1f}%  |  "
        f"{drive.drive_type} ({drive.file_system})"
    )
