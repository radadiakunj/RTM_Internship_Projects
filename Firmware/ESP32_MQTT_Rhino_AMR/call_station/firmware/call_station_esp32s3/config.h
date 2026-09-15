#pragma once
// Same Wi-Fi as the AMR + laptop (example from your lab)
#define WIFI_SSID     "RTM_Speed"
#define WIFI_PASSWORD "1234"

// MQTT broker = YOUR LAPTOP IP running Mosquitto (not the AMR IP)
#define MQTT_HOST     "192.168.5.117"
#define MQTT_PORT     1883
// Stage-1 SOP broker is anonymous — leave blank.
// If you enabled Mosquitto user/pass, set them here (e.g. Robo / 1234).
#define MQTT_USER     ""
#define MQTT_PASS     ""

#define STATION_ID    "home1"
// Must match exact point names on the AMR map (from --request-points)
#define POINT_HOME    "Home"
#define POINT_PICK    "A"
#define POINT_DROP    "D"
