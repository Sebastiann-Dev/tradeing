# -*- coding: utf-8 -*-
"""
app.py — Congressional Trade Tracker
Panel cuantitativo de seguimiento de operaciones de congresistas de EE.UU.
1. Interfaz limpia tipo screener institucional (sin emojis, sin iconos desalineados).
2. Selección directa y confiable de cualquier acción para ver su análisis de inmediato.
3. Tabla de métricas limpia sin columnas de interrogación descuadradas.
4. Gráfica de velas limpia con niveles técnicos y marca de compra del congresista (sin herramientas de medición innecesarias).
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import sys, os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_collector import DataCollector
from filtro_calidad import FiltroCalidad
from scoring_politico import ScoringPolitico, detectar_clusters
from position_sizer import PositionSizer
from alpaca_executor import AlpacaExecutor
from config import Config

st.set_page_config(
    page_title="Congressional Trade Tracker",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS profesionales terminal oscuro
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0a0e17; color: #c9d1d9; }
.block-container { padding-top: 1rem; padding-bottom: 2rem; }

[data-testid="stSidebar"] {
    background: #0d1117;
    border-right: 1px solid #21262d;
}
[data-testid="stSidebar"] * { color: #c9d1d9 !important; }

/* KPIs */
.kpi {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 10px 14px;
}
.kpi-lbl { font-size: 0.68rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.08em; }
.kpi-val { font-size: 1.35rem; font-weight: 700; color: #f0f6fc; line-height: 1.2; margin-top: 2px; }
.kpi-sub { font-size: 0.7rem; color: #8b949e; margin-top: 2px; }

/* Tabla de métricas de posición sin botones descuadrados */
.metric-table {
    width: 100%;
    border-collapse: collapse;
    background: #161b22;
    border-radius: 6px;
    border: 1px solid #30363d;
    overflow: hidden;
    margin-top: 4px;
}
.metric-table tr {
    border-bottom: 1px solid #21262d;
}
.metric-table tr:last-child {
    border-bottom: none;
}
.metric-table td {
    padding: 8px 12px;
    font-size: 0.8rem;
    vertical-align: middle;
}
.metric-table td.lbl {
    color: #8b949e;
    width: 55%;
}
.metric-table td.val {
    color: #f0f6fc;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    text-align: right;
    width: 45%;
}

.stNumberInput input, .stSelectbox select {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    color: #f0f6fc !important;
    border-radius: 6px !important;
}

.stButton button {
    background: #238636;
    color: #ffffff;
    border: 1px solid rgba(240,246,252,0.1);
    border-radius: 6px;
    font-weight: 600;
    padding: 8px 16px;
}
.stButton button:hover { background: #2ea043; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_and_classify_trades(pages):
    collector = DataCollector()
    raw = collector.fetch_all_recent_trades(max_pages=pages)
    filtro = FiltroCalidad()
    scorer = ScoringPolitico()
    results = []
    for t in raw:
        sig_type, motivo, te = filtro.clasificar(t)
        sc, cl, desgl = scorer.calcular_score(te)
        te.update({
            "score": sc,
            "clasificacion": cl,
            "desglose": desgl,
            "motivo": motivo,
            "signal_type": sig_type
        })
        results.append(te)

    clusters = detectar_clusters([x for x in results if x.get("signal_type") in ("EQUITY_STRONG", "EQUITY_SMALL")])
    return raw, results, clusters


# Sidebar
st.sidebar.markdown("### Configuración del Sistema")
pages = st.sidebar.slider("Páginas a consultar", min_value=5, max_value=30, value=15, step=1)
capital = st.sidebar.number_input("Capital de Portafolio ($)", min_value=1000.0, max_value=10000000.0, value=10000.0, step=1000.0)

st.sidebar.markdown("---")
st.sidebar.markdown("### Filtro de Señales")
min_score = st.sidebar.slider("Score Mínimo", min_value=0, max_value=80, value=20, step=5)

st.sidebar.markdown("---")
st.sidebar.markdown("### Alpaca Paper Trading")
alpaca_key = st.sidebar.text_input("API Key", value=Config.ALPACA_API_KEY, type="password")
alpaca_secret = st.sidebar.text_input("Secret Key", value=Config.ALPACA_SECRET_KEY, type="password")
if alpaca_key and alpaca_secret:
    st.sidebar.markdown('''
<div style="background:#161b22; border:1px solid #238636; border-radius:6px; padding:6px 10px; margin-top:8px;">
    <div style="font-size:0.75rem; color:#3fb950; font-weight:600;">Estado: Conectado (Paper Trading)</div>
</div>
''', unsafe_allow_html=True)

col_btn, _ = st.columns([1, 5])
with col_btn:
    if st.button("Actualizar Datos", use_container_width=True):
        st.cache_data.clear()

with st.spinner("Consultando operaciones del Congreso de EE.UU..."):
    raw_trades, all_results, clusters = load_and_classify_trades(pages)

# Jerarquía de ordenamiento institucional:
# 1. Compras directas operables de acciones (EQUITY_STRONG) por Score y menor Lag
# 2. Compras directas informativas (EQUITY_SMALL)
# 3. Macro deuda / bonos (MACRO_BOND)
# 4. Ventas (SELL)
# 5. Caducadas (STALE)
PRIORITY_MAP = {
    "EQUITY_STRONG": 0,
    "EQUITY_SMALL": 1,
    "MACRO_BOND": 2,
    "SELL": 3,
    "STALE": 4,
    "INDEX_ETF": 5,
    "INVALID": 6
}

all_results.sort(
    key=lambda x: (
        PRIORITY_MAP.get(x.get("signal_type"), 9),
        -x.get("score", 0),
        x.get("lag_days") if x.get("lag_days") is not None else 999
    )
)

strong_trades = [t for t in all_results if t.get("signal_type") == "EQUITY_STRONG"]
small_trades  = [t for t in all_results if t.get("signal_type") == "EQUITY_SMALL"]
macro_trades  = [t for t in all_results if t.get("signal_type") == "MACRO_BOND"]
sell_trades   = [t for t in all_results if t.get("signal_type") == "SELL"]

# Encabezado principal
st.markdown("""
<div style="padding: 4px 0 14px 0; border-bottom: 1px solid #21262d; margin-bottom: 14px;">
    <div style="font-size: 1.35rem; font-weight: 700; color: #f0f6fc;">CONGRESSIONAL TRADE TRACKER</div>
    <div style="font-size: 0.74rem; color: #8b949e;">Terminal institucional de réplica y análisis cuantitativo de operaciones políticas</div>
</div>
""", unsafe_allow_html=True)

# KPIs
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(f"""<div class="kpi"><div class="kpi-lbl">Operaciones Leídas</div><div class="kpi-val">{len(raw_trades)}</div><div class="kpi-sub">Total {pages} páginas</div></div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class="kpi"><div class="kpi-lbl">Acciones Operables</div><div class="kpi-val" style="color:#3fb950;">{len(strong_trades)}</div><div class="kpi-sub">Monto &gt;=$15K, Lag &lt;=30d</div></div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""<div class="kpi"><div class="kpi-lbl">Acciones Informativas</div><div class="kpi-val" style="color:#58a6ff;">{len(small_trades)}</div><div class="kpi-sub">Monto &lt;$15K</div></div>""", unsafe_allow_html=True)
with k4:
    st.markdown(f"""<div class="kpi"><div class="kpi-lbl">Macro Deuda / Bonos</div><div class="kpi-val" style="color:#bc8cff;">{len(macro_trades)}</div><div class="kpi-sub">Tesoro / Renta Fija</div></div>""", unsafe_allow_html=True)
with k5:
    st.markdown(f"""<div class="kpi"><div class="kpi-lbl">Ventas Registradas</div><div class="kpi-val" style="color:#f85149;">{len(sell_trades)}</div><div class="kpi-sub">Clusters: {len(clusters)}</div></div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Pestañas limpias
tab_screener, tab_charts, tab_framework = st.tabs([
    "Screener y Análisis de Posición",
    "Distribución y Segmentos",
    "Framework & Reglas"
])

# ==============================================================================
# TAB 1: SCREENER INSTITUCIONAL Y ANÁLISIS DE POSICIÓN (TODO INTEGRADO SIN REDIRECCIONES)
# ==============================================================================
with tab_screener:
    st.markdown("#### Registro de Operaciones y Selección de Activo")

    # Filtros de tabla (clic directo sin cajas de texto editables)
    tipo_opciones = [
        "Acciones Operables",
        "Acciones Informativas",
        "Macro Deuda/Bonos",
        "Ventas",
        "Caducadas"
    ]
    tipo_map = {
        "Acciones Operables": "EQUITY_STRONG",
        "Acciones Informativas": "EQUITY_SMALL",
        "Macro Deuda/Bonos": "MACRO_BOND",
        "Ventas": "SELL",
        "Caducadas": "STALE"
    }
    filtro_tipos = st.pills(
        "Filtrar screener por tipo (clic para activar/desactivar):",
        options=tipo_opciones,
        default=["Acciones Operables", "Acciones Informativas"],
        selection_mode="multi",
        key="pills_filtro_tipos"
    )
    seleccionados = filtro_tipos if filtro_tipos else ["Acciones Operables", "Acciones Informativas"]
    tipos_activos = [tipo_map[x] for x in seleccionados]

    senales_tabla = [
        t for t in all_results
        if t.get("signal_type") in tipos_activos and t.get("score", 0) >= min_score
    ]

    # Tabla screener completa
    df_rows = []
    for t in senales_tabla:
        df_rows.append({
            "Ticker": t.get("ticker", ""),
            "Clasificación": t.get("clasificacion", ""),
            "Score": t.get("score"),
            "Político": t.get("politician", "")[:18],
            "Cámara": t.get("chamber", ""),
            "Lag": f"{t.get('lag_days','?')}d",
            "Monto": t.get("amount_range", ""),
            "Empresa": (t.get("issuer_name", "") or t.get("asset_description", ""))[:40],
            "Tipo": t.get("signal_type", "")
        })

    st.dataframe(pd.DataFrame(df_rows), use_container_width=True, hide_index=True, height=260)

    st.markdown("---")
    st.markdown("#### Análisis y Dimensionamiento de la Acción Seleccionada")

    # Lista exclusiva de acciones operables / informativas con ticker válido
    acciones_disponibles = [
        t for t in all_results
        if t.get("ticker")
        and t.get("ticker") not in ("--", "N/A", "UNKNOWN")
        and len(t.get("ticker")) <= 5
        and t.get("ticker").isalpha()
        and t.get("signal_type") in ("EQUITY_STRONG", "EQUITY_SMALL")
    ]

    # Ordenar estrictamente por calidad de mayor a menor
    acciones_disponibles.sort(
        key=lambda x: (
            0 if x.get("signal_type") == "EQUITY_STRONG" else 1,
            -x.get("score", 0),
            x.get("lag_days") if x.get("lag_days") is not None else 999
        )
    )

    if not acciones_disponibles:
        st.info("No se encontraron acciones comunes con ticker válido en las páginas analizadas.")
    else:
        # Eliminar tickers duplicados manteniendo el de mayor puntuacion
        acciones_unicas = []
        tickers_vistos = set()
        for t in acciones_disponibles:
            tk = t["ticker"]
            if tk not in tickers_vistos:
                tickers_vistos.add(tk)
                acciones_unicas.append(t)

        ticker_keys = [t["ticker"] for t in acciones_unicas]
        etiquetas_ticker = {
            t["ticker"]: f"{t['ticker']} ({t['clasificacion']} {t['score']}p) - {t['politician'][:16]}"
            for t in acciones_unicas
        }

        st.markdown("**Seleccione la acción a dimensionar (clic directo en la opción deseada):**")
        ticker_elegido = st.pills(
            "Acción a analizar:",
            options=ticker_keys,
            default=ticker_keys[0] if ticker_keys else None,
            format_func=lambda tk: etiquetas_ticker.get(tk, tk),
            label_visibility="collapsed",
            key="pills_accion_seleccionada"
        )
        if not ticker_elegido and ticker_keys:
            ticker_elegido = ticker_keys[0]

        senal_elegida = next(t for t in acciones_unicas if t["ticker"] == ticker_elegido)
        is_cluster_ticker = ticker_elegido in clusters

        if is_cluster_ticker:
            st.success(f"Cluster Detectado: Múltiples congresistas han comprado {ticker_elegido}: {', '.join(clusters[ticker_elegido])}")

        with st.spinner(f"Descargando cotizaciones y calculando parámetros para {ticker_elegido}..."):
            sizer = PositionSizer(portfolio_equity=capital)
            plan = sizer.calcular_posicion(ticker_elegido, senal_elegida["score"], is_cluster=is_cluster_ticker)

        if not plan:
            st.error(f"No fue posible obtener cotización y métricas para {ticker_elegido}.")
        else:
            hist_df = plan.get("hist")

            # Ficha de la empresa
            f1, f2, f3, f4 = st.columns([3, 1, 1, 1])
            with f1:
                mc = plan.get("market_cap")
                mc_str = f"${mc/1e9:.1f}B" if mc and mc >= 1e9 else (f"${mc/1e6:.0f}M" if mc else "N/A")
                st.markdown(f"""
<div style="background:#161b22; border:1px solid #30363d; border-radius:6px; padding:10px 14px;">
    <div style="font-size:1.05rem; font-weight:700; color:#58a6ff;">{plan.get('company', ticker_elegido)} ({ticker_elegido})</div>
    <div style="font-size:0.75rem; color:#8b949e; margin-top:2px;">Sector: {plan.get('sector','N/A')} | Industria: {plan.get('industry','N/A')} | Cap: {mc_str}</div>
    <div style="font-size:0.72rem; color:#c9d1d9; margin-top:6px; line-height:1.4;">{plan.get('description','')[:240]}...</div>
</div>
""", unsafe_allow_html=True)
            with f2:
                pe = plan.get("pe_ratio")
                st.markdown(f"""<div class="kpi"><div class="kpi-lbl">P/E Ratio</div><div class="kpi-val" style="font-size:1.1rem;">{f'{pe:.1f}x' if pe else 'N/A'}</div></div>""", unsafe_allow_html=True)
            with f3:
                dy = plan.get("dividend_yield")
                st.markdown(f"""<div class="kpi"><div class="kpi-lbl">Dividendo</div><div class="kpi-val" style="font-size:1.1rem;">{f'{dy*100:.2f}%' if dy else '0.00%'}</div></div>""", unsafe_allow_html=True)
            with f4:
                eps = plan.get("eps")
                st.markdown(f"""<div class="kpi"><div class="kpi-lbl">EPS (TTM)</div><div class="kpi-val" style="font-size:1.1rem;">{f'${eps:.2f}' if eps else 'N/A'}</div></div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            col_chart_pos, col_plan_pos = st.columns([3, 2])

            with col_chart_pos:
                if hist_df is not None and not hist_df.empty:
                    fig_stock = go.Figure()

                    # Velas
                    fig_stock.add_trace(go.Candlestick(
                        x=hist_df.index,
                        open=hist_df["Open"], high=hist_df["High"],
                        low=hist_df["Low"], close=hist_df["Close"],
                        increasing_line_color="#3fb950", decreasing_line_color="#f85149",
                        name=ticker_elegido
                    ))

                    # Precio actual
                    p_act = plan["entry_price"]
                    fig_stock.add_hline(
                        y=p_act, line_color="#58a6ff", line_width=1.5,
                        annotation_text=f"Precio Actual ${p_act:,.2f}",
                        annotation_font_color="#58a6ff"
                    )

                    # Stop Loss
                    fig_stock.add_hline(
                        y=plan["stop_loss_price"], line_dash="dash", line_color="#f85149",
                        annotation_text=f"Stop Loss ${plan['stop_loss_price']:,.2f} (-{plan['stop_loss_pct']}%)",
                        annotation_font_color="#f85149"
                    )

                    # TP1 y TP2
                    fig_stock.add_hline(
                        y=plan["tp1_price"], line_dash="dot", line_color="#3fb950",
                        annotation_text=f"TP1 ${plan['tp1_price']:,.2f} (+15%)",
                        annotation_font_color="#3fb950"
                    )
                    fig_stock.add_hline(
                        y=plan["tp2_price"], line_dash="dot", line_color="#d29922",
                        annotation_text=f"TP2 ${plan['tp2_price']:,.2f} (+30%)",
                        annotation_font_color="#d29922"
                    )

                    # Marca de compra del congresista
                    trade_date_str = senal_elegida.get("transaction_date", "")
                    try:
                        import dateutil.parser as dparser
                        clean_d = re.sub(r"\s+", " ", trade_date_str.strip())
                        b_date = dparser.parse(clean_d, dayfirst=True)
                        closest_d = min(hist_df.index, key=lambda d: abs((d.replace(tzinfo=None) - b_date).total_seconds()), default=None)
                        if closest_d is not None:
                            p_at_buy = float(hist_df.loc[closest_d, "Close"])
                            fig_stock.add_vline(
                                x=closest_d, line_color="#bc8cff", line_dash="dash",
                                annotation_text=f"Compra Congresista ${p_at_buy:,.2f}",
                                annotation_font_color="#bc8cff"
                            )
                            fig_stock.add_trace(go.Scatter(
                                x=[closest_d], y=[p_at_buy],
                                mode="markers",
                                marker=dict(symbol="star", size=14, color="#bc8cff"),
                                name="Punto Compra Político"
                            ))
                    except Exception:
                        pass

                    fig_stock.update_layout(
                        title=f"{ticker_elegido} - Cotización y Niveles Técnicos",
                        plot_bgcolor="#161b22", paper_bgcolor="#161b22",
                        font_color="#c9d1d9", height=420,
                        xaxis=dict(gridcolor="#30363d", rangeslider_visible=False),
                        yaxis=dict(gridcolor="#30363d"),
                        margin=dict(t=40, b=20, l=40, r=20),
                        legend=dict(bgcolor="#161b22", bordercolor="#30363d")
                    )
                    st.plotly_chart(fig_stock, use_container_width=True, key=f"chart_{ticker_elegido}")

            with col_plan_pos:
                r_used = plan["risk_pct_used"]
                r_color = "#3fb950" if r_used >= 1.5 else ("#d29922" if r_used >= 1.0 else "#8b949e")

                st.markdown(f"""
<div style="background:#161b22; border:1px solid #30363d; border-radius:6px; padding:10px; margin-bottom:8px; text-align:center;">
    <div style="font-size:0.68rem; color:#8b949e; text-transform:uppercase;">Riesgo Asignado por Algoritmo (Score + Beta)</div>
    <div style="font-size:1.5rem; font-weight:700; color:{r_color}; font-family:'JetBrains Mono';">{r_used}%</div>
    <div style="font-size:0.7rem; color:#8b949e;">Máximo a perder: ${plan['risk_dollar']:,.2f} en Stop Loss</div>
</div>
""", unsafe_allow_html=True)

                st.markdown(f"""
<div style="background:#161b22; border:1px solid #1f6feb; border-radius:6px; padding:8px; margin-bottom:10px; text-align:center;">
    <div style="font-size:0.68rem; color:#8b949e; text-transform:uppercase;">Mínimo de Compra (1 acción) = ${plan['min_investment']:,.2f}</div>
    <div style="font-size:1.05rem; font-weight:700; color:#58a6ff; font-family:'JetBrains Mono';">Sugerido: {plan['shares']} acciones (${plan['total_investment']:,.2f})</div>
</div>
""", unsafe_allow_html=True)

                # Tabla limpia de métricas sin columnas desalineadas
                metricas_detalle = [
                    ("Precio de Entrada", f"${plan['entry_price']:,.2f}"),
                    ("Stop Loss (ATR)", f"${plan['stop_loss_price']:,.2f} (-{plan['stop_loss_pct']}%)"),
                    ("ATR (14 días)", f"${plan['atr']}"),
                    ("Beta", f"{plan['beta']}"),
                    ("Acciones a Comprar", f"{plan['shares']} acciones"),
                    ("Capital Comprometido", f"${plan['total_investment']:,.2f} ({plan['portfolio_allocation_pct']}%)"),
                    ("Riesgo en Stop Loss", f"${plan['risk_dollar']:,.2f} ({plan['risk_pct_portfolio']}%)"),
                    ("Take Profit 1 (+15%)", f"${plan['tp1_price']:,.2f}"),
                    ("Take Profit 2 (+30%)", f"${plan['tp2_price']:,.2f}")
                ]

                table_rows_html = ""
                for lbl, val in metricas_detalle:
                    table_rows_html += f"""
<tr>
    <td class="lbl">{lbl}</td>
    <td class="val">{val}</td>
</tr>
"""

                st.markdown(f"""
<table class="metric-table">
    {table_rows_html}
</table>
""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Ejecutar Orden Bracket en Alpaca Paper", key=f"btn_alpaca_{ticker_elegido}", use_container_width=True):
                    executor = AlpacaExecutor(api_key=alpaca_key, secret_key=alpaca_secret)
                    res = executor.execute_bracket_order(plan)
                    if res.get("status") == "SUBMITTED":
                        st.success(f"Orden Bracket enviada a Alpaca Paper (ID: {res.get('order_id')}) para {ticker_elegido} ({plan['shares']} acciones).")
                    elif res.get("status") == "SIMULATED_SUCCESS":
                        st.info(f"Simulacion ejecutada: {plan['shares']} acciones de {ticker_elegido}.")
                    else:
                        st.error(f"Error al enviar orden a Alpaca: {res.get('error')}")


# ==============================================================================
# TAB 2: DISTRIBUCIÓN Y SEGMENTOS
# ==============================================================================
with tab_charts:
    st.markdown("#### Distribución de Scores y Tipos de Activo")
    c1, c2 = st.columns(2)

    with c1:
        scores = [t.get("score", 0) for t in all_results]
        bins = list(range(0, 105, 10))
        counts = [sum(1 for s in scores if bins[i] <= s < bins[i+1]) for i in range(len(bins)-1)]
        bar_colors = ["#f85149" if b < 30 else ("#d29922" if b < 60 else "#3fb950") for b in bins[:-1]]

        fig_dist = go.Figure(go.Bar(
            x=[f"{b}-{b+10}" for b in bins[:-1]],
            y=counts,
            marker_color=bar_colors,
            text=counts,
            textposition="outside"
        ))
        fig_dist.update_layout(
            title="Distribución de Frecuencia por Score",
            plot_bgcolor="#161b22", paper_bgcolor="#161b22",
            font_color="#c9d1d9", height=280,
            margin=dict(t=40, b=30, l=30, r=20),
            xaxis=dict(gridcolor="#30363d"), yaxis=dict(gridcolor="#30363d")
        )
        st.plotly_chart(fig_dist, use_container_width=True, key="fig_dist")

    with c2:
        type_counts = {}
        for t in all_results:
            stype = t.get("signal_type", "INVALID")
            type_counts[stype] = type_counts.get(stype, 0) + 1

        fig_types = go.Figure(go.Pie(
            labels=list(type_counts.keys()),
            values=list(type_counts.values()),
            hole=0.6,
            marker_colors=["#3fb950", "#58a6ff", "#bc8cff", "#f85149", "#484f58"]
        ))
        fig_types.update_layout(
            title="Composición por Tipo de Operación",
            plot_bgcolor="#161b22", paper_bgcolor="#161b22",
            font_color="#c9d1d9", height=280,
            margin=dict(t=40, b=20, l=20, r=20),
            legend=dict(bgcolor="#161b22", bordercolor="#30363d")
        )
        st.plotly_chart(fig_types, use_container_width=True, key="fig_pie")


# ==============================================================================
# TAB 3: FRAMEWORK & REGLAS
# ==============================================================================
with tab_framework:
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("""
### Jerarquía y Clasificación de Señales
- **Acciones Operables (`EQUITY_STRONG`):** Compra directa de acción individual, monto >= $15,000 y lag <= 30 días. Pasan automáticamente a cálculo de dimensionamiento.
- **Acciones Informativas (`EQUITY_SMALL`):** Compras de montos menores a $15,000. Visibles para análisis de contexto.
- **Macro Deuda / Bonos (`MACRO_BOND`):** Operaciones en Notas del Tesoro y fondos de renta fija.
- **Ventas (`SELL`):** Desinversión del político.
- **Caducadas (`STALE`):** Reportadas con más de 30 días de retraso.

### Modelo de Dimensionamiento por Riesgo
Fórmula matemática:
$$\\text{Acciones} = \\frac{\\text{Capital} \\times \\text{Riesgo \\%}}{\\text{Precio Entrada} - \\text{Stop Loss}}$$

- **Score >= 75:** Riesgo 2.0%
- **Score 60-74:** Riesgo 1.5%
- **Score 45-59:** Riesgo 1.0%
- **Beta > 1.5:** Deducción defensiva de -0.5%
- **Cluster (2+ políticos en el mismo ticker):** Bonificación de +0.5%
- **Cap Máximo:** 15% del portafolio total por activo
""")

    with r2:
        st.markdown("""
### Los 4 Niveles de Salida (Stop Loss)
1. **Stop Técnico ATR:** Situado a `2.5x ATR` (o `3.0x ATR` en activos volátiles) por debajo de la entrada para evitar salidas prematuras por ruido de mercado.
2. **Trailing Stop:** Al alcanzar +15% de beneficio, el Stop Loss se mueve automáticamente a precio de entrada (Breakeven / Riesgo Cero).
3. **Time Stop:** Posiciones sin avance tras 45 días se cierran para liberar capital.
4. **Signal Stop:** Venta reportada por el mismo congresista en el ticker obliga a la salida inmediata.

### Salida Escalonada (Take Profit)
- **TP1 (+15%):** Venta del 33% de los títulos.
- **TP2 (+30%):** Venta de un segundo 33%.
- **34% Restante:** Se deja correr con Trailing Stop para capturar tendencias mayores.
""")
