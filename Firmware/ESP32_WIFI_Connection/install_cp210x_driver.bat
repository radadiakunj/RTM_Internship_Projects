@echo off
REM Install Silicon Labs CP210x Universal Windows Driver
REM Right-click this file -> Run as administrator

set "INF=%~dp0CP210x_Universal_Windows_Driver\silabser.inf"

echo ============================================
echo  CP210x driver install
echo ============================================
echo INF: %INF%
echo.

if not exist "%INF%" (
  echo ERROR: silabser.inf not found.
  pause
  exit /b 1
)

pnputil /add-driver "%INF%" /install
echo.
echo pnputil exit code: %ERRORLEVEL%
echo.
echo If the ESP32 is plugged in:
echo   Device Manager -^> Ports ^(COM ^& LPT^) should show
echo   "Silicon Labs CP210x USB to UART Bridge (COMx)"
echo.
echo If NO new USB device appears when you plug the board,
echo the driver is fine but the cable/board is not enumerating.
echo Run: python usb_plug_watcher.py
echo.
pause
