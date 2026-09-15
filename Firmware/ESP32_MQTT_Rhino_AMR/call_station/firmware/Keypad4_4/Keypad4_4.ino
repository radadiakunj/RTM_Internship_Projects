/*
 * Direct Reeman ESP32-S3 — keypad + LCD call station
 * ==================================================
 * Boot: Wi-Fi → Mosquitto → wait STATUS → Ready
 *
 * 4x4 keypad:
 *   A  = auto pick p2 → place p3 → then calling home
 *   B  = store mission record to browser portal (MQTT)
 *   C  = cancel ESP32 workflow (physical e-stop still required)
 *   D  = navigate home only (no fork action)
 *
 * Serial 115200 mirrors the same A/B/C/D keys for debug.
 *
 * Requires: PubSubClient, ArduinoJson | Board: ESP32S3 Dev Module
 * Guide: call_station/DIRECT_ESP32_GUIDE.md
 */

#include <WiFi.h>
#include <Wire.h>
#include <Keypad.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_system.h>
#include "mbedtls/aes.h"
#include "mbedtls/base64.h"
#include "config.h"
#include "lcd_i2c.h"

String topicPhoneHb;
String topicTaskCalling;
String topicTaskAuto;
String topicRobotSub;

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

struct RobotSnap {
  bool valid = false;
  unsigned long atMs = 0;
  int battery = -1;
  int eStop = -1;
  bool navigating = false;
  bool executing = false;
  bool lifting = false;
  String targetPoint;
};

enum class Phase : uint8_t {
  Boot, Wifi, Mqtt, WaitRobot, Ready,
  AutoSent, AutoRun, AutoIdle,
  HomeSent, HomeRun,
  Error
};

enum class Workflow : uint8_t {
  None,
  FullJob,     // A: auto then home
  NavOnly      // P / D / H
};

RobotSnap robot;
Phase phase = Phase::Boot;
Workflow workflow = Workflow::None;

bool jobBusy = false;
bool taskAccepted = false;
bool sawMotion = false;
unsigned long dispatchedAtMs = 0;
unsigned long idleSinceMs = 0;
bool idleLatch = false;
unsigned long autoIdleAtMs = 0;
String lastPoint;

LcdI2c lcd(LCD_I2C_ADDR, LCD_COLS, LCD_ROWS);
bool lcdReady = false;
char lcdLine0[17] = "Booting...";
char lcdLine1[17] = "";

uint32_t nextMissionId = 1;
uint32_t activeMissionId = 0;
unsigned long missionStartedMs = 0;
const char* missionResult = "none";

char kpKeys[4][4] = {
  {'C','D','A','B'},
  {'9','#','3','6'},
  {'8','0','2','5'},
  {'7','*','1','4'}
};
byte kpRowPins[4] = {12, 11, 10, 8};
byte kpColPins[4] = {5, 4, 7, 6};
Keypad kpad = Keypad(makeKeymap(kpKeys), kpRowPins, kpColPins, 4, 4);

unsigned long lcdFlashUntilMs = 0;

void rgbWrite(uint8_t r, uint8_t g, uint8_t b) {
  neopixelWrite(PIN_RGB, r, g, b);
}

const char* phaseName(Phase p) {
  switch (p) {
    case Phase::Boot: return "Boot";
    case Phase::Wifi: return "Wifi";
    case Phase::Mqtt: return "Mqtt";
    case Phase::WaitRobot: return "WaitRobot";
    case Phase::Ready: return "Ready";
    case Phase::AutoSent: return "AutoSent";
    case Phase::AutoRun: return "AutoRun";
    case Phase::AutoIdle: return "AutoIdle";
    case Phase::HomeSent: return "HomeSent";
    case Phase::HomeRun: return "HomeRun";
    case Phase::Error: return "Error";
  }
  return "Unknown";
}

const char* workflowName(Workflow w) {
  switch (w) {
    case Workflow::None: return "None";
    case Workflow::FullJob: return "FullJob";
    case Workflow::NavOnly: return "NavOnly";
  }
  return "Unknown";
}

void lcdShow(const char* line0, const char* line1 = "") {
  strncpy(lcdLine0, line0 ? line0 : "", sizeof(lcdLine0) - 1);
  lcdLine0[sizeof(lcdLine0) - 1] = '\0';
  strncpy(lcdLine1, line1 ? line1 : "", sizeof(lcdLine1) - 1);
  lcdLine1[sizeof(lcdLine1) - 1] = '\0';
  if (!lcdReady) return;
  lcd.printLine(0, lcdLine0);
  lcd.printLine(1, lcdLine1);
}

void lcdShowFlash(const char* line0, const char* line1, unsigned long ms = 2500) {
  lcdShow(line0, line1);
  lcdFlashUntilMs = millis() + ms;
}

void updateLcdFromPhase() {
  if (lcdFlashUntilMs > millis()) return;

  char line1[17];
  if (robot.valid && robot.battery >= 0) {
    snprintf(line1, sizeof(line1), "Bat %d%% M#%lu", robot.battery, (unsigned long)activeMissionId);
  } else if (activeMissionId > 0) {
    snprintf(line1, sizeof(line1), "Mission #%lu", (unsigned long)activeMissionId);
  } else {
    snprintf(line1, sizeof(line1), "A=job B=store");
  }

  switch (phase) {
    case Phase::Boot:
      lcdShow("Booting...", "ESP32 call box");
      break;
    case Phase::Wifi:
      lcdShow("Wi-Fi...", WIFI_SSID);
      break;
    case Phase::Mqtt:
      lcdShow("MQTT broker...", MQTT_HOST);
      break;
    case Phase::WaitRobot:
      lcdShow("Wait AMR STATUS", "Call Mode?");
      break;
    case Phase::Ready:
      lcdShow("Ready at home", "A=job D=home");
      break;
    case Phase::AutoSent:
      lcdShow("From home", "Going p2 pick");
      break;
    case Phase::AutoRun:
      if (robot.lifting) lcdShow("At p2", "Picking pallet");
      else if (robot.targetPoint == String(POINT_DROP)) lcdShow("Going p3", "Place pallet");
      else lcdShow("Pick/place", "p2 -> p3");
      break;
    case Phase::AutoIdle:
      lcdShow("Place done", "Return home soon");
      break;
    case Phase::HomeSent:
    case Phase::HomeRun:
      lcdShow("Return home", line1);
      break;
    case Phase::Error:
      lcdShow("ERROR", "Press C cancel");
      break;
  }
}

bool initLcd() {
  uint8_t addr = findLcdAddress();
  if (addr == 0) addr = LCD_I2C_ADDR;
  LcdI2c trial(addr, LCD_COLS, LCD_ROWS);
  if (trial.begin(LCD_SDA_PIN, LCD_SCL_PIN)) {
    lcd = trial;
    lcdReady = true;
    Serial.printf("LCD ok at 0x%02X SDA=%d SCL=%d\n", addr, LCD_SDA_PIN, LCD_SCL_PIN);
    return true;
  }
  Serial.println("LCD init failed — check wiring/address");
  return false;
}

void scanI2cBus() {
  pinMode(LCD_SDA_PIN, INPUT_PULLUP);
  pinMode(LCD_SCL_PIN, INPUT_PULLUP);
  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  Wire.setClock(100000);
  delay(50);
  Serial.printf("I2C scan SDA=GPIO%d SCL=GPIO%d:\n", LCD_SDA_PIN, LCD_SCL_PIN);
  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      Serial.printf("  found 0x%02X\n", addr);
      found++;
    }
  }
  if (found == 0) {
    Serial.println("  none — check LCD VCC/GND, SDA/SCL wires (try swap SDA<->SCL)");
  }
}

uint8_t findLcdAddress() {
  static const uint8_t common[] = {0x27, 0x3F, 0x26, 0x25, 0x24, 0x23, 0x22, 0x21, 0x20, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E};
  for (uint8_t addr : common) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) return addr;
  }
  return 0;
}

void setPhase(Phase p, const char* why = "") {
  phase = p;
  if (why && why[0]) Serial.printf("PHASE: %s\n", why);
  switch (p) {
    case Phase::Boot:
    case Phase::Wifi:
    case Phase::Mqtt:
      rgbWrite(0, 0, RGB_BRIGHT);
      break;
    case Phase::WaitRobot:
      rgbWrite(RGB_BRIGHT, 0, RGB_BRIGHT);
      break;
    case Phase::Ready:
      rgbWrite(0, RGB_BRIGHT / 3, 0);
      break;
    case Phase::AutoSent:
    case Phase::AutoRun:
      rgbWrite(RGB_BRIGHT, RGB_BRIGHT, 0);  // yellow = pick/place
      break;
    case Phase::AutoIdle:
      rgbWrite(RGB_BRIGHT, RGB_BRIGHT / 2, 0);
      break;
    case Phase::HomeSent:
    case Phase::HomeRun:
      rgbWrite(0, RGB_BRIGHT, 0);           // green = going home
      break;
    case Phase::Error:
      rgbWrite(RGB_BRIGHT, 0, 0);
      break;
  }
  updateLcdFromPhase();
}

static void aesKeyAndIv(const char* key, uint8_t key16[16], uint8_t iv16[16]) {
  memset(key16, 0, 16);
  size_t n = strlen(key);
  memcpy(key16, key, n < 16 ? n : 16);
  memcpy(iv16, key16, 16);
}

static bool pkcs7Pad(const uint8_t* in, size_t inLen, uint8_t* out, size_t* outLen, size_t outCap) {
  size_t pad = 16 - (inLen % 16);
  size_t total = inLen + pad;
  if (total > outCap) return false;
  memcpy(out, in, inLen);
  for (size_t i = 0; i < pad; i++) out[inLen + i] = (uint8_t)pad;
  *outLen = total;
  return true;
}

bool aesEncryptToBase64(const char* plaintext, char* out, size_t outCap) {
  uint8_t key16[16], iv16[16];
  aesKeyAndIv(ROBOT_KEY, key16, iv16);
  uint8_t padded[512];
  size_t paddedLen = 0;
  if (!pkcs7Pad((const uint8_t*)plaintext, strlen(plaintext), padded, &paddedLen, sizeof(padded))) {
    return false;
  }
  uint8_t cipher[512];
  mbedtls_aes_context ctx;
  mbedtls_aes_init(&ctx);
  if (mbedtls_aes_setkey_enc(&ctx, key16, 128) != 0) {
    mbedtls_aes_free(&ctx);
    return false;
  }
  uint8_t ivWork[16];
  memcpy(ivWork, iv16, 16);
  int rc = mbedtls_aes_crypt_cbc(&ctx, MBEDTLS_AES_ENCRYPT, paddedLen, ivWork, padded, cipher);
  mbedtls_aes_free(&ctx);
  if (rc != 0) return false;
  size_t olen = 0;
  if (mbedtls_base64_encode((unsigned char*)out, outCap - 1, &olen, cipher, paddedLen) != 0) return false;
  out[olen] = '\0';
  return true;
}

bool aesDecryptFromBase64(const char* b64, char* out, size_t outCap) {
  uint8_t key16[16], iv16[16];
  aesKeyAndIv(ROBOT_KEY, key16, iv16);
  uint8_t cipher[512];
  size_t clen = 0;
  if (mbedtls_base64_decode(cipher, sizeof(cipher), &clen, (const unsigned char*)b64, strlen(b64)) != 0) {
    return false;
  }
  if (clen == 0 || (clen % 16) != 0) return false;
  uint8_t plain[512];
  mbedtls_aes_context ctx;
  mbedtls_aes_init(&ctx);
  if (mbedtls_aes_setkey_dec(&ctx, key16, 128) != 0) {
    mbedtls_aes_free(&ctx);
    return false;
  }
  uint8_t ivWork[16];
  memcpy(ivWork, iv16, 16);
  int rc = mbedtls_aes_crypt_cbc(&ctx, MBEDTLS_AES_DECRYPT, clen, ivWork, cipher, plain);
  mbedtls_aes_free(&ctx);
  if (rc != 0) return false;
  uint8_t pad = plain[clen - 1];
  if (pad < 1 || pad > 16 || pad > clen) return false;
  size_t plen = clen - pad;
  if (plen + 1 > outCap) return false;
  memcpy(out, plain, plen);
  out[plen] = '\0';
  return true;
}

bool setupWifi() {
  setPhase(Phase::Wifi, "1) Wi-Fi connecting...");
  Serial.printf("WiFi SSID=%s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40; i++) {
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("IP: ");
      Serial.println(WiFi.localIP());
      Serial.printf("RSSI: %d\n", WiFi.RSSI());
      return true;
    }
    delay(400);
    Serial.print(".");
  }
  Serial.println("\nWiFi FAILED");
  return false;
}

void buildTopics() {
  String base = String("reeman/calling/phone/") + ROBOT_HOSTNAME + "/forklift/";
  topicPhoneHb = base + "heartbeat";
  topicTaskCalling = base + "task/calling_model";
  topicTaskAuto = base + "task/auto_model";
  topicRobotSub = String("reeman/calling/robot/") + ROBOT_HOSTNAME + "/forklift/#";
}

void publishPhoneHeartbeat() {
  char buf[192];
  snprintf(buf, sizeof(buf), "{\"token\":\"%s\"}", ROBOT_TOKEN);
  mqtt.publish(topicPhoneHb.c_str(), buf, false);
}

bool robotIdle() {
  return robot.valid && !robot.navigating && !robot.executing && !robot.lifting;
}

bool robotHealthy() {
  if (!robot.valid) return false;
  if (millis() - robot.atMs > ROBOT_HB_MAX_AGE_MS) return false;
  if (robot.eStop != 1) return false;
  if (!robotIdle()) return false;
  if (robot.battery >= 0 && robot.battery < MIN_BATTERY_PCT) return false;
  return true;
}

void lcdShowNotReady() {
  if (!robot.valid || millis() - robot.atMs > ROBOT_HB_MAX_AGE_MS) {
    lcdShowFlash("Not ready", "No AMR STATUS", 3000);
  } else if (robot.eStop != 1) {
    lcdShowFlash("Not ready", "E-stop pressed?", 3000);
  } else if (!robotIdle()) {
    lcdShowFlash("Not ready", "AMR busy/wait", 3000);
  } else if (robot.battery >= 0 && robot.battery < MIN_BATTERY_PCT) {
    lcdShowFlash("Not ready", "Low battery", 3000);
  } else {
    lcdShowFlash("Not ready", "Wait STATUS", 3000);
  }
}

void printReadyHelp() {
  Serial.println();
  Serial.println("========================================");
  Serial.println("  A = pick p2 -> place p3 -> home");
  Serial.println("  B = store mission record (portal)");
  Serial.println("  C = cancel ESP32 job state");
  Serial.println("  D = go home only (navigate)");
  Serial.println("========================================");
}

void resetStageFlags() {
  taskAccepted = false;
  sawMotion = false;
  idleLatch = false;
  idleSinceMs = 0;
  dispatchedAtMs = millis();
}

void handleRobotHeartbeat(JsonDocument& doc) {
  robot.valid = true;
  robot.atMs = millis();
  robot.battery = doc["level"] | -1;
  robot.eStop = doc["emergencyButton"] | -1;
  robot.navigating = doc["isNavigating"] | false;
  robot.executing = doc["taskExecuting"] | false;
  robot.lifting = doc["isLifting"] | false;
  JsonVariant cur = doc["currentTask"];
  if (cur.isNull()) robot.targetPoint = "";
  else robot.targetPoint = cur["targetPoint"] | "";

  static unsigned long lastPrint = 0;
  if (millis() - lastPrint > 4500) {
    lastPrint = millis();
    Serial.printf(
      "STATUS battery=%d%% eStop=%d nav=%d exec=%d lifting=%d task=%s\n",
      robot.battery, robot.eStop, robot.navigating, robot.executing, robot.lifting,
      robot.targetPoint.c_str());
  }

  if (phase == Phase::WaitRobot && robotHealthy()) {
    setPhase(Phase::Ready, "3) Ready");
    printReadyHelp();
  }

  if (phase == Phase::AutoSent || phase == Phase::AutoRun ||
      phase == Phase::HomeSent || phase == Phase::HomeRun) {
    updateLcdFromPhase();
  }

  bool busyNow = robot.navigating || robot.executing || robot.lifting ||
                 robot.targetPoint.length() > 0;
  if ((phase == Phase::AutoSent || phase == Phase::AutoRun ||
       phase == Phase::HomeSent || phase == Phase::HomeRun) && busyNow) {
    sawMotion = true;
    if (phase == Phase::AutoSent) setPhase(Phase::AutoRun, "auto pick/place running");
    if (phase == Phase::HomeSent) setPhase(Phase::HomeRun, "going home");
  }
}

void handleTaskResponse(JsonDocument& doc) {
  int code = doc["code"] | -1;
  const char* body = doc["body"] | "";
  char plain[256];
  if (code == 0) {
    taskAccepted = true;
    if (body[0] && aesDecryptFromBase64(body, plain, sizeof(plain))) {
      Serial.printf("TASK RESULT code=0 -> %s\n", plain);
    } else {
      Serial.println("TASK RESULT code=0");
    }
    if (phase == Phase::AutoSent) setPhase(Phase::AutoRun, "auto task accepted");
    if (phase == Phase::HomeSent) setPhase(Phase::HomeRun, "home task accepted");
  } else {
    Serial.printf("TASK RESULT code=%d body=%s\n", code, body);
    jobBusy = false;
    workflow = Workflow::None;
    missionResult = "error";
    setPhase(Phase::Error, "task rejected");
    Serial.println("Press C then A when idle. Physical e-stop if moving.");
  }
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, length)) return;
  String t(topic);
  if (t.endsWith("/heartbeat")) {
    if (doc.containsKey("level") || doc.containsKey("emergencyButton")) {
      handleRobotHeartbeat(doc);
    }
  } else if (t.endsWith("/task/response")) {
    handleTaskResponse(doc);
  }
}

bool mqttReconnect() {
  setPhase(Phase::Mqtt, "2) MQTT connecting to broker...");
  String cid = String("esp-direct-") + String((uint32_t)ESP.getEfuseMac(), HEX);
  bool ok = MQTT_USER[0]
    ? mqtt.connect(cid.c_str(), MQTT_USER, MQTT_PASS)
    : mqtt.connect(cid.c_str());
  if (!ok) {
    Serial.printf("MQTT fail rc=%d (is Mosquitto service running?)\n", mqtt.state());
    return false;
  }
  Serial.println("MQTT ok (broker connected)");
  mqtt.subscribe(topicRobotSub.c_str(), 1);
  Serial.printf("Subscribed %s\n", topicRobotSub.c_str());
  publishPhoneHeartbeat();
  return true;
}

bool publishEncrypted(const char* topic, const char* plaintext) {
  char b64[640];
  if (!aesEncryptToBase64(plaintext, b64, sizeof(b64))) {
    setPhase(Phase::Error, "AES encrypt failed");
    return false;
  }
  JsonDocument doc;
  doc["token"] = ROBOT_TOKEN;
  doc["body"] = b64;
  char payload[768];
  size_t n = serializeJson(doc, payload, sizeof(payload));
  if (n == 0 || n >= sizeof(payload)) {
    setPhase(Phase::Error, "payload too large");
    return false;
  }
  bool pub = mqtt.publish(topic, payload, false);
  Serial.printf("Publish %s -> %s\n", topic, pub ? "ok" : "FAIL");
  if (!pub) {
    setPhase(Phase::Error, "MQTT publish failed");
    return false;
  }
  return true;
}

void formatMapJson(char* out, size_t cap) {
  if (TASK_MAP[0] == '\0') snprintf(out, cap, "null");
  else snprintf(out, cap, "\"%s\"", TASK_MAP);
}

bool dispatchCalling(const char* point) {
  if (!mqtt.connected()) {
    Serial.println("MQTT offline");
    setPhase(Phase::Error, "MQTT offline");
    return false;
  }
  if (!robotHealthy()) {
    Serial.println("Robot STATUS not healthy yet (need eStop=1, idle, battery OK)");
    lcdShowNotReady();
    return false;
  }

  char mapj[48];
  formatMapJson(mapj, sizeof(mapj));
  char plaintext[160];
  snprintf(plaintext, sizeof(plaintext), "{\"map\": %s, \"point\": \"%s\"}", mapj, point);

  Serial.printf("Dispatched calling_model: %s\n", plaintext);
  if (!publishEncrypted(topicTaskCalling.c_str(), plaintext)) return false;

  lastPoint = point;
  jobBusy = true;
  resetStageFlags();
  return true;
}

bool dispatchAutoPickPlace() {
  if (!mqtt.connected()) {
    Serial.println("MQTT offline");
    setPhase(Phase::Error, "MQTT offline");
    return false;
  }
  if (!robotHealthy()) {
    Serial.println("Robot STATUS not healthy yet (need eStop=1, idle, battery OK)");
    lcdShowNotReady();
    return false;
  }

  char mapj[48];
  formatMapJson(mapj, sizeof(mapj));
  char plaintext[256];
  // Match Python json.dumps([{first:{map,point}, second:{map,point}}])
  snprintf(plaintext, sizeof(plaintext),
           "[{\"first\": {\"map\": %s, \"point\": \"%s\"}, "
           "\"second\": {\"map\": %s, \"point\": \"%s\"}}]",
           mapj, POINT_PICK, mapj, POINT_DROP);

  Serial.printf("Dispatched auto_model pick %s → place %s\n", POINT_PICK, POINT_DROP);
  Serial.println(plaintext);
  if (!publishEncrypted(topicTaskAuto.c_str(), plaintext)) return false;

  lastPoint = POINT_PICK;
  jobBusy = true;
  resetStageFlags();
  return true;
}

bool publishMissionRecord(const char* notes) {
  if (!mqtt.connected()) {
    Serial.println("Mission store failed: MQTT offline");
    lcdShowFlash("MQTT offline", "Mission not saved");
    return false;
  }

  uint32_t missionId = activeMissionId > 0 ? activeMissionId : nextMissionId;
  JsonDocument doc;
  doc["missionId"] = missionId;
  doc["stationId"] = STATION_ID;
  doc["hostname"] = ROBOT_HOSTNAME;
  doc["action"] = "store";
  doc["workflow"] = workflowName(workflow);
  doc["phase"] = phaseName(phase);
  doc["pick"] = POINT_PICK;
  doc["drop"] = POINT_DROP;
  doc["home"] = POINT_HOME;
  doc["batteryPct"] = robot.battery;
  doc["uptimeMs"] = millis();
  doc["startedAtMs"] = missionStartedMs;
  doc["result"] = missionResult;
  doc["notes"] = notes;

  char payload[512];
  size_t n = serializeJson(doc, payload, sizeof(payload));
  if (n == 0 || n >= sizeof(payload)) {
    Serial.println("Mission store failed: payload too large");
    return false;
  }

  bool ok = mqtt.publish(MISSION_TOPIC, payload, false);
  Serial.printf("Mission record #%lu -> %s\n", (unsigned long)missionId, ok ? "ok" : "FAIL");
  if (ok) {
    char l0[17];
    char l1[17];
    snprintf(l0, sizeof(l0), "Mission #%lu", (unsigned long)missionId);
    snprintf(l1, sizeof(l1), "stored");
    lcdShowFlash(l0, l1, 3000);
  } else {
    lcdShowFlash("Store failed", "Check broker");
  }
  return ok;
}

bool startFullJob() {
  if (jobBusy) {
    Serial.println("Job busy — wait, or C to cancel ESP32 state");
    lcdShowFlash("Job busy", "Press C cancel");
    return false;
  }
  workflow = Workflow::FullJob;
  activeMissionId = nextMissionId++;
  missionStartedMs = millis();
  missionResult = "in_progress";
  Serial.println("=== A: pick p2 -> place p3, then home ===");
  Serial.println("Place a pallet at p2. Path clear. Hand on e-stop.");
  lcdShow("Starting job", "home -> p2 pick");
  if (!dispatchAutoPickPlace()) {
    workflow = Workflow::None;
    activeMissionId = 0;
    missionResult = "error";
    if (phase != Phase::Error) lcdShowFlash("Job not sent", "See Serial", 3000);
    return false;
  }
  setPhase(Phase::AutoSent, "auto p2->p3 sent");
  return true;
}

bool startNavOnly(const char* point, const char* label) {
  if (jobBusy) {
    Serial.println("Job busy — wait, or C to cancel ESP32 state");
    return false;
  }
  workflow = Workflow::NavOnly;
  Serial.printf("=== %s (NAVIGATE only — forks NOT commanded) ===\n", label);
  if (!dispatchCalling(point)) {
    workflow = Workflow::None;
    return false;
  }
  setPhase(Phase::HomeSent, label);
  return true;
}

void cancelWorkflow() {
  jobBusy = false;
  workflow = Workflow::None;
  resetStageFlags();
  if (missionResult == "in_progress") missionResult = "cancelled";
  Serial.println("ESP32 job state cleared. Physical e-stop if robot is moving.");
  lcdShowFlash("Job cancelled", "E-stop if moving");
  setPhase(Phase::Ready, "cancelled — press A/D");
}

bool storeMissionFromKeypad() {
  Serial.println("Keypad B -> store mission record");
  return publishMissionRecord("stored via keypad B");
}

bool stageStarted() {
  return sawMotion || taskAccepted;
}

bool stageCompletedVerified() {
  if (!stageStarted()) return false;
  if (!robotIdle()) {
    idleLatch = false;
    return false;
  }
  if (!idleLatch) {
    idleLatch = true;
    idleSinceMs = millis();
    return false;
  }
  return (millis() - idleSinceMs) >= IDLE_HOLD_MS;
}

void serviceWorkflow() {
  if (!jobBusy) return;

  unsigned long since = millis() - dispatchedAtMs;

  if ((phase == Phase::AutoSent || phase == Phase::HomeSent) &&
      !stageStarted() && since > NO_MOTION_TIMEOUT_MS) {
    jobBusy = false;
    workflow = Workflow::None;
    missionResult = "error";
    setPhase(Phase::Error, "no motion / no TASK RESULT — not assuming done");
    Serial.println("Robot did not start. Check Call Mode / tablet. Press C then retry.");
    return;
  }

  if (phase == Phase::AutoSent || phase == Phase::AutoRun) {
    if (stageCompletedVerified()) {
      if (workflow == Workflow::FullJob) {
        autoIdleAtMs = millis();
        setPhase(Phase::AutoIdle, "pick/place idle — then home");
        Serial.println("Auto pick/place looks complete. Sending home after dwell...");
      } else {
        jobBusy = false;
        workflow = Workflow::None;
        setPhase(Phase::Ready, "nav done");
        printReadyHelp();
      }
    }
    return;
  }

  if (phase == Phase::AutoIdle) {
    if (millis() - autoIdleAtMs < HOME_DWELL_MS) return;
    if (!robotHealthy()) {
      Serial.println("Waiting idle/healthy before home...");
      return;
    }
    Serial.println("=== return home (calling_model) ===");
    if (!dispatchCalling(POINT_HOME)) {
      if (phase == Phase::Error) {
        workflow = Workflow::None;
        jobBusy = false;
      } else {
        Serial.println("Home dispatch deferred — will retry while idle/healthy");
      }
      return;
    }
    setPhase(Phase::HomeSent, "home sent");
    return;
  }

  if (phase == Phase::HomeSent || phase == Phase::HomeRun) {
    if (stageCompletedVerified()) {
      bool wasFull = (workflow == Workflow::FullJob);
      jobBusy = false;
      workflow = Workflow::None;
      if (wasFull) {
        missionResult = "complete";
        lcdShowFlash("Job complete", "home p2 p3 done", 3000);
      }
      setPhase(Phase::Ready, wasFull ? "job complete — Ready" : "nav done — Ready");
      if (wasFull) Serial.println("=== DONE: p2 pick -> p3 place -> home ===");
      else Serial.println("=== NAV-only move finished (forks were not commanded) ===");
      printReadyHelp();
    }
  }
}

void servicePhoneHeartbeat() {
  static unsigned long last = 0;
  if (millis() - last >= PHONE_HB_INTERVAL_MS) {
    last = millis();
    if (mqtt.connected()) publishPhoneHeartbeat();
  }
}

void serviceCancelButton() {
  if (PIN_CANCEL_BTN < 0) return;
  static int lastBtn = HIGH;
  static unsigned long lastDb = 0;
  int btn = digitalRead(PIN_CANCEL_BTN);
  if (btn != lastBtn && (millis() - lastDb) > 40) {
    lastDb = millis();
    if (btn == LOW && lastBtn == HIGH) {
      Serial.println("GPIO cancel btn");
      cancelWorkflow();
    }
    lastBtn = btn;
  }
}

void handleKey(char key) {
  char keyMsg[17];
  snprintf(keyMsg, sizeof(keyMsg), "Key pressed: %c", key);
  lcdShowFlash(keyMsg, "Processing...", 1200);

  switch (key) {
    case 'A':
      Serial.println("Key A -> pick p2, place p3, then home");
      startFullJob();
      break;
    case 'B':
      storeMissionFromKeypad();
      break;
    case 'C':
      cancelWorkflow();
      break;
    case 'D':
      Serial.println("Key D -> NAVIGATE home only");
      startNavOnly(POINT_HOME, "NAV home");
      break;
    default:
      break;
  }
}

void serviceKeypad() {
  char key = kpad.getKey();
  if (!key) return;
  Serial.printf("Keypad %c\n", key);
  handleKey(key);
}

void serviceSerialKeys() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r' || c == '\n') continue;
    Serial.printf("Serial %c\n", c);
    if (c == 'A' || c == 'a') handleKey('A');
    else if (c == 'B' || c == 'b') handleKey('B');
    else if (c == 'C' || c == 'c') handleKey('C');
    else if (c == 'D' || c == 'd') handleKey('D');
    else {
      Serial.printf("Unknown '%c' — A=job B=store C=cancel D=home\n",
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
  Serial.begin(115200);
  delay(600);
  if (PIN_CANCEL_BTN >= 0) pinMode(PIN_CANCEL_BTN, INPUT_PULLUP);
  pinMode(PIN_RGB, OUTPUT);
  rgbWrite(0, 0, 0);

  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  scanI2cBus();
  initLcd();
  if (lcdReady) {
    lcdShow("Booting...", "Keypad+LCD ok");
  } else {
    Serial.println("WARNING: LCD not found — check SDA/SCL and address 0x27/0x3F");
    lcdShow("Booting...", "LCD NOT FOUND");
  }

  Serial.println();
  Serial.println("=== Direct Reeman keypad call station ===");
  Serial.printf("Reset reason: %d\n", (int)esp_reset_reason());

  {
    char testPt[80];
    char testAuto[256];
    char testB64[320];
    snprintf(testPt, sizeof(testPt), "{\"map\": null, \"point\": \"home\"}");
    snprintf(testAuto, sizeof(testAuto),
             "[{\"first\": {\"map\": null, \"point\": \"p2\"}, "
             "\"second\": {\"map\": null, \"point\": \"p3\"}}]");
    if (aesEncryptToBase64(testPt, testB64, sizeof(testB64)) &&
        strcmp(ROBOT_KEY, "a5F6dmfr") == 0) {
      Serial.printf("AES calling-home body: %s\n", testB64);
    }
    if (aesEncryptToBase64(testAuto, testB64, sizeof(testB64)) &&
        strcmp(ROBOT_KEY, "a5F6dmfr") == 0) {
      Serial.printf("AES auto p2→p3 body: %s\n", testB64);
    }
  }

  if (strcmp(ROBOT_TOKEN, "PASTE_TOKEN_HERE") == 0) {
    Serial.println("ERROR: set ROBOT_TOKEN in config.h");
    setPhase(Phase::Error, "token missing");
    return;
  }

  buildTopics();
  if (!setupWifi()) {
    setPhase(Phase::Error, "WiFi failed");
    return;
  }
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(1536);
  if (!mqttReconnect()) {
    setPhase(Phase::Error, "MQTT failed — start Mosquitto service");
    return;
  }

  setPhase(Phase::WaitRobot, "waiting for AMR STATUS (Call Mode online?)");
  Serial.println("Waiting for robot heartbeat... then press A on keypad");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    delay(100);
    return;
  }
  if (!mqtt.connected()) {
    delay(2000);
    if (mqttReconnect()) setPhase(Phase::WaitRobot, "reconnected — wait STATUS");
    return;
  }
  mqtt.loop();
  servicePhoneHeartbeat();
  serviceWorkflow();
  serviceCancelButton();
  serviceKeypad();
  serviceSerialKeys();
  if (lcdFlashUntilMs <= millis()) updateLcdFromPhase();
}
