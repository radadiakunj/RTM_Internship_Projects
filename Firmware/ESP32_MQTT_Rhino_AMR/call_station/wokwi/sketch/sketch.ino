/*
 * Wokwi SIMULATION ONLY — buttons + LED phases (no real MQTT/AMR).
 * Upload the real sketch from ../firmware/call_station_esp32s3/ to hardware.
 *
 * White button: cycles demo phases Green → White → Blue → Idle
 * Blue button: jump to "to_home" then idle
 */
const int PIN_BTN_WHITE = 4;
const int PIN_BTN_BLUE  = 5;
const int PIN_LED_RED = 6, PIN_LED_YELLOW = 7, PIN_LED_GREEN = 8;
const int PIN_LED_WHITE = 9, PIN_LED_BLUE = 10;

void setLeds(bool r, bool y, bool g, bool w, bool b) {
  digitalWrite(PIN_LED_RED, r); digitalWrite(PIN_LED_YELLOW, y);
  digitalWrite(PIN_LED_GREEN, g); digitalWrite(PIN_LED_WHITE, w);
  digitalWrite(PIN_LED_BLUE, b);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BTN_WHITE, INPUT_PULLUP);
  pinMode(PIN_BTN_BLUE, INPUT_PULLUP);
  for (int p : {PIN_LED_RED, PIN_LED_YELLOW, PIN_LED_GREEN, PIN_LED_WHITE, PIN_LED_BLUE})
    pinMode(p, OUTPUT);
  setLeds(false, true, false, false, false);
  Serial.println("Wokwi call-station LED demo. Press WHITE=job, BLUE=home");
}

void demoJob() {
  Serial.println("DEMO job: to_pick");
  setLeds(false, false, true, false, false); delay(1500);
  Serial.println("DEMO lifting");
  delay(800);
  Serial.println("DEMO to_drop");
  setLeds(false, false, false, true, false); delay(1500);
  Serial.println("DEMO to_home");
  setLeds(false, false, false, false, true); delay(1500);
  Serial.println("DEMO idle");
  setLeds(false, true, false, false, false);
}

void loop() {
  static int w = HIGH, b = HIGH;
  int nw = digitalRead(PIN_BTN_WHITE);
  int nb = digitalRead(PIN_BTN_BLUE);
  if (w == HIGH && nw == LOW) demoJob();
  if (b == HIGH && nb == LOW) {
    Serial.println("DEMO go_home");
    setLeds(false, false, false, false, true);
    delay(1200);
    setLeds(false, true, false, false, false);
  }
  w = nw; b = nb;
  delay(20);
}
