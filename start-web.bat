@echo off
REM Ebook Optimizer - lokale Oberflaeche starten
cd /d "%~dp0"
python -m ebook_optimizer.web %*
if errorlevel 1 (
  echo.
  echo Start fehlgeschlagen. Pruefe:
  echo   1^) Python 3.8+ installiert und im PATH
  echo   2^) Pillow installiert:  pip install pillow
  pause
)
