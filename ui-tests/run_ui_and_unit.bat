@echo off
REM Pipeline runner: execute UI flow first, then run .NET unit tests.
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=..\..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] Python virtualenv not found.
  echo [ERROR] Checked: ..\.venv\Scripts\python.exe, ..\..\.venv\Scripts\python.exe, .venv\Scripts\python.exe
  exit /b 1
)

if "%AUTO_QUIT%"=="" set "AUTO_QUIT=1"

echo [INFO] Step 1/3: Run UI flow (Appium)
call run_all.bat
if errorlevel 1 (
  echo [ERROR] UI flow failed.
  exit /b 1
)

echo [INFO] Step 2/3: Verify UI exported runtime JSON
if not exist "..\unit-tests\runtime\ui_result.json" (
  echo [ERROR] Runtime JSON not found: ..\unit-tests\runtime\ui_result.json
  echo [HINT] UI flow could not extract order values. Set UI_RESULT_FOOD_PRICE and run again.
  exit /b 1
)

echo [INFO] Step 3/3: Run unit-tests
where dotnet >nul 2>&1
if errorlevel 1 (
  echo [ERROR] dotnet not found in PATH.
  exit /b 1
)

pushd ..\unit-tests
 dotnet test -c Release --nologo --verbosity minimal
 if errorlevel 1 (
   popd
   echo [ERROR] unit-tests failed.
   exit /b 1
 )
popd

echo [INFO] Pipeline completed successfully.
endlocal
