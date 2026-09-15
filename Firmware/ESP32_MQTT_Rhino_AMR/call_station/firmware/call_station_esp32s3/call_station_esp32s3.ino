/*
 * Call Station — ESP32-S3 DevKit-N16R8
 * =====================================
 * Goal:
 *   ONE white push button starts the full AMR job:
 *     Home → Point A (pick) → Point D (place) → Home
 *
 * LEDs (only 3) — ONE White press starts MQTT job + this light order:
 *   1) GREEN  = leave Home → Point A (pick)
 *   2) YELLOW = → Placement Point D
 *   3) RED    = → return Home
 *   all off = idle | all on = error
 *
 * MQTT: one "run_job" publish for the whole trip (not three presses).
 *
 * Architecture (same Wi-Fi as AMR + laptop):
 *   ESP32  --MQTT floor topics-->  Mosquitto on laptop
 *   Laptop bridge/client         --Reeman SOP MQTT-->  AMR
 *
 * The ESP32 does NOT AES-encrypt Reeman Calling API.
 * It only publishes: {"cmd":"run_job", ...}
 * Your PC (call_station_dashboard.py or forklift client flow) talks to the AMR.
 *
 * Libraries (Arduino Library Manager):
 *   PubSubClient, ArduinoJson
 *
 * Board: ESP32S3 Dev Module
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "config.h"

// ---- Pins (ESP32-S3 safe GPIOs) ----
static const int PIN_BTN_WHITE  = 4;   // White START button → GND (INPUT_PULLUP)
static const int PIN_LED_YELLOW = 7;   // idle / wait
static const int PIN_LED_GREEN  = 8;   // job running
static const int PIN_LED_RED    = 6;   // error

static const unsigned long DEBOUNCE_MS   = 50;
static const unsigned long WIFI_RETRY_MS = 5000;
static const unsigned long MQTT_RETRY_MS = 3000;
static const unsigned long HB_MS         = 4000;

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

String topicCmd;
String topicLeds;
String topicStatus;
String topicHeartbeat;

unsigned long lastWifiTry = 0;
unsigned long lastMqttTry = 0;
unsigned long lastHbOut   = 0;

// --------------------------------- LEDs ---------------------------------
void setLeds(bool yellow, bool green, bool red) {
  digitalWrite(PIN_LED_YELLOW, yellow ? HIGH : LOW);
  digitalWrite(PIN_LED_GREEN,  green  ? HIGH : LOW);
  digitalWrite(PIN_LED_RED,    red    ? HIGH : LOW);
}

/*
 * Bridge sends {"phase":"..."}.
 * Single White-button job LED sequence:
 *   Home → Point A  → GREEN
 *   → Placement D   → YELLOW
 *   → Home          → RED
 * Idle / connecting → all off
 * error             → all three on
 */
void applyPhase(const char* phase) {
  if (!phase || !*phase) phase = "idle";

  if (strcmp(phase, "error") == 0) {
    setLeds(true, true, true);  // all on = fault
  } else if (strcmp(phase, "to_pick") == 0 || strcmp(phase, "lifting") == 0) {
    setLeds(false, true, false);   // GREEN → Point A / pick
  } else if (strcmp(phase, "to_drop") == 0 || strcmp(phase, "placing") == 0) {
    setLeds(true, false, false);   // YELLOW → Point D / place
  } else if (strcmp(phase, "to_home") == 0) {
    setLeds(false, false, true);   // RED → return Home
  } else if (strcmp(phase, "done") == 0) {
    setLeds(false, false, true);   // still RED briefly at home, then idle
  } else {
    // idle / connecting
    setLeds(false, false, false);
  }
  Serial.printf("LED phase: %s\n", phase);
}

// --------------------------------- MQTT pub ---------------------------------
void publishJson(const String& topic, JsonDocument& doc) {
  char buf[384];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(topic.c_str(), buf, n);
}

void publishStationStatus(const char* state) {
  JsonDocument doc;
  doc["station"] = STATION_ID;
  doc["state"] = state;
  doc["wifi_rssi"] = WiFi.RSSI();
  doc["ip"] = WiFi.localIP().toString();
  doc["point_home"] = POINT_HOME;
  doc["point_pick"] = POINT_PICK;
  doc["point_drop"] = POINT_DROP;
  publishJson(topicStatus, doc);
}

void publishCmd(const char* cmd) {
  JsonDocument doc;
  doc["cmd"] = cmd;
  doc["station"] = STATION_ID;
  doc["home"] = POINT_HOME;
  doc["pick"] = POINT_PICK;
  doc["drop"] = POINT_DROP;
  doc["ts"] = (long)(millis() / 1000);
  publishJson(topicCmd, doc);
  Serial.printf("CMD -> %s : %s\n", topicCmd.c_str(), cmd);
}

// Bridge → ESP32 LED commands
void onMqttMessage(char* topic, byte* payload, unsigned int len) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, len)) {
    Serial.println("Bad LED JSON");
    return;
  }
  const char* phase = doc["phase"] | "idle";
  applyPhase(phase);
}

// --------------------------------- WiFi / MQTT ---------------------------------
bool ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  unsigned long now = millis();
  if (now - lastWifiTry < WIFI_RETRY_MS) return false;
  lastWifiTry = now;

  applyPhase("connecting");
  Serial.printf("WiFi connecting to %s ...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  return false;
}

bool ensureMqtt() {
  if (mqtt.connected()) return true;
  unsigned long now = millis();
  if (now - lastMqttTry < MQTT_RETRY_MS) return false;
  lastMqttTry = now;

  String clientId = String("callstation-") + STATION_ID + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  Serial.printf("MQTT connecting %s:%d as %s ...\n", MQTT_HOST, MQTT_PORT, clientId.c_str());

  bool ok;
  if (strlen(MQTT_USER) > 0) {
    ok = mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASS);
  } else {
    ok = mqtt.connect(clientId.c_str());
  }

  if (!ok) {
    Serial.printf("MQTT failed, state=%d\n", mqtt.state());
    applyPhase("error");
    return false;
  }

  mqtt.subscribe(topicLeds.c_str());
  Serial.println("MQTT connected");
  applyPhase("idle");
  publishStationStatus("online");
  return true;
}

// --------------------------------- Button (white only) ---------------------------------
void readButtons() {
  unsigned long now = millis();
  static int whiteStable = HIGH;
  static unsigned long whiteChange = 0;

  int white = digitalRead(PIN_BTN_WHITE);

  if (white != whiteStable) {
    if (now - whiteChange >= DEBOUNCE_MS) {
      // Pressed (falling edge): start full job
      if (white == LOW && whiteStable == HIGH) {
        if (mqtt.connected()) {
          // Laptop bridge hears this and runs Home→A→D→Home on the AMR
          publishCmd("run_job");
          // Optimistic local feedback until bridge replies with phases
          applyPhase("to_pick");
        } else {
          Serial.println("Button ignored: MQTT offline");
          applyPhase("error");
        }
      }
      whiteStable = white;
      whiteChange = now;
    }
  } else {
    whiteChange = now;
  }
}

// --------------------------------- Arduino ---------------------------------
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("Call Station ESP32-S3 — White button = full job A→D→Home");

  topicCmd       = String("floor/callstation/") + STATION_ID + "/cmd";
  topicLeds      = String("floor/callstation/") + STATION_ID + "/leds";
  topicStatus    = String("floor/callstation/") + STATION_ID + "/status";
  topicHeartbeat = String("floor/callstation/") + STATION_ID + "/hb";

  pinMode(PIN_BTN_WHITE, INPUT_PULLUP);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  applyPhase("connecting");

  WiFi.mode(WIFI_STA);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(512);

  Serial.printf("WiFi SSID : %s\n", WIFI_SSID);
  Serial.printf("MQTT host : %s:%d\n", MQTT_HOST, MQTT_PORT);
  Serial.printf("Publish   : %s\n", topicCmd.c_str());
  Serial.printf("Subscribe : %s\n", topicLeds.c_str());
}

void loop() {
  if (!ensureWifi()) {
    delay(50);
    return;
  }
  if (!ensureMqtt()) {
    delay(50);
    return;
  }

  mqtt.loop();
  readButtons();

  unsigned long now = millis();
  if (now - lastHbOut > HB_MS) {
    lastHbOut = now;
    JsonDocument doc;
    doc["station"] = STATION_ID;
    doc["up_ms"] = now;
    publishJson(topicHeartbeat, doc);
  }
}
