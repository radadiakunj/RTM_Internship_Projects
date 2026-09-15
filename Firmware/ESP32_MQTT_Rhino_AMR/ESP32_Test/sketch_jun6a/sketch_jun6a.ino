#include <WiFi.h>

const char* ssid = "RTM_HighSpeed";
const char* password = "AtpL@0214#";

void setup() {
  Serial.begin(9600);
  delay(1000);

  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  // nothing needed here yet
}