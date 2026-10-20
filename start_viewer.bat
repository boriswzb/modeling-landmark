@echo off
setlocal
cd /d "%~dp0"

echo Starting Giza 3D viewer at http://127.0.0.1:8765/viewer/
start "Giza Viewer Server" /min cmd /c "python -m http.server 8765 --bind 127.0.0.1"
timeout /t 2 >nul
start "" "http://127.0.0.1:8765/viewer/"
endlocal
