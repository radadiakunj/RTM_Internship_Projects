/**
 * Keypads
 *
 * This code demonstrates how to interface with a 1 row, 4 button style membrane keypad
 * 
 * e.g.
 * http://www.ebay.co.uk/itm/1x4-key-switch-Membrane-Matrix-KeyPad-Arduino-PIC-Pi-ARM-UK-seller-UK-Stock/191514648111
 */
// DEFINES
#define DEBUG

// CONSTANTS
// Pins to which each key is connected
const byte keyPins[4] = {12, 13, 10, 11};

// GLOBALS
// Record the last known state of each key (pressed or not)
bool lastKeyState[4] = {false, false, false, false};

void setup() {
  // The serial monitor is required for debugging and calibration
  #if defined(DEBUG)
    Serial.begin(9600);
  #endif

  // Initialise the pins attached to each key
  for(int i=0; i<4; i++){
    pinMode(keyPins[i], INPUT_PULLUP);
  }
}

void loop() {

  for(int i=0; i<4; i++){
    bool isPressed = !digitalRead(keyPins[i]);
    #ifdef DEBUG
      if(lastKeyState[i] == false && isPressed == true) {
        Serial.print(i);
        Serial.println(" was pressed");
      }
      else if(lastKeyState[i] == true && isPressed == false) {
       Serial.print(i);
       Serial.println(" was released");
      }
    #endif
    lastKeyState[i] = isPressed;
  }
  delay(100);
}
