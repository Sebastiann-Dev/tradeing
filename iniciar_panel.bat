@echo off
cd /d "C:\Users\u\Desktop\tradeing"
title Congressional Trade Tracker

echo ============================================================
echo   Congressional Trade Tracker - Abriendo Panel...
echo ============================================================

powershell -NoProfile -Command "if (-not (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)) { Start-Process '.\venv\Scripts\streamlit.exe' -ArgumentList 'run app.py --server.headless=true --server.port=8501' -WindowStyle Hidden; Start-Sleep -Seconds 2 }"

start "" "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" "http://localhost:8501"
