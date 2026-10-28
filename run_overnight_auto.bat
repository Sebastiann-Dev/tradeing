@echo off
cd /d "c:\Users\u\Desktop\tradeing"
title Overnight Trader Auto Daemon
echo Iniciando Overnight Trader en modo automatico 24/7...
".\venv\Scripts\python.exe" overnight_trader.py --auto
pause
