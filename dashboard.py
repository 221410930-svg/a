#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hydrogen Electrolyzer Real‑time Dashboard
- Historical data (blue)
- TimeGPT prediction (red dashed)
- 95% confidence band (pink fill)
- Critical threshold line
- Failure probability timeline
- Realtime auto-refresh
"""
import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from timegpt_model import TimeGPTModel

st.set_page_config(page_title="⚡ Hydrogen Electrolyzer Monitor", page_icon="⚡", layout="wide")

# ---------- Styles ----------
st.markdown("""
<style>
    .main-header { color:#1f77b4; text-align:center; margin-bottom:1rem; font-size:2rem; font-weight:700; }
    .section-header { color:#2c3e50; font-size:1.25rem; font-weight:700; margin:1.25rem 0 .5rem 0;
                      border-bottom:2px solid #3498db; padding-bottom:.25rem; }
    .metric-card { background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white;
                   padding:1rem; border-radius:12px; text-align:center; }
    .metric-value { font-size:1.5rem; font-weight:800; }
    .metric-label { font-size:.85rem; opacity:.9; }
    .live-pill { position:fixed; top:10px; right:10px; background:#28a745; color:#fff; padding:6px 10px;
                 border-radius:20px; font-size:12px; z-index:1000; }
</style>
""", unsafe_allow_html=True)

def main():
    # ---------- Session State Initialization ----------
    if "model" not in st.session_state: st.session_state.model = None
    if "historical" not in st.session_state: st.session_state.historical = None
    if "forecast" not in st.session_state: st.session_state.forecast = None
    if "last_pred" not in st.session_state: st.session_state.last_pred = None
    if "last_update" not in st.session_state: st.session_state.last_update = None

    # ---------- Sidebar ----------
    st.sidebar.markdown("## ⚙️ Controls")
    critical_threshold = st.sidebar.slider("Critical Threshold (V)", 0.50, 0.70, 0.60, 0.01)
    horizon_min = st.sidebar.slider("Prediction Horizon (minutes)", 30, 120, 120, 10)
    refresh_seconds = st.sidebar.slider("UI Refresh (seconds)", 2, 10, 5)
    auto_refresh = st.sidebar.checkbox("🔄 Real-time monitoring", value=True)

    # Model
    if st.session_state.model is None: 
        try:
            st.session_state.model = TimeGPTModel()
            st.sidebar.success("🤖 TimeGPT connected")
        except ValueError as e:
            st.sidebar.error(f"❌ {e}")
            st.stop()

    def add_realtime_point(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or len(df) == 0: return df
        df = df.copy()
        df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
        last_time = pd.to_datetime(df["ds"].iloc[-1])
        last_value = float(df["y"].iloc[-1])
        new_time = last_time + pd.Timedelta(minutes=1)
        new_value = float(np.clip(last_value + np.random.normal(0, 0.001), 0.45, 0.70))
        return pd.concat([df, pd.DataFrame({"ds": [new_time], "y": [new_value]})], ignore_index=True)
    # ---------- Data ----------
    if st.session_state.historical is None:
        with st.spinner("📊 Loading data..."):
            st.session_state.historical = st.session_state.model.load_voltage_data()
            st.success(f"✅ Loaded {len(st.session_state.historical)} points")

    st.session_state.historical = add_realtime_point(st.session_state.historical)
    st.session_state.last_update = datetime.now()

    # ---------- Forecast ----------
    with st.spinner("🤖 Generating prediction..."):
        st.session_state.forecast = st.session_state.model.predict(
            st.session_state.historical, horizon_minutes=horizon_min, critical_threshold_v=critical_threshold
        )
        st.session_state.last_pred = datetime.now()

    # Ensure datetime
    st.session_state.historical["ds"] = pd.to_datetime(st.session_state.historical["ds"], errors="coerce")
    st.session_state.forecast["ds"] = pd.to_datetime(st.session_state.forecast["ds"], errors="coerce")

    # ---------- Header & Metrics ----------
    st.markdown('<div class="main-header">⚡ Hydrogen Electrolyzer Monitor</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="live-pill">LIVE • {st.session_state.last_update.strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

    current_v = float(st.session_state.historical["y"].iloc[-1])
    pred_v = float(st.session_state.forecast["TimeGPT"].iloc[-1])
    max_risk = float(st.session_state.forecast["failure_probability"].max())

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><div class="metric-value">{current_v:.3f}V</div><div class="metric-label">🔋 Current Voltage</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><div class="metric-value">{pred_v:.3f}V</div><div class="metric-label">🤖 Predicted (end of horizon)</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card"><div class="metric-value">{critical_threshold:.3f}V</div><div class="metric-label">🚨 Critical Threshold</div></div>', unsafe_allow_html=True)
    with c4:
        risk_status = "🟢" if max_risk < 0.1 else "🟡" if max_risk < 0.3 else "🔴"
        st.markdown(f'<div class="metric-card"><div class="metric-value">{risk_status} {max_risk:.1%}</div><div class="metric-label">⚠️ Max Failure Risk</div></div>', unsafe_allow_html=True)

    # ---------- Main Chart ----------
    st.markdown('<div class="section-header">📊 Cell Voltage Prediction with Uncertainty Bands</div>', unsafe_allow_html=True)
    hist = st.session_state.historical; fc = st.session_state.forecast

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["ds"], y=hist["y"], mode="lines", name="Historical",
                             line=dict(color="#1f77b4", width=4),
                             hovertemplate="Time: %{x}<br>Voltage: %{y:.3f}V<extra></extra>"))
    fig.add_trace(go.Scatter(x=fc["ds"], y=fc["TimeGPT-hi-95"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fc["ds"], y=fc["TimeGPT-lo-95"], mode="lines", name="95% Confidence",
                             fill="tonexty", fillcolor="rgba(255,182,193,0.4)", line=dict(width=0),
                             hovertemplate="Lower 95%: %{y:.3f}V<extra></extra>"))
    fig.add_trace(go.Scatter(x=fc["ds"], y=fc["TimeGPT"], mode="lines", name="Prediction",
                             line=dict(color="#d62728", width=4, dash="dash"),
                             hovertemplate="Predicted: %{y:.3f}V<extra></extra>"))
    fig.add_hline(y=critical_threshold, line_dash="dash", line_color="#d62728", line_width=4,
                  annotation_text=f"Critical Failure Threshold: {critical_threshold:.2f}V",
                  annotation_position="top right", annotation_font_color="#d62728", annotation_font_size=14)
    # Add vertical line at current time
    current_time = hist["ds"].iloc[-1]
    fig.add_shape(
        type="line",
        x0=current_time, x1=current_time,
        y0=0, y1=1,
        yref="paper",
        line=dict(color="#666", width=1, dash="dot")
    )

    fig.update_layout(
        xaxis_title="Time", 
        yaxis_title="Cell Voltage (V)", 
        plot_bgcolor="white", 
        paper_bgcolor="white",
        hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=80, r=80, t=60, b=80), 
        height=600,  # Increased height
        width=1200,   # Set explicit width
        font=dict(size=14),  # Larger font
        title=dict(
            text="Cell Voltage Prediction with Uncertainty Bands",
            font=dict(size=18, color="#2c3e50"),
            x=0.5,
            xanchor="center"
        )
    )
    fig.update_yaxes(
        range=[0.45, 0.70], 
        gridcolor="#e0e0e0",
        title_font=dict(size=16),
        tickfont=dict(size=12),
        showgrid=True,
        gridwidth=1
    )
    fig.update_xaxes(
        gridcolor="#e0e0e0",
        title_font=dict(size=16),
        tickfont=dict(size=12),
        showgrid=True,
        gridwidth=1
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---------- Failure Probability Chart ----------
    st.markdown('<div class="section-header">📊 Failure Probability Timeline</div>', unsafe_allow_html=True)
    pfig = go.Figure()
    pfig.add_trace(go.Scatter(x=fc["ds"], y=fc["failure_probability"], mode="lines", name="Failure Probability",
                              fill="tozeroy", fillcolor="rgba(255,99,132,0.30)", line=dict(width=4, color="#ff6384")))
    pfig.add_hline(y=0.30, line_dash="dash", line_color="#ff6384", annotation_text="High (30%)")
    pfig.add_hline(y=0.10, line_dash="dash", line_color="#ffa500", annotation_text="Medium (10%)")
    pfig.update_layout(
        xaxis_title="Time", 
        yaxis_title="Failure Probability", 
        yaxis=dict(tickformat=".0%", range=[0,1]),
        plot_bgcolor="white", 
        height=350,  # Increased height
        width=1200,   # Set explicit width
        margin=dict(l=80, r=80, t=40, b=60),
        font=dict(size=14),
        title=dict(
            text="Failure Probability Timeline",
            font=dict(size=18, color="#2c3e50"),
            x=0.5,
            xanchor="center"
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    pfig.update_xaxes(
        gridcolor="#e0e0e0",
        title_font=dict(size=16),
        tickfont=dict(size=12),
        showgrid=True,
        gridwidth=1
    )
    pfig.update_yaxes(
        gridcolor="#e0e0e0",
        title_font=dict(size=16),
        tickfont=dict(size=12),
        showgrid=True,
        gridwidth=1
    )
    st.plotly_chart(pfig, use_container_width=True)

    # ---------- Data Tables ----------
    st.markdown('<div class="section-header">📋 Data Summary</div>', unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA: st.markdown("**Recent Historical (last 10):**"); st.dataframe(hist.tail(10), use_container_width=True)
    with colB: st.markdown("**Forecast (first 10):**"); st.dataframe(fc.head(10), use_container_width=True)

    # ---------- Auto-refresh ----------
    if auto_refresh:
        time.sleep(refresh_seconds)
        st.rerun()

if __name__ == "__main__":
    main()