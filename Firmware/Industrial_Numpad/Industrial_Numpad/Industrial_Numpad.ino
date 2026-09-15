/*
 * Industrial Numpad - ESP32 + RTM Cloud
 * -------------------------------------
 * Type digits, press A (Enter):
 *   1) Read the entered number
 *   2) Ensure RTM Cloud exists (create if missing)
 *   3) Upload the number to RTM Cloud
 *   4) Confirm success on LCD + Serial
 *
 * Board: ESP32-S3 N16R8 Dev Module
 *
 * Arduino IDE Tools settings:
 *   Board: ESP32S3 Dev Module
 *   USB CDC On Boot: Enabled
 *   PSRAM: OPI PSRAM
 *   Flash Size: 16MB (128Mb)
 *   Partition Scheme: 16M Flash (3MB APP/9.9MB FATFS)
 *   Upload Mode: UART0 / Hardware CDC
 *   USB Mode: Hardware CDC and JTAG
 *   Port: the COM port of the USB (not UART) Type-C
 *
 * Required libraries (Arduino Library Manager):
 *   - Keypad by Mark Stanley, Alexander Brevig
 *   - LiquidCrystal I2C by Frank de Brabander
 *
 * Before uploading firmware:
 *   1) Start RTM Cloud on your PC:
 *        cd rtm_cloud
 *        python server.py
 *   2) Copy the printed LAN IP into config.h -> RTM_CLOUD_HOST
 *   3) Join ESP32 to the same Wi-Fi as the PC (WIFI_SSID / WIFI_PASSWORD)
 *
 * Key map:
 *   1  2  3  A=Enter (upload to RTM Cloud)
 *   4  5  6  B=Esc
 *   7  8  9  C=PgUp
 *   *=Bksp 0  #=Clear  D=PgDn
 *
 * Wiring (ESP32-S3 — pins in config.h):
 *   Keypad R1..R4 -> GPIO 10, 11, 12, 13
 *   Keypad C1..C4 -> GPIO 14, 15, 16, 17
 *   LCD I2C SDA/SCL -> GPIO 8 / 9
 *   LCD VCC/GND -> 3V3 / GND  (or 5V if backpack needs 5V)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Keypad.h>
#include <LiquidCrystal_I2C.h>
#include "config.h"

// -------------------- LCD --------------------
#define LCD_ADDR 0x27
LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);

// -------------------- Keypad --------------------
const byte ROWS = 4;
const byte COLS = 4;

char keys[ROWS][COLS] = {
  { '1', '2', '3', 'A' },
  { '4', '5', '6', 'B' },
  { '7', '8', '9', 'C' },
  { '*', '0', '#', 'D' }
};

byte rowPins[ROWS] = { PIN_KP_R1, PIN_KP_R2, PIN_KP_R3, PIN_KP_R4 };
byte colPins[COLS] = { PIN_KP_C1, PIN_KP_C2, PIN_KP_C3, PIN_KP_C4 };

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// -------------------- Input buffer --------------------
const size_t MAX_DIGITS = 16;
char entry[MAX_DIGITS + 1];
size_t entryLen = 0;

unsigned long lastKeyMs = 0;
const unsigned long DEBOUNCE_MS = 40;

bool wifiReady = false;

// -------------------- UI helpers --------------------
void clearEntry() {
  entryLen = 0;
  entry[0] = '\0';
}

void updateLcd() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Enter number:");
  lcd.setCursor(0, 1);
  if (entryLen == 0) {
    lcd.print("_");
  } else {
    size_t start = (entryLen > 16) ? (entryLen - 16) : 0;
    lcd.print(entry + start);
  }
}

void showStatus(const char* line1, const char* line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}

// -------------------- Wi-Fi --------------------
bool connectWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    wifiReady = true;
    return true;
  }

  showStatus("WiFi connecting", WIFI_SSID);
  Serial.print(F("[WiFi] Connecting to "));
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print('.');
    if (millis() - start > 25000) {
      Serial.println();
      Serial.println(F("[WiFi] FAILED"));
      wifiReady = false;
      showStatus("WiFi FAILED", "Check config.h");
      delay(1200);
      return false;
    }
  }

  Serial.println();
  Serial.print(F("[WiFi] OK  IP="));
  Serial.println(WiFi.localIP());
  wifiReady = true;
  showStatus("WiFi OK", WiFi.localIP().toString().c_str());
  delay(800);
  return true;
}

String cloudBaseUrl() {
  return String("http://") + RTM_CLOUD_HOST + ":" + String(RTM_CLOUD_PORT);
}

// Ensure RTM Cloud exists (server creates it if missing)
bool ensureRtmCloud() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  String url = cloudBaseUrl() + "/api/cloud/create";
  Serial.print(F("[RTM] Ensure cloud: "));
  Serial.println(url);

  // Explicit WiFiClient is more reliable on ESP32 Arduino HTTPClient
  WiFiClient client;
  if (!http.begin(client, url)) {
    Serial.println(F("[RTM] http.begin failed"));
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000);

  String body = String("{\"name\":\"") + RTM_CLOUD_NAME + "\"}";
  int code = http.POST(body);
  String resp = http.getString();
  Serial.print(F("[RTM] create HTTP "));
  Serial.println(code);
  if (code <= 0) {
    Serial.print(F("[RTM] error: "));
    Serial.println(HTTPClient::errorToString(code));
  }
  Serial.println(resp);
  http.end();

  return (code >= 200 && code < 300);
}

// Upload entered number and return true on confirmed store
bool uploadToRtmCloud(const char* value) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("[RTM] Upload aborted: WiFi down"));
    return false;
  }

  HTTPClient http;
  String url = cloudBaseUrl() + "/api/upload";
  Serial.print(F("[RTM] Upload: "));
  Serial.println(url);

  WiFiClient client;
  if (!http.begin(client, url)) {
    Serial.println(F("[RTM] http.begin failed"));
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000);

  String body = String("{\"value\":\"") + value +
                "\",\"device\":\"" + RTM_DEVICE_ID + "\"}";
  int code = http.POST(body);
  String resp = http.getString();
  Serial.print(F("[RTM] upload HTTP "));
  Serial.println(code);
  if (code <= 0) {
    Serial.print(F("[RTM] error: "));
    Serial.println(HTTPClient::errorToString(code));
  }
  Serial.println(resp);
  http.end();

  // Confirm stored: HTTP 200 and response contains "ok":true
  bool ok = (code == 200) && (resp.indexOf("\"ok\":true") >= 0 || resp.indexOf("\"ok\": true") >= 0);
  return ok;
}

void submitEntry() {
  if (entryLen == 0) {
    Serial.println(F("[WARN] Enter pressed with empty input"));
    showStatus("Empty input", "Type digits...");
    delay(800);
    updateLcd();
    return;
  }

  // Keep a local copy — buffer is cleared after upload
  char value[MAX_DIGITS + 1];
  memcpy(value, entry, entryLen + 1);

  Serial.println(F("========== SUBMIT =========="));
  Serial.print(F("VALUE="));
  Serial.println(value);
  Serial.println(F("============================"));

  showStatus("Uploading...", value);

  if (!connectWifi()) {
    showStatus("Upload FAIL", "No WiFi");
    delay(1200);
    updateLcd();
    return;
  }

  showStatus("RTM Cloud...", "Creating/check");
  if (!ensureRtmCloud()) {
    Serial.println(F("[RTM] Cloud ensure FAILED — is server.py running?"));
    showStatus("Cloud FAIL", "Start server.py");
    delay(1500);
    updateLcd();
    return;
  }

  showStatus("Uploading to", "RTM Cloud...");
  bool stored = uploadToRtmCloud(value);

  if (stored) {
    Serial.println(F("[RTM] Stored successfully"));
    showStatus("Cloud OK", value);
  } else {
    Serial.println(F("[RTM] Store FAILED"));
    showStatus("Upload FAIL", value);
  }
  delay(1500);

  clearEntry();
  updateLcd();
}

void appendDigit(char digit) {
  if (entryLen >= MAX_DIGITS) {
    Serial.println(F("[WARN] Max digits reached"));
    showStatus("Max 16 digits", entry);
    delay(600);
    updateLcd();
    return;
  }
  entry[entryLen++] = digit;
  entry[entryLen] = '\0';
  updateLcd();
}

void backspace() {
  if (entryLen > 0) {
    entry[--entryLen] = '\0';
  }
  updateLcd();
}

void processKey(char key) {
  switch (key) {
    case '0': case '1': case '2': case '3': case '4':
    case '5': case '6': case '7': case '8': case '9':
      appendDigit(key);
      Serial.print(F("[KEY] digit "));
      Serial.println(key);
      break;

    case 'A':
      Serial.println(F("[KEY] Enter -> RTM Cloud upload"));
      submitEntry();
      break;

    case 'B':
      Serial.println(F("[KEY] Esc"));
      clearEntry();
      showStatus("Cleared (Esc)", "");
      delay(500);
      updateLcd();
      break;

    case '*':
      Serial.println(F("[KEY] Backspace"));
      backspace();
      break;

    case '#':
      Serial.println(F("[KEY] Clear"));
      clearEntry();
      updateLcd();
      break;

    case 'C':
      Serial.println(F("[KEY] PgUp"));
      showStatus("PgUp", entryLen ? entry : "-");
      delay(400);
      updateLcd();
      break;

    case 'D':
      Serial.println(F("[KEY] PgDn"));
      showStatus("PgDn", entryLen ? entry : "-");
      delay(400);
      updateLcd();
      break;

    default:
      Serial.print(F("[KEY] Unknown: "));
      Serial.println(key);
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  Serial.println();
  Serial.println(F("Industrial Numpad + RTM Cloud"));
  Serial.println(F("Type digits, then press A to upload"));
  Serial.print(F("Cloud URL: "));
  Serial.println(cloudBaseUrl());

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  lcd.init();
  lcd.backlight();

  clearEntry();
  showStatus("Industrial Pad", "RTM Cloud mode");
  delay(700);

  // Best-effort WiFi at boot (upload will retry if needed)
  if (connectWifi()) {
    ensureRtmCloud();
  }

  updateLcd();
}

void loop() {
  char key = keypad.getKey();
  if (!key) {
    return;
  }

  unsigned long now = millis();
  if (now - lastKeyMs < DEBOUNCE_MS) {
    return;
  }
  lastKeyMs = now;

  processKey(key);
}
