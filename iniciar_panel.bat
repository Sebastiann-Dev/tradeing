@echo off
title Congressional Trade Tracker
cd /d "C:\Users\u\Desktop\tradeing"

echo ============================================================
echo   Congressional Trade Tracker - Iniciando servidor...
echo ============================================================

REM Arrancar Streamlit en background
start "" /B ".\venv\Scripts\streamlit.exe" run app.py --server.headless=true --server.port=8501 --server.address=localhost

REM Esperar 3 segundos a que inicie
timeout /t 3 /nobreak > NUL

REM Abrir Brave directamente en la URL del panel
start "" "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --new-window "http://localhost:8501"
