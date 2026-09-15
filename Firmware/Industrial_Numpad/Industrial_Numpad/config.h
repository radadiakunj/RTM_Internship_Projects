#pragma once

// -------------------- Wi-Fi (edit for your lab) --------------------
// ESP32 and PC must be on the SAME Wi-Fi network.
#define WIFI_SSID     "RTM_HighSpeed"
#define WIFI_PASSWORD "AtpL@0214#"

// -------------------- RTM Cloud (laptop running rtm_cloud/server.py) --------------------
// Must match the LAN IP printed by: python server.py
#define RTM_CLOUD_HOST "192.168.5.115"
#define RTM_CLOUD_PORT 8080

#define RTM_CLOUD_NAME "Industrial_Numpad_Cloud"
#define RTM_DEVICE_ID  "industrial-numpad"

// -------------------- Pins for ESP32-S3 N16R8 --------------------
// Avoid GPIO 19/20 (USB) and OPI Flash/PSRAM pins.
// LCD I2C
#define PIN_I2C_SDA  8
#define PIN_I2C_SCL  9

// 4x4 keypad rows / cols
#define PIN_KP_R1    10
#define PIN_KP_R2    11
#define PIN_KP_R3    12
#define PIN_KP_R4    13
#define PIN_KP_C1    14
#define PIN_KP_C2    15
#define PIN_KP_C3    16
#define PIN_KP_C4    17
