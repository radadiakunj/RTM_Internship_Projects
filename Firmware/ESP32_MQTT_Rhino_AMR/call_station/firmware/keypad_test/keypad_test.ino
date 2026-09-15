/**
 * 4x4 Keypad test — ESP32-S3
 *
 * Library: Install "Keypad" by Mark Stanley from Library Manager
 * Board: ESP32S3 Dev Module
 * Serial Monitor: 115200
 *
 * Keypad 8 pins (no 3V3/GND):
 *   Row 1-4: GPIO 12, 11, 10, 8
 *   Col 1-4: GPIO 4, 5, 6, 7
 */

 #include <Keypad.h>

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
 
 void setup() {
   Serial.begin(115200);
   delay(500);
   Serial.println();
   Serial.println("=== Keypad Test (ESP32-S3) ===");
   Serial.println("Press any key...");
 }
 
 void loop() {
   char key = keypad.getKey();
   if (!key) return;
 
   Serial.printf("Key pressed: %c\n", key);
 
   switch (key) {
     case 'A':
       Serial.println("A pressed from keypad");
       Serial.println("Task: home -> p2 (pick) -> p3 (place) -> home");
       break;
     case 'B':
       Serial.println("B pressed from keypad");
       Serial.println("Action: Store mission record");
       break;
     case 'C':
       Serial.println("C pressed from keypad");
       Serial.println("Action: Cancel job");
       break;
     case 'D':
       Serial.println("D pressed from keypad");
       Serial.println("Action: Navigate home only");
       break;
     default:
       Serial.printf("%c pressed from keypad\n", key);
       break;
   }
   Serial.println();
 }
 