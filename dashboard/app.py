from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data.generator import generate_historical_data, get_current_state, ACCOUNTS, FX_RATES
from models.forecaster import CashFlowForecaster
from models.alert_system import AlertSystem, SEVERITY_COLORS
from models.optimizer import LiquidityOptimizer
from models.stress_tester import StressTester, SCENARIOS

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LiquidityAI — Fintech Treasury",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stMetric"] {
    background: #0f1117;
    border: 1px solid #262730;
    border-radius: 8px;
    padding: 12px 16px;
}
.alert-critical { background:#2d0a0a; border-left:4px solid #FF4444; padding:10px; border-radius:4px; margin:4px 0; }
.alert-high     { background:#2d1a00; border-left:4px solid #FF8800; padding:10px; border-radius:4px; margin:4px 0; }
.alert-medium   { background:#2d2800; border-left:4px solid #FFCC00; padding:10px; border-radius:4px; margin:4px 0; }
.alert-low      { background:#0a2d0a; border-left:4px solid #44AA44; padding:10px; border-radius:4px; margin:4px 0; }
.rec-card { background:#12161f; border:1px solid #2a2f3d; border-radius:8px; padding:14px; margin:6px 0; }
.kpi-label { font-size:12px; color:#8b949e; text-transform:uppercase; letter-spacing:.5px; }
</style>
""", unsafe_allow_html=True)

# ── Data loading (cached) ─────────────────────────────────────────────────────
@st.cache_data(show_spinner="Генерация исторических данных…")
def load_data():
    return generate_historical_data(months=12)


@st.cache_resource(show_spinner="Обучение ML-модели прогнозирования…")
def load_forecaster(df_hash: int):
    df = load_data()
    fc = CashFlowForecaster()
    fc.train(df)
    return fc


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bank.png", width=60)
    st.markdown("## LiquidityAI")
    st.markdown("*Treasury Intelligence Platform*")
    st.divider()

    horizon = st.slider("Горизонт прогноза (дни)", 1, 7, 3)
    show_pending = st.checkbox("Учитывать pending-клиринг", value=True)

    st.divider()
    st.markdown("**Фильтр валют**")
    show_usd = st.checkbox("USD", value=True)
    show_eur = st.checkbox("EUR", value=True)
    show_gbp = st.checkbox("GBP", value=True)
    currencies = [c for c, v in [("USD", show_usd), ("EUR", show_eur), ("GBP", show_gbp)] if v]

    st.divider()
    if st.button("🔄 Обновить данные", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    st.caption(f"Данные за 12 мес. | Модель: Random Forest + GBM")

# ── Load everything ───────────────────────────────────────────────────────────
df = load_data()
df_hash = hash(str(df.shape))
forecaster = load_forecaster(df_hash)
state = get_current_state(df)
state_filtered = state[state["currency"].isin(currencies)]

balances = dict(zip(state["account_id"], state["balance"]))
forecasts = forecaster.forecast_all(days=horizon, current_balances=balances)
forecasts_filtered = forecasts[forecasts["currency"].isin(currencies)]

alert_sys = AlertSystem()
alerts = alert_sys.generate(state_filtered, forecasts_filtered)
alert_summary = alert_sys.summary(alerts)

optimizer = LiquidityOptimizer()
recommendations = optimizer.recommend(state_filtered, forecasts_filtered)
idle_report = optimizer.idle_capital_report(state_filtered)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 💧 LiquidityAI — Предиктивное управление ликвидностью")
st.markdown(f"**Дата:** {df['date'].max().strftime('%d.%m.%Y')} | **Аккаунтов:** {len(state_filtered)} | **Горизонт:** {horizon} дн.")

# ── KPI Row ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

total_liq = state_filtered["usd_equivalent"].sum()
frozen = idle_report["total_idle_usd"]
opp_cost = idle_report["annual_opportunity_cost_usd"]
critical_cnt = alert_summary.get("CRITICAL", 0)
high_cnt = alert_summary.get("HIGH", 0)
pending_usd = (state_filtered["pending_inflow"] * state_filtered["currency"].map(FX_RATES)).sum()

with col1:
    st.metric("Общая ликвидность", f"${total_liq/1e6:.2f}M", help="Сумма всех балансов в USD-эквиваленте")
with col2:
    delta_color = "inverse" if critical_cnt + high_cnt > 0 else "normal"
    st.metric("Критических алертов", f"{critical_cnt + high_cnt}", delta=f"+{critical_cnt} CRITICAL" if critical_cnt else None, delta_color="inverse" if critical_cnt else "off")
with col3:
    st.metric("Заморожено (idle)", f"${frozen/1e6:.2f}M", help="Средства сверх целевых балансов")
with col4:
    st.metric("Упущ. доход/год", f"${opp_cost/1e3:.0f}K", help="При ставке 4.5% годовых на idle-средства")
with col5:
    st.metric("Pending клиринг", f"${pending_usd/1e6:.2f}M", help="Деньги в процессе клиринга")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Обзор",
    "🏦 Счета",
    "📈 Прогноз cash flow",
    "🚨 Алерты",
    "⚖️ Оптимизация",
    "🧪 Стресс-тест",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Overview
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    c1, c2 = st.columns([2, 1])

    with c1:
        st.subheader("Распределение ликвидности по счетам")
        fig = px.bar(
            state_filtered.sort_values("usd_equivalent", ascending=True),
            x="usd_equivalent",
            y="account_name",
            color="currency",
            orientation="h",
            color_discrete_map={"USD": "#1f77b4", "EUR": "#2ca02c", "GBP": "#d62728"},
            labels={"usd_equivalent": "Баланс (USD-эквив.)", "account_name": ""},
            text_auto=".2s",
        )
        target_usd = [
            next(a for a in ACCOUNTS if a["id"] == row["account_id"])["target_balance"] * FX_RATES[row["currency"]]
            for _, row in state_filtered.iterrows()
        ]
        fig.add_trace(go.Scatter(
            x=target_usd,
            y=state_filtered.sort_values("usd_equivalent", ascending=True)["account_name"].tolist(),
            mode="markers",
            marker=dict(symbol="line-ns", size=12, color="white", line=dict(width=2, color="white")),
            name="Целевой баланс",
        ))
        min_usd = [
            next(a for a in ACCOUNTS if a["id"] == row["account_id"])["min_balance"] * FX_RATES[row["currency"]]
            for _, row in state_filtered.iterrows()
        ]
        fig.add_trace(go.Scatter(
            x=min_usd,
            y=state_filtered.sort_values("usd_equivalent", ascending=True)["account_name"].tolist(),
            mode="markers",
            marker=dict(symbol="line-ns", size=12, color="#FF4444", line=dict(width=2, color="#FF4444")),
            name="Минимальный баланс",
        ))
        fig.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("По валютам")
        ccy_df = state_filtered.groupby("currency")["usd_equivalent"].sum().reset_index()
        fig_pie = px.pie(
            ccy_df, values="usd_equivalent", names="currency",
            color_discrete_map={"USD": "#1f77b4", "EUR": "#2ca02c", "GBP": "#d62728"},
            hole=0.5,
        )
        fig_pie.update_layout(height=200, paper_bgcolor="rgba(0,0,0,0)", font_color="white", margin=dict(t=10, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Статус алертов")
        for sev, cnt in sorted(alert_summary.items(), key=lambda x: ["CRITICAL","HIGH","MEDIUM","LOW"].index(x[0])):
            color = SEVERITY_COLORS[sev]
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:6px 10px;background:#1a1a2e;border-left:3px solid {color};margin:2px 0;border-radius:3px"><span style="color:{color}">{sev}</span><strong>{cnt}</strong></div>', unsafe_allow_html=True)

    # Historical trend
    st.subheader("Историческая динамика балансов (90 дней)")
    hist90 = df[df["date"] >= df["date"].max() - pd.Timedelta(days=90)]
    hist90 = hist90[hist90["currency"].isin(currencies)]
    daily_total = hist90.groupby("date").apply(
        lambda g: (g["balance"] * g["currency"].map(FX_RATES)).sum()
    ).reset_index(name="total_usd")

    fig_hist = px.area(daily_total, x="date", y="total_usd", labels={"total_usd": "Ликвидность (USD)", "date": ""})
    fig_hist.update_traces(fill="tozeroy", line_color="#1f77b4", fillcolor="rgba(31,119,180,0.2)")
    fig_hist.update_layout(height=220, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
    st.plotly_chart(fig_hist, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Accounts
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Детали по счетам")

    for _, row in state_filtered.iterrows():
        acc_cfg = next(a for a in ACCOUNTS if a["id"] == row["account_id"])
        bal = row["balance"]
        min_b = acc_cfg["min_balance"]
        tgt_b = acc_cfg["target_balance"]

        fill_pct = min(1.0, bal / tgt_b)
        status_color = "#FF4444" if bal < min_b else ("#FFCC00" if bal < tgt_b * 0.8 else "#44AA44")

        with st.expander(f"{row['account_name']} — {bal:,.0f} {row['currency']}", expanded=False):
            cc1, cc2, cc3 = st.columns(3)
            cc1.metric("Баланс", f"{bal:,.0f} {row['currency']}")
            cc2.metric("Мин. порог", f"{min_b:,.0f} {row['currency']}", delta=f"{bal - min_b:+,.0f}", delta_color="normal" if bal >= min_b else "inverse")
            cc3.metric("Целевой", f"{tgt_b:,.0f} {row['currency']}", delta=f"{bal - tgt_b:+,.0f}", delta_color="normal" if bal >= tgt_b else "off")

            if row["pending_inflow"] > 0:
                st.info(f"В клиринге: **{row['pending_inflow']:,.0f} {row['currency']}** (задержка: {acc_cfg.get('payment_system','?')})")

            # Balance gauge
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number",
                value=bal,
                number={"suffix": f" {row['currency']}", "valueformat": ",.0f"},
                gauge={
                    "axis": {"range": [0, tgt_b * 1.5]},
                    "bar": {"color": status_color},
                    "steps": [
                        {"range": [0, min_b], "color": "rgba(255,68,68,0.2)"},
                        {"range": [min_b, tgt_b], "color": "rgba(255,204,0,0.1)"},
                        {"range": [tgt_b, tgt_b * 1.5], "color": "rgba(68,170,68,0.1)"},
                    ],
                    "threshold": {"line": {"color": "red", "width": 2}, "value": min_b},
                },
            ))
            fig_g.update_layout(height=180, paper_bgcolor="rgba(0,0,0,0)", font_color="white", margin=dict(t=10, b=0))
            st.plotly_chart(fig_g, use_container_width=True)

            # 30-day history for this account
            hist_acc = df[(df["account_id"] == row["account_id"]) & (df["date"] >= df["date"].max() - pd.Timedelta(days=30))]
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(x=hist_acc["date"], y=hist_acc["balance"], name="Баланс", line=dict(color=status_color)))
            fig_line.add_hline(y=min_b, line_dash="dash", line_color="#FF4444", annotation_text="MIN")
            fig_line.add_hline(y=tgt_b, line_dash="dot", line_color="#44AA44", annotation_text="TARGET")
            fig_line.update_layout(height=180, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white", showlegend=False, margin=dict(t=5, b=5))
            st.plotly_chart(fig_line, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Forecast
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader(f"Прогноз cash flow на {horizon} дней")

    if forecasts_filtered.empty:
        st.warning("Нет данных для прогноза. Выберите хотя бы одну валюту.")
    else:
        selected_acc = st.selectbox(
            "Выберите счёт",
            options=state_filtered["account_id"].tolist(),
            format_func=lambda x: state_filtered[state_filtered["account_id"] == x]["account_name"].iloc[0],
        )
        acc_fc = forecasts_filtered[forecasts_filtered["account_id"] == selected_acc]
        acc_state = state_filtered[state_filtered["account_id"] == selected_acc].iloc[0]
        acc_cfg = next(a for a in ACCOUNTS if a["id"] == selected_acc)

        # Combined: history (14d) + forecast
        hist14 = df[(df["account_id"] == selected_acc) & (df["date"] >= df["date"].max() - pd.Timedelta(days=14))]

        fig = go.Figure()

        # Historical balance
        fig.add_trace(go.Scatter(
            x=hist14["date"], y=hist14["balance"],
            name="Факт", line=dict(color="#1f77b4", width=2),
        ))

        # Forecast with CI
        fig.add_trace(go.Scatter(
            x=acc_fc["date"], y=acc_fc["upper_bound"],
            name="Верхняя граница", line=dict(color="rgba(255,165,0,0)", width=0),
            fillcolor="rgba(255,165,0,0.15)", fill="tonexty", showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=acc_fc["date"], y=acc_fc["lower_bound"],
            name="Нижняя граница", line=dict(color="rgba(255,165,0,0)", width=0),
            showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=acc_fc["date"], y=acc_fc["predicted_balance"],
            name="Прогноз", line=dict(color="#ff7f0e", width=2, dash="dash"),
            mode="lines+markers",
        ))

        fig.add_hline(y=acc_cfg["min_balance"], line_dash="dash", line_color="#FF4444", annotation_text="Минимальный баланс")
        fig.add_hline(y=acc_cfg["target_balance"], line_dash="dot", line_color="#44AA44", annotation_text="Целевой баланс")

        # Mark today
        today_ts = df["date"].max().timestamp() * 1000
        fig.add_vline(x=today_ts, line_dash="solid", line_color="gray", annotation_text="Сегодня")

        fig.update_layout(
            height=380,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            xaxis_title="Дата",
            yaxis_title=f"Баланс ({acc_state['currency']})",
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Inflow / Outflow breakdown
        st.subheader("Прогноз входящих и исходящих потоков")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=acc_fc["date"], y=acc_fc["predicted_inflow"], name="Приток", marker_color="#44AA44"))
        fig2.add_trace(go.Bar(x=acc_fc["date"], y=-acc_fc["predicted_outflow"], name="Отток", marker_color="#FF4444"))
        fig2.add_trace(go.Scatter(x=acc_fc["date"], y=acc_fc["predicted_net"], name="Нетто", line=dict(color="white", width=2)))
        fig2.update_layout(
            barmode="overlay", height=250,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="white", hovermode="x unified",
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Forecast table
        st.subheader("Таблица прогноза")
        display_fc = acc_fc[["date", "predicted_inflow", "predicted_outflow", "predicted_net", "predicted_balance", "clearing_delay"]].copy()
        display_fc.columns = ["Дата", "Прогноз притока", "Прогноз оттока", "Нетто", "Прогноз баланса", "Задержка клиринга (дн.)"]
        for col in ["Прогноз притока", "Прогноз оттока", "Нетто", "Прогноз баланса"]:
            display_fc[col] = display_fc[col].apply(lambda x: f"{x:,.0f}")
        st.dataframe(display_fc, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Alerts
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader(f"Активные алерты: {len(alerts)}")

    if not alerts:
        st.success("Нет активных алертов. Все счета в норме.")
    else:
        # Summary cards
        cols = st.columns(4)
        for i, (sev, label) in enumerate([("CRITICAL","Критических"),("HIGH","Высоких"),("MEDIUM","Средних"),("LOW","Низких")]):
            cnt = alert_summary.get(sev, 0)
            cols[i].metric(label, cnt)

        st.divider()

        for alert in alerts:
            sev = alert["severity"]
            css_class = f"alert-{sev.lower()}"
            color = SEVERITY_COLORS[sev]
            time_str = f"{alert['time_to_breach_h']}ч" if alert.get("time_to_breach_h") else "Сейчас"
            st.markdown(f"""
<div class="{css_class}">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <strong style="color:{color}">[{sev}] {alert['type']}</strong>
    <span style="color:#8b949e;font-size:12px">⏱ {time_str} | {alert['account_name']} ({alert['currency']})</span>
  </div>
  <div style="margin-top:6px">{alert['message']}</div>
  <div style="margin-top:4px;font-size:12px;color:#aaa">💡 {alert['recommended_action']}</div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Optimizer
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("Оптимизация распределения ликвидности")

    ic1, ic2, ic3 = st.columns(3)
    ic1.metric("Всего ликвидности", f"${idle_report['total_liquidity_usd']/1e6:.2f}M")
    ic2.metric("Заморожено (idle)", f"${idle_report['total_idle_usd']/1e6:.2f}M", f"{idle_report['idle_pct']:.1f}% от общего")
    ic3.metric("Упущ. доход/год", f"${idle_report['annual_opportunity_cost_usd']/1e3:.0f}K", "при 4.5% годовых")

    # Idle capital breakdown
    idle_df = pd.DataFrame(idle_report["details"])
    if not idle_df.empty:
        fig_idle = px.bar(
            idle_df.sort_values("idle_usd", ascending=False),
            x="account", y=["balance_usd", "idle_usd"],
            barmode="overlay",
            labels={"value": "USD", "account": ""},
            color_discrete_map={"balance_usd": "#1f77b4", "idle_usd": "#ff7f0e"},
            title="Баланс vs. Замороженные средства (USD)",
        )
        fig_idle.update_layout(height=250, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig_idle, use_container_width=True)

    st.divider()
    st.subheader(f"Рекомендации по переводам ({len(recommendations)} шт.)")

    if not recommendations:
        st.success("Все счета сбалансированы. Перераспределение не требуется.")
    else:
        for i, rec in enumerate(recommendations, 1):
            urgency_color = "#FF4444" if rec["urgency"] == "НЕМЕДЛЕННО" else "#FFCC00"
            st.markdown(f"""
<div class="rec-card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <strong>#{i} {rec['from_account']} → {rec['to_account']}</strong>
    <span style="color:{urgency_color};font-size:12px;font-weight:bold">{rec['urgency']}</span>
  </div>
  <div style="margin-top:8px;font-size:15px">
    💰 <strong>{rec['amount']:,.0f} {rec['currency_from']}</strong>
    {f"→ {rec['amount_dest']:,.0f} {rec['currency_to']}" if rec['currency_from'] != rec['currency_to'] else ""}
  </div>
  <div style="margin-top:4px;color:#8b949e;font-size:12px">
    ⏱ {rec['transfer_time_days']} дн. | Стоимость: ~{rec['estimated_cost']:,.0f} {rec['currency_from']} ({rec['cost_bps']} bps)
  </div>
  <div style="margin-top:4px;font-size:12px;color:#aaa">{rec['reason']}</div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Stress Test
# ═══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.subheader("Стресс-тестирование сценариев")

    scenario_key = st.selectbox(
        "Выберите сценарий",
        options=list(SCENARIOS.keys()),
        format_func=lambda k: f"{SCENARIOS[k]['icon']} {SCENARIOS[k]['name']}",
    )

    meta = SCENARIOS[scenario_key]
    st.info(f"**{meta['icon']} {meta['name']}**\n\n{meta['description']}")

    if st.button("▶ Запустить стресс-тест", type="primary", use_container_width=True):
        with st.spinner("Симуляция сценария…"):
            tester = StressTester()
            result = tester.run(scenario_key, state_filtered, forecasts_filtered)

        sev_colors = {"КРИТИЧЕСКИЙ": "#FF4444", "ВЫСОКИЙ": "#FF8800", "СРЕДНИЙ": "#FFCC00", "НИЗКИЙ": "#44AA44"}
        sev_c = sev_colors.get(result["severity"], "#aaa")

        rs1, rs2, rs3, rs4 = st.columns(4)
        rs1.metric("Общий удар (USD)", f"${result['total_delta_usd']/1e6:.2f}M")
        rs2.metric("Счетов в зоне риска", result["accounts_at_risk"])
        rs3.metric("Дефицит (USD)", f"${result['total_shortfall_usd']/1e3:.0f}K")
        rs4.metric("Уровень риска", result["severity"])

        st.divider()

        impact_df = result["impact_df"]
        if not impact_df.empty:
            # Comparison chart
            fig_stress = go.Figure()
            fig_stress.add_trace(go.Bar(
                name="Базовый прогноз",
                x=impact_df["account_name"],
                y=impact_df["base_balance_end"],
                marker_color="#1f77b4",
            ))
            fig_stress.add_trace(go.Bar(
                name="Стресс-сценарий",
                x=impact_df["account_name"],
                y=impact_df["stressed_balance_end"],
                marker_color=[("#FF4444" if r["at_risk"] else "#ff7f0e") for _, r in impact_df.iterrows()],
            ))

            # Min balance lines
            for _, acc_row in impact_df.iterrows():
                acc_cfg = next(a for a in ACCOUNTS if a["id"] == acc_row["account_id"])
                fig_stress.add_shape(
                    type="line",
                    x0=acc_row["account_name"], x1=acc_row["account_name"],
                    y0=0, y1=acc_cfg["min_balance"],
                    line=dict(color="red", width=1, dash="dot"),
                )

            fig_stress.update_layout(
                barmode="group", height=350,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="white", title="Сравнение: базовый прогноз vs. стресс",
                xaxis_tickangle=-25,
            )
            st.plotly_chart(fig_stress, use_container_width=True)

            # Impact table
            display_impact = impact_df[["account_name", "currency", "base_balance_end", "stressed_balance_end", "delta", "shortfall", "at_risk"]].copy()
            display_impact.columns = ["Счёт", "Валюта", "Базовый прогноз", "Стресс-сценарий", "Изменение", "Дефицит", "Риск"]
            for c in ["Базовый прогноз", "Стресс-сценарий", "Изменение", "Дефицит"]:
                display_impact[c] = display_impact[c].apply(lambda x: f"{x:,.0f}")
            display_impact["Риск"] = display_impact["Риск"].apply(lambda x: "🔴 ДА" if x else "🟢 НЕТ")
            st.dataframe(display_impact, use_container_width=True, hide_index=True)

            if result["accounts_at_risk"] > 0:
                at_risk_names = impact_df[impact_df["at_risk"]]["account_name"].tolist()
                st.error(f"⚠️ Счета в зоне риска: **{', '.join(at_risk_names)}**\n\nРекомендуется пополнить до запуска сценария.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("LiquidityAI v1.0 | FinTech Hackathon 2026 | ML-powered treasury intelligence")
