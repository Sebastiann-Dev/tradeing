@echo off
cd /d "C:\Users\u\Desktop\tradeing"
title Control Bot Congreso
".\venv\Scripts\python.exe" control_congreso.py
if errorlevel 1 pause
