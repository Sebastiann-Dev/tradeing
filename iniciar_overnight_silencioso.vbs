' iniciar_overnight_silencioso.vbs
' Ejecuta el Overnight Trader en segundo plano sin ventana de consola visible
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\u\Desktop\tradeing"
WshShell.Run "c:\Users\u\Desktop\tradeing\venv\Scripts\python.exe c:\Users\u\Desktop\tradeing\overnight_trader.py --auto", 0, False
Set WshShell = Nothing
