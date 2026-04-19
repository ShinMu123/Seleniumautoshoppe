@echo off
REM Run full validation pipeline: UI + Unit + JMeter(500/1000).
setlocal

cd /d "%~dp0"

echo [INFO] ==========================================
echo [INFO] PART 1+2: UI Appium + Unit tests
echo [INFO] ==========================================
pushd ui-tests
call run_ui_and_unit.bat
if errorlevel 1 (
  popd
  echo [ERROR] UI + Unit pipeline failed.
  exit /b 1
)
popd

echo [INFO] ==========================================
echo [INFO] PART 3: JMeter 500 users
echo [INFO] ==========================================
pushd performance-tests
call run_500_users.bat
if errorlevel 1 (
  popd
  echo [ERROR] JMeter 500 users failed.
  exit /b 1
)

echo [INFO] ==========================================
echo [INFO] PART 3: JMeter 1000 users
echo [INFO] ==========================================
call run_1000_users.bat
if errorlevel 1 (
  popd
  echo [ERROR] JMeter 1000 users failed.
  exit /b 1
)
popd

echo [INFO] ==========================================
echo [INFO] ALL 3 PARTS COMPLETED SUCCESSFULLY
echo [INFO] ==========================================
echo [INFO] Unit runtime: unit-tests\runtime\ui_result.json
echo [INFO] JMeter 500 report: performance-tests\results\menu_500_html\index.html
echo [INFO] JMeter 1000 report: performance-tests\results\menu_1000_html\index.html

endlocal
