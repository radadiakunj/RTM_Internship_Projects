"""Data models for scan results and drive information."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Classification(str, Enum):
    NECESSARY = "Necessary"
    UNNECESSARY = "Unnecessary"
    REVIEW = "Review"


class ScanMode(str, Enum):
    DIAGNOSTIC = "diagnostic"
    CLEAN = "clean"


@dataclass
class DriveInfo:
    letter: str
    label: str
    file_system: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    drive_type: str

    @property
    def display_name(self) -> str:
        name = self.label.strip() or "Local Disk"
        return f"{self.letter} ({name})"

    @property
    def used_percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return (self.used_bytes / self.total_bytes) * 100.0


@dataclass
class ScanItem:
    path: str
    name: str
    is_directory: bool
    size_bytes: int
    classification: Classification
    reason: str
    category: str
    selected: bool = False
    safe_to_delete: bool = False

    @property
    def size_display(self) -> str:
        if (
            self.is_directory
            and self.size_bytes == 0
            and self.classification == Classification.NECESSARY
        ):
            return "Protected"
        return format_bytes(self.size_bytes)


@dataclass
class ScanSummary:
    drive: str
    mode: ScanMode
    items: list[ScanItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    scanned_paths: int = 0

    @property
    def unnecessary(self) -> list[ScanItem]:
        return [i for i in self.items if i.classification == Classification.UNNECESSARY]

    @property
    def necessary(self) -> list[ScanItem]:
        return [i for i in self.items if i.classification == Classification.NECESSARY]

    @property
    def review(self) -> list[ScanItem]:
        return [i for i in self.items if i.classification == Classification.REVIEW]

    @property
    def reclaimable_bytes(self) -> int:
        return sum(i.size_bytes for i in self.unnecessary if i.safe_to_delete)

    @property
    def selected_bytes(self) -> int:
        return sum(
            i.size_bytes
            for i in self.items
            if i.selected
            and i.classification == Classification.UNNECESSARY
            and i.safe_to_delete
        )

    @property
    def selected_cleanable(self) -> list[ScanItem]:
        return [
            i
            for i in self.items
            if i.selected
            and i.classification == Classification.UNNECESSARY
            and i.safe_to_delete
        ]


@dataclass
class CleanResult:
    deleted: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    bytes_freed: int = 0
    files_removed: int = 0
    files_skipped: int = 0


def format_bytes(num: int) -> str:
    if num < 0:
        num = 0
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{num} B"
