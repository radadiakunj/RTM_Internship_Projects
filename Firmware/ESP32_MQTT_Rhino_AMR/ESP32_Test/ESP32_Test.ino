/*
In this program, we will test the ESP32 by creating a simple web server that can be accessed from any device connected to the same router. 
The web server will display LED ON and LED OFF buttons. 
Clicking these buttons will control the onboard LED of the ESP32, which is connected to GPIO2.
When you click LED ON, the onboard LED will turn on, and clicking LED OFF will turn it off. 
This provides a simple and interactive way to test the ESP32's functionality.
*/
#include <WiFi.h>
#include <WebServer.h>

// Replace with your network credentials
const char* ssid = "RTM_HighSpeed";
const char* password = "AtpL@0214#";

WebServer server(80); // Web server on port 80

const int ledPin = 2; // Onboard LED pin (GPIO2 for ESP32)
bool ledState = false; // Track LED state

// HTML content for the web page
String HTMLPage() {
  String html = "<!DOCTYPE html><html>";
  html += "<head><title>ESP32 LED Control</title></head>";
  html += "<body style='text-align: center; font-family: Arial;'>";

  html += "<h1>ESP32 LED Control</h1>";
  html += ledState ? "<p>LED is <strong>ON</strong></p>" : "<p>LED is <strong>OFF</strong></p>";
  html += "<a href='/on' style='padding: 10px 20px; background-color: green; color: white; text-decoration: none;'>Turn ON</a>&nbsp;";
  html += "<a href='/off' style='padding: 10px 20px; background-color: red; color: white; text-decoration: none;'>Turn OFF</a>";

  html += "</body></html>";
  return html;
}

// Handle the root path "/"
void handleRoot() {
  server.send(200, "text/html", HTMLPage());
}

// Handle LED ON request
void handleLEDOn() {
  ledState = true;
  digitalWrite(ledPin, HIGH);
  server.send(200, "text/html", HTMLPage());
}

// Handle LED OFF request
void handleLEDOff() {
  ledState = false;
  digitalWrite(ledPin, LOW);
  server.send(200, "text/html", HTMLPage());
}

void setup() {
  Serial.begin(115200);

  // Initialize onboard LED pin as output
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW); // Start with LED off

  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to Wi-Fi");
  Serial.println(WiFi.localIP());

  // Define server routes
  server.on("/", handleRoot);
  server.on("/on", handleLEDOn);
  server.on("/off", handleLEDOff);

  // Start the server
  server.begin();
  Serial.println("Server started");
}

void loop() {
  server.handleClient(); // Handle client requests
}
