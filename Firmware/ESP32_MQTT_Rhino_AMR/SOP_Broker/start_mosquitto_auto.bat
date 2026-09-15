@echo off
REM Auto-start Mosquitto with SOP config (run at Windows logon, or double-click).
REM ESP32 cannot host the broker — this keeps Mosquitto ready so ESP32 can connect on power-up.

set MOSQUITTO_EXE=E:\mosquitto\mosquitto.exe
set MOSQUITTO_CONF=D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\SOP_Broker\mosquitto.conf

REM If default Windows service already holds port 1883, stop it first (needs Admin once):
REM   net stop mosquitto

cd /d "D:\RTM_Tasks\ESP32_MQTT_Rhino_AMR\SOP_Broker"

tasklist /FI "IMAGENAME eq mosquitto.exe" 2>NUL | find /I "mosquitto.exe" >NUL
if %ERRORLEVEL%==0 (
  echo Mosquitto already running.
  exit /b 0
)

echo Starting Mosquitto...
start "Mosquitto SOP" /MIN "%MOSQUITTO_EXE%" -c "%MOSQUITTO_CONF%" -v
echo Mosquitto started with SOP config.
exit /b 0
