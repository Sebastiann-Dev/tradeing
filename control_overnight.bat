@echo off
cd /d "C:\Users\u\Desktop\tradeing"
title Control Bot Overnight
".\venv\Scripts\python.exe" control_overnight.py
if errorlevel 1 pause
