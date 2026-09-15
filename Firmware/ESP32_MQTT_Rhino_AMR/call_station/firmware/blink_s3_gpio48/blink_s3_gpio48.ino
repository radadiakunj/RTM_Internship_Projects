/*
 * ESP32-S3-DevKitC-1 — onboard LED blink (GPIO 48)
 * =================================================
 * Many ESP32-S3-DevKitC-1 boards have an addressable RGB LED (WS2812)
 * on GPIO 48 — same idea as common setup videos for this board.
 *
 * RX / TX LEDs often do NOT blink on S3 when you use the USB-C port:
 * the S3 uses built-in USB (CDC), not a separate USB-UART chip that
 * drives classic RX/TX activity lights. Use THIS RGB LED to confirm life.
 *
 * Arduino IDE:
 *   Board: "ESP32S3 Dev Module"
 *   USB CDC On Boot: "Enabled"  (recommended)
 *   Port: your COMx
 *
 * USB power ONLY for this test — no 12V battery / LEDs.
 */

#if !defined(LED_PIN)
  // DevKitC-1 RGB LED (common)
  #define LED_PIN 48
#endif

// Brightness 0–255 (keep low so it is not harsh)
static const uint8_t BRIGHT = 40;

void ledOff() {
  // R, G, B
  neopixelWrite(LED_PIN, 0, 0, 0);
}

void ledOn(uint8_t r, uint8_t g, uint8_t b) {
  neopixelWrite(LED_PIN, r, g, b);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("ESP32-S3 onboard RGB LED test (GPIO 48)");
  Serial.println("If you see color blinks, the board is healthy.");
  Serial.println("RX/TX LEDs may stay off on USB-C — that is normal.");

  // Some cores also accept pinMode; neopixelWrite drives the WS2812.
  pinMode(LED_PIN, OUTPUT);
  ledOff();
}

void loop() {
  // Red
  Serial.println("LED RED");
  ledOn(BRIGHT, 0, 0);
  delay(400);
  ledOff();
  delay(200);

  // Green
  Serial.println("LED GREEN");
  ledOn(0, BRIGHT, 0);
  delay(400);
  ledOff();
  delay(200);

  // Blue
  Serial.println("LED BLUE");
  ledOn(0, 0, BRIGHT);
  delay(400);
  ledOff();
  delay(600);
}
