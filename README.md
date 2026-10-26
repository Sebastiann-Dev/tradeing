# Bot de Réplica de Trades del Congreso de EE.UU.

Sistema automatizado en Python para monitorear, calificar, dimensionar y replicar operaciones financieras de congresistas de EE.UU. siguiendo las reglas del marco de gestión de riesgo institucional.

## Estructura del Proyecto

- [main.py](file:///c:/Users/u/Desktop/tradeing/main.py): Orquestador principal que ejecuta todo el flujo.
- [data_collector.py](file:///c:/Users/u/Desktop/tradeing/data_collector.py): Extractor de datos en tiempo real de transacciones políticas (sin necesidad de API keys de pago).
- [filtro_calidad.py](file:///c:/Users/u/Desktop/tradeing/filtro_calidad.py): Descarta operaciones con lag > 30 días, montos menores a $15k o fondos generales.
- [scoring_politico.py](file:///c:/Users/u/Desktop/tradeing/scoring_politico.py): Sistema de scoring (0 a 100) que premia comités relevantes (ej. Armed Services -> Defensa), convicción del monto y frescura del reporte.
- [position_sizer.py](file:///c:/Users/u/Desktop/tradeing/position_sizer.py): Calcula el número exacto de acciones a comprar arriesgando solo el 1% de la cartera y fijando Stop Loss amplio (2.5x a 3.0x ATR) adaptado al ruido del mercado.
- [alpaca_executor.py](file:///c:/Users/u/Desktop/tradeing/alpaca_executor.py): Ejecutor de órdenes Bracket (Compra + Stop Loss + Take Profit) para Alpaca Paper Trading y simulación local.
- [config.py](file:///c:/Users/u/Desktop/tradeing/config.py): Variables de configuración y límites del portafolio.
- [FRAMEWORK.md](file:///c:/Users/u/Desktop/tradeing/FRAMEWORK.md): Documento con las reglas matemáticas y de riesgo completas.

## Cómo Ejecutar el Sistema

En la terminal (con el entorno virtual activado):

```powershell
.\venv\Scripts\python.exe main.py
```

## Para Conectar con Alpaca Paper Trading

1. Crea tu cuenta gratuita en [Alpaca Markets](https://alpaca.markets) (modo Paper).
2. Copia `.env.example` a un archivo llamado `.env`.
3. Pega tus llaves:
   ```env
   ALPACA_API_KEY=tu_api_key_de_alpaca
   ALPACA_SECRET_KEY=tu_secret_key_de_alpaca
   ALPACA_PAPER=True
   ```
4. Al correr `main.py`, las órdenes se enviarán automáticamente a tu cuenta de simulación de Alpaca.
