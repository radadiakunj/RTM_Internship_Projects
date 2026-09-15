"""
Open the call-station firmware visualizer in your default browser.
  python open_visualizer.py
"""
from pathlib import Path
import webbrowser

html = Path(__file__).resolve().parent / "firmware_visualizer.html"
webbrowser.open(html.as_uri())
print("Opened:", html)
