/**
 * 4x4 Keypad + I2C LCD + WiFi Cloud Upload — ESP32-S3
 * Stores completed task info to a custom REST API when D is pressed
 *
 * Libraries required:
 *   - "Keypad" by Mark Stanley
 *   - "LiquidCrystal I2C" by Frank de Brabander
 *   - WiFi.h and HTTPClient.h (built into ESP32 board package, no install needed)
 */

#include <Keypad.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ---------- WiFi credentials ----------
static const char* WIFI_SSID     = "RTM_HighSpeed";
static const char* WIFI_PASSWORD = "AtpL@0214#";

// ---------- REST API config (PLACEHOLDERS — replace with your real values) ----------
static const char* API_ENDPOINT   = "https://192.168.5.115:3000/api/missions";  // <-- replace
static const char* API_AUTH_TOKEN = "your-bearer-token-here";                     // <-- replace, or leave blank if no auth

// ---------- Keypad setup ----------
const byte ROWS = 4;
const byte COLS = 4;

char keys[ROWS][COLS] = {
  {'C','D','A','B'},
  {'9','#','3','6'},
  {'8','0','2','5'},
  {'7','*','1','4'}
};

byte rowPins[ROWS] = {12, 11, 10, 8};
byte colPins[COLS] = {5, 4, 7, 6};

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// ---------- LCD setup ----------
#define SDA_PIN 1
#define SCL_PIN 2
#define LCD_ADDR 0x27

LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);

// ---------- Task state ----------
bool taskRunning = false;
char runningKey = 0;
unsigned long taskStartTime = 0;

char lastCompletedKey = 0;
bool taskStored = false;

const unsigned long TASK_DURATION_MS = 5000;  // placeholder — replace with real completion signal

void showMessage(const String &line1, const String &line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}

String taskLabel(char key) {
  switch (key) {
    case 'A': return "A";
    case 'B': return "B";
    case '1': return "1";
    case '2': return "2";
    default:  return String(key);
  }
}

String taskDescription(char key) {
  switch (key) {
    case 'A': return "home->p2->p3";
    case 'B': return "p3->p2->home";
    case '1': return "Navigate home";
    case '2': return "Go to chg stn";
    default:  return "";
  }
}

// ---------- WiFi connect (called once in setup) ----------
void connectWiFi() {
  showMessage("Connecting WiFi", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 15000) {
    delay(300);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
    showMessage("WiFi Connected", WiFi.localIP().toString());
  } else {
    Serial.println("\nWiFi connection FAILED");
    showMessage("WiFi FAILED", "Check credentials");
  }
  delay(1500);
}

// ---------- Upload a completed task to the REST API ----------
bool uploadTaskToCloud(char key) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Upload skipped: WiFi not connected");
    return false;
  }

  HTTPClient http;
  http.begin(API_ENDPOINT);
  http.addHeader("Content-Type", "application/json");

  if (strlen(API_AUTH_TOKEN) > 0) {
    http.addHeader("Authorization", String("Bearer ") + API_AUTH_TOKEN);
  }

  // Build JSON payload
  String payload = "{";
  payload += "\"task\":\"" + taskLabel(key) + "\",";
  payload += "\"description\":\"" + taskDescription(key) + "\",";
  payload += "\"timestamp\":" + String(millis());
  payload += "}";

  Serial.println("POST payload: " + payload);

  int httpCode = http.POST(payload);
  bool success = (httpCode >= 200 && httpCode < 300);

  Serial.printf("HTTP response code: %d\n", httpCode);
  if (httpCode > 0) {
    Serial.println("Response: " + http.getString());
  }

  http.end();
  return success;
}

void startTask(char key, const String &line1, const String &line2) {
  taskRunning = true;
  runningKey = key;
  taskStartTime = millis();
  showMessage(line1, line2);
  Serial.printf("Task %c started\n", key);
}

void completeTask() {
  Serial.printf("Task %c complete\n", runningKey);
  lastCompletedKey = runningKey;
  taskStored = false;

  taskRunning = false;
  runningKey = 0;

  showMessage("Task complete", "Ready...");
  delay(1000);
  showMessage("Keypad Ready", "Press a key...");
}

void cancelTask() {
  char cancelledKey = runningKey;
  Serial.printf("Task %c cancelled\n", cancelledKey);

  taskRunning = false;
  runningKey = 0;

  showMessage("Cancelling Task " + taskLabel(cancelledKey), taskDescription(cancelledKey));
  delay(1500);
  showMessage("Keypad Ready", "Press a key...");
}

void handleStore() {
  if (lastCompletedKey == 0) {
    showMessage("No completed task", "to store yet");
    delay(1200);
  } else if (taskStored) {
    showMessage("Task " + taskLabel(lastCompletedKey) + " already", "stored on cloud");
    Serial.printf("D: Task %c already stored\n", lastCompletedKey);
    delay(1200);
  } else {
    showMessage("Task " + taskLabel(lastCompletedKey), "uploading...");
    Serial.printf("D: Uploading Task %c to cloud\n", lastCompletedKey);

    bool success = uploadTaskToCloud(lastCompletedKey);

    if (success) {
      showMessage("Task " + taskLabel(lastCompletedKey) + " stored", "on cloud!");
      taskStored = true;
    } else {
      showMessage("Upload FAILED", "Check WiFi/API");
    }
    delay(1500);
  }

  if (taskRunning) {
    showMessage("Task " + taskLabel(runningKey), "running...");
  } else {
    showMessage("Keypad Ready", "Press a key...");
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);

  Wire.begin(SDA_PIN, SCL_PIN);
  lcd.init();
  lcd.backlight();

  showMessage("I2C OK: 0x27", "LCD Ready");
  delay(1000);

  connectWiFi();

  showMessage("Keypad Ready", "Press a key...");
  Serial.println("=== Keypad + LCD + Cloud Ready ===");
}

void loop() {
  if (taskRunning && millis() - taskStartTime >= TASK_DURATION_MS) {
    completeTask();
  }

  char key = keypad.getKey();
  if (!key) return;

  Serial.printf("Key pressed: %c\n", key);

  if (key == 'C') {
    if (taskRunning) {
      cancelTask();
    } else {
      showMessage("No task running", "Nothing to cancel");
    }
    return;
  }

  if (key == 'D') {
    handleStore();
    return;
  }

  bool isTaskKey = (key == 'A' || key == 'B' || key == '1' || key == '2');

  if (isTaskKey) {
    if (taskRunning) {
      if (key == runningKey) {
        showMessage("Task " + taskLabel(key), "already running");
      } else {
        showMessage("Busy: Task " + taskLabel(runningKey), "Press C to cancel");
      }
      return;
    }

    switch (key) {
      case 'A': startTask('A', "home->p2->p3", "Task running..."); break;
      case 'B': startTask('B', "p3->p2->home", "Task running..."); break;
      case '1': startTask('1', "Navigate to", "home only"); break;
      case '2': startTask('2', "Go to", "charging stn"); break;
    }
    return;
  }

  if (taskRunning) {
    showMessage("Busy: Task " + taskLabel(runningKey), "Press C to cancel");
  } else {
    showMessage("Key pressed:", String(key));
  }
}