/*
 * DEMO — Serial key A → AMR moves (small-map safe)
 * =================================================
 * Serial Monitor 115200, click in the box:
 *   A  →  go to point "home"  (short drive, no pallet lift)
 *   J  →  pick p2 → drop p5 → home  (longer; only after A works)
 *
 * Current map (small area): home, charging, p1..p5, w1/w3/way4/wp
 * Do NOT use A/D/Home — those names are not on this map.
 *
 * Bridge must be running or the robot will not move.
 * Edit ssid / password / mqtt_server to match YOUR laptop (ipconfig).
 *
 * If AMR Android Wi-Fi is OFF (ROS Wi-Fi only on robot):
 *   - This .ino still uses normal Wi-Fi → laptop Mosquitto (ssid/password/mqtt_server).
 *   - AMR Call Mode must use Ethernet → laptop Ethernet IP (not changed in this file).
 *   - No ROS-specific code is needed here.
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

const char* ssid        = "RTM_HighSpeed";  // must match laptop Wi-Fi
const char* password    = "AtpL@0214#";           // change if your AP uses another password
const char* mqtt_server = "192.168.5.115";  // laptop Mosquitto IP (ipconfig)
const int   mqtt_port   = 1883;
const char* mqtt_user   = "";
const char* mqtt_pass   = "";
const char* station_id  = "home1";

const int PIN_BTN = 4;
const int PIN_YEL = 7;   // external Yellow (Point D) — optional
const int PIN_GRN = 8;   // external Green (Point A) — optional
const int PIN_RED = 6;   // external Red (Home) — optional
const int PIN_RGB = 48;  // ESP32-S3-DevKitC onboard WS2812 RGB

static const uint8_t RGB_BRIGHT = 40;
const unsigned long PHASE_MS = 2500;

WiFiClient espClient;
PubSubClient client(espClient);

String topic_cmd, topic_leds, topic_status;

unsigned long lastDebounce = 0;
int lastBtn = HIGH;

bool jobBusy = false;
int jobStep = 0;
unsigned long jobStepAt = 0;
bool bridgeOwnsLeds = false;

void rgbWrite(uint8_t r, uint8_t g, uint8_t b) {
  neopixelWrite(PIN_RGB, r, g, b);
}

void setLeds(bool y, bool g, bool r) {
  digitalWrite(PIN_YEL, y ? HIGH : LOW);
  digitalWrite(PIN_GRN, g ? HIGH : LOW);
  digitalWrite(PIN_RED, r ? HIGH : LOW);

  // Onboard RGB mirrors the same meaning
  if (r && g && y) {
    rgbWrite(RGB_BRIGHT, RGB_BRIGHT, RGB_BRIGHT);      // error = white-ish
  } else if (g && !y && !r) {
    rgbWrite(0, RGB_BRIGHT, 0);                        // Point A = green
  } else if (y && !g && !r) {
    rgbWrite(RGB_BRIGHT, RGB_BRIGHT, 0);                // Point D = yellow
  } else if (r && !y && !g) {
    rgbWrite(RGB_BRIGHT, 0, 0);                        // Home = red
  } else {
    rgbWrite(0, 0, 0);                                 // idle = off
  }
}

void applyPhase(const char* phase) {
  if (!strcmp(phase, "error")) {
    setLeds(true, true, true);
  } else if (!strcmp(phase, "to_pick") || !strcmp(phase, "lifting")) {
    setLeds(false, true, false);   // GREEN — Home → A
  } else if (!strcmp(phase, "to_drop") || !strcmp(phase, "placing")) {
    setLeds(true, false, false);   // YELLOW — → D
  } else if (!strcmp(phase, "to_home") || !strcmp(phase, "done")) {
    setLeds(false, false, true);   // RED — → Home
  } else {
    setLeds(false, false, false);  // idle
  }
  Serial.printf("phase=%s\n", phase);
}

const char* wifiStatusText(wl_status_t s) {
  switch (s) {
    case WL_IDLE_STATUS:     return "IDLE";
    case WL_NO_SSID_AVAIL:   return "NO_SSID (name wrong / out of range / 5GHz-only)";
    case WL_SCAN_COMPLETED:  return "SCAN_DONE";
    case WL_CONNECTED:       return "CONNECTED";
    case WL_CONNECT_FAILED:  return "CONNECT_FAILED (wrong password?)";
    case WL_CONNECTION_LOST: return "LOST";
    case WL_DISCONNECTED:    return "DISCONNECTED";
    default:                 return "UNKNOWN";
  }
}

void scanNearbyWifi() {
  Serial.println("Scanning 2.4 GHz APs nearby...");
  int n = WiFi.scanNetworks();
  if (n <= 0) {
    Serial.println("  (no networks found)");
    return;
  }
  bool sawTarget = false;
  for (int i = 0; i < n; i++) {
    String name = WiFi.SSID(i);
    Serial.printf("  %2d) %s  RSSI=%d\n", i + 1, name.c_str(), WiFi.RSSI(i));
    if (name == ssid) sawTarget = true;
  }
  if (sawTarget) {
    Serial.printf("Found \"%s\" — if still failing, password is likely wrong.\n", ssid);
  } else {
    Serial.printf("Did NOT see \"%s\". Fix SSID spelling or move closer / use 2.4 GHz AP.\n", ssid);
  }
}

// Returns true when connected. Does not hang forever.
bool setup_wifi() {
  Serial.print("WiFi: "); Serial.println(ssid);
  Serial.printf("Password length: %u chars\n", (unsigned)strlen(password));
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true, true);
  delay(200);
  WiFi.begin(ssid, password);

  const int maxTries = 40;  // ~16 seconds
  for (int i = 0; i < maxTries; i++) {
    wl_status_t st = WiFi.status();
    if (st == WL_CONNECTED) {
      Serial.println();
      Serial.print("IP: "); Serial.println(WiFi.localIP());
      Serial.print("RSSI: "); Serial.println(WiFi.RSSI());
      return true;
    }
    delay(400);
    Serial.print(".");
    if ((i % 10) == 9) {
      Serial.printf(" [%s]\n", wifiStatusText(st));
    }
    setLeds(false, false, false);
  }

  Serial.println();
  Serial.printf("WiFi FAILED: %s\n", wifiStatusText(WiFi.status()));
  scanNearbyWifi();
  Serial.println("Fix ssid/password in the sketch, re-upload, press RESET.");
  applyPhase("error");
  return false;
}

void callback(char* topic, byte* payload, unsigned int length) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, length)) return;
  const char* phase = doc["phase"] | "idle";
  bridgeOwnsLeds = true;
  jobBusy = false;
  applyPhase(phase);
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("MQTT...");
    String id = String("learn-") + station_id;
    bool ok = (strlen(mqtt_user) > 0)
      ? client.connect(id.c_str(), mqtt_user, mqtt_pass)
      : client.connect(id.c_str());
    if (ok) {
      Serial.println("ok");
      client.subscribe(topic_leds.c_str());
      client.publish(topic_status.c_str(), "{\"state\":\"online\"}", true);
      applyPhase("idle");
    } else {
      Serial.printf("fail rc=%d\n", client.state());
      applyPhase("error");
      delay(3000);
    }
  }
}

bool beginDispatch(const char* reason) {
  if (jobBusy) {
    Serial.println("Job already running — ignore");
    return false;
  }
  if (!client.connected()) {
    Serial.println("MQTT offline — cannot send");
    applyPhase("error");
    return false;
  }
  (void)reason;
  return true;
}

// Key A — short move, good for the smaller floor.
void startGoHome(const char* reason) {
  if (!beginDispatch(reason)) return;

  JsonDocument doc;
  doc["cmd"] = "go_home";
  doc["station"] = station_id;
  doc["home"] = "home";   // production point on YOUR map
  doc["via"] = reason;
  char buf[180];
  serializeJson(doc, buf);
  client.publish(topic_cmd.c_str(), buf);

  Serial.println("=== MQTT go_home (point: home) ===");
  Serial.println(buf);

  bridgeOwnsLeds = false;
  jobBusy = true;
  jobStep = 3;
  jobStepAt = millis();
  applyPhase("to_home");
}

// Key J — pallet job on nearby points (skip p1↔p2; too long for this small map).
void startJob(const char* reason) {
  if (!beginDispatch(reason)) return;

  JsonDocument doc;
  doc["cmd"] = "run_job";
  doc["station"] = station_id;
  doc["home"] = "home";
  doc["pick"] = "p2";
  doc["drop"] = "p5";
  doc["via"] = reason;
  char buf[220];
  serializeJson(doc, buf);
  client.publish(topic_cmd.c_str(), buf);

  Serial.println("=== MQTT run_job (p2→p5→home) ===");
  Serial.println(buf);

  bridgeOwnsLeds = false;
  jobBusy = true;
  jobStep = 1;
  jobStepAt = millis();
  applyPhase("to_pick");
}

void serviceLocalLedMovie() {
  if (!jobBusy || bridgeOwnsLeds) return;
  if (millis() - jobStepAt < PHASE_MS) return;

  jobStepAt = millis();
  jobStep++;
  if (jobStep == 2) {
    applyPhase("to_drop");   // yellow
  } else if (jobStep == 3) {
    applyPhase("to_home");   // red
  } else {
    applyPhase("idle");
    jobBusy = false;
    jobStep = 0;
    Serial.println("=== LED movie done (idle) ===");
  }
}

void serviceSerialKeys() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r' || c == '\n') continue;

    if (c == 'A' || c == 'a') {
      Serial.println("Serial key A → go to home");
      startGoHome("serial_A");
    } else if (c == 'J' || c == 'j') {
      Serial.println("Serial key J → run_job p2→p5→home");
      startJob("serial_J");
    } else {
      Serial.printf("Unknown key '%c' — press A (go home) or J (p2→p5)\n",
                    (c >= 32 && c < 127) ? c : '?');
    }

    while (Serial.available() > 0) {
      char d = (char)Serial.read();
      if (d == '\n') break;
    }
    break;
  }
}

void setup() {
  Serial.begin(9600);
  delay(800);

  pinMode(PIN_BTN, INPUT_PULLUP);
  pinMode(PIN_YEL, OUTPUT);
  pinMode(PIN_GRN, OUTPUT);
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_RGB, OUTPUT);
  rgbWrite(0, 0, 0);

  topic_cmd    = String("floor/callstation/") + station_id + "/cmd";
  topic_leds   = String("floor/callstation/") + station_id + "/leds";
  topic_status = String("floor/callstation/") + station_id + "/status";

  if (!setup_wifi()) {
    Serial.println("Stuck without WiFi — edit ssid/password and re-upload.");
    return;  // loop() will keep retrying WiFi below
  }
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  Serial.println();
  Serial.println("Ready (small map).");
  Serial.println("  A = go to home     (short, use this first)");
  Serial.println("  J = p2 → p5 → home (pallet job, more space needed)");
  Serial.println("  White button GPIO4 = same as A");
  Serial.println("  MQTTX watch: floor/callstation/home1/#");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastWifiTry = 0;
    if (millis() - lastWifiTry > 10000) {
      lastWifiTry = millis();
      Serial.println("WiFi lost/not connected — retrying...");
      setup_wifi();
    }
    delay(50);
    return;
  }

  if (!client.connected()) reconnect();
  client.loop();
  serviceLocalLedMovie();
  serviceSerialKeys();

  int btn = digitalRead(PIN_BTN);
  if (btn != lastBtn && (millis() - lastDebounce) > 50) {
    lastDebounce = millis();
    if (btn == LOW && lastBtn == HIGH) {
      startGoHome("button");
    }
    lastBtn = btn;
  }
}
