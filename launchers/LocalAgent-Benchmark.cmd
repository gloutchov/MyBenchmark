@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 guided_benchmark.py
) else (
  python guided_benchmark.py
)
if %ERRORLEVEL% NEQ 0 pause
endlocal
