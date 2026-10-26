# -*- coding: utf-8 -*-
"""
app.py — Congressional Trade Tracker (Versión Cuantitativa Institucional)
1. Navegación fluida por tabs con st.session_state (redirección inmediata al hacer clic en cualquier tarjeta).
2. Cada tarjeta de señal es un botón completo interactivo que abre el desglose en la Calculadora.
3. Tabla de métricas perfectamente alineada con tooltips explicativos sin descuadres visuales.
4. Calculadora 100% funcional con claves únicas para evitar errores de Plotly.
5. Cero emojis. Estilo terminal Bloomberg / FactSet oscuro.
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

# Inicializar estados de navegación
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "Todas las Señales"
if "selected_ticker" not in st.session_state:
    st.session_state["selected_ticker"] = "EL"

# Estilos CSS profesionales
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

/* Estilo para convertir los botones de señal en recuadros completos interactivos */
div.stButton > button.card-btn {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-left: 4px solid #388bfd !important;
    border-radius: 6px !important;
    color: #c9d1d9 !important;
    text-align: left !important;
    padding: 12px 16px !important;
    width: 100% !important;
    margin-bottom: 6px !important;
    transition: all 0.15s ease-in-out !important;
}
div.stButton > button.card-btn:hover {
    background: #1c2128 !important;
    border-color: #58a6ff !important;
    color: #f0f6fc !important;
    transform: translateX(2px) !important;
}

/* Tabla financiera de métricas alineada */
.metric-table {
    width: 100%;
    border-collapse: collapse;
    background: #161b22;
    border-radius: 6px;
    border: 1px solid #30363d;
    overflow: hidden;
    margin-top: 6px;
}
.metric-table tr {
    border-bottom: 1px solid #21262d;
}
.metric-table tr:last-child {
    border-bottom: none;
}
.metric-table td {
    padding: 7px 12px;
    font-size: 0.78rem;
    vertical-align: middle;
}
.metric-table td.lbl {
    color: #8b949e;
    width: 48%;
}
.metric-table td.val {
    color: #f0f6fc;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    text-align: right;
    width: 44%;
}
.metric-table td.help-col {
    width: 8%;
    text-align: center;
}
.help-icon {
    display: inline-block;
    width: 16px;
    height: 16px;
    line-height: 15px;
    border-radius: 50%;
    background: #21262d;
    color: #8b949e;
    font-size: 10px;
    font-weight: bold;
    cursor: help;
    text-align: center;
    border: 1px solid #30363d;
}
.help-icon:hover {
    background: #388bfd;
    color: #ffffff;
    border-color: #58a6ff;
}

.stNumberInput input, .stSelectbox select {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    color: #f0f6fc !important;
    border-radius: 6px !important;
}

/* Modal popup explicativo cuando se hace click en [?] */
.dialog-content {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 16px;
    color: #c9d1d9;
}

/* Regla interactiva en la gráfica */
.calc-measure-box {
    background: #161b22;
    border: 1px solid #388bfd;
    border-radius: 6px;
    padding: 12px 16px;
    margin-top: 10px;
}

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
st.sidebar.markdown("### Configuración")
pages = st.sidebar.slider("Páginas a consultar", min_value=5, max_value=30, value=15, step=1)
capital = st.sidebar.number_input("Capital de Portafolio ($)", min_value=1000.0, max_value=10000000.0, value=10000.0, step=1000.0)

st.sidebar.markdown("---")
st.sidebar.markdown("### Filtro Global")
min_score = st.sidebar.slider("Score Mínimo", min_value=0, max_value=80, value=20, step=5)

st.sidebar.markdown("---")
st.sidebar.markdown("### Alpaca Paper Trading")
alpaca_key = st.sidebar.text_input("API Key", value=Config.ALPACA_API_KEY, type="password")
alpaca_secret = st.sidebar.text_input("Secret Key", value=Config.ALPACA_SECRET_KEY, type="password")


col_btn, _ = st.columns([1, 5])
with col_btn:
    if st.button("Actualizar Datos", use_container_width=True):
        st.cache_data.clear()

with st.spinner("Consultando registros del Congreso de EE.UU..."):
    raw_trades, all_results, clusters = load_and_classify_trades(pages)

# Jerarquía estricta de ordenamiento:
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

# Encabezado
st.markdown("""
<div style="padding: 6px 0 14px 0; border-bottom: 1px solid #21262d; margin-bottom: 14px;">
    <div style="font-size: 1.35rem; font-weight: 700; color: #f0f6fc;">CONGRESSIONAL TRADE TRACKER</div>
    <div style="font-size: 0.74rem; color: #8b949e;">Sistema cuantitativo institucional de seguimiento y réplica de operaciones políticas</div>
</div>
""", unsafe_allow_html=True)

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

# NAVEGACIÓN PROGRAMÁTICA CONTROLADA POR SESSION_STATE
tab_options = ["Todas las Señales", "Análisis Visual", "Calculadora de Posición", "Framework & Reglas"]
selected_tab = st.radio(
    "Navegación:",
    options=tab_options,
    index=tab_options.index(st.session_state["active_tab"]) if st.session_state["active_tab"] in tab_options else 0,
    horizontal=True,
    label_visibility="collapsed"
)
st.session_state["active_tab"] = selected_tab

st.markdown("<hr style='border:none; border-top:1px solid #21262d; margin: 4px 0 16px 0;'>", unsafe_allow_html=True)

# ==============================================================================
# TAB 1: TODAS LAS SEÑALES (CON CLIC EN EL RECUADRO COMPLETO PARA ABRIR EN CALCULADORA)
# ==============================================================================
if st.session_state["active_tab"] == "Todas las Señales":
    col_filter, _ = st.columns([3, 1])
    with col_filter:
        tipo_opciones = [
            "Acciones Operables (EQUITY_STRONG)",
            "Acciones Informativas (EQUITY_SMALL)",
            "Macro Deuda / Bonos (MACRO_BOND)",
            "Ventas (SELL)",
            "Caducadas (STALE)"
        ]
        filtro_tipos = st.multiselect(
            "Filtrar tipos de señal en vista:",
            options=tipo_opciones,
            default=tipo_opciones[:3]
        )

    tipo_map = {
        "Acciones Operables (EQUITY_STRONG)": "EQUITY_STRONG",
        "Acciones Informativas (EQUITY_SMALL)": "EQUITY_SMALL",
        "Macro Deuda / Bonos (MACRO_BOND)": "MACRO_BOND",
        "Ventas (SELL)": "SELL",
        "Caducadas (STALE)": "STALE"
    }
    tipos_activos = [tipo_map[x] for x in filtro_tipos]

    senales_visibles = [
        t for t in all_results
        if t.get("signal_type") in tipos_activos and t.get("score", 0) >= min_score
    ]

    c_cards, c_table = st.columns([3, 2])
    with c_cards:
        st.markdown(f"**Registros visibles ({len(senales_visibles)})** — *Haz clic en cualquier recuadro para abrir su desglose y calculadora:*")

        for idx, t in enumerate(senales_visibles[:25]):
            sig = t.get("signal_type", "INVALID")
            clasif = t.get("clasificacion", "")
            ticker = t.get("ticker", "N/A")
            pol = t.get("politician", "Desconocido")
            score = t.get("score", 0)
            lag = t.get("lag_days")
            lag_str = f"{lag}d" if lag is not None else "N/A"
            amt = t.get("amount_range", "")
            issuer = (t.get("issuer_name", "") or t.get("asset_description", ""))[:45]

            # Construir texto del recuadro completo
            cluster_tag = " [CLUSTER]" if ticker in clusters else ""
            card_label = f"[{ticker}]  |  {clasif} ({score}/100){cluster_tag}  |  {pol} ({t.get('chamber','')})  |  Lag: {lag_str}  |  {amt}  —  {issuer}"

            # Al hacer clic en el recuadro, redirige de inmediato a la Calculadora
            if st.button(card_label, key=f"btn_card_{idx}_{ticker}", use_container_width=True):
                if ticker and ticker not in ("--", "N/A", "UNKNOWN") and ticker.isalpha():
                    st.session_state["selected_ticker"] = ticker
                    st.session_state["active_tab"] = "Calculadora de Posición"
                    st.rerun()

    with c_table:
        st.markdown("**Tabla Resumen**")
        rows = []
        for t in senales_visibles:
            rows.append({
                "Ticker": t.get("ticker", ""),
                "Político": t.get("politician", "")[:18],
                "Score": t.get("score"),
                "Tipo": t.get("signal_type", ""),
                "Lag": f"{t.get('lag_days','?')}d",
                "Monto": t.get("amount_range", "")
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=520)


# ==============================================================================
# TAB 2: ANÁLISIS VISUAL CON INTERACCIÓN LATERAL
# ==============================================================================
elif st.session_state["active_tab"] == "Análisis Visual":
    st.markdown("#### Segmentación Cuantitativa de Señales")
    rango_score_sel = st.select_slider(
        "Filtrar señales por segmento de calidad:",
        options=["Todos (0-100)", "DÉBIL (0-29)", "BAJA (30-44)", "MODERADA (45-59)", "FUERTE (60-100)"],
        value="Todos (0-100)"
    )

    if rango_score_sel == "DÉBIL (0-29)":
        trades_segmento = [t for t in all_results if t.get("score", 0) < 30]
    elif rango_score_sel == "BAJA (30-44)":
        trades_segmento = [t for t in all_results if 30 <= t.get("score", 0) < 45]
    elif rango_score_sel == "MODERADA (45-59)":
        trades_segmento = [t for t in all_results if 45 <= t.get("score", 0) < 60]
    elif rango_score_sel == "FUERTE (60-100)":
        trades_segmento = [t for t in all_results if t.get("score", 0) >= 60]
    else:
        trades_segmento = all_results

    col_charts, col_filtered_list = st.columns([3, 2])

    with col_charts:
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
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22",
            font_color="#c9d1d9",
            height=280,
            margin=dict(t=40, b=30, l=30, r=20),
            xaxis=dict(gridcolor="#30363d"),
            yaxis=dict(gridcolor="#30363d")
        )
        st.plotly_chart(fig_dist, use_container_width=True, key="fig_dist_chart")

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
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22",
            font_color="#c9d1d9",
            height=240,
            margin=dict(t=40, b=20, l=20, r=20),
            legend=dict(bgcolor="#161b22", bordercolor="#30363d")
        )
        st.plotly_chart(fig_types, use_container_width=True, key="fig_types_chart")

    with col_filtered_list:
        st.markdown(f"**Señales en Segmento: `{rango_score_sel}` ({len(trades_segmento)})**")
        seg_rows = []
        for ts in trades_segmento:
            seg_rows.append({
                "Ticker": ts.get("ticker", ""),
                "Político": ts.get("politician", "")[:16],
                "Score": ts.get("score"),
                "Tipo": ts.get("signal_type", ""),
                "Lag": f"{ts.get('lag_days', '?')}d",
                "Monto": ts.get("amount_range", "")
            })
        st.dataframe(pd.DataFrame(seg_rows), use_container_width=True, hide_index=True, height=540)


# ==============================================================================
# TAB 3: CALCULADORA DE POSICIÓN (100% OPERATIVA, ROBUSTA Y SIN DESCUADRES)
# ==============================================================================
elif st.session_state["active_tab"] == "Calculadora de Posición":
    st.markdown("#### Calculadora y Desglose Financiero de Posición")

    # FILTRO ESTRICTO: Solo acciones reales (no bonos, no N/A, ticker alfabetico)
    acciones_para_calculadora = [
        t for t in all_results
        if t.get("ticker")
        and t.get("ticker") not in ("--", "N/A", "UNKNOWN")
        and len(t.get("ticker")) <= 5
        and t.get("ticker").isalpha()
        and t.get("signal_type") in ("EQUITY_STRONG", "EQUITY_SMALL")
    ]

    acciones_para_calculadora.sort(
        key=lambda x: (
            0 if x.get("signal_type") == "EQUITY_STRONG" else 1,
            -x.get("score", 0),
            x.get("lag_days") if x.get("lag_days") is not None else 999
        )
    )

    if not acciones_para_calculadora:
        st.info("No se encontraron compras directas de acciones con ticker disponible en las páginas consultadas.")
    else:
        # Lista de tickers disponibles
        ticker_list = [t["ticker"] for t in acciones_para_calculadora]
        current_selected = st.session_state.get("selected_ticker", ticker_list[0])
        if current_selected not in ticker_list:
            current_selected = ticker_list[0]

        opciones_select = [
            f"{t['ticker']} | {t['politician']} | Score: {t['score']}/100 | Lag: {t.get('lag_days')}d | {t.get('amount_range')}"
            for t in acciones_para_calculadora
        ]
        default_idx = ticker_list.index(current_selected)

        seleccion_str = st.selectbox(
            "Acción en análisis (puedes cambiarla aquí o hacer clic en cualquier tarjeta de la primera pestaña):",
            opciones_select,
            index=default_idx
        )
        ticker_elegido = seleccion_str.split("|")[0].strip()
        st.session_state["selected_ticker"] = ticker_elegido
        senal_elegida = next(t for t in acciones_para_calculadora if t["ticker"] == ticker_elegido)

        is_cluster_ticker = ticker_elegido in clusters

        if is_cluster_ticker:
            st.success(f"Cluster Detectado: Múltiples congresistas han comprado {ticker_elegido}: {', '.join(clusters[ticker_elegido])}")

        with st.spinner(f"Obteniendo datos de mercado y calculando niveles para {ticker_elegido}..."):
            sizer = PositionSizer(portfolio_equity=capital)
            plan = sizer.calcular_posicion(ticker_elegido, senal_elegida["score"], is_cluster=is_cluster_ticker)

        if not plan:
            st.error(f"No fue posible obtener cotización histórica y métricas para {ticker_elegido}.")
        else:
            hist_df = plan.get("hist")

            # Ficha de la Empresa
            st.markdown("---")
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

                    # Línea de precio actual
                    p_act = plan["entry_price"]
                    fig_stock.add_hline(
                        y=p_act, line_color="#58a6ff", line_width=1.5,
                        annotation_text=f"Precio Actual ${p_act:,.2f}",
                        annotation_font_color="#58a6ff"
                    )

                    # Línea de Stop Loss
                    fig_stock.add_hline(
                        y=plan["stop_loss_price"], line_dash="dash", line_color="#f85149",
                        annotation_text=f"Stop Loss ${plan['stop_loss_price']:,.2f} (-{plan['stop_loss_pct']}%)",
                        annotation_font_color="#f85149"
                    )

                    # Take Profit 1 y 2
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

                    # Ubicar fecha de compra del político
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

                    # Habilitar modo de dibujo / medicion en Plotly
                    fig_stock.update_layout(
                        title=f"{ticker_elegido} - Cotización y Niveles Técnicos (Usa el modo selección para medir)",
                        plot_bgcolor="#161b22", paper_bgcolor="#161b22",
                        font_color="#c9d1d9", height=420,
                        xaxis=dict(gridcolor="#30363d", rangeslider_visible=False),
                        yaxis=dict(gridcolor="#30363d"),
                        margin=dict(t=40, b=20, l=40, r=20),
                        legend=dict(bgcolor="#161b22", bordercolor="#30363d"),
                        dragmode="select" # Modo de selección y medición por defecto al arrastrar
                    )
                    
                    # Capturar evento de selección para calcular el % de cambio exacto
                    selected_data = st.plotly_chart(
                        fig_stock, 
                        use_container_width=True, 
                        key=f"chart_calc_{ticker_elegido}",
                        on_select="rerun",
                        selection_mode=["box", "points"]
                    )
                    
                    # Medidor de porcentaje interactivo
                    st.markdown("##### Herramienta de Medición (% de Variación)")
                    col_m1, col_m2 = st.columns(2)
                    
                    # Lista de fechas y precios disponibles para referencia rápida o cálculo por selector
                    fechas_disponibles = [d.strftime("%Y-%m-%d") for d in hist_df.index]
                    
                    # Si el usuario seleccionó un área arrastrando el ratón en la gráfica
                    medicion_calculada = False
                    if selected_data and "selection" in selected_data and selected_data["selection"].get("box"):
                        box = selected_data["selection"]["box"][0]
                        y_vals = box.get("y", [])
                        if len(y_vals) >= 2:
                            p_inicio = float(y_vals[0])
                            p_fin = float(y_vals[1])
                            var_pct = ((p_fin - p_inicio) / p_inicio) * 100
                            diff_usd = p_fin - p_inicio
                            c_res = "#3fb950" if diff_usd >= 0 else "#f85149"
                            signo = "+" if diff_usd >= 0 else ""
                            st.markdown(f"""
<div style="background:#161b22; border:1px solid {c_res}; border-radius:6px; padding:10px 14px; margin-bottom:8px;">
    <div style="font-size:0.7rem; color:#8b949e; text-transform:uppercase;">Medición de Rango Seleccionado en Gráfica</div>
    <div style="font-size:1.3rem; font-weight:700; color:{c_res}; font-family:'JetBrains Mono';">{signo}{var_pct:.2f}% ({signo}${diff_usd:.2f})</div>
    <div style="font-size:0.72rem; color:#c9d1d9;">Punto Inicial: <b>${p_inicio:.2f}</b>  →  Punto Final: <b>${p_fin:.2f}</b></div>
</div>
""", unsafe_allow_html=True)
                            medicion_calculada = True
                    
                    # Controles de medición manual con puntos exactos de la acción
                    with col_m1:
                        f_inicio_sel = st.selectbox("Fecha o Punto Inicial:", fechas_disponibles, index=max(0, len(fechas_disponibles)-15), key=f"f_ini_{ticker_elegido}")
                    with col_m2:
                        f_fin_sel = st.selectbox("Fecha o Punto Final:", fechas_disponibles, index=len(fechas_disponibles)-1, key=f"f_fin_{ticker_elegido}")
                    
                    p_start = float(hist_df.loc[hist_df.index.strftime("%Y-%m-%d") == f_inicio_sel, "Close"].iloc[0])
                    p_end = float(hist_df.loc[hist_df.index.strftime("%Y-%m-%d") == f_fin_sel, "Close"].iloc[0])
                    
                    diff_val = p_end - p_start
                    pct_val = ((p_end - p_start) / p_start) * 100
                    color_val = "#3fb950" if diff_val >= 0 else "#f85149"
                    signo_val = "+" if diff_val >= 0 else ""
                    
                    if not medicion_calculada:
                        st.markdown(f"""
<div style="background:#161b22; border:1px solid #30363d; border-radius:6px; padding:10px 14px; margin-bottom:8px;">
    <div style="font-size:0.7rem; color:#8b949e; text-transform:uppercase;">Variación Entre Puntos Seleccionados</div>
    <div style="font-size:1.3rem; font-weight:700; color:{color_val}; font-family:'JetBrains Mono';">{signo_val}{pct_val:.2f}% ({signo_val}${diff_val:.2f})</div>
    <div style="font-size:0.72rem; color:#c9d1d9;">Inicio ({f_inicio_sel}): <b>${p_start:.2f}</b>  →  Final ({f_fin_sel}): <b>${p_end:.2f}</b></div>
</div>
""", unsafe_allow_html=True)

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

                # Tabla de métricas con popovers interactivos al clic y alineación vertical perfecta
                metricas_detalle = [
                    ("Precio de Entrada", f"${plan['entry_price']:,.2f}", "Precio actual estimado al colocar la orden en el mercado."),
                    ("Stop Loss (ATR)", f"${plan['stop_loss_price']:,.2f} (-{plan['stop_loss_pct']}%)", "Nivel de salida por corte de pérdidas. Calculado a 2.5x o 3.0x ATR para absorber la oscilación normal del activo."),
                    ("ATR (14 días)", f"${plan['atr']}", "Average True Range. Volatilidad en dólares que experimenta la acción por sesión."),
                    ("Beta", f"{plan['beta']}", "Sensibilidad frente al S&P 500. Valores mayores a 1.5 activan ajuste de riesgo defensivo."),
                    ("Acciones a Comprar", f"{plan['shares']} acciones", "Número de títulos calculado a partir de la distancia al Stop Loss."),
                    ("Capital Comprometido", f"${plan['total_investment']:,.2f} ({plan['portfolio_allocation_pct']}%)", "Monto asignado. No supera el 15% del total de la cartera."),
                    ("Riesgo en Stop Loss", f"${plan['risk_dollar']:,.2f} ({plan['risk_pct_portfolio']}%)", "Pérdida monetaria en el peor de los casos."),
                    ("Take Profit 1 (+15%)", f"${plan['tp1_price']:,.2f}", "Primer objetivo. Se liquida el 33% y se sube el Stop a precio de compra (Breakeven)."),
                    ("Take Profit 2 (+30%)", f"${plan['tp2_price']:,.2f}", "Segundo objetivo. Se liquida otro 33%. El resto corre con Trailing Stop.")
                ]

                st.markdown('<div style="background:#161b22; border:1px solid #30363d; border-radius:6px; padding:4px 10px;">', unsafe_allow_html=True)
                for i_m, (lbl, val, exp) in enumerate(metricas_detalle):
                    c_l, c_v, c_btn = st.columns([2.6, 2.0, 0.4])
                    with c_l:
                        st.markdown(f'<div style="font-size:0.77rem; color:#8b949e; line-height:32px;">{lbl}</div>', unsafe_allow_html=True)
                    with c_v:
                        st.markdown(f'<div style="font-size:0.77rem; font-weight:600; color:#f0f6fc; font-family:JetBrains Mono; line-height:32px; text-align:right;">{val}</div>', unsafe_allow_html=True)
                    with c_btn:
                        with st.popover("?", use_container_width=True):
                            st.markdown(f"**{lbl}**")
                            st.caption(exp)
                    if i_m < len(metricas_detalle) - 1:
                        st.markdown('<div style="border-top:1px solid #21262d; margin:0;"></div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Ejecutar Orden Bracket en Alpaca Paper", key=f"btn_alpaca_exec_{ticker_elegido}", use_container_width=True):
                    executor = AlpacaExecutor(api_key=alpaca_key, secret_key=alpaca_secret)
                    res = executor.execute_bracket_order(plan)
                    st.success(f"Orden enviada: {res.get('status')} para {ticker_elegido} ({plan['shares']} acciones)")


# ==============================================================================
# TAB 4: FRAMEWORK & REGLAS
# ==============================================================================
elif st.session_state["active_tab"] == "Framework & Reglas":
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("""
### Jerarquía y Clasificación de Señales
- **Acciones Operables (`EQUITY_STRONG`):** Compra directa de acción individual, monto superior o igual a $15,000 y lag inferior o igual a 30 días. Son las únicas que pasan a cálculo automático de ejecución.
- **Acciones Informativas (`EQUITY_SMALL`):** Compras de montos menores a $15,000. Son visibles para contexto, pero no son operables por falta de convicción de capital.
- **Macro Deuda / Bonos (`MACRO_BOND`):** Operaciones en Notas del Tesoro y fondos de renta fija. No se replican en acciones; sirven como termómetro de liquidez o aversión al riesgo.
- **Ventas (`SELL`):** Desinversión del político. Alerta de salida si se posee la acción.
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
1. **Stop Técnico ATR:** Situado a `2.5x ATR` (o `3.0x ATR` en activos volátiles) por debajo de la entrada para evitar salidas prematuras por volatilidad natural.
2. **Trailing Stop:** Al alcanzar +15% de beneficio, el Stop Loss se mueve automáticamente a precio de entrada (Breakeven / Riesgo Cero).
3. **Time Stop:** Posiciones sin avance tras 45 días se cierran para liberar capital.
4. **Signal Stop:** Venta reportada por el mismo congresista en el ticker obliga a la salida inmediata.

### Salida Escalonada (Take Profit)
- **TP1 (+15%):** Venta del 33% de los títulos.
- **TP2 (+30%):** Venta de un segundo 33%.
- **34% Restante:** Se deja correr con Trailing Stop para capturar tendencias mayores.
""")
