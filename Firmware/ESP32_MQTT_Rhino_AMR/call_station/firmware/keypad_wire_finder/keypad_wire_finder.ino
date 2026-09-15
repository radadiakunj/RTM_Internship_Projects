/*
 * ESP32-S3 — Keypad wire finder (NO LIBRARY REQUIRED)
 * ===================================================
 * This sketch does NOT use any Keypad library.
 * It reads GPIO directly — nothing to install except ESP32 board support.
 *
 * Arduino IDE: Tools -> Board -> ESP32S3 Dev Module
 * Serial Monitor: 115200
 *
 * Wire keypad ribbon pin 1..10 to GPIO below (count pin 1 on PCB back).
 * Do NOT connect keypad wires to 3V3 or GND.
 *
 *   Ribbon 1->GPIO1   6->GPIO6    (avoid GPIO3 strapping pin)
 *   Ribbon 2->GPIO2   7->GPIO7
 *   Ribbon 3->GPIO4   8->GPIO10
 *   Ribbon 4->GPIO5   9->GPIO11
 *   Ribbon 5->GPIO8  10->GPIO12
 *
 * If still nothing: use multimeter continuity while holding a key.
 */

static const int NUM_PINS = 10;
// Ribbon pin 1..10 -> ESP32 GPIO (GPIO3 skipped — strapping pin on S3)
static const int PIN_GPIO[NUM_PINS] = {1, 2, 4, 5, 8, 6, 7, 10, 11, 12};

void allInputsPullup() {
  for (int i = 0; i < NUM_PINS; i++) {
    pinMode(PIN_GPIO[i], INPUT_PULLUP);
  }
}

bool scanHeldKey(int& outDriveIdx, int& outSenseIdx) {
  for (int drive = 0; drive < NUM_PINS; drive++) {
    allInputsPullup();
    pinMode(PIN_GPIO[drive], OUTPUT);
    digitalWrite(PIN_GPIO[drive], LOW);
    delayMicroseconds(200);
    for (int sense = 0; sense < NUM_PINS; sense++) {
      if (sense == drive) continue;
      if (digitalRead(PIN_GPIO[sense]) == LOW) {
        outDriveIdx = drive;
        outSenseIdx = sense;
        pinMode(PIN_GPIO[drive], INPUT_PULLUP);
        return true;
      }
    }
    pinMode(PIN_GPIO[drive], INPUT_PULLUP);
  }
  return false;
}

void printPinTable() {
  Serial.println();
  Serial.println("NO LIBRARY NEEDED — raw GPIO scan only.");
  Serial.println("Ribbon pin -> ESP32 GPIO:");
  for (int i = 0; i < NUM_PINS; i++) {
    Serial.printf("  Keypad pin %2d  ->  GPIO %d\n", i + 1, PIN_GPIO[i]);
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  allInputsPullup();

  Serial.println();
  Serial.println("========================================");
  Serial.println("  KEYPAD WIRE FINDER");
  Serial.println("  Library: NONE required");
  Serial.println("========================================");
  printPinTable();
  Serial.println("Hold any key 1 second. Heartbeat every 3s if idle.");
  Serial.println("If NEVER detects: check wires, remove 3V3/GND from keypad.");
  Serial.println();
}

void loop() {
  static unsigned long lastHb = 0;
  unsigned long now = millis();

  int driveIdx = -1;
  int senseIdx = -1;

  if (scanHeldKey(driveIdx, senseIdx)) {
    static int lastD = -1, lastS = -1;
    static unsigned long lastPrint = 0;
    if (driveIdx != lastD || senseIdx != lastS || (now - lastPrint) > 500) {
      lastD = driveIdx;
      lastS = senseIdx;
      lastPrint = now;
      Serial.println("----------------------------------------");
      Serial.printf("KEY DETECTED: ribbon pin %d (GPIO %d) <-> pin %d (GPIO %d)\n",
                      driveIdx + 1, PIN_GPIO[driveIdx],
                      senseIdx + 1, PIN_GPIO[senseIdx]);
      Serial.println("----------------------------------------");
    }
    lastHb = now;
    return;
  }

  if (now - lastHb > 3000) {
    lastHb = now;
    Serial.println("[heartbeat] scanning... hold a key down firmly");
  }
}
