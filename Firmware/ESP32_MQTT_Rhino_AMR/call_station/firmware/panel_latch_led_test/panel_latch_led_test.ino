/*
 * Panel latch + LED test (no Wi-Fi / no AMR)
 * Board: ESP32-S3 Dev Module | Serial: 115200
 *
 * === YOUR PARTS (pin count) ===
 *
 * Each LANBOO button (White R165046 / Blue R165054) has 4 pins:
 *   [A] SWITCH (1NO) — 2 pins  → ESP32 GPIO + common GND  (NOT 5V!)
 *   [B] RING LED     — 2 pins  → see RING_USE_5V below
 *
 * Each status module R228871/872/873 has 2 pins:
 *   VCC → common GND
 *   IN  → ESP32 GPIO (10 / 11 / 12)
 *
 * === WIRING CHECK (is it correct?) ===
 *
 *   CORRECT:
 *     Switch pin 1 ── GPIO4 (START) or GPIO7 (CANCEL)
 *     Switch pin 2 ── common GND
 *     Green  IN ── GPIO10 ,  Green  VCC ── GND
 *     Yellow IN ── GPIO11 ,  Yellow VCC ── GND
 *     Red    IN ── GPIO12 ,  Red    VCC ── GND
 *     All GND joined: ESP GND + switch + all VCC + ring LED −
 *
 *   RING LED (pick one):
 *     Best:  RING+ → buck 5V , RING− → GND  (set RING_USE_5V true, no GPIO)
 *     Test:  White RING+ → GPIO13 , Blue RING+ → GPIO14 , RING− → GND
 *
 *   WRONG:
 *     Switch pins to 5V/GND (power) instead of GPIO/GND
 *     Mixing switch pins with ring LED pins
 */

#define USE_CANCEL_BUTTON 1   // 0 = only White START wired

// --- LANBOO SWITCH contacts (1NO each) → INPUT_PULLUP ---
static const int PIN_SWITCH_START  = 4;   // White button switch → GPIO
static const int PIN_SWITCH_CANCEL = 7;   // Blue button switch → GPIO (if used)

// --- LANBOO RING LED (2 pins each: + and −) ---
#define RING_USE_5V 0
static const int PIN_RING_WHITE_PLUS = 13;  // White ring + ; − → GND
static const int PIN_RING_BLUE_PLUS  = 14;  // Blue ring +  ; − → GND

// --- Status modules (IN only; VCC soldered to common GND) ---
static const int PIN_STATUS_GREEN  = 10;
static const int PIN_STATUS_YELLOW = 11;
static const int PIN_STATUS_RED    = 12;

static const unsigned long DEBOUNCE_MS = 40;

struct Latch {
  int pin;
  const char* name;
  bool stableHigh;
  bool rawHigh;
  unsigned long changeMs;
};

Latch latchStart  = {PIN_SWITCH_START,  "START",  true, true, 0};
#if USE_CANCEL_BUTTON
Latch latchCancel = {PIN_SWITCH_CANCEL, "CANCEL", true, true, 0};
#endif

int pollLatch(Latch& b) {
  unsigned long now = millis();
  bool rh = digitalRead(b.pin) == HIGH;
  if (rh != b.rawHigh) {
    b.rawHigh = rh;
    b.changeMs = now;
  }
  if ((now - b.changeMs) < DEBOUNCE_MS) return 0;
  if (rh == b.stableHigh) return 0;
  b.stableHigh = rh;
  return rh ? -1 : 1;
}

void setStatusGreen(bool on)  { digitalWrite(PIN_STATUS_GREEN,  on ? HIGH : LOW); }
void setStatusYellow(bool on) { digitalWrite(PIN_STATUS_YELLOW, on ? HIGH : LOW); }
void setStatusRed(bool on)    { digitalWrite(PIN_STATUS_RED,    on ? HIGH : LOW); }

void setAllStatus(bool g, bool y, bool r) {
  setStatusGreen(g);
  setStatusYellow(y);
  setStatusRed(r);
}

void setButtonRingLed(bool whiteOn, bool blueOn) {
#if RING_USE_5V
  (void)whiteOn;
  (void)blueOn;
#else
  digitalWrite(PIN_RING_WHITE_PLUS, whiteOn ? HIGH : LOW);
  digitalWrite(PIN_RING_BLUE_PLUS, blueOn ? HIGH : LOW);
#endif
}

void showRunning() {
  setButtonRingLed(true, false);
  setAllStatus(true, false, false);   // Green = job running
}

void showIdle() {
  setButtonRingLed(false, false);
  setAllStatus(false, false, true);   // Red = idle / ready
}

void showCancel() {
  setButtonRingLed(false, true);
  setAllStatus(false, true, false);   // Yellow = cancel / pause
}

void applyAfterCancelOff() {
  if (!latchStart.stableHigh) showRunning();
  else showIdle();
}

void printWiringHelp() {
  Serial.println();
  Serial.println("=== Wiring map ===");
  Serial.println("WHITE switch: GPIO4 + GND");
  Serial.println("WHITE ring+:  GPIO13 + GND");
#if USE_CANCEL_BUTTON
  Serial.println("BLUE  switch: GPIO7 + GND");
  Serial.println("BLUE  ring+:  GPIO14 + GND");
#endif
#if RING_USE_5V
  Serial.println("(RING_USE_5V: wire ring+ to 5V instead of GPIO)");
#endif
  Serial.println("Green  module: IN=GPIO10, VCC=GND");
  Serial.println("Yellow module: IN=GPIO11, VCC=GND");
  Serial.println("Red    module: IN=GPIO12, VCC=GND");
  Serial.println("Common GND: ESP + all switch GND + all VCC + ring LED -");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(PIN_SWITCH_START, INPUT_PULLUP);
#if USE_CANCEL_BUTTON
  pinMode(PIN_SWITCH_CANCEL, INPUT_PULLUP);
#endif
#if !RING_USE_5V
  pinMode(PIN_RING_WHITE_PLUS, OUTPUT);
  pinMode(PIN_RING_BLUE_PLUS, OUTPUT);
#endif
  pinMode(PIN_STATUS_GREEN, OUTPUT);
  pinMode(PIN_STATUS_YELLOW, OUTPUT);
  pinMode(PIN_STATUS_RED, OUTPUT);

  latchStart.changeMs = millis();
#if USE_CANCEL_BUTTON
  latchCancel.changeMs = millis();
#endif

  setButtonRingLed(false, false);
  setAllStatus(false, false, false);

  Serial.println();
  Serial.println("=== Panel test: switch + ring LED + status IN pins ===");
  printWiringHelp();
  Serial.println("Boot self-test: Red -> Yellow -> Green");

  setStatusRed(true);
  delay(400);
  setStatusRed(false);
  setStatusYellow(true);
  delay(400);
  setStatusYellow(false);
  setStatusGreen(true);
  delay(400);
  setStatusGreen(false);

  showIdle();
  Serial.println("Ready. Latch START ON/OFF (and CANCEL if wired).");
}

void loop() {
  int s = pollLatch(latchStart);
  if (s == 1) {
    Serial.println("START switch ON  -> ring ON, status GREEN ON");
    showRunning();
  } else if (s == -1) {
    Serial.println("START switch OFF -> ring OFF, status RED ON");
    showIdle();
  }

#if USE_CANCEL_BUTTON
  int c = pollLatch(latchCancel);
  if (c == 1) {
    Serial.println("CANCEL switch ON -> status YELLOW ON");
    showCancel();
  } else if (c == -1) {
    Serial.println("CANCEL switch OFF");
    applyAfterCancelOff();
  }
#endif

  delay(5);
}
