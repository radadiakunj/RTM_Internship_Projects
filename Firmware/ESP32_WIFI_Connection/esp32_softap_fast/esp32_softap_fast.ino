/*
  FAST SoftAP firmware for ESP32-WROOM (no office WiFi password needed)

  After upload:
    1) ESP32 creates WiFi: ESP32-RTM  password: 12345678
    2) On laptop: connect to WiFi "ESP32-RTM"
    3) Run:
         python wifi_connection_monitor.py --mode wifi --ip 192.168.4.1
    4) Unplug ESP32 power -> Disconnected
       Plug power, reconnect laptop to ESP32-RTM -> Connected
*/

#include <WiFi.h>
#include <WebServer.h>

const char* AP_SSID = "RTM_HighSpeed";
const char* AP_PASS = "AtpL@0214#";  // min 8 chars

WebServer server(80);

void handleRoot() {
  String html = "<html><body><h1>ESP32 Connected</h1><p>IP: ";
  html += WiFi.softAPIP().toString();
  html += "</p></body></html>";
  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  WiFi.mode(WIFI_AP);
  bool ok = WiFi.softAP(AP_SSID, AP_PASS);
  IPAddress ip = WiFi.softAPIP();

  Serial.println();
  Serial.println(ok ? "SoftAP OK" : "SoftAP FAILED");
  Serial.print("SSID: ");
  Serial.println(AP_SSID);
  Serial.print("PASS: ");
  Serial.println(AP_PASS);
  Serial.print("ESP32 IP: ");
  Serial.println(ip);

  server.on("/", handleRoot);
  server.begin();
  Serial.println("Open http://192.168.4.1 in browser after joining ESP32-RTM");
}

void loop() {
  server.handleClient();
}
