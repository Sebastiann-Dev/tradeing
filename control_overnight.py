# -*- coding: utf-8 -*-
"""control_overnight.py — Panel interactivo de control para el Bot Overnight"""
import os
import sys
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

def get_bot_processes():
    try:
        out = subprocess.check_output(
            ['powershell', '-NoProfile', '-Command',
             "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*overnight_trader.py --auto*' } | Select-Object -ExpandProperty ProcessId"],
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
        print("         OVERNIGHT TRADER — PANEL DE CONTROL Y ESTADO")
        print("=" * 68)

        procs = get_bot_processes()
        if procs:
            print(f"  ESTADO: [ ACTIVO Y CORRIENDO EN SEGUNDO PLANO ] (PID: {procs[0]})")
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
        print("  [1] Ver bitácora y estadísticas de rendimiento")
        print("  [2] Ejecutar evaluación manual de entrada AHORA (3:50 PM)")
        print("  [3] Ejecutar liquidación de salida AHORA (9:32 AM)")
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
            subprocess.run([sys.executable, "overnight_trader.py", "--resumen"], check=False)
            input("\nPresione Enter para continuar...")

        elif choice == "2":
            print("\nEjecutando evaluación de entrada...\n")
            subprocess.run([sys.executable, "overnight_trader.py", "--entrar"], check=False)
            input("\nPresione Enter para continuar...")

        elif choice == "3":
            print("\nEjecutando liquidación de salida...\n")
            subprocess.run([sys.executable, "overnight_trader.py", "--salir"], check=False)
            input("\nPresione Enter para continuar...")

        elif choice == "4":
            if procs:
                print("\nEl bot ya está corriendo en segundo plano.")
            else:
                vbs_path = os.path.abspath("iniciar_overnight_silencioso.vbs")
                subprocess.run(["wscript.exe", vbs_path], check=False)
                print("\nBot Overnight iniciado en segundo plano.")
            input("\nPresione Enter para continuar...")

        elif choice == "5":
            if not procs:
                print("\nEl bot ya está detenido.")
            else:
                subprocess.run(
                    ['powershell', '-NoProfile', '-Command',
                     "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*overnight_trader.py --auto*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                    check=False
                )
                print("\nBot detenido con éxito.")
            input("\nPresione Enter para continuar...")

        elif choice == "6":
            break

if __name__ == "__main__":
    main()
