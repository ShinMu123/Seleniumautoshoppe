@echo off
REM Bootstrap and run Appium UI flow: env setup, dependency install, adb/appium checks.
setlocal

REM Di chuyen vao thu muc chua script
cd /d "%~dp0"

set "PYTHON_EXE=..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=..\..\.venv\Scripts\python.exe"

REM Tao virtualenv neu chua co
if not exist "%PYTHON_EXE%" (
    echo [INFO] Chua co virtualenv, dang tao moi...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv ..\.venv
    ) else (
        where python >nul 2>&1
        if not errorlevel 1 (
            python -m venv ..\.venv
        )
    )
    if exist "..\.venv\Scripts\python.exe" set "PYTHON_EXE=..\.venv\Scripts\python.exe"
    if errorlevel 1 (
        echo [ERROR] Tao virtualenv that bai.
        exit /b 1
    )
    if not exist "%PYTHON_EXE%" (
        echo [ERROR] Khong tim thay Python de tao virtualenv. Hay cai Python hoac them vao PATH.
        exit /b 1
    )
)

echo [INFO] Dang cap nhat pip...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Cap nhat pip that bai.
    exit /b 1
)

echo [INFO] Dang cai thu vien tu requirements.txt...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Cai thu vien that bai.
    exit /b 1
)

if "%APPIUM_SERVER_URL%"=="" set "APPIUM_SERVER_URL=http://127.0.0.1:4723"
if "%ANDROID_UDID%"=="" set "ANDROID_UDID=emulator-5554"
if "%SHOPEEFOOD_APP_PACKAGE%"=="" set "SHOPEEFOOD_APP_PACKAGE=com.deliverynow"
if "%STEP_RETRY%"=="" set "STEP_RETRY=1"
if "%DISABLE_ANDROID_ANIMATIONS%"=="" set "DISABLE_ANDROID_ANIMATIONS=1"
if "%AUTO_START_EMULATOR%"=="" set "AUTO_START_EMULATOR=0"
if "%AVD_NAME%"=="" set "AVD_NAME="

set "ADB_EXE=adb"
where adb >nul 2>&1
if errorlevel 1 (
    if not "%ADB_PATH%"=="" if exist "%ADB_PATH%" (
        set "ADB_EXE=%ADB_PATH%"
    ) else if not "%ANDROID_SDK_ROOT%"=="" if exist "%ANDROID_SDK_ROOT%\platform-tools\adb.exe" (
        set "ADB_EXE=%ANDROID_SDK_ROOT%\platform-tools\adb.exe"
    ) else if not "%ANDROID_HOME%"=="" if exist "%ANDROID_HOME%\platform-tools\adb.exe" (
        set "ADB_EXE=%ANDROID_HOME%\platform-tools\adb.exe"
    ) else if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
        set "ADB_EXE=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
    ) else if exist "%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe" (
        set "ADB_EXE=%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    ) else if exist "C:\platform-tools\adb.exe" (
        set "ADB_EXE=C:\platform-tools\adb.exe"
    ) else if exist "C:\Android\platform-tools\adb.exe" (
        set "ADB_EXE=C:\Android\platform-tools\adb.exe"
    ) else (
        echo [ERROR] Khong tim thay adb. Hay cai Android SDK Platform-Tools.
        echo [HINT] Co the set tam bang: set ADB_PATH=C:\Users\^<you^>\AppData\Local\Android\Sdk\platform-tools\adb.exe
        echo [HINT] Hoac set vinh vien PATH bang: setx PATH "%%PATH%%;C:\Users\^<you^>\AppData\Local\Android\Sdk\platform-tools"
        exit /b 1
    )
)

set "ADB_PATH=%ADB_EXE%"

for %%I in ("%ADB_PATH%") do set "ADB_DIR=%%~dpI"
if "%ADB_DIR%"=="" (
    set "ADB_DIR=%LOCALAPPDATA%\Android\Sdk\platform-tools\"
)

for %%I in ("%ADB_DIR%..") do set "SDK_ROOT=%%~fI"
if not "%SDK_ROOT%"=="" (
    if "%ANDROID_HOME%"=="" set "ANDROID_HOME=%SDK_ROOT%"
    if "%ANDROID_SDK_ROOT%"=="" set "ANDROID_SDK_ROOT=%SDK_ROOT%"
)

where appium >nul 2>&1
if errorlevel 1 (
    echo [WARN] Khong tim thay lenh appium trong PATH.
    echo [WARN] Neu Appium server da chay san thi co the bo qua canh bao nay.
)

set "APPIUM_STATUS_URL=%APPIUM_SERVER_URL%/status"
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri '%APPIUM_STATUS_URL%' -TimeoutSec 3 ^| Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    where appium >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Appium server dang tat va khong tim thay lenh appium de tu khoi dong.
        echo [ERROR] Hay mo Appium bang tay roi chay lai run_all.bat
        exit /b 1
    )

    echo [INFO] Appium server chua chay, dang khoi dong nen...
    start "AppiumServer" cmd /c "set ANDROID_HOME=%ANDROID_HOME%&& set ANDROID_SDK_ROOT=%ANDROID_SDK_ROOT%&& appium"

    set "APPIUM_READY=0"
    for /L %%i in (1,1,25) do (
        powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri '%APPIUM_STATUS_URL%' -TimeoutSec 3 ^| Out-Null; exit 0 } catch { exit 1 }"
        if not errorlevel 1 (
            set "APPIUM_READY=1"
            goto :appium_ok
        )
        timeout /t 1 /nobreak >nul
    )

    :appium_ok
    if "%APPIUM_READY%"=="0" (
        echo [ERROR] Da khoi dong Appium nhung server chua san sang sau 25s.
        echo [ERROR] Kiem tra cua so AppiumServer de xem log loi.
        exit /b 1
    )
)

echo [INFO] APPIUM_SERVER_URL=%APPIUM_SERVER_URL%
echo [INFO] ANDROID_UDID=%ANDROID_UDID%
echo [INFO] SHOPEEFOOD_APP_PACKAGE=%SHOPEEFOOD_APP_PACKAGE%
echo [INFO] ADB_PATH=%ADB_PATH%
echo [INFO] ANDROID_HOME=%ANDROID_HOME%
echo [INFO] ANDROID_SDK_ROOT=%ANDROID_SDK_ROOT%
echo [INFO] STEP_RETRY=%STEP_RETRY%

"%ADB_PATH%" -s "%ANDROID_UDID%" get-state 1>nul 2>nul
if errorlevel 1 (
    if /I "%AUTO_START_EMULATOR%"=="1" (
        set "EMU_EXE=%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe"
        if exist "%EMU_EXE%" (
            if "%AVD_NAME%"=="" (
                echo [WARN] Chua set AVD_NAME, bo qua auto start emulator.
            ) else (
                echo [INFO] Chua co device, dang auto start emulator: %AVD_NAME%
                start "AndroidEmulator" /min "%EMU_EXE%" -avd "%AVD_NAME%"
                for /L %%i in (1,1,90) do (
                    "%ADB_PATH%" -s "%ANDROID_UDID%" get-state 1>nul 2>nul
                    if not errorlevel 1 goto :device_ready
                    timeout /t 2 /nobreak >nul
                )
                echo [WARN] Da cho emulator 180s nhung chua thay device %ANDROID_UDID%.
            )
        ) else (
            echo [WARN] Khong tim thay emulator.exe de auto start.
        )
    )
)

:device_ready

echo [INFO] Bat dau chay automation test...
"%PYTHON_EXE%" main.py

if errorlevel 1 (
    echo [ERROR] Chay test bi loi.
    exit /b 1
)

echo [INFO] Hoan tat.
endlocal
