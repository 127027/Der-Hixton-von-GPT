@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  Hixton Agent Chat - lokaler persistenter Engineering-Agent
echo ============================================================
echo.

where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo FEHLER: PowerShell wurde nicht gefunden.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\agent_chat.ps1"
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
  echo Agent-Chat beendet.
) else (
  echo Agent-Chat mit Fehlercode %EXITCODE% beendet.
)
echo.
pause
exit /b %EXITCODE%
