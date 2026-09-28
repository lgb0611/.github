@echo off
setlocal
cd /d "%~dp0"
echo Astra Speaking Lab v2
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3.10+ is required. Install Python and enable Add to PATH.
    pause
    exit /b 1
  )
  python bootstrap.py
) else (
  py -3 bootstrap.py
)
pause
