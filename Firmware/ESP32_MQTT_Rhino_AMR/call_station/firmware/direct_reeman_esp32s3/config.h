#pragma once
/*
 * Direct Reeman ESP32-S3 — industrial panel call station
 * ======================================================
 * UI_MODE:
 *   0 = breadboard tactile + LCD (lab)
 *   1 = latching metal buttons + R/Y/G LED modules (production panel)
 *
 * Panel Task-14 (UI_MODE=1):
 *   White latch (R165046) → battery power switch (B+ → buck IN+). Not a GPIO.
 *   Blue  latch (R165054) → Task-14 START: CLOSED starts job, OPEN cancels ESP state
 *   Job path: leave home → pick at p2 → place at p3 → return home
 *   Green LED  (R228873) → starting from home / job dispatched
 *   Yellow LED (R228872) → go to p2 pick / pick-place running
 *   Red LED    (R228871) → returning home (then OFF when complete)
 *
 * Credentials: paste Call Mode token, then upload.
 */

// 0 = tactile+LCD lab UI, 1 = latch buttons + status LEDs (no LCD)
#ifndef UI_MODE
#define UI_MODE 1
#endif

// ---- Wi-Fi (ESP32) ----
static const char* WIFI_SSID     = "USERNAME";
static const char* WIFI_PASSWORD = "XYZ";

// ---- Mosquitto on laptop ----
static const char* MQTT_HOST = "X.X.X.X";
static const int   MQTT_PORT = 1883;
static const char* MQTT_USER = "";
static const char* MQTT_PASS = "";

// ---- Reeman Call Mode (paste from AMR; reflash if token changes) ----
static const char* ROBOT_HOSTNAME = "rbot55f-260114-003-001";
static const char* ROBOT_TOKEN    = "Z2IcM93div5zO1jdJ5EgzaRlNaIHot1iTBDN19gjri4d0rbG6dIaVeWl";
static const char* ROBOT_KEY      = "a5F6dmfr";

// ---- Map: "" => JSON null (elevator off) ----
static const char* TASK_MAP = "";

// ---- Pallet workflow points ----
static const char* POINT_HOME   = "home";
static const char* POINT_CHARGE = "charge";
static const char* POINT_PICK   = "p2";
static const char* POINT_DROP   = "p3";

static const unsigned long HOME_DWELL_MS = 2500;
static const unsigned long IDLE_HOLD_MS = 2500;
static const unsigned long NO_MOTION_TIMEOUT_MS = 45000;

static const int MIN_BATTERY_PCT = 20;
static const unsigned long ROBOT_HB_MAX_AGE_MS = 8000;
static const unsigned long PHONE_HB_INTERVAL_MS = 4000;

static const int PIN_CANCEL_BTN = -1;
static const int PIN_RGB        = 48;
static const uint8_t RGB_BRIGHT = 40;

#if UI_MODE == 1
/*
 * === PANEL WIRING (Task-14) ===
 *
 * Power:
 *   Battery B+ → White SWITCH → Buck IN+
 *   Battery B− → Buck IN−
 *   Buck OUT+ → ESP32 5V | Buck OUT− → ESP32 GND
 *   White is POWER only — do not put VCC across blue switch contacts.
 *
 * Blue Task-14 switch (1NO):
 *   Beep pin → GPIO7 | other → common GND   (INPUT_PULLUP; CLOSED = LOW)
 *   No series 10k/15k required. Optional: 10k pull-up GPIO7→3.3V.
 *
 * Status modules (Robu LED Indicator Signal Light — Red/Yellow/Green):
 *   Same idea as button rings — drive IN HIGH to light.
 *     IN  → Green GPIO10 | Yellow GPIO11 | Red GPIO12
 *     VCC → common GND
 *   ON = GPIO HIGH | OFF = GPIO LOW
 *
 * Ring LEDs:
 *   White LED+ → GPIO13 | Blue LED+ → GPIO14 | LED− → common GND
 *
 * COMMON GND: ESP GND + blue switch return + ring LED− + status VCC + buck OUT−
 */
// White power latch is not on GPIO. Set >=0 only if you wire a second start switch.
static const int LATCH_START_PIN   = -1;
// Blue latch = Task-14 start (CLOSED) / cancel ESP state (OPEN)
static const int LATCH_TASK14_PIN  = 7;
static const int PIN_RING_WHITE    = 13;
static const int PIN_RING_BLUE     = 14;
static const int LED_GREEN_PIN     = 10;
static const int LED_YELLOW_PIN    = 11;
static const int LED_RED_PIN       = 12;
static const unsigned long BTN_DEBOUNCE_MS = 50;
// Robu signal modules + rings: ON = HIGH
static const bool LED_STATUS_ACTIVE_HIGH = true;
static const bool LED_RING_ACTIVE_HIGH = true;
static const bool RING_FOLLOW_LATCH = true;
static const bool LED_BOOT_SELFTEST = true;

// Panel local LED: Blue pressed → blue ring ON + Green 2s → Red 2s → Yellow
// Blue released → blue ring OFF + G/Y/R OFF | White ring ON while ESP powered
static const bool PANEL_LOCAL_LED_SEQ = true;
static const unsigned long PANEL_LED_STEP_MS = 2000;
// Robu modules: IN→GPIO, VCC→GND → light when IN is HIGH
static const int PANEL_STATUS_ON_LEVEL = HIGH;
static const int PANEL_STATUS_OFF_LEVEL = LOW;
static const int PANEL_RING_ON_LEVEL = HIGH;
static const int PANEL_RING_OFF_LEVEL = LOW;

// Diagnose: true = force ALL LEDs ON forever. false = Blue sequence.
static const bool LED_FORCE_DIAG = false;

// Back-compat
static const bool LED_ACTIVE_HIGH = LED_STATUS_ACTIVE_HIGH;
static const bool LED_FORCE_ALL_HIGH = LED_FORCE_DIAG;
static const bool LED_STATUS_FORCE_HIGH = false;

// Back-compat aliases (older snippets)
static const int LATCH_CANCEL_PIN = LATCH_TASK14_PIN;
static const int PIN_RING_START   = PIN_RING_WHITE;
static const int PIN_RING_CANCEL  = PIN_RING_BLUE;
#else
// Lab tactile buttons + LCD
static const int BTN_D_PIN = 5;
static const int BTN_1_PIN = 4;
static const int BTN_A_PIN = 6;
static const int BTN_C_PIN = 7;
static const int BTN_B_PIN = 8;
static const int BTN_2_PIN = 10;
static const unsigned long BTN_DEBOUNCE_MS = 40;

static const int LCD_SDA_PIN = 1;
static const int LCD_SCL_PIN = 2;
static const uint8_t LCD_I2C_ADDR = 0x27;
static const uint8_t LCD_COLS = 16;
static const uint8_t LCD_ROWS = 2;
#endif

static const char* MISSION_TOPIC = "callstation/mission/record";
static const char* STATION_ID    = "esp-panel-1";
