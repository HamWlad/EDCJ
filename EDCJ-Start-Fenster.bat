@echo off
chcp 65001 >nul
title EDCJ - Elite Dangerous Commander's Journey
cd /d "%~dp0"
set PYTHONUTF8=1
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 edcj.py --app %*
  goto ende
)
where python >nul 2>nul
if %errorlevel%==0 (
  python edcj.py --app %*
  goto ende
)
echo.
echo Python 3 wurde nicht gefunden.
echo Bitte Python von https://www.python.org/downloads/ installieren
echo (beim Installieren den Haken "Add python.exe to PATH" setzen) und diese Datei erneut starten.
:ende
echo.
echo EDCJ wurde beendet. Zum Schliessen eine Taste druecken.
pause >nul
