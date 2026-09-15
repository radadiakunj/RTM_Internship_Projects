/*
  ESP32-WROOM WiFi firmware (Arduino)
  -----------------------------------
  1. Install "esp32" board support in Arduino IDE (Espressif).
  2. Set Board: ESP32 Dev Module.
  3. Edit WIFI_SSID and WIFI_PASSWORD below.
  4. Select the correct COM port (needs CP210x/CH340 or external USB-UART).
  5. Upload once.
  6. Open Serial Monitor at 115200 baud to read the ESP32 IP.
  7. On your PC run:
       python esp32_wifi_sta_monitor.py
*/

#include <WiFi.h>

// ---- edit these ----
const char* WIFI_SSID     = "RTM_HighSpeed";
const char* WIFI_PASSWORD = "AtpL@0214#";
// --------------------

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("ESP32 WiFi connecting...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if (millis() - start > 30000) {
      Serial.println();
      Serial.println("WiFi connect timeout. Check SSID/password.");
      // Fallback: open SoftAP so laptop can still reach the board
      WiFi.mode(WIFI_AP);
      WiFi.softAP("ESP32-Setup", "esp32pass");
      Serial.print("SoftAP started. Connect laptop to WiFi 'ESP32-Setup'");
      Serial.print(" then use IP: ");
      Serial.println(WiFi.softAPIP());
      return;
    }
  }

  Serial.println();
  Serial.println("WiFi Connected!");
  Serial.print("ESP32 IPv4: ");
  Serial.println(WiFi.localIP());
  Serial.println("Use this IP with: python esp32_wifi_sta_monitor.py");
}

void loop() {
  // Keep WiFi alive; print IP every 10s
  static uint32_t last = 0;
  if (millis() - last > 10000) {
    last = millis();
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("ESP32 IPv4: ");
      Serial.println(WiFi.localIP());
    } else if (WiFi.getMode() & WIFI_AP) {
      Serial.print("SoftAP IP: ");
      Serial.println(WiFi.softAPIP());
    } else {
      Serial.println("WiFi lost. Reconnecting...");
      WiFi.reconnect();
    }
  }
}
