@echo off
REM Build script for Smartest Search File Watcher
echo Building Smartest Search File Watcher...

cd /d "%~dp0"

REM Clean previous builds
if exist bin rmdir /s /q bin
if exist obj rmdir /s /q obj

REM Build single-file executable
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=true

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Build successful!
echo Output: bin\Release\net6.0\win-x64\publish\SmartestSearchWatcher.exe
echo.
pause
