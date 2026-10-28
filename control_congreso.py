# -*- coding: utf-8 -*-
"""control_congreso.py — Panel interactivo de control para el Bot del Congreso"""
import os
import sys
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

def get_bot_processes():
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = " ".join(p.info['cmdline'] or [])
                if 'main.py --auto' in cmd:
                    procs.append(p)
            except Exception:
                pass
        return procs
    except ImportError:
        pass

    # Fallback con tasklist / wmic
    try:
        out = subprocess.check_output(
            ['powershell', '-NoProfile', '-Command',
             "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py --auto*' } | Select-Object -ExpandProperty ProcessId"],
            text=True
        ).strip()
        if out:
            return [int(pid) for pid in out.splitlines() if pid.isdigit()]
    except Exception:
        pass
    return []

def main():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 68)
        print("         BOT DEL CONGRESO — PANEL DE CONTROL Y ESTADO")
        print("=" * 68)

        procs = get_bot_processes()
        if procs:
            pid_str = f"PID: {procs[0]}" if isinstance(procs[0], int) else f"PID: {procs[0].pid}"
            print(f"  ESTADO: [ ACTIVO Y CORRIENDO EN SEGUNDO PLANO ] ({pid_str})")
        else:
            print("  ESTADO: [ DETENIDO ]")

        try:
            et = datetime.now(ZoneInfo("America/New_York"))
            print(f"  Hora de Wall Street (ET): {et.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            pass

        print("-" * 68)
        print("  OPCIONES:")
        print("-" * 68)
        print("  [1] Ver bitácora de operaciones (congreso_trades.csv)")
        print("  [2] Forzar escaneo manual de Capitol Trades AHORA")
        print("  [3] Abrir el Panel Gráfico en Brave (localhost:8501)")
        print("  [4] Iniciar bot en segundo plano (si está detenido)")
        print("  [5] Detener bot en segundo plano")
        print("  [6] Salir")
        print("-" * 68)

        try:
            choice = input("Seleccione una opción [1-6]: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            print("\n" + "=" * 68)
            log_file = "congreso_trades.csv"
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    print(f.read())
            else:
                print("Aún no hay trades registrados en congreso_trades.csv.")
            print("=" * 68)
            input("\nPresione Enter para continuar...")

        elif choice == "2":
            print("\nIniciando escaneo del Congreso en tiempo real...\n")
            try:
                subprocess.run([sys.executable, "main.py"], check=False)
            except Exception as e:
                print(f"Error al ejecutar: {e}")
            input("\nPresione Enter para continuar...")

        elif choice == "3":
            print("\nAbriendo Brave en http://localhost:8501...")
            brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
            if os.path.exists(brave_path):
                subprocess.Popen([brave_path, "http://localhost:8501"])
            else:
                import webbrowser
                webbrowser.open("http://localhost:8501")
            input("\nPresione Enter para continuar...")

        elif choice == "4":
            if procs:
                print("\nEl bot ya está corriendo en segundo plano.")
            else:
                vbs_path = os.path.abspath("iniciar_congreso_silencioso.vbs")
                subprocess.run(["wscript.exe", vbs_path], check=False)
                print("\nBot del Congreso iniciado en segundo plano.")
            input("\nPresione Enter para continuar...")

        elif choice == "5":
            if not procs:
                print("\nEl bot ya está detenido.")
            else:
                subprocess.run(
                    ['powershell', '-NoProfile', '-Command',
                     "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py --auto*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                    check=False
                )
                print("\nBot detenido con éxito.")
            input("\nPresione Enter para continuar...")

        elif choice == "6":
            break

if __name__ == "__main__":
    main()
