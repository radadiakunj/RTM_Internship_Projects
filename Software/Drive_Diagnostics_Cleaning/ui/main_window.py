"""Modern Drive Diagnostics & Cleaning UI."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from app.cleaner import clean_items, describe_clean_plan
from app.drives import list_drives
from app.models import Classification, DriveInfo, ScanMode, ScanSummary, format_bytes
from app.scanner import scan_drive

# Light professional palette (utility tool — clear hierarchy, no purple/dark cliché)
BG = "#eef2f6"
SURFACE = "#ffffff"
SURFACE_2 = "#f8fafc"
BORDER = "#d8dee8"
TEXT = "#0f172a"
MUTED = "#64748b"
ACCENT = "#0f766e"
ACCENT_SOFT = "#ccfbf1"
ACCENT_HOVER = "#0d9488"
DANGER = "#dc2626"
DANGER_HOVER = "#b91c1c"
OK = "#059669"
WARN = "#d97706"
ROW_ALT = "#f1f5f9"
SELECT_BG = "#ecfdf5"


class DriveCleanerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Drive Diagnostics & Cleaning")
        self.geometry("1240x780")
        self.minsize(1020, 640)
        self.configure(bg=BG)

        self.drives: list[DriveInfo] = []
        self.selected_drive: Optional[DriveInfo] = None
        self.summary: Optional[ScanSummary] = None
        self._cancel = False
        self._busy = False
        self._item_vars: dict[str, tk.BooleanVar] = {}
        self._filter = tk.StringVar(value="cleanable")

        self._setup_style()
        self._build_ui()
        self.refresh_drives()

    # --- style ---

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=SURFACE, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 20))
        style.configure("H2.TLabel", background=SURFACE, foreground=TEXT, font=("Segoe UI Semibold", 12))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=SURFACE_2, foreground=MUTED, padding=(16, 8), font=("Segoe UI Semibold", 10))
        style.map("TNotebook.Tab", background=[("selected", SURFACE)], foreground=[("selected", ACCENT)])
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#ffffff",
            font=("Segoe UI Semibold", 10),
            padding=(16, 9),
            borderwidth=0,
        )
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#94a3b8")])
        style.configure(
            "Ghost.TButton",
            background=SURFACE,
            foreground=TEXT,
            font=("Segoe UI", 10),
            padding=(12, 8),
            borderwidth=1,
            relief="solid",
        )
        style.map("Ghost.TButton", background=[("active", SURFACE_2)])
        style.configure(
            "Danger.TButton",
            background=DANGER,
            foreground="#ffffff",
            font=("Segoe UI Semibold", 10),
            padding=(16, 9),
            borderwidth=0,
        )
        style.map("Danger.TButton", background=[("active", DANGER_HOVER), ("disabled", "#fca5a5")])
        style.configure("Horizontal.TProgressbar", troughcolor=BORDER, background=ACCENT, thickness=8)
        style.configure(
            "TCombobox",
            fieldbackground=SURFACE,
            background=SURFACE,
            foreground=TEXT,
            arrowcolor=TEXT,
            padding=6,
        )
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE)], foreground=[("readonly", TEXT)])
        style.configure(
            "Treeview",
            background=SURFACE,
            foreground=TEXT,
            fieldbackground=SURFACE,
            borderwidth=0,
            rowheight=32,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background=SURFACE_2,
            foreground=MUTED,
            font=("Segoe UI Semibold", 9),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", SELECT_BG)], foreground=[("selected", TEXT)])
        style.configure("TCheckbutton", background=SURFACE, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Card.TCheckbutton", background=SURFACE, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TRadiobutton", background=SURFACE, foreground=TEXT, font=("Segoe UI", 10))

    # --- layout ---

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(header, text="Drive Diagnostics & Cleaning", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(
            header,
            text="Scan a drive → select Unnecessary items → remove only what you checked.",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        # Toolbar card
        bar = tk.Frame(self, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill="x", padx=24, pady=8)
        inner = tk.Frame(bar, bg=SURFACE)
        inner.pack(fill="x", padx=16, pady=14)

        tk.Label(inner, text="Drive", bg=SURFACE, fg=MUTED, font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w")
        self.drive_var = tk.StringVar()
        self.drive_combo = ttk.Combobox(inner, textvariable=self.drive_var, state="readonly", width=36)
        self.drive_combo.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.drive_combo.bind("<<ComboboxSelected>>", self._on_drive_selected)

        ttk.Button(inner, text="Refresh", style="Ghost.TButton", command=self.refresh_drives).grid(
            row=1, column=1, padx=(10, 0), sticky="w"
        )
        self.scan_btn = ttk.Button(inner, text="Scan drive", style="Accent.TButton", command=self.start_scan)
        self.scan_btn.grid(row=1, column=2, padx=(10, 0), sticky="w")
        self.cancel_btn = ttk.Button(inner, text="Cancel", style="Ghost.TButton", command=self.cancel_scan, state="disabled")
        self.cancel_btn.grid(row=1, column=3, padx=(8, 0), sticky="w")

        self.drive_info_var = tk.StringVar(value="Choose a drive, then click Scan drive.")
        tk.Label(inner, textvariable=self.drive_info_var, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=2, column=0, columnspan=5, sticky="w", pady=(10, 0)
        )

        self.progress = ttk.Progressbar(inner, mode="indeterminate", style="Horizontal.TProgressbar")
        self.progress.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        inner.columnconfigure(4, weight=1)

        # Stats
        stats = tk.Frame(self, bg=BG)
        stats.pack(fill="x", padx=20, pady=(4, 4))
        self.stat_cleanable = self._stat(stats, "Cleanable", "0", OK)
        self.stat_protected = self._stat(stats, "Protected", "0", MUTED)
        self.stat_review = self._stat(stats, "Review", "0", WARN)
        self.stat_selected = self._stat(stats, "Selected to remove", "0 B", DANGER)

        # Main split
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=24, pady=(4, 8))

        # Left: list
        left = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        left.pack(side="left", fill="both", expand=True)

        left_top = tk.Frame(left, bg=SURFACE)
        left_top.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(left_top, text="Results", bg=SURFACE, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(side="left")

        filters = tk.Frame(left_top, bg=SURFACE)
        filters.pack(side="right")
        for value, label in (
            ("cleanable", "Unnecessary"),
            ("protected", "Necessary"),
            ("review", "Review"),
            ("all", "All"),
        ):
            ttk.Radiobutton(
                filters,
                text=label,
                value=value,
                variable=self._filter,
                command=self._render_list,
                style="Card.TCheckbutton",
            ).pack(side="left", padx=4)

        actions = tk.Frame(left, bg=SURFACE)
        actions.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Button(actions, text="Select all Unnecessary", style="Ghost.TButton", command=self.select_all_unnecessary).pack(
            side="left"
        )
        ttk.Button(actions, text="Clear selection", style="Ghost.TButton", command=self.clear_selection).pack(
            side="left", padx=(8, 0)
        )
        self.clean_btn = ttk.Button(
            actions, text="Remove selected", style="Danger.TButton", command=self.start_clean, state="disabled"
        )
        self.clean_btn.pack(side="right")

        # Scrollable checklist
        list_wrap = tk.Frame(left, bg=SURFACE)
        list_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.canvas = tk.Canvas(list_wrap, bg=SURFACE, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_wrap, orient="vertical", command=self.canvas.yview)
        self.list_host = tk.Frame(self.canvas, bg=SURFACE)
        self.list_host.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._list_window = self.canvas.create_window((0, 0), window=self.list_host, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Right: detail
        right = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, width=340)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        tk.Label(right, text="Item details", bg=SURFACE, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        self.detail_title = tk.Label(right, text="Select an item", bg=SURFACE, fg=TEXT, font=("Segoe UI Semibold", 11), wraplength=300, justify="left")
        self.detail_title.pack(anchor="w", padx=16)
        self.detail_meta = tk.Label(right, text="", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9), wraplength=300, justify="left")
        self.detail_meta.pack(anchor="w", padx=16, pady=(6, 0))
        self.detail_reason = tk.Label(
            right,
            text="After scanning, check Unnecessary items on the left, then click Remove selected.",
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI", 10),
            wraplength=300,
            justify="left",
        )
        self.detail_reason.pack(anchor="w", padx=16, pady=(14, 0))

        tip = tk.Frame(right, bg=ACCENT_SOFT)
        tip.pack(fill="x", padx=16, pady=20)
        tk.Label(
            tip,
            text="Tip: For Windows\\Temp, Prefetch, and Update cache, run this app as Administrator so locked system files can be cleared.",
            bg=ACCENT_SOFT,
            fg=ACCENT,
            font=("Segoe UI", 9),
            wraplength=290,
            justify="left",
        ).pack(padx=10, pady=10)

        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self.status_var, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(
            anchor="w", padx=26, pady=(0, 12)
        )

    def _stat(self, parent, title: str, value: str, color: str) -> tk.StringVar:
        card = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        card.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        tk.Label(card, text=title, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(10, 0))
        var = tk.StringVar(value=value)
        tk.Label(card, textvariable=var, bg=SURFACE, fg=color, font=("Segoe UI Semibold", 14)).pack(
            anchor="w", padx=12, pady=(2, 10)
        )
        return var

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._list_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # --- drives ---

    def refresh_drives(self) -> None:
        previous = self.selected_drive.letter if self.selected_drive else None
        try:
            self.drives = list_drives(include_removable=True, include_network=False)
        except Exception as exc:
            messagebox.showerror("Drive list failed", str(exc))
            self.drives = []
        labels = [f"{d.display_name}  ·  {format_bytes(d.free_bytes)} free" for d in self.drives]
        self.drive_combo["values"] = labels
        if not self.drives:
            self.selected_drive = None
            self.drive_info_var.set("No drives found.")
            return
        idx = 0
        if previous:
            for i, d in enumerate(self.drives):
                if d.letter == previous:
                    idx = i
                    break
        self.drive_combo.current(idx)
        self._on_drive_selected()

    def _on_drive_selected(self, _event=None) -> None:
        idx = self.drive_combo.current()
        if idx < 0 or idx >= len(self.drives):
            self.selected_drive = None
            return
        d = self.drives[idx]
        self.selected_drive = d
        self.drive_info_var.set(
            f"{d.display_name}  |  Free {format_bytes(d.free_bytes)} / {format_bytes(d.total_bytes)}  |  "
            f"Used {d.used_percent:.1f}%  |  {d.drive_type} ({d.file_system})"
        )

    # --- scan ---

    def start_scan(self) -> None:
        if self._busy:
            return
        if not self.selected_drive:
            messagebox.showwarning("Select a drive", "Please choose a drive first.")
            return
        self._cancel = False
        self._set_busy(True)
        self.status_var.set(f"Scanning {self.selected_drive.letter}…")
        self.progress.start(12)
        self._clear_list()

        drive = self.selected_drive.letter

        def worker():
            try:
                summary = scan_drive(
                    drive,
                    mode=ScanMode.DIAGNOSTIC,
                    progress=lambda msg, n: self.after(
                        0, lambda m=msg, c=n: self.status_var.set(f"Scanning ({c}): {m}")
                    ),
                    cancel_check=lambda: self._cancel,
                )
                self.after(0, lambda: self._on_scan_done(summary, None))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_scan_done(None, e))

        threading.Thread(target=worker, daemon=True).start()

    def cancel_scan(self) -> None:
        self._cancel = True
        self.status_var.set("Cancelling…")

    def _on_scan_done(self, summary: Optional[ScanSummary], error: Optional[Exception]) -> None:
        self.progress.stop()
        self._set_busy(False)
        if error:
            self.status_var.set("Scan failed.")
            messagebox.showerror("Scan failed", str(error))
            return
        assert summary is not None
        self.summary = summary
        self._filter.set("cleanable")
        self._update_stats()
        self._render_list()
        reclaim = format_bytes(summary.reclaimable_bytes)
        self.status_var.set(
            f"Scan complete — {len(summary.unnecessary)} cleanable · ~{reclaim} reclaimable. "
            "Check items, then click Remove selected."
        )
        if not summary.unnecessary:
            messagebox.showinfo(
                "Scan complete",
                f"No Unnecessary items found on {summary.drive}.\nProtected/Review items are listed for reference.",
            )

    # --- selection / clean ---

    def select_all_unnecessary(self) -> None:
        if not self.summary:
            return
        for item in self.summary.unnecessary:
            if item.safe_to_delete:
                item.selected = True
                var = self._item_vars.get(item.path)
                if var is not None:
                    var.set(True)
        self._update_stats()
        self._sync_clean_btn()

    def clear_selection(self) -> None:
        if not self.summary:
            return
        for item in self.summary.items:
            item.selected = False
        for var in self._item_vars.values():
            var.set(False)
        self._update_stats()
        self._sync_clean_btn()

    def start_clean(self) -> None:
        if self._busy or not self.summary:
            return
        selected = self.summary.selected_cleanable
        if not selected:
            messagebox.showwarning(
                "Nothing selected",
                "Check one or more Unnecessary items first, then click Remove selected.",
            )
            return
        plan = describe_clean_plan(self.summary.items)
        if not messagebox.askyesno("Confirm removal", plan + "\n\nThis cannot be undone. Continue?", icon="warning"):
            return

        self._set_busy(True)
        self.status_var.set("Removing selected items…")
        self.progress.start(12)
        items = list(self.summary.items)

        def worker():
            try:
                result = clean_items(
                    items,
                    progress=lambda p, i, t: self.after(
                        0,
                        lambda path=p, cur=i, tot=t: self.status_var.set(f"Removing ({cur}/{tot}): {path}"),
                    ),
                )
                self.after(0, lambda: self._on_clean_done(result, None))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_clean_done(None, e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_clean_done(self, result, error) -> None:
        self.progress.stop()
        self._set_busy(False)
        if error:
            messagebox.showerror("Clean failed", str(error))
            self.status_var.set("Clean failed.")
            return

        freed = format_bytes(result.bytes_freed)
        msg = (
            f"Removed from {len(result.deleted)} selected path(s).\n"
            f"Files cleared: {result.files_removed}\n"
            f"Space freed: {freed}"
        )
        if result.files_skipped:
            msg += f"\nSkipped (locked/in use): {result.files_skipped}"
        if result.failed:
            msg += f"\n\n{len(result.failed)} path(s) had issues:\n"
            msg += "\n".join(f"• {p}\n    {e}" for p, e in result.failed[:6])
            if len(result.failed) > 6:
                msg += f"\n… and {len(result.failed) - 6} more"
            msg += "\n\nTip: Run as Administrator for Windows system folders."
        messagebox.showinfo("Clean finished", msg)
        self.status_var.set(f"Clean finished — {freed} freed. Re-scanning…")
        self.refresh_drives()
        self.start_scan()

    # --- list rendering ---

    def _clear_list(self) -> None:
        for child in self.list_host.winfo_children():
            child.destroy()
        self._item_vars.clear()

    def _filtered_items(self):
        if not self.summary:
            return []
        f = self._filter.get()
        if f == "cleanable":
            return self.summary.unnecessary
        if f == "protected":
            return self.summary.necessary
        if f == "review":
            return self.summary.review
        return self.summary.items

    def _render_list(self) -> None:
        self._clear_list()
        items = self._filtered_items()
        if not items:
            tk.Label(
                self.list_host,
                text="No items in this view. Scan a drive to begin.",
                bg=SURFACE,
                fg=MUTED,
                font=("Segoe UI", 10),
            ).pack(anchor="w", padx=16, pady=24)
            return

        for idx, item in enumerate(items):
            bg = SURFACE if idx % 2 == 0 else ROW_ALT
            row = tk.Frame(self.list_host, bg=bg, cursor="hand2")
            row.pack(fill="x", padx=6, pady=1)

            cleanable = item.classification == Classification.UNNECESSARY and item.safe_to_delete
            if cleanable:
                var = tk.BooleanVar(value=item.selected)
                self._item_vars[item.path] = var

                def on_toggle(it=item, v=var):
                    it.selected = bool(v.get())
                    self._update_stats()
                    self._sync_clean_btn()

                chk = tk.Checkbutton(
                    row,
                    variable=var,
                    command=on_toggle,
                    bg=bg,
                    activebackground=bg,
                    highlightthickness=0,
                    bd=0,
                )
                chk.pack(side="left", padx=(8, 4), pady=8)
            else:
                tk.Label(row, text="🔒", bg=bg, fg=MUTED, font=("Segoe UI", 10), width=3).pack(side="left", padx=(8, 4))

            color = {
                Classification.UNNECESSARY: OK,
                Classification.NECESSARY: MUTED,
                Classification.REVIEW: WARN,
            }[item.classification]

            badge = tk.Label(
                row,
                text=item.classification.value,
                bg=bg,
                fg=color,
                font=("Segoe UI Semibold", 8),
                width=11,
                anchor="w",
            )
            badge.pack(side="left", padx=(0, 8))

            mid = tk.Frame(row, bg=bg)
            mid.pack(side="left", fill="x", expand=True, pady=6)
            tk.Label(mid, text=f"{item.name}  ·  {item.category}", bg=bg, fg=TEXT, font=("Segoe UI Semibold", 10), anchor="w").pack(
                fill="x"
            )
            tk.Label(mid, text=item.path, bg=bg, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x")

            tk.Label(row, text=item.size_display, bg=bg, fg=TEXT, font=("Segoe UI Semibold", 10), width=12, anchor="e").pack(
                side="right", padx=12
            )

            def show_detail(it=item, _e=None):
                self.detail_title.configure(text=it.name)
                self.detail_meta.configure(
                    text=f"{it.classification.value}  ·  {it.category}  ·  {it.size_display}\n{it.path}"
                )
                self.detail_reason.configure(text=it.reason)

            for w in (row, mid, badge):
                w.bind("<Button-1>", show_detail)

        self._sync_clean_btn()

    def _update_stats(self) -> None:
        if not self.summary:
            self.stat_cleanable.set("0")
            self.stat_protected.set("0")
            self.stat_review.set("0")
            self.stat_selected.set("0 B")
            return
        self.stat_cleanable.set(str(len(self.summary.unnecessary)))
        self.stat_protected.set(str(len(self.summary.necessary)))
        self.stat_review.set(str(len(self.summary.review)))
        n = len(self.summary.selected_cleanable)
        self.stat_selected.set(f"{n} · {format_bytes(self.summary.selected_bytes)}")

    def _sync_clean_btn(self) -> None:
        if self._busy:
            self.clean_btn.configure(state="disabled")
            return
        has = bool(self.summary and self.summary.selected_cleanable)
        self.clean_btn.configure(state="normal" if has else "disabled")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.scan_btn.configure(state=state)
        self.drive_combo.configure(state="disabled" if busy else "readonly")
        self.cancel_btn.configure(state="normal" if busy else "disabled")
        if busy:
            self.clean_btn.configure(state="disabled")
        else:
            self._sync_clean_btn()


def run_app() -> None:
    app = DriveCleanerApp()
    app.mainloop()
