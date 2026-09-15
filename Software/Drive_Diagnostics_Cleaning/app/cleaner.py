"""Reliable deletion of user-selected Unnecessary items only."""

from __future__ import annotations

import ctypes
import os
import shutil
import stat
import subprocess
import tempfile
from typing import Callable, Optional

from .models import CleanResult, Classification, ScanItem, format_bytes
from .rules import is_protected_path, _rel_to_drive, _norm

ProgressCallback = Callable[[str, int, int], None]

_KEEP_DIRECTORY_ROOTS = (
    r"$recycle.bin",
    r"windows\temp",
    r"windows\softwaredistribution\download",
    r"windows\prefetch",
    r"windows\logs",
    r"windows\minidump",
    r"temp",
)

_USER_KEEP_SUFFIXES = (
    r"\appdata\local\temp",
    r"\appdata\local\microsoft\windows\inetcache",
    r"\appdata\local\microsoft\windows\webcache",
    r"\appdata\local\crashdumps",
    r"\appdata\local\pip\cache",
    r"\appdata\local\npm-cache",
    r"\appdata\roaming\microsoft\windows\recent",
)

FILE_ATTRIBUTE_NORMAL = 0x80


def _on_rm_error(func, path, _exc_info):
    try:
        _force_writable(path)
        func(path)
    except OSError:
        pass


def _force_writable(path: str) -> None:
    try:
        ctypes.windll.kernel32.SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL)
    except Exception:
        pass
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def _path_size(path: str) -> int:
    if not os.path.exists(path):
        return 0
    if os.path.isfile(path) or os.path.islink(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    try:
        for root, dirs, files in os.walk(path, topdown=True, onerror=lambda e: None):
            for name in files:
                fp = os.path.join(root, name)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    continue
    except OSError:
        pass
    return total


def _should_keep_directory_root(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    rel = _rel_to_drive(path).replace("/", "\\")
    for root in _KEEP_DIRECTORY_ROOTS:
        if rel == root:
            return True
    return any(rel.endswith(suf) or rel.endswith(suf.lstrip("\\")) for suf in _USER_KEEP_SUFFIXES)


def _is_recycle_bin(path: str) -> bool:
    return _rel_to_drive(path) == r"$recycle.bin"


def _empty_recycle_bin(drive_letter: str) -> tuple[bool, str, int]:
    """Use Windows Shell API to empty recycle bin for a drive."""
    before_free = _disk_free(drive_letter)
    # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    flags = 0x00000001 | 0x00000002 | 0x00000004
    root = drive_letter if drive_letter.endswith("\\") else drive_letter + "\\"
    try:
        result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, root, flags)
        # S_OK = 0; ERROR_NOT_FOUND-ish codes still OK if already empty
        after_free = _disk_free(drive_letter)
        freed = max(0, after_free - before_free)
        if result in (0, -2147418113, 0x80070002, 2147942402):
            return True, "", freed
        # Non-zero HRESULT — still may have partially emptied
        if freed > 0:
            return True, "", freed
        return False, f"Recycle Bin API returned code {result}", 0
    except Exception as exc:
        return False, str(exc), 0


def _disk_free(drive_letter: str) -> int:
    root = drive_letter if drive_letter.endswith("\\") else drive_letter + "\\"
    free = ctypes.c_ulonglong(0)
    total = ctypes.c_ulonglong(0)
    total_free = ctypes.c_ulonglong(0)
    ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(root),
        ctypes.byref(free),
        ctypes.byref(total),
        ctypes.byref(total_free),
    )
    return int(total_free.value) if ok else 0


def _robocopy_mirror_clear(path: str) -> tuple[int, int]:
    """
    Windows-reliable folder clear: mirror an empty dir into the target.
    Returns (removed_hint, skipped_hint).
    """
    removed = 0
    skipped = 0
    empty = tempfile.mkdtemp(prefix="ddc_empty_")
    try:
        # /MIR mirrors empty → deletes target children. Exit codes 0-7 are success-ish.
        proc = subprocess.run(
            ["robocopy", empty, path, "/MIR", "/R:1", "/W:0", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # Count remaining
        try:
            leftover = list(os.scandir(path))
            skipped = len(leftover)
        except OSError:
            skipped = 0
        if proc.returncode < 8:
            removed = 1
    except OSError:
        skipped = 1
    finally:
        shutil.rmtree(empty, ignore_errors=True)
    return removed, skipped


def _clear_directory_contents(path: str) -> tuple[bool, str, int, int, int]:
    """
    Clear children; keep directory.
    Returns (ok, error, bytes_freed, files_removed, files_skipped).
    """
    before = _path_size(path)
    removed = 0
    skipped = 0
    errors: list[str] = []

    try:
        entries = list(os.scandir(path))
    except PermissionError:
        # Fallback: robocopy
        _robocopy_mirror_clear(path)
        after = _path_size(path)
        freed = max(0, before - after)
        if freed > 0 or after < before:
            return True, "", freed, 1, 0
        return False, "Access denied — run as Administrator", 0, 0, 0
    except OSError as exc:
        return False, str(exc), 0, 0, 0

    for entry in entries:
        child = entry.path
        try:
            _force_writable(child)
            is_link = entry.is_symlink()
            is_junc = bool(getattr(entry, "is_junction", lambda: False)())
            if is_link or is_junc:
                os.unlink(child)
                removed += 1
                continue
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(child, onerror=_on_rm_error)
                if os.path.exists(child):
                    # Retry with robocopy into the child, then remove child
                    _robocopy_mirror_clear(child)
                    try:
                        os.rmdir(child)
                    except OSError:
                        pass
                if os.path.exists(child):
                    skipped += 1
                    errors.append(f"{os.path.basename(child)}: locked")
                else:
                    removed += 1
            else:
                os.remove(child)
                removed += 1
        except PermissionError:
            skipped += 1
            errors.append(f"{os.path.basename(child)}: access denied")
        except OSError as exc:
            skipped += 1
            errors.append(f"{os.path.basename(child)}: {exc}")

    # If many leftovers, try robocopy sweep once
    try:
        leftover = list(os.scandir(path))
    except OSError:
        leftover = []
    if leftover:
        _robocopy_mirror_clear(path)
        try:
            leftover = list(os.scandir(path))
            skipped = len(leftover)
        except OSError:
            leftover = []

    after = _path_size(path)
    freed = max(0, before - after)
    if removed == 0 and freed == 0 and skipped > 0:
        return False, "; ".join(errors[:3]) or "Nothing could be removed (files locked)", 0, 0, skipped
    return True, "", freed, removed, skipped


def _delete_file(path: str) -> tuple[bool, str, int]:
    before = _path_size(path)
    try:
        _force_writable(path)
        os.remove(path)
        return True, "", before
    except PermissionError:
        return False, "Access denied — file in use or needs Administrator", 0
    except OSError as exc:
        # Retry after attribute clear
        try:
            _force_writable(path)
            os.remove(path)
            return True, "", before
        except OSError:
            return False, str(exc), 0


def _delete_path(path: str) -> tuple[bool, str, int, int, int]:
    """
    Returns (ok, error, bytes_freed, files_removed, files_skipped).
    """
    if not os.path.exists(path):
        return False, "Path no longer exists", 0, 0, 0

    normed = _norm(path)
    if len(normed) <= 2 or (len(normed) == 3 and normed[1] == ":"):
        return False, "Blocked: refusing to delete drive root", 0, 0, 0

    if is_protected_path(path):
        return False, "Blocked: protected system/user path", 0, 0, 0

    # Recycle Bin — Shell API
    if _is_recycle_bin(path):
        drive = os.path.splitdrive(os.path.abspath(path))[0] + "\\"
        ok, err, freed = _empty_recycle_bin(drive)
        # Also try clearing leftover SID folders
        if os.path.isdir(path):
            ok2, err2, freed2, rem, skip = _clear_directory_contents(path)
            return (ok or ok2), (err if not ok and not ok2 else ""), freed + freed2, rem + (1 if ok else 0), skip
        return ok, err, freed, (1 if ok else 0), 0

    if os.path.isdir(path) and not os.path.islink(path):
        if _should_keep_directory_root(path):
            return _clear_directory_contents(path)
        before = _path_size(path)
        try:
            shutil.rmtree(path, onerror=_on_rm_error)
        except OSError:
            pass
        if os.path.exists(path):
            _robocopy_mirror_clear(path)
            try:
                os.rmdir(path)
            except OSError:
                pass
        if os.path.exists(path):
            # Keep trying clear; if still exists report partial
            ok, err, freed, rem, skip = _clear_directory_contents(path)
            return ok, err or "Folder root remains (contents cleared if possible)", freed, rem, skip
        return True, "", before, 1, 0

    ok, err, freed = _delete_file(path)
    return ok, err, freed, (1 if ok else 0), (0 if ok else 1)


def clean_items(
    items: list[ScanItem],
    progress: Optional[ProgressCallback] = None,
    require_unnecessary: bool = True,
) -> CleanResult:
    """Delete only selected Unnecessary + safe_to_delete items."""
    result = CleanResult()
    eligible: list[ScanItem] = []
    for item in items:
        if not item.selected:
            continue
        if require_unnecessary:
            if item.classification != Classification.UNNECESSARY or not item.safe_to_delete:
                result.failed.append(
                    (item.path, "Refused: only selected Unnecessary items can be cleaned")
                )
                continue
        if is_protected_path(item.path):
            result.failed.append((item.path, "Blocked: protected path"))
            continue
        eligible.append(item)

    eligible.sort(key=lambda i: _norm(i.path).count("\\"), reverse=True)
    total = len(eligible)

    for idx, item in enumerate(eligible, start=1):
        if progress:
            progress(item.path, idx, total)
        ok, err, freed, rem, skip = _delete_path(item.path)
        result.files_removed += rem
        result.files_skipped += skip
        if ok and (freed > 0 or rem > 0 or not os.path.exists(item.path) or _should_keep_directory_root(item.path)):
            result.deleted.append(item.path)
            # Prefer measured freed; fall back to scan estimate if OS still reports same (rare)
            result.bytes_freed += freed if freed > 0 else (item.size_bytes if not os.path.exists(item.path) else freed)
            if skip and err:
                result.failed.append((item.path, f"Partial: {err}"))
        else:
            result.failed.append((item.path, err or "Could not remove (locked or access denied)"))

    return result


def describe_clean_plan(items: list[ScanItem]) -> str:
    selected = [
        i
        for i in items
        if i.selected
        and i.classification == Classification.UNNECESSARY
        and i.safe_to_delete
    ]
    if not selected:
        return "No Unnecessary items selected. Check the items you want to remove first."
    total = sum(i.size_bytes for i in selected)
    lines = [
        f"You selected {len(selected)} item(s).",
        f"Estimated space to free: {format_bytes(total)}",
        "",
        "Only these items will be removed:",
    ]
    for i in selected:
        kind = "Folder contents" if i.is_directory else "File"
        lines.append(f"  • {i.name}  ({i.size_display})")
        lines.append(f"      {i.path}")
        lines.append(f"      {kind} — {i.reason}")
    lines.append("")
    lines.append("Necessary and Review items will NOT be touched.")
    return "\n".join(lines)
