@echo off
chcp 65001 > nul
cd /d "c:\Users\u\Desktop\tradeing"
cls
echo =====================================================================
echo           OVERNIGHT TRADER — PANEL DE CONTROL Y ESTADO
echo =====================================================================
echo.

powershell -NoProfile -Command "
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*overnight_trader.py --auto*' }
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
echo   [1] Ver bitácora y estadísticas de rendimiento
echo   [2] Ejecutar evaluación manual de entrada AHORA
echo   [3] Ejecutar liquidación de salida AHORA
echo   [4] Iniciar el bot en segundo plano (si está detenido)
echo   [5] Detener el bot en segundo plano
echo   [6] Salir
echo ---------------------------------------------------------------------
set /p opt="Seleccione una opción [1-6]: "

if "%opt%"=="1" (
    cls
    .\venv\Scripts\python.exe overnight_trader.py --resumen
    pause
    goto :eof
)
if "%opt%"=="2" (
    cls
    .\venv\Scripts\python.exe overnight_trader.py --entrar
    pause
    goto :eof
)
if "%opt%"=="3" (
    cls
    .\venv\Scripts\python.exe overnight_trader.py --salir
    pause
    goto :eof
)
if "%opt%"=="4" (
    wscript.exe "c:\Users\u\Desktop\tradeing\iniciar_overnight_silencioso.vbs"
    echo Bot iniciado en segundo plano.
    pause
    goto :eof
)
if "%opt%"=="5" (
    powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*overnight_trader.py --auto*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Write-Host 'Bot detenido con éxito.' -ForegroundColor Yellow"
    pause
    goto :eof
)
