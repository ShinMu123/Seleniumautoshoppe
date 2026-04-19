@echo off
REM Run JMeter non-GUI load test for 1000 concurrent users and generate HTML report.
setlocal EnableDelayedExpansion

cd /d "%~dp0"

set "ENV_FILE=..\ui-tests\.env"
if exist "%ENV_FILE%" (
  for /f "usebackq tokens=* delims=" %%L in ("%ENV_FILE%") do (
    set "line=%%L"
    if not "!line!"=="" if not "!line:~0,1!"=="#" (
      for /f "tokens=1* delims==" %%A in ("!line!") do set "%%A=%%B"
    )
  )
)

if "%JMETER_BIN%"=="" set "JMETER_BIN=C:\apache-jmeter-5.6.3\bin\jmeter.bat"
set "JMETER_EXE=%JMETER_BIN%"
set "JMETER_BIN="
if "%API_PROTOCOL%"=="" set "API_PROTOCOL=https"
if "%API_HOST%"=="" set "API_HOST=your-api-host.com"
if "%API_PORT%"=="" set "API_PORT=443"
if "%API_MENU_PATH%"=="" set "API_MENU_PATH=/api/menu"
if "%CONNECT_TIMEOUT%"=="" set "CONNECT_TIMEOUT=10000"
if "%RESPONSE_TIMEOUT%"=="" set "RESPONSE_TIMEOUT=15000"
if "%MAX_RESPONSE_MS%"=="" set "MAX_RESPONSE_MS=2000"
if "%LOAD_DURATION_SEC%"=="" set "LOAD_DURATION_SEC=300"
if not exist "%JMETER_EXE%" (
  echo [ERROR] Cannot find JMeter at: %JMETER_EXE%
  echo [HINT] Set JMETER_BIN to your jmeter.bat path.
  exit /b 1
)

if exist "results\menu_1000_html" rmdir /s /q "results\menu_1000_html"

"%JMETER_EXE%" -n -t menu_api_load_test.jmx -l results\menu_1000.jtl -e -o results\menu_1000_html ^
 -JAPI_PROTOCOL=%API_PROTOCOL% ^
 -JAPI_HOST=%API_HOST% ^
 -JAPI_PORT=%API_PORT% ^
 -JAPI_MENU_PATH=%API_MENU_PATH% ^
 -JUSERS=1000 ^
 -JRAMP_UP=180 ^
 -JDURATION=%LOAD_DURATION_SEC% ^
 -JLOOPS=-1 ^
 -JCONNECT_TIMEOUT=%CONNECT_TIMEOUT% ^
 -JRESPONSE_TIMEOUT=%RESPONSE_TIMEOUT% ^
 -JMAX_RESPONSE_MS=%MAX_RESPONSE_MS% ^
 -JCSV_FILE=users.csv

if errorlevel 1 (
  echo [ERROR] JMeter run failed.
  exit /b 1
)

echo [INFO] Done. Report: results\menu_1000_html\index.html
endlocal
