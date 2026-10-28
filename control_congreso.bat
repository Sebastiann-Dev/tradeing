@echo off
chcp 65001 > nul
cd /d "c:\Users\u\Desktop\tradeing"
cls
echo =====================================================================
echo          BOT DEL CONGRESO — PANEL DE CONTROL Y ESTADO
echo =====================================================================
echo.

powershell -NoProfile -Command "
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py --auto*' }
if ($procs) {
    Write-Host '  ESTADO DEL BOT: [ ACTIVO Y CORRIENDO EN SEGUNDO PLANO ]' -ForegroundColor Green
    Write-Host ('  PID: ' + $procs.ProcessId) -ForegroundColor Gray
} else {
    Write-Host '  ESTADO DEL BOT: [ DETENIDO ]' -ForegroundColor Red
}

$et = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([System.DateTime]::UtcNow, 'Eastern Standard Time')
Write-Host ('  Hora de Wall Street (ET): ' + $et.ToString('yyyy-MM-dd HH:mm:ss')) -ForegroundColor Cyan
"

echo.
echo ---------------------------------------------------------------------
echo   OPCIONES:
echo ---------------------------------------------------------------------
echo   [1] Ver bitácora de trades ejecutados (congreso_trades.csv)
echo   [2] Forzar escaneo completo AHORA (15 páginas)
echo   [3] Abrir el Panel Gráfico en Brave
echo   [4] Iniciar el bot en segundo plano (si está detenido)
echo   [5] Detener el bot en segundo plano
echo   [6] Salir
echo ---------------------------------------------------------------------
set /p opt="Seleccione una opción [1-6]: "

if "%opt%"=="1" (
    cls
    if exist congreso_trades.csv (
        type congreso_trades.csv
    ) else (
        echo Aún no hay trades registrados en congreso_trades.csv
    )
    echo.
    pause
    goto :eof
)
if "%opt%"=="2" (
    cls
    .\venv\Scripts\python.exe main.py
    pause
    goto :eof
)
if "%opt%"=="3" (
    start "" "http://localhost:8501"
    goto :eof
)
if "%opt%"=="4" (
    wscript.exe "c:\Users\u\Desktop\tradeing\iniciar_congreso_silencioso.vbs"
    echo Bot iniciado en segundo plano.
    pause
    goto :eof
)
if "%opt%"=="5" (
    powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py --auto*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Write-Host 'Bot del Congreso detenido con éxito.' -ForegroundColor Yellow"
    pause
    goto :eof
)
