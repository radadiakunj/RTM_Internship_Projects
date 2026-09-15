"""
Drive Diagnostics & Cleaning
Entry point — run this file to start the application.

  python main.py
"""

from __future__ import annotations

import sys


def _check_platform() -> None:
    if sys.platform != "win32":
        print("This application is designed for Windows (drive letters, Win32 APIs).")
        sys.exit(1)


def main() -> None:
    _check_platform()
    from ui.main_window import run_app

    run_app()


if __name__ == "__main__":
    main()
