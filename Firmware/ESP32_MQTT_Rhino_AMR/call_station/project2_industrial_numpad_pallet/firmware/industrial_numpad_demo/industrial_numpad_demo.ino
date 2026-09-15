/*
 * Project 2 — Industrial 4×4 numpad + cloud pallet ID
 * =====================================================
 * Type pallet number → press A → status "placed" =
 *   "Warehouse placement validated" in the cloud.
 * Download Excel from cloud UI. Admin-only void.
 *
 * Board: ESP32S3 Dev Module | Serial: 115200
 * Libraries: Keypad, LiquidCrystal_I2C, PubSubClient, ArduinoJson
 */

#include <WiFi.h>
#include <Wire.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Keypad.h>
#include <LiquidCrystal_I2C.h>
#include "config.h"

char keys[KEYPAD_ROWS][KEYPAD_COLS] = {
  {'C', 'D', 'A', 'B'},
  {'9', '#', '3', '6'},
  {'8', '0', '2', '5'},
  {'7', '*', '1', '4'}
};
byte rowPins[KEYPAD_ROWS] = {12, 11, 10, 8};
byte colPins[KEYPAD_COLS] = {5, 4, 7, 6};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, KEYPAD_ROWS, KEYPAD_COLS);

LiquidCrystal_I2C lcd(LCD_I2C_ADDR, LCD_COLS, LCD_ROWS);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

char palletId[PALLET_ID_MAX + 1] = "";
uint32_t nextMissionId = 1;
bool lcdOk = false;

void lcdShow(const char* l0, const char* l1) {
  if (!lcdOk) return;
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(l0);
  lcd.setCursor(0, 1);
  lcd.print(l1);
}

void refreshIdScreen(const char* statusLine) {
  char line0[17];
  snprintf(line0, sizeof(line0), "ID: %s", palletId[0] ? palletId : "-");
  lcdShow(line0, statusLine ? statusLine : "A=store *=bksp");
}

void appendDigit(char d) {
  size_t n = strlen(palletId);
  if (n >= (size_t)PALLET_ID_MAX) return;
  palletId[n] = d;
  palletId[n + 1] = '\0';
  refreshIdScreen("A=store *=bksp");
}

void backspaceId() {
  size_t n = strlen(palletId);
  if (n == 0) return;
  palletId[n - 1] = '\0';
  refreshIdScreen("A=store *=bksp");
}

void clearId() {
  palletId[0] = '\0';
  refreshIdScreen("Enter pallet");
}

bool mqttReconnect() {
  if (mqtt.connected()) return true;
  String cid = String("numpad-") + String((uint32_t)ESP.getEfuseMac(), HEX);
  bool ok;
  if (MQTT_USER && MQTT_USER[0]) {
    ok = mqtt.connect(cid.c_str(), MQTT_USER, MQTT_PASS);
  } else {
    ok = mqtt.connect(cid.c_str());
  }
  Serial.printf("MQTT %s\n", ok ? "ok" : "fail");
  return ok;
}

bool publishPallet(const char* status, const char* notes) {
  if (!mqttReconnect()) {
    lcdShow("MQTT fail", "Check broker");
    return false;
  }
  StaticJsonDocument<512> doc;
  doc["palletId"] = palletId;
  doc["stationId"] = STATION_ID;
  doc["status"] = status;
  doc["purpose"] = "Warehouse placement validated";
  doc["action"] = "upsert";
  doc["missionId"] = nextMissionId;
  doc["notes"] = notes;
  char payload[512];
  size_t n = serializeJson(doc, payload, sizeof(payload));
  bool ok = mqtt.publish(PALLET_TOPIC, payload, false);
  Serial.printf("Publish %s (%u bytes) %s\n", PALLET_TOPIC, (unsigned)n, ok ? "ok" : "FAIL");
  Serial.println(payload);
  return ok;
}

void handleA() {
  if (!palletId[0]) {
    lcdShow("Need pallet ID", "Type digits");
    Serial.println("A rejected — empty pallet ID");
    delay(900);
    refreshIdScreen("Enter pallet");
    return;
  }
  // status "placed" = showcase: pallet successfully logged as in warehouse
  bool ok = publishPallet("placed", "A pressed — warehouse placement validated");
  if (ok) {
    char msg[17];
    snprintf(msg, sizeof(msg), "ID %s", palletId);
    lcdShow("Placed OK", msg);
    Serial.printf("Pallet %s PLACED (warehouse validated) missionId=%lu\n",
                  palletId, (unsigned long)nextMissionId);
    nextMissionId++;
  } else {
    lcdShow("Store failed", "See Serial");
  }
  delay(1200);
  refreshIdScreen("A=place *=bksp");
}

void setupWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Wi-Fi %s ...\n", WIFI_SSID);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - t0) < WIFI_TIMEOUT_MS) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("IP %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("Wi-Fi FAILED — MQTT will not work until connected");
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("=== Project 2: keypad → A = warehouse PLACED ===");
  Serial.println("Digits | *=bksp | #=clear | A=place/validate | C=clear local");

  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  lcd.init();
  lcd.backlight();
  lcdOk = true;
  lcdShow("Pallet place", "Type ID then A");
  delay(800);

  setupWifi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  mqttReconnect();

  clearId();
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!mqtt.connected()) mqttReconnect();
    mqtt.loop();
  }

  char key = keypad.getKey();
  if (!key) {
    delay(5);
    return;
  }

  Serial.printf("Key %c\n", key);

  if (key >= '0' && key <= '9') {
    appendDigit(key);
  } else if (key == '*') {
    backspaceId();
  } else if (key == '#') {
    clearId();
  } else if (key == 'A') {
    handleA();
  } else if (key == 'C') {
    clearId();
    lcdShow("Local cleared", "Cloud unchanged");
    delay(800);
    refreshIdScreen("Enter pallet");
  } else {
    refreshIdScreen("Ignored key");
    delay(400);
    refreshIdScreen("A=store *=bksp");
  }
}
