/*
 * Direct Reeman ESP32-S3 — Call Mode call station
 * ==================================================
 * Boot: Wi-Fi → Mosquitto → wait STATUS → Ready
 *
 * Lab (UI_MODE=0): tactile + LCD — A/B/C/D/1/2
 * Panel (UI_MODE=1) Task-14:
 *   Blue latch CLOSED → start forward job (leave home → p2 pick → p3 place → home)
 *   Blue latch OPEN   → cancel ESP job state (e-stop still needed if robot moving)
 *   Status LEDs: Green = start from home | Yellow = p2 pick/place | Red = return home | OFF = idle/done
 *
 * Portal MQTT topic callstation/mission/record — live state machine:
 *   start+run → running | cancel → pausing | done → complete | D → stored
 *
 * Serial 115200 mirrors A/B/C/D/1/2 for debug.
 *
 * Requires: PubSubClient, ArduinoJson | Board: ESP32S3 Dev Module
 * Guide: call_station/SOP_DIRECT_ESP32_AMR.md
 */

#include <WiFi.h>
#include <Wire.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_system.h>
#include "mbedtls/aes.h"
#include "mbedtls/base64.h"
#include "config.h"
#if UI_MODE == 0
#include <LiquidCrystal_I2C.h>
#endif

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
  FullJob,     // A: home -> p2 pick -> p3 place -> home
  ReverseJob,  // B: p3 pick -> p2 place -> home
  NavOnly      // 1: navigate home only after jobs are idle
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

#if UI_MODE == 0
LiquidCrystal_I2C lcd(LCD_I2C_ADDR, LCD_COLS, LCD_ROWS);
#endif
bool lcdReady = false;
char lcdLine0[17] = "Booting...";
char lcdLine1[17] = "";

uint32_t nextMissionId = 1;
uint32_t activeMissionId = 0;
unsigned long missionStartedMs = 0;
const char* missionResult = "idle";
char lastKeyPressed = '-';

#if UI_MODE == 1
// Panel latch buttons (Task-14 blue + optional GPIO start)
bool latchStartStableHigh = true;
bool latchStartLastRawHigh = true;
unsigned long latchStartChangeMs = 0;
bool latchTask14StableHigh = true;
bool latchTask14LastRawHigh = true;
unsigned long latchTask14ChangeMs = 0;
bool panelBlueClosed = false;
bool panelSeqActive = false;
unsigned long panelSeqStartMs = 0;
#else
struct BtnMap {
  int pin;
  char key;
};
static const BtnMap BUTTONS[] = {
  {BTN_A_PIN, 'A'},
  {BTN_B_PIN, 'B'},
  {BTN_C_PIN, 'C'},
  {BTN_D_PIN, 'D'},
  {BTN_1_PIN, '1'},
  {BTN_2_PIN, '2'},
};
static const int BUTTON_COUNT = sizeof(BUTTONS) / sizeof(BUTTONS[0]);
bool btnStableHigh[BUTTON_COUNT];
bool btnLastRawHigh[BUTTON_COUNT];
unsigned long btnLastChangeMs[BUTTON_COUNT];
#endif

unsigned long lcdFlashUntilMs = 0;

void setPhase(Phase p, const char* why);
bool mqttReconnect();
bool publishMissionEvent(const char* status, const char* notes, bool flashLcd);
void updateStatusLeds();
void initUi();
void serviceUi();

// Copied once from config.h at boot (edit config.h + reflash if token changes).
char robotHostname[80] = "";
char robotToken[160] = "";
char robotKey[32] = "";

void initCredentials() {
  strncpy(robotHostname, ROBOT_HOSTNAME, sizeof(robotHostname) - 1);
  robotHostname[sizeof(robotHostname) - 1] = '\0';
  strncpy(robotToken, ROBOT_TOKEN, sizeof(robotToken) - 1);
  robotToken[sizeof(robotToken) - 1] = '\0';
  strncpy(robotKey, ROBOT_KEY, sizeof(robotKey) - 1);
  robotKey[sizeof(robotKey) - 1] = '\0';

  size_t n = strlen(robotToken);
  const char* tail = (n >= 8) ? (robotToken + n - 8) : robotToken;
  Serial.printf("Credentials from config.h: host=%s token_end=%s\n", robotHostname, tail);
}

bool credentialsValid() {
  return robotToken[0] != '\0' && strcmp(robotToken, "PASTE_TOKEN_HERE") != 0;
}

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
    case Workflow::ReverseJob: return "ReverseJob";
    case Workflow::NavOnly: return "NavOnly";
  }
  return "Unknown";
}

#if UI_MODE == 0
void lcdPrintLine(uint8_t row, const char* text) {
  char buf[17];
  size_t n = 0;
  if (text) {
    n = strlen(text);
    if (n > LCD_COLS) n = LCD_COLS;
    memcpy(buf, text, n);
  }
  for (size_t i = n; i < LCD_COLS; i++) buf[i] = ' ';
  buf[LCD_COLS] = '\0';
  lcd.setCursor(0, row);
  lcd.print(buf);
}
#endif

void lcdShow(const char* line0, const char* line1 = "") {
  strncpy(lcdLine0, line0 ? line0 : "", sizeof(lcdLine0) - 1);
  lcdLine0[sizeof(lcdLine0) - 1] = '\0';
  strncpy(lcdLine1, line1 ? line1 : "", sizeof(lcdLine1) - 1);
  lcdLine1[sizeof(lcdLine1) - 1] = '\0';
#if UI_MODE == 0
  if (!lcdReady) return;
  lcdPrintLine(0, lcdLine0);
  lcdPrintLine(1, lcdLine1);
#else
  (void)line0;
  (void)line1;
#endif
}

void lcdShowFlash(const char* line0, const char* line1, unsigned long ms = 2500) {
  lcdShow(line0, line1);
  lcdFlashUntilMs = millis() + ms;
#if UI_MODE == 1
  Serial.printf("UI: %s | %s\n", line0 ? line0 : "", line1 ? line1 : "");
  updateStatusLeds();
#endif
}

void setStatusLed(int pin, bool on) {
#if UI_MODE == 1
  if (pin < 0) return;
  bool level = LED_STATUS_ACTIVE_HIGH ? on : !on;
  digitalWrite(pin, level ? HIGH : LOW);
#else
  (void)pin;
  (void)on;
#endif
}

void setRingLed(int pin, bool on) {
#if UI_MODE == 1
  if (pin < 0) return;
  bool level = LED_RING_ACTIVE_HIGH ? on : !on;
  digitalWrite(pin, level ? HIGH : LOW);
#else
  (void)pin;
  (void)on;
#endif
}

void setLed(int pin, bool on) {
  // Default = status polarity (G/Y/R). Rings use setRingLed().
  setStatusLed(pin, on);
}

void updateStatusLeds() {
#if UI_MODE != 1
  return;
#else
  // HARD force — all pins ON with raw levels (proves wiring)
  if (LED_FORCE_DIAG) {
    digitalWrite(LED_GREEN_PIN, PANEL_STATUS_ON_LEVEL);
    digitalWrite(LED_YELLOW_PIN, PANEL_STATUS_ON_LEVEL);
    digitalWrite(LED_RED_PIN, PANEL_STATUS_ON_LEVEL);
    digitalWrite(PIN_RING_WHITE, PANEL_RING_ON_LEVEL);
    digitalWrite(PIN_RING_BLUE, PANEL_RING_ON_LEVEL);
    return;
  }

  if (PANEL_LOCAL_LED_SEQ) {
    // Live Blue read every call — do NOT wait for edge debounce alone
    bool bluePressed = (digitalRead(LATCH_TASK14_PIN) == LOW);

    // White switch = power: ESP alive → white ring always ON
    digitalWrite(PIN_RING_WHITE, PANEL_RING_ON_LEVEL);

    if (bluePressed) {
      digitalWrite(PIN_RING_BLUE, PANEL_RING_ON_LEVEL);

      if (!panelSeqActive) {
        panelSeqActive = true;
        panelSeqStartMs = millis();
        Serial.println("BLUE DOWN → blue ring ON | Green 2s → Red 2s → Yellow");
      }
      panelBlueClosed = true;

      unsigned long elapsed = millis() - panelSeqStartMs;
      digitalWrite(LED_GREEN_PIN, PANEL_STATUS_OFF_LEVEL);
      digitalWrite(LED_YELLOW_PIN, PANEL_STATUS_OFF_LEVEL);
      digitalWrite(LED_RED_PIN, PANEL_STATUS_OFF_LEVEL);

      // Exact sequence: Green → (2s) → Red → (2s) → Yellow
      if (elapsed < PANEL_LED_STEP_MS) {
        digitalWrite(LED_GREEN_PIN, PANEL_STATUS_ON_LEVEL);   // 0–2s Green
      } else if (elapsed < (2UL * PANEL_LED_STEP_MS)) {
        digitalWrite(LED_RED_PIN, PANEL_STATUS_ON_LEVEL);     // 2–4s Red
      } else {
        digitalWrite(LED_YELLOW_PIN, PANEL_STATUS_ON_LEVEL);  // 4s+ Yellow
      }
    } else {
      if (panelBlueClosed || panelSeqActive) {
        Serial.println("BLUE UP → all status OFF + blue ring OFF");
      }
      panelBlueClosed = false;
      panelSeqActive = false;
      digitalWrite(PIN_RING_BLUE, PANEL_RING_OFF_LEVEL);
      digitalWrite(LED_GREEN_PIN, PANEL_STATUS_OFF_LEVEL);
      digitalWrite(LED_YELLOW_PIN, PANEL_STATUS_OFF_LEVEL);
      digitalWrite(LED_RED_PIN, PANEL_STATUS_OFF_LEVEL);
    }
    return;
  }

  // Task-14 AMR phase mode (PANEL_LOCAL_LED_SEQ=false)
  bool green = false;
  bool yellow = false;
  bool red = false;

  switch (phase) {
    case Phase::AutoSent:
      green = true;
      break;
    case Phase::AutoRun:
      yellow = true;
      break;
    case Phase::AutoIdle:
    case Phase::HomeSent:
    case Phase::HomeRun:
      red = true;
      break;
    case Phase::Error:
      red = true;
      break;
    default:
      break;
  }

  if (strcmp(missionResult, "pausing") == 0 && phase == Phase::Ready) {
    green = false;
    yellow = false;
    red = false;
  }

  setStatusLed(LED_GREEN_PIN, green);
  setStatusLed(LED_YELLOW_PIN, yellow);
  setStatusLed(LED_RED_PIN, red);

  if (RING_FOLLOW_LATCH) {
    setRingLed(PIN_RING_BLUE, digitalRead(LATCH_TASK14_PIN) == LOW);
    setRingLed(PIN_RING_WHITE, true);
  }
#endif
}

void updateLcdFromPhase() {
#if UI_MODE == 1
  updateStatusLeds();
  return;
#endif
  if (lcdFlashUntilMs > millis()) return;

  char line1[17];
  if (robot.valid && robot.battery >= 0) {
    snprintf(line1, sizeof(line1), "Bat %d%% M#%lu", robot.battery, (unsigned long)activeMissionId);
  } else if (activeMissionId > 0) {
    snprintf(line1, sizeof(line1), "Mission #%lu", (unsigned long)activeMissionId);
  } else {
    snprintf(line1, sizeof(line1), "A/B job D=store");
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
      lcdShow("Ready", "A/B job 1/2 nav");
      break;
    case Phase::AutoSent:
      if (workflow == Workflow::ReverseJob)
        lcdShow("B: Start reverse", "Going p3 pick");
      else
        lcdShow("A: Start forward", "Going p2 pick");
      break;
    case Phase::AutoRun:
      if (workflow == Workflow::ReverseJob) {
        if (robot.lifting) lcdShow("At p3", "Picking pallet");
        else if (robot.targetPoint == String(POINT_PICK)) lcdShow("Going p2", "Place pallet");
        else lcdShow("Pick/place", "p3 -> p2");
      } else {
        if (robot.lifting) lcdShow("At p2", "Picking pallet");
        else if (robot.targetPoint == String(POINT_DROP)) lcdShow("Going p3", "Place pallet");
        else lcdShow("Pick/place", "p2 -> p3");
      }
      break;
    case Phase::AutoIdle:
      lcdShow("Place done", "Return home soon");
      break;
    case Phase::HomeSent:
    case Phase::HomeRun:
      if (workflow == Workflow::NavOnly)
        lcdShow(lastPoint.length() ? lastPoint.c_str() : "Navigate", line1);
      else
        lcdShow("Return home", line1);
      break;
    case Phase::Error:
      lcdShow("ERROR", "Press C cancel");
      break;
  }
}

bool initLcd() {
#if UI_MODE != 0
  lcdReady = false;
  return false;
#else
  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  Wire.setClock(100000);
  delay(50);

  Wire.beginTransmission(LCD_I2C_ADDR);
  if (Wire.endTransmission() != 0) {
    Serial.printf("LCD not responding at 0x%02X (SDA=GPIO%d SCL=GPIO%d)\n",
                  LCD_I2C_ADDR, LCD_SDA_PIN, LCD_SCL_PIN);
    lcdReady = false;
    return false;
  }

  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcdReady = true;
  Serial.printf("LCD ok (LiquidCrystal_I2C) at 0x%02X SDA=%d SCL=%d\n",
                LCD_I2C_ADDR, LCD_SDA_PIN, LCD_SCL_PIN);
  return true;
#endif
}

void scanI2cBus() {
#if UI_MODE != 0
  return;
#else
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
    Serial.println("  none — check LCD VCC/GND, SDA/SCL wires");
  }
#endif
}

void setPhase(Phase p, const char* why = "") {
  Phase prev = phase;
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

  // Live portal state machine: push status on job phase changes
  if (activeMissionId == 0 || p == prev) return;
  if (workflow != Workflow::FullJob && workflow != Workflow::ReverseJob &&
      workflow != Workflow::NavOnly) {
    return;
  }
  const char* status = nullptr;
  const char* notes = why && why[0] ? why : phaseName(p);
  switch (p) {
    case Phase::AutoSent:
      status = "running";
      notes = (workflow == Workflow::ReverseJob) ? "B: reverse started" : "A: forward started";
      break;
    case Phase::AutoRun:
      status = "running";
      notes = (workflow == Workflow::ReverseJob) ? "B: pick/place running" : "A: pick/place running";
      break;
    case Phase::AutoIdle:
      status = "running";
      notes = "place done — return home soon";
      break;
    case Phase::HomeSent:
    case Phase::HomeRun:
      status = "running";
      notes = (workflow == Workflow::NavOnly) ? "nav running" : "returning home";
      break;
    case Phase::Error:
      status = "error";
      break;
    default:
      break;
  }
  if (status) publishMissionEvent(status, notes, false);
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
  aesKeyAndIv(robotKey, key16, iv16);
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
  aesKeyAndIv(robotKey, key16, iv16);
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
  String base = String("reeman/calling/phone/") + robotHostname + "/forklift/";
  topicPhoneHb = base + "heartbeat";
  topicTaskCalling = base + "task/calling_model";
  topicTaskAuto = base + "task/auto_model";
  topicRobotSub = String("reeman/calling/robot/") + robotHostname + "/forklift/#";
}

void publishPhoneHeartbeat() {
  char buf[192];
  snprintf(buf, sizeof(buf), "{\"token\":\"%s\"}", robotToken);
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
  Serial.println("  A = home -> p2 pick -> p3 place -> home");
  Serial.println("  B = p3 pick -> p2 place -> home (reverse)");
  Serial.println("  C = cancel current task");
  Serial.println("  D = store / snapshot mission to portal");
  Serial.println("  Portal statuses: running | pausing | complete | stored | error");
  Serial.println("  1 = go home only (after job is idle)");
  Serial.println("  2 = go charge only (after job is idle)");
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
    publishMissionEvent("error", "task rejected — check token", true);
    workflow = Workflow::None;
    setPhase(Phase::Error, "task rejected");
    Serial.println("Task rejected — check ROBOT_TOKEN in config.h matches AMR Call Mode, then reflash.");
    lcdShowFlash("Bad token?", "Fix config.h");
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
  doc["token"] = robotToken;
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

  Serial.printf("Dispatched calling_model (%s token=%.8s...): %s\n",
                robotHostname, robotToken, plaintext);
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

  {
    size_t n = strlen(robotToken);
    const char* tail = (n >= 8) ? (robotToken + n - 8) : robotToken;
    Serial.printf("Dispatched auto_model pick %s -> place %s (%s token_end=%s)\n",
                  POINT_PICK, POINT_DROP, robotHostname, tail);
  }
  Serial.println(plaintext);
  if (!publishEncrypted(topicTaskAuto.c_str(), plaintext)) return false;
  Serial.println("Waiting for TASK RESULT from AMR (if none = wrong token / Call Mode)");

  lastPoint = POINT_PICK;
  jobBusy = true;
  resetStageFlags();
  return true;
}

bool publishMissionEvent(const char* status, const char* notes, bool flashLcd) {
  if (!mqtt.connected()) {
    Serial.println("Mission portal update failed: MQTT offline");
    if (flashLcd) lcdShowFlash("MQTT offline", "Not saved");
    return false;
  }

  if (activeMissionId == 0) {
    activeMissionId = nextMissionId++;
    missionStartedMs = millis();
  }

  missionResult = status ? status : "unknown";

  char keyStr[2] = { lastKeyPressed, '\0' };
  const char* action =
      (lastKeyPressed == 'A') ? "forward" :
      (lastKeyPressed == 'B') ? "reverse" :
      (lastKeyPressed == 'C') ? "cancel" :
      (lastKeyPressed == 'D') ? "store" :
      (lastKeyPressed == '1') ? "home" :
      (lastKeyPressed == '2') ? "charge" : "update";

  JsonDocument doc;
  doc["missionId"] = activeMissionId;
  doc["stationId"] = STATION_ID;
  doc["hostname"] = robotHostname;
  doc["key"] = keyStr;
  doc["action"] = action;
  doc["workflow"] = workflowName(workflow);
  doc["phase"] = phaseName(phase);
  doc["status"] = missionResult;
  doc["result"] = missionResult;  // same field for older portal UIs
  doc["pick"] = POINT_PICK;
  doc["drop"] = POINT_DROP;
  doc["home"] = POINT_HOME;
  doc["charge"] = POINT_CHARGE;
  doc["batteryPct"] = robot.battery;
  doc["uptimeMs"] = millis();
  doc["startedAtMs"] = missionStartedMs;
  doc["notes"] = notes ? notes : "";

  char payload[640];
  size_t n = serializeJson(doc, payload, sizeof(payload));
  if (n == 0 || n >= sizeof(payload)) {
    Serial.println("Mission portal update failed: payload too large");
    return false;
  }

  bool ok = mqtt.publish(MISSION_TOPIC, payload, false);
  Serial.printf("Mission #%lu status=%s -> %s\n",
                (unsigned long)activeMissionId, missionResult, ok ? "portal ok" : "FAIL");
  if (ok && flashLcd) {
    char l0[17];
    char l1[17];
    snprintf(l0, sizeof(l0), "Mission #%lu", (unsigned long)activeMissionId);
    snprintf(l1, sizeof(l1), "%.15s", missionResult);
    lcdShowFlash(l0, l1, 2500);
  } else if (!ok && flashLcd) {
    lcdShowFlash("Store failed", "Check broker");
  }
  return ok;
}

bool publishMissionRecord(const char* notes) {
  return publishMissionEvent("stored", notes, true);
}

bool startFullJob() {
  if (jobBusy) {
    Serial.println("Job busy — wait, or C to cancel ESP32 state");
    lcdShowFlash("Job busy", "Press C cancel");
    return false;
  }
  lastKeyPressed = 'A';
  workflow = Workflow::FullJob;
  activeMissionId = nextMissionId++;
  missionStartedMs = millis();
  missionResult = "running";
  Serial.println("=== A: pick p2 -> place p3, then home ===");
  Serial.println("Place a pallet at p2. Path clear. Hand on e-stop.");
  lcdShow("Starting job", "home -> p2 pick");
  if (!dispatchAutoPickPlace()) {
    workflow = Workflow::None;
    missionResult = "error";
    publishMissionEvent("error", "A: job not sent", true);
    activeMissionId = 0;
    if (phase != Phase::Error) lcdShowFlash("Job not sent", "See Serial", 3000);
    return false;
  }
  setPhase(Phase::AutoSent, "auto p2->p3 sent");
  return true;
}

bool dispatchAutoReverse() {
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
  snprintf(plaintext, sizeof(plaintext),
           "[{\"first\": {\"map\": %s, \"point\": \"%s\"}, "
           "\"second\": {\"map\": %s, \"point\": \"%s\"}}]",
           mapj, POINT_DROP, mapj, POINT_PICK);

  {
    size_t n = strlen(robotToken);
    const char* tail = (n >= 8) ? (robotToken + n - 8) : robotToken;
    Serial.printf("Dispatched auto_model pick %s -> place %s (REVERSE, %s token_end=%s)\n",
                  POINT_DROP, POINT_PICK, robotHostname, tail);
  }
  Serial.println(plaintext);
  if (!publishEncrypted(topicTaskAuto.c_str(), plaintext)) return false;
  Serial.println("Waiting for TASK RESULT from AMR (if none = wrong token / Call Mode)");

  lastPoint = POINT_DROP;
  jobBusy = true;
  resetStageFlags();
  return true;
}

bool startReverseJob() {
  if (jobBusy) {
    Serial.println("Job busy — wait, or C to cancel ESP32 state");
    lcdShowFlash("Job busy", "Press C cancel");
    return false;
  }
  lastKeyPressed = 'B';
  workflow = Workflow::ReverseJob;
  activeMissionId = nextMissionId++;
  missionStartedMs = millis();
  missionResult = "running";
  Serial.println("=== B: pick p3 -> place p2, then home ===");
  Serial.println("Place a pallet at p3. Path clear. Hand on e-stop.");
  lcdShow("Starting rev job", "p3 -> p2 pick");
  if (!dispatchAutoReverse()) {
    workflow = Workflow::None;
    missionResult = "error";
    publishMissionEvent("error", "B: job not sent", true);
    activeMissionId = 0;
    if (phase != Phase::Error) lcdShowFlash("Job not sent", "See Serial", 3000);
    return false;
  }
  setPhase(Phase::AutoSent, "auto p3->p2 sent");
  return true;
}

bool startNavOnly(const char* point, const char* label) {
  if (jobBusy) {
    Serial.println("Job still running — wait until complete, then press 1 (home) or 2 (charge)");
    lcdShowFlash("Job running", "Wait then 1/2");
    return false;
  }
  if (phase != Phase::Ready && phase != Phase::Error) {
    Serial.println("Not idle yet — wait for Ready, then press 1 or 2");
    lcdShowFlash("Not idle", "Wait job done");
    return false;
  }
  workflow = Workflow::NavOnly;
  activeMissionId = nextMissionId++;
  missionStartedMs = millis();
  missionResult = "running";
  Serial.printf("=== %s (NAVIGATE only — forks NOT commanded) ===\n", label);
  lcdShow(label, point);
  if (!dispatchCalling(point)) {
    workflow = Workflow::None;
    missionResult = "error";
    publishMissionEvent("error", "nav not sent", false);
    activeMissionId = 0;
    return false;
  }
  setPhase(Phase::HomeSent, label);
  return true;
}

void cancelWorkflow() {
  lastKeyPressed = 'C';
  bool hadJob = jobBusy || workflow == Workflow::FullJob ||
                workflow == Workflow::ReverseJob || workflow == Workflow::NavOnly;
  Workflow prevWf = workflow;
  // Keep workflow name for this portal event, then clear local FSM
  if (hadJob && activeMissionId > 0) {
    publishMissionEvent("pausing", "interrupted via keypad C", true);
  } else {
    lcdShowFlash("No job", "Already idle");
  }
  jobBusy = false;
  workflow = Workflow::None;
  resetStageFlags();
  (void)prevWf;
  Serial.println("ESP32 job state cleared. Physical e-stop if robot is moving.");
  setPhase(Phase::Ready, "cancelled — press A/B or D");
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
    publishMissionEvent("error", "no motion / no TASK RESULT", true);
    workflow = Workflow::None;
    setPhase(Phase::Error, "no motion / no TASK RESULT — not assuming done");
    Serial.println("Robot did not start. Check Call Mode / tablet. Press C then retry.");
    return;
  }

  if (phase == Phase::AutoSent || phase == Phase::AutoRun) {
    if (stageCompletedVerified()) {
      if (workflow == Workflow::FullJob || workflow == Workflow::ReverseJob) {
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
      bool wasJob = (workflow == Workflow::FullJob || workflow == Workflow::ReverseJob);
      bool wasReverse = (workflow == Workflow::ReverseJob);
      jobBusy = false;
      if (wasJob) {
        if (wasReverse) {
          lcdShowFlash("Job complete", "p3 p2 home done", 3000);
          Serial.println("=== DONE: p3 pick -> p2 place -> home ===");
          publishMissionEvent("complete", "auto: p3->p2->home", false);
        } else {
          lcdShowFlash("Job complete", "home p2 p3 done", 3000);
          Serial.println("=== DONE: p2 pick -> p3 place -> home ===");
          publishMissionEvent("complete", "auto: home->p2->p3->home", false);
        }
      } else {
        publishMissionEvent("complete", "nav finished", false);
        Serial.println("=== NAV-only move finished (forks were not commanded) ===");
      }
      workflow = Workflow::None;
      setPhase(Phase::Ready, wasJob ? "job complete — Ready" : "nav done — Ready");
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
#if UI_MODE == 1
  // Production panel mode: only Task-14 start/cancel semantics are allowed.
  if (!(key == 'A' || key == 'C')) {
    Serial.printf("UI_MODE=1 ignores key '%c' (only Blue latch start/cancel)\n",
                  (key >= 32 && key < 127) ? key : '?');
    return;
  }
#endif
  switch (key) {
    case 'A':
      lastKeyPressed = 'A';
      Serial.println("Key A -> pick p2, place p3, then home");
#if UI_MODE == 0
      lcdShow("A: Forward job", "home->p2->p3->hm");
      delay(900);
#endif
      startFullJob();
      break;
    case 'B':
      lastKeyPressed = 'B';
      Serial.println("Key B -> pick p3, place p2, then home (reverse)");
      lcdShow("B: Reverse job", "p3->p2->home");
      delay(900);
      startReverseJob();
      break;
    case 'C':
      lastKeyPressed = 'C';
      Serial.println("Key C -> pause/cancel current ESP32 job");
#if UI_MODE == 0
      lcdShow("C: Pausing", "Portal update");
      delay(500);
#endif
      cancelWorkflow();
      break;
    case 'D':
      lastKeyPressed = 'D';
      Serial.println("Key D -> store mission snapshot to portal");
      lcdShow("D: Store mission", "Sending to portal");
      delay(500);
      publishMissionEvent("stored", "stored via keypad D", true);
      break;
    case '1':
      lastKeyPressed = '1';
      Serial.println("Key 1 -> NAVIGATE home only (after job idle)");
      lcdShow("1: Go HOME", "If robot idle");
      delay(500);
      startNavOnly(POINT_HOME, "Go home only");
      break;
    case '2':
      lastKeyPressed = '2';
      Serial.println("Key 2 -> NAVIGATE charge only (after job idle)");
      lcdShow("2: Go CHARGE", "If robot idle");
      delay(500);
      startNavOnly(POINT_CHARGE, "Go charge only");
      break;
    default: {
      char keyMsg[17];
      snprintf(keyMsg, sizeof(keyMsg), "Key: %c", key);
      lcdShowFlash(keyMsg, "Ignored", 800);
      break;
    }
  }
}

void initUi() {
#if UI_MODE == 1
  if (LATCH_START_PIN >= 0) pinMode(LATCH_START_PIN, INPUT_PULLUP);
  if (LATCH_TASK14_PIN >= 0) pinMode(LATCH_TASK14_PIN, INPUT_PULLUP);
  pinMode(LED_GREEN_PIN, OUTPUT);
  pinMode(LED_YELLOW_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);
  pinMode(PIN_RING_WHITE, OUTPUT);
  pinMode(PIN_RING_BLUE, OUTPUT);
  latchStartStableHigh = true;
  latchStartLastRawHigh = true;
  latchStartChangeMs = millis();
  latchTask14StableHigh = true;
  latchTask14LastRawHigh = true;
  latchTask14ChangeMs = millis();
  panelBlueClosed = false;
  panelSeqActive = false;

  // RAW boot flash — must see lights even before Wi‑Fi
  Serial.println("*** BOOT LED RAW TEST (HIGH=ON for Robu modules + rings) ***");
  digitalWrite(PIN_RING_WHITE, PANEL_RING_ON_LEVEL);
  digitalWrite(PIN_RING_BLUE, PANEL_RING_ON_LEVEL);
  Serial.println("  rings WHITE+BLUE ON 1s");
  delay(1000);
  digitalWrite(PIN_RING_BLUE, PANEL_RING_OFF_LEVEL);

  digitalWrite(LED_GREEN_PIN, PANEL_STATUS_ON_LEVEL);
  digitalWrite(LED_YELLOW_PIN, PANEL_STATUS_OFF_LEVEL);
  digitalWrite(LED_RED_PIN, PANEL_STATUS_OFF_LEVEL);
  Serial.println("  GREEN ON 1s — if dark: put Green VCC on GND, IN on GPIO10");
  delay(1000);

  digitalWrite(LED_GREEN_PIN, PANEL_STATUS_OFF_LEVEL);
  digitalWrite(LED_RED_PIN, PANEL_STATUS_ON_LEVEL);
  Serial.println("  RED ON 1s");
  delay(1000);

  digitalWrite(LED_RED_PIN, PANEL_STATUS_OFF_LEVEL);
  digitalWrite(LED_YELLOW_PIN, PANEL_STATUS_ON_LEVEL);
  Serial.println("  YELLOW ON 1s");
  delay(1000);

  digitalWrite(LED_YELLOW_PIN, PANEL_STATUS_OFF_LEVEL);
  digitalWrite(PIN_RING_WHITE, PANEL_RING_ON_LEVEL);  // stay on while powered
  digitalWrite(PIN_RING_BLUE, PANEL_RING_OFF_LEVEL);
  Serial.println("*** BOOT LED TEST DONE — white ring stays ON ***");

  if (LED_FORCE_DIAG) {
    Serial.println("*** LED_FORCE_DIAG=true — ALL LEDs forced ON ***");
    digitalWrite(LED_GREEN_PIN, PANEL_STATUS_ON_LEVEL);
    digitalWrite(LED_YELLOW_PIN, PANEL_STATUS_ON_LEVEL);
    digitalWrite(LED_RED_PIN, PANEL_STATUS_ON_LEVEL);
    digitalWrite(PIN_RING_WHITE, PANEL_RING_ON_LEVEL);
    digitalWrite(PIN_RING_BLUE, PANEL_RING_ON_LEVEL);
  }

  Serial.println("Panel UI: Blue GPIO7 LOW=pressed");
  Serial.printf("  G=%d Y=%d R=%d ringW=%d ringB=%d\n",
                LED_GREEN_PIN, LED_YELLOW_PIN, LED_RED_PIN, PIN_RING_WHITE, PIN_RING_BLUE);
  Serial.println("  Blue press: blue ring + Green 2s → Red 2s → Yellow");
  Serial.printf("  GPIO7 now=%s (LOW=pressed)\n",
                digitalRead(LATCH_TASK14_PIN) == LOW ? "LOW" : "HIGH");
#else
  for (int i = 0; i < BUTTON_COUNT; i++) {
    pinMode(BUTTONS[i].pin, INPUT_PULLUP);
    btnStableHigh[i] = true;
    btnLastRawHigh[i] = true;
    btnLastChangeMs[i] = millis();
  }
  Serial.println("Lab UI: tactile buttons + LCD");
#endif
}

#if UI_MODE == 1
// edge: -1 = opened (LOW→HIGH), +1 = closed (HIGH→LOW), 0 = no change
int pollLatchEdge(int pin, bool& stableHigh, bool& lastRawHigh, unsigned long& changeMs) {
  if (pin < 0) return 0;
  unsigned long now = millis();
  bool rawHigh = digitalRead(pin) == HIGH;
  if (rawHigh != lastRawHigh) {
    lastRawHigh = rawHigh;
    changeMs = now;
  }
  if ((now - changeMs) < BTN_DEBOUNCE_MS) return 0;
  if (rawHigh == stableHigh) return 0;
  stableHigh = rawHigh;
  return rawHigh ? -1 : 1;  // +1 CLOSED, -1 OPEN
}
#endif

void serviceUi() {
#if UI_MODE == 1
  // LEDs first every loop (live GPIO7) — then optional AMR job edge
  updateStatusLeds();

  int blueEdge = pollLatchEdge(LATCH_TASK14_PIN, latchTask14StableHigh, latchTask14LastRawHigh, latchTask14ChangeMs);
  if (blueEdge == 1) {
    Serial.println("Blue CLOSED edge → AMR job start");
    handleKey('A');
  } else if (blueEdge == -1) {
    Serial.println("Blue OPEN edge → AMR cancel");
    handleKey('C');
  }

  static unsigned long lastGpioLogMs = 0;
  if (millis() - lastGpioLogMs > 2000) {
    lastGpioLogMs = millis();
    Serial.printf("GPIO7=%s bluePressed=%d seq=%d\n",
                  digitalRead(LATCH_TASK14_PIN) == LOW ? "LOW" : "HIGH",
                  (int)(digitalRead(LATCH_TASK14_PIN) == LOW),
                  (int)panelSeqActive);
  }
#else
  char key = 0;
  unsigned long now = millis();
  for (int i = 0; i < BUTTON_COUNT; i++) {
    bool rawHigh = digitalRead(BUTTONS[i].pin) == HIGH;
    if (rawHigh != btnLastRawHigh[i]) {
      btnLastRawHigh[i] = rawHigh;
      btnLastChangeMs[i] = now;
    }
    if ((now - btnLastChangeMs[i]) < BTN_DEBOUNCE_MS) continue;
    if (rawHigh == btnStableHigh[i]) continue;
    btnStableHigh[i] = rawHigh;
    if (!rawHigh) {
      key = BUTTONS[i].key;
      break;
    }
  }
  if (key) {
    Serial.printf("Button %c\n", key);
    handleKey(key);
  }
#endif
}

void initButtons() { initUi(); }
void serviceButtons() { serviceUi(); }
void serviceKeypad() { serviceUi(); }

void serviceSerialKeys() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r' || c == '\n') continue;
    Serial.printf("Serial %c\n", c);
#if UI_MODE == 1
    if (c == 'A' || c == 'a') handleKey('A');
    else if (c == 'C' || c == 'c') handleKey('C');
    else {
      Serial.printf("Unknown '%c' — UI_MODE=1 accepts only A(start) or C(cancel)\n",
                    (c >= 32 && c < 127) ? c : '?');
    }
#else
    if (c == 'A' || c == 'a') handleKey('A');
    else if (c == 'B' || c == 'b') handleKey('B');
    else if (c == 'C' || c == 'c') handleKey('C');
    else if (c == 'D' || c == 'd') handleKey('D');
    else if (c == '1') handleKey('1');
    else if (c == '2') handleKey('2');
    else {
      Serial.printf("Unknown '%c' — A=fwd B=rev C=cancel D=store 1=home 2=charge\n",
                    (c >= 32 && c < 127) ? c : '?');
    }
#endif

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
  initUi();

#if UI_MODE == 0
  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  scanI2cBus();
  initLcd();
  if (lcdReady) {
    lcdShow("Booting...", "Btns+LCD ok");
  } else {
    Serial.println("WARNING: LCD not found");
    lcdShow("Booting...", "LCD NOT FOUND");
  }
#else
  lcdShow("Booting...", "Panel UI");
  updateStatusLeds();
#endif

  Serial.println();
  Serial.printf("=== Direct Reeman call station (UI_MODE=%d) ===\n", UI_MODE);
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

  initCredentials();

  if (!setupWifi()) {
    setPhase(Phase::Error, "WiFi failed");
    updateStatusLeds();
    return;
  }

  buildTopics();

  if (!robotHostname[0]) {
    Serial.println("ERROR: ROBOT_HOSTNAME empty in config.h");
    setPhase(Phase::Error, "hostname missing");
    updateStatusLeds();
    return;
  }

  if (!credentialsValid()) {
    Serial.println("ERROR: set ROBOT_TOKEN in config.h, then reflash");
    lcdShow("No token", "Edit config.h");
    setPhase(Phase::Error, "token missing");
    updateStatusLeds();
    return;
  }

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(1536);
  if (!mqttReconnect()) {
    setPhase(Phase::Error, "MQTT failed — start Mosquitto service");
    updateStatusLeds();
    return;
  }

  setPhase(Phase::WaitRobot, "waiting for AMR STATUS (Call Mode online?)");
  Serial.println("Waiting for robot heartbeat...");
#if UI_MODE == 1
  Serial.println("Then: Blue latch CLOSED = Task-14 start | Blue OPEN = cancel ESP state");
  Serial.println("LEDs: Green=start home → Yellow=p2 pick → Red=return home → OFF=done");
#else
  Serial.println("Then press A on tactile buttons");
#endif
  updateStatusLeds();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    updateStatusLeds();
    delay(100);
    return;
  }
  if (!mqtt.connected()) {
    updateStatusLeds();
    delay(2000);
    if (mqttReconnect()) setPhase(Phase::WaitRobot, "reconnected — wait STATUS");
    return;
  }
  mqtt.loop();
  servicePhoneHeartbeat();
  serviceWorkflow();
  serviceCancelButton();
  serviceUi();
  serviceSerialKeys();
  if (lcdFlashUntilMs <= millis()) updateLcdFromPhase();
  else updateStatusLeds();
}
