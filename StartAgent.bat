@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  Hixton Local Engineering Agent - ChatGPT/Codex
 echo ============================================================
echo.
echo Dieser Agent verwendet deinen normalen ChatGPT/Codex-Login.
echo Es wird KEIN OpenAI-API-Key benoetigt oder abgefragt.
echo Hinweis: Der Agent unterliegt damit demselben Codex-Nutzungslimit.
echo.

where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo FEHLER: PowerShell wurde nicht gefunden.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local_agent.ps1"
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
  echo Agent-Lauf beendet.
) else (
  echo Agent-Lauf mit Fehlercode %EXITCODE% beendet.
)
echo.
pause
exit /b %EXITCODE%
