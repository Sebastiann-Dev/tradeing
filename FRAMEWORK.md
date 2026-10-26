# Framework: Sistema de Réplica de Trades del Congreso

## 1. El Flujo de Decisión: De la Señal a la Ejecución

```
[📡 Señal: Nuevo PTR publicado]
               │
               ▼
   ¿Pasa Filtros de Calidad?  ────(NO)────► [🗑️ Descartar]
   (Lag < 30d, Monto > $15k, etc.)
               │ (SÍ)
               ▼
     Scoring del Político
   (Comité, Historial, Volumen)
               │
      ┌────────┴────────┐
   Score < 50        Score ≥ 50
      │                 │
      ▼                 ▼
[🗑️ Descartar]   ¿Qué tamaño asignar? (Position Sizing)
                        │
                        ▼
                 Cálculo de Stop Loss (ATR)
                        │
                        ▼
                 Ejecutar Orden (Broker)
                        │
                        ▼
                 Monitoreo Activo (Trailing / Time / Inverse Exit)
```

---

## 2. Filtros de Calidad (Descarte Inmediato)

Antes de analizar al político o la empresa, la operación debe superar estos filtros duros:

1. **Lag Máximo (≤ 30 días):**  
   Si el político operó el 1 de enero y lo reportó el 15 de febrero (45 días después), **se descarta**. El movimiento ya se dio o el mercado ya lo descontó. Señales con lag ≤ 15 días son las que tienen ventaja estadística.
2. **Monto Mínimo (≥ $15,000):**  
   Las compras de $1,000 a $15,000 suelen ser aportes periódicos o ajustes menores. Las operaciones significativas son de $50k a $250k+.
3. **Tipo de Activo:**  
   Solo compras directas de acciones comunes o calls. Se descartan bonos, ETFs indexados (SPY, QQQ) y herencias/fideicomisos ciegos.
4. **Liquidez del Ticker:**  
   Volumen promedio diario > 500k acciones para evitar falta de liquidez o deslizamiento (*slippage*).

---

## 3. Scoring del Político (0 a 100 Puntos)

No todos los congresistas tienen información privilegiada relevante. Evaluamos la señal con esta ponderación:

| Criterio | Puntos | Detalle |
| :--- | :---: | :--- |
| **Comité Relevante** | **+30 pts** | ¿El político está en el comité que regula el sector? *(Ej: Armed Services comprando Lockheed Martin o Raytheon; Subcomité de Tech comprando Nvidia/Google)*. |
| **Historial de Retorno** | **+25 pts** | Rendimiento histórico de sus operaciones pasadas frente al S&P 500. |
| **Convicción (Monto)** | **+20 pts** | $15k–$50k: +5 pts \| $50k–$200k: +12 pts \| >$200k: +20 pts. |
| **Tasa de Éxito Histórica** | **+15 pts** | Porcentaje de operaciones cerradas en verde en los últimos 2 años. |
| **Frescura (Lag)** | **+10 pts** | < 7 días: +10 pts \| 7–14 días: +6 pts \| 15–30 días: +2 pts. |

### Clasificación de Señal:
- **Score ≥ 70:** 🟢 Señal FUERTE (Tamaño Completo).
- **Score 50 – 69:** 🟡 Señal MODERADA (Tamaño Reducido al 50%).
- **Score < 50:** 🔴 Señal DÉBIL (Descartar).

---

## 4. ¿Cuánto % del Portafolio? (Dimensionamiento de Posición)

El error más común es decir: *"Le pongo 10% a cada trade"*. En trading profesional, **el tamaño de la posición lo define el Stop Loss**, no el capital total.

### Regla de Riesgo Fijo por Operación:
- **Señal Fuerte:** Arriesgas el **2%** de tu capital total en caso de que toque el stop.
- **Señal Moderada:** Arriesgas el **1%** de tu capital total.

### Fórmula Matemática de Tamaño:
$$\text{Número de Acciones} = \frac{\text{Capital Total} \times \text{Riesgo \%}}{\text{Precio Entrada} - \text{Precio Stop Loss}}$$

#### Ejemplo Práctico:
- Portafolio total: **$10,000**
- Señal Fuerte en acción **XYZ**: Riesgo máx = 2% = **$200**
- Precio actual de XYZ: **$100**
- Stop Loss fijado en: **$90** (diferencia de $10 por acción)
- **Acciones a comprar:** $\frac{\$200}{\$10} = 20\text{ acciones}$ (Inversión total: $2,000, que representa el 20% del capital, pero arriesgando exactamente $200).

### Límites de Seguridad de la Cartera (Caps):
- **Máximo por activo individual:** 15% del portafolio (si la fórmula pide más de 15%, se recorta al 15%).
- **Máximo por sector:** 35% del portafolio (no tener todo en semiconductores).
- **Máximo de posiciones simultáneas:** 8 a 10 activos.

---

## 5. Gestión del Stop Loss: Los 4 Tipos de Salida

No dependas de un único stop fijo porcentual (ej. -5% fijo). Usamos 4 niveles de protección:

1. **Stop Loss Técnico (Volatilidad ATR):**  
   Basado en el **ATR (Average True Range)** de 14 períodos para evitar que el ruido natural del mercado te saque antes de tiempo:
   $$\text{Stop Loss} = \text{Precio Entrada} - (2 \times \text{ATR})$$
2. **Trailing Stop (Proteger Ganancias):**  
   Cuando la posición supere **+15% de ganancia**, el stop se mueve automáticamente al **Breakeven** (precio de compra, trade libre de riesgo). Si sigue subiendo, dejamos un trailing stop dinámico a $2.5 \times \text{ATR}$ del máximo alcanzado.
3. **Time Stop (Parada por Tiempo):**  
   Si después de **45 a 60 días** la acción no se ha movido y está estancada, se cierra la posición. El catalizador que motivó al político ya expiró o falló.
4. **Signal Stop (Salida Inversa):**  
   Si el político (o varios del mismo comité) reportan una **VENTA** parcial o total del activo, cerramos la posición inmediatamente.

---

## 6. Estrategia de Toma de Ganancias (Take Profit)

Salida escalonada para maximizar el *edge*:
- **TP 1 (+15% de beneficio):** Vender el **33%** de la posición y mover Stop Loss a precio de entrada (*Free Roll*).
- **TP 2 (+30% de beneficio):** Vender otro **33%**.
- **Restante (34%):** Dejar correr con el Trailing Stop hasta que el mercado o una venta del político marquen el techo.

---

## 7. Qué Más Debemos Saber y Prever

1. **El Político puede equivocarse:** No todos los trades de congresistas ganan. De hecho, muchos pierden dinero. Por eso el scoring de políticos y el límite del 2% de riesgo por trade son obligatorios.
2. **Comportamiento en Elecciones y Períodos de Receso:** Durante recesos parlamentarios o vísperas electorales el volumen de reportes cambia radicalmente.
3. **Simulación previa (Paper Trading obligatorio):** Antes de arriesgar dinero real, el sistema debe correr mínimo 60 a 90 días en modo papel (ej. API de Alpaca Paper) para calibrar el ratio de acierto (*Win Rate*) y el factor de beneficio (*Profit Factor*).
