"""Scan a drive and classify folders/files with sizes and reasons."""

from __future__ import annotations

import os
from typing import Callable, Optional

from .models import Classification, ScanItem, ScanMode, ScanSummary
from .rules import classify_path, _norm

ProgressCallback = Callable[[str, int], None]


def _dir_size(path: str, cancel_check: Optional[Callable[[], bool]] = None) -> int:
    total = 0
    try:
        for root, dirs, files in os.walk(path, topdown=True, onerror=lambda e: None):
            if cancel_check and cancel_check():
                break
            # Skip reparse points / junctions that can loop
            dirs[:] = [d for d in dirs if not _is_reparse(os.path.join(root, d))]
            for name in files:
                fp = os.path.join(root, name)
                try:
                    if _is_reparse(fp):
                        continue
                    total += os.path.getsize(fp)
                except OSError:
                    continue
    except OSError:
        pass
    return total


def _is_reparse(path: str) -> bool:
    try:
        st = os.lstat(path)
        attrs = getattr(st, "st_file_attributes", 0)
        return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except OSError:
        return False


def _file_size(path: str) -> int:
    try:
        if _is_reparse(path):
            return 0
        return os.path.getsize(path)
    except OSError:
        return 0


def _item_from_path(
    path: str,
    is_dir: bool,
    match,
    size: int,
    *,
    preselect: bool = False,
) -> ScanItem:
    can_clean = match.classification == Classification.UNNECESSARY and match.safe_to_delete
    return ScanItem(
        path=path,
        name=os.path.basename(path.rstrip("\\/")) or path,
        is_directory=is_dir,
        size_bytes=size,
        classification=match.classification,
        reason=match.reason,
        category=match.category,
        # Only Clean mode pre-selects reclaimable items; Diagnostic never does
        selected=bool(preselect and can_clean),
        safe_to_delete=match.safe_to_delete,
    )


# Well-known scan targets relative to drive (always attempt if present)
_KNOWN_TARGETS = [
    "$Recycle.Bin",
    "Windows\\Temp",
    "Windows\\SoftwareDistribution\\Download",
    "Windows\\Prefetch",
    "Windows\\Logs",
    "Windows\\Minidump",
    "Temp",
    "Windows",
    "Program Files",
    "Program Files (x86)",
    "ProgramData",
    "Users",
    "Recovery",
    "System Volume Information",
    "pagefile.sys",
    "hiberfil.sys",
    "swapfile.sys",
]


def scan_drive(
    drive_letter: str,
    mode: ScanMode = ScanMode.DIAGNOSTIC,
    progress: Optional[ProgressCallback] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> ScanSummary:
    """
    Scan the selected drive.

    - Reports Necessary system/user areas (with reasons) so the client sees what is protected.
    - Reports Unnecessary reclaimable areas (with reasons) that can be cleaned.
    - Reports Review items (e.g. Downloads / AppData) that need human judgment.
    """
    root = drive_letter.rstrip("\\/") + "\\"
    # Never auto-select — user explicitly checks what to remove
    preselect = False

    summary = ScanSummary(drive=drive_letter.rstrip("\\"), mode=mode)
    seen: set[str] = set()
    count = 0

    def report(msg: str) -> None:
        nonlocal count
        count += 1
        summary.scanned_paths = count
        if progress:
            progress(msg, count)

    def add_item(path: str, is_dir: bool, compute_size: bool = True) -> None:
        key = _norm(path)
        if key in seen:
            return
        match = classify_path(path, is_dir)
        if match is None:
            return
        seen.add(key)
        report(path)
        size = 0
        # Deep size only for reclaimable / review targets — never walk entire Windows / Program Files
        should_size = compute_size and (
            match.classification in (Classification.UNNECESSARY, Classification.REVIEW)
            or not is_dir
        )
        if should_size:
            if is_dir:
                size = _dir_size(path, cancel_check)
            else:
                size = _file_size(path)
        summary.items.append(_item_from_path(path, is_dir, match, size, preselect=preselect))

    # Root-level known targets
    for rel in _KNOWN_TARGETS:
        if cancel_check and cancel_check():
            summary.errors.append("Scan cancelled by user.")
            break
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        is_dir = os.path.isdir(path)
        try:
            add_item(path, is_dir, compute_size=True)
        except OSError as exc:
            summary.errors.append(f"{path}: {exc}")

    # Per-user temp / cache / profile highlights
    users_dir = os.path.join(root, "Users")
    if os.path.isdir(users_dir):
        try:
            profiles = [
                d
                for d in os.listdir(users_dir)
                if os.path.isdir(os.path.join(users_dir, d))
                and d.lower() not in ("public", "default", "default user", "all users")
            ]
        except OSError as exc:
            summary.errors.append(f"{users_dir}: {exc}")
            profiles = []

        user_targets = [
            ("AppData\\Local\\Temp", True),
            ("AppData\\Local\\Microsoft\\Windows\\INetCache", True),
            ("AppData\\Local\\Microsoft\\Windows\\WebCache", True),
            ("AppData\\Local\\CrashDumps", True),
            ("AppData\\Local\\pip\\cache", True),
            ("AppData\\Local\\npm-cache", True),
            ("AppData\\Roaming\\Microsoft\\Windows\\Recent", True),
            ("Documents", True),
            ("Desktop", True),
            ("Pictures", True),
            ("Videos", True),
            ("Music", True),
            ("Downloads", True),
            ("OneDrive", True),
        ]

        for profile in profiles:
            if cancel_check and cancel_check():
                summary.errors.append("Scan cancelled by user.")
                break
            for rel, is_dir_expected in user_targets:
                path = os.path.join(users_dir, profile, rel)
                if not os.path.exists(path):
                    continue
                is_dir = os.path.isdir(path)
                try:
                    add_item(path, is_dir, compute_size=True)
                except OSError as exc:
                    summary.errors.append(f"{path}: {exc}")

            # Thumbnail cache files
            thumb_dir = os.path.join(
                users_dir, profile, "AppData", "Local", "Microsoft", "Windows", "Explorer"
            )
            if os.path.isdir(thumb_dir):
                try:
                    for name in os.listdir(thumb_dir):
                        if name.lower().startswith("thumbcache_"):
                            fp = os.path.join(thumb_dir, name)
                            if os.path.isfile(fp):
                                add_item(fp, False, compute_size=True)
                except OSError as exc:
                    summary.errors.append(f"{thumb_dir}: {exc}")

    # Sort: Unnecessary first (by size), then Review, then Necessary
    order = {
        Classification.UNNECESSARY: 0,
        Classification.REVIEW: 1,
        Classification.NECESSARY: 2,
    }
    summary.items.sort(
        key=lambda i: (order.get(i.classification, 9), -i.size_bytes, i.path.lower())
    )

    return summary
