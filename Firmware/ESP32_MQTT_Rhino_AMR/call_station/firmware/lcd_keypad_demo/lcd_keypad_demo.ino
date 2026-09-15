/**
 * I2C Scanner + LCD Status Display — ESP32-S3
 * Scans for I2C devices and shows result directly on the LCD screen
 * (works standalone on battery power, no Serial Monitor needed)
 *
 * Wiring:
 *   LCD SDA -> GPIO 1
 *   LCD SCL -> GPIO 2
 *   LCD VCC -> 5V
 *   LCD GND -> GND
 *
 * Library required: "LiquidCrystal I2C" by Frank de Brabander
 */

 #include <Wire.h>
 #include <LiquidCrystal_I2C.h>
 
 #define SDA_PIN 1
 #define SCL_PIN 2
 
 LiquidCrystal_I2C* lcd = nullptr;
 byte foundAddress = 0;
 
 byte scanI2C() {
   for (byte address = 1; address < 127; address++) {
     Wire.beginTransmission(address);
     byte error = Wire.endTransmission();
     if (error == 0) {
       return address;  // return first device found
     }
   }
   return 0;  // nothing found
 }
 
 void setup() {
   Serial.begin(115200);
   delay(500);
 
   Wire.begin(SDA_PIN, SCL_PIN);
 
   foundAddress = scanI2C();
 
   if (foundAddress != 0) {
     Serial.printf("I2C device found at 0x%02X\n", foundAddress);
 
     lcd = new LiquidCrystal_I2C(foundAddress, 16, 2);
     lcd->init();
     lcd->backlight();
     lcd->setCursor(0, 0);
     lcd->print("I2C OK: 0x");
     lcd->print(foundAddress, HEX);
     lcd->setCursor(0, 1);
     lcd->print("LCD Ready!");
   } else {
     Serial.println("No I2C device found!");
     // Can't drive the LCD without knowing its address,
     // so just blink onboard behavior via Serial only.
   }
 }
 
 void loop() {
   // Nothing here yet — this sketch just confirms I2C + LCD are alive.
 }