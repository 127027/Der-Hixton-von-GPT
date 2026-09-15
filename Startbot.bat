@echo off
setlocal
title Der Hixton - Bot aktiv nur mit Konsole und Bot-Seite
cd /d "%~dp0"

set "HIXTON_PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%HIXTON_PYTHON%" (
  echo [Hixton] Erstelle die lokale Python-Umgebung .venv ...
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)

"%HIXTON_PYTHON%" -c "import fastapi, uvicorn, websockets; from importlib.metadata import version; assert fastapi.__version__ == '0.115.5'; assert uvicorn.__version__ == '0.32.0'; assert websockets.__version__ == '12.0'; assert version('tzdata') == '2026.3'" >nul 2>&1
if errorlevel 1 (
  echo [Hixton] Installiere die festgelegten Python-Abhaengigkeiten ...
  "%HIXTON_PYTHON%" -m pip install .
  if errorlevel 1 goto :error
)

if not exist "src\hixton\ui\static\index.html" (
  echo [Hixton] Die gebaute UI fehlt. Fuehre zuerst den dokumentierten UI-Build aus.
  goto :error
)

echo [Hixton] Starte aktuelle Instanz. Eine bisherige Hixton-Instanz wird geordnet abgeloest.
echo [Hixton] Konsole ODER letzte Bot-Seite schliessen = Bot AUS. Kein Hintergrundbetrieb.
echo [Hixton] Offene Binance-Positionen werden beim Beenden NICHT automatisch verkauft.
"%HIXTON_PYTHON%" src\main.py start %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo [Hixton] Start fehlgeschlagen. Die Fehlermeldung steht direkt darueber.
pause
exit /b 1
