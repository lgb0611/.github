@echo off
setlocal
cd /d "%~dp0"
echo Astra Speaking Lab - FREE MODE
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Open OPEN_ME.html directly, or install Python 3.10+ for this launcher.
    pause
    exit /b 1
  )
  python free_server.py
) else (
  py -3 free_server.py
)
pause
