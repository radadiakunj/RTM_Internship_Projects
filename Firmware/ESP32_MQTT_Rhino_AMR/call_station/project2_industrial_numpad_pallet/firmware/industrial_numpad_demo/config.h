#pragma once
/*
 * Project 2 — Industrial numpad demo config
 * Copy from config.h.example if you need a clean template.
 */

// Wi‑Fi
static const char* WIFI_SSID     = "moto edge 60 pro_4008";
static const char* WIFI_PASSWORD = "bfh4bqveq2ydqtz";

// Mosquitto (same LAN as Project 2 cloud listener)
static const char* MQTT_HOST = "10.35.39.20";
static const int   MQTT_PORT = 1883;
static const char* MQTT_USER = "";
static const char* MQTT_PASS = "";

static const char* STATION_ID   = "esp-numpad-1";
static const char* PALLET_TOPIC = "callstation/pallet/record";

// LCD I2C
static const int LCD_SDA_PIN = 1;
static const int LCD_SCL_PIN = 2;
static const uint8_t LCD_I2C_ADDR = 0x27;
static const uint8_t LCD_COLS = 16;
static const uint8_t LCD_ROWS = 2;

// 4×4 keypad (same as keypad_test)
static const byte KEYPAD_ROWS = 4;
static const byte KEYPAD_COLS = 4;
// Row pins: 12,11,10,8 | Col pins: 5,4,7,6  — set in .ino

static const int PALLET_ID_MAX = 12;
static const unsigned long WIFI_TIMEOUT_MS = 20000;
