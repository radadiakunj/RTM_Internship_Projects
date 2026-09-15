"""Open How_to_Use_MQTT_with_ESP32_Step_by_Step.ino simulator."""
from pathlib import Path
import webbrowser

html = Path(__file__).resolve().parent / "howto_mqtt_visualizer.html"
webbrowser.open(html.as_uri())
print("Opened:", html)
