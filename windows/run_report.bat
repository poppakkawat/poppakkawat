@echo off
REM ============================================================
REM  polytrack - daily Prediction Markets report
REM  Writes YYYY-MM-DD.md into your OneDrive folder.
REM ============================================================

REM --- Where to save the report (your OneDrive folder) ---
set "OUTDIR=%USERPROFILE%\OneDrive\Prediction Market update"

REM --- Run from the repo root (folder above this script) ---
cd /d "%~dp0\.."

REM --- Pick python launcher (py -3 preferred, else python) ---
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

echo Generating report into "%OUTDIR%" ...
%PY% -m polytrack ^
  --source both ^
  --hours 24 ^
  --min 10000 ^
  --kalshi-min 5000 ^
  --watchlist watchlist.json ^
  --out-dir "%OUTDIR%"

if errorlevel 1 (
  echo.
  echo  ERROR: report generation failed. Is Python 3 installed and on PATH?
  exit /b 1
)

echo Done.
exit /b 0
