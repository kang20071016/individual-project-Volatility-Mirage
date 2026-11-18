"""Volatility Mirage visual prototype. All displayed observations are simulated."""

import json
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from research_chat import ask_free_model, build_evidence

st.set_page_config(page_title="Volatility Mirage", page_icon="📈", layout="wide")
CYAN, CORAL, MUTED = "#39dce5", "#f08876", "#91a7b6"

st.markdown("""
<style>
.stApp {background:#07131f;color:#e7f3f5}
.block-container {max-width:1540px;padding-top:1.5rem}
h1,h2,h3 {color:#e7f3f5;font-family:'Segoe UI','Microsoft YaHei',sans-serif}
div[data-testid='stMetric'] {background:#102235;border:1px solid #254255;border-radius:10px;padding:.65rem .9rem}
div[data-testid='stMetricLabel'] {color:#a2b9c5}
.vm-kicker {color:#39dce5;font:600 .72rem Consolas,monospace;letter-spacing:.2em}
.vm-title {font-size:clamp(2rem,4vw,3.5rem);font-weight:700;letter-spacing:-.045em;margin:.1rem 0}
.vm-title span {color:#39dce5}
.vm-sub {color:#a3b9c5;margin-bottom:1rem}
.vm-tag {display:inline-block;border:1px solid #27707b;color:#8fe8e9;border-radius:20px;padding:.28rem .7rem;font-size:.72rem}
.vm-rule {border-top:1px solid #254255;margin:1.1rem 0}
.vm-answer {border-left:2px solid #39dce5;padding:.2rem 0 .2rem 1rem;line-height:1.8;color:#d4e5eb}
div[data-testid='stChatMessage'] {background:#0e2232;border:1px solid #244456;border-radius:12px}
div[data-testid='stChatInput'] {border:1px solid #28717a;border-radius:12px}
</style>""", unsafe_allow_html=True)

@st.cache_data
def demo_data():
    rng = np.random.default_rng(20261118)
    dates = pd.date_range("2010-01-01", "2025-12-01", freq="MS")
    market = rng.normal(.004, .045, len(dates))
    rows = []
    for board, bias in [("主板", .001), ("创业板", -.001), ("科创板", 0)]:
        for decile in range(1, 11):
            returns = market * (.7 + decile*.06) + (6-decile)*.0013 + bias + rng.normal(0, .013+decile*.001, len(dates))
            rows += [(date, board, decile, float(ret)) for date, ret in zip(dates, returns) if board != "科创板" or date.year >= 2020]
    return pd.DataFrame(rows, columns=["date", "board", "decile", "ret"])

def style(chart):
    return chart.configure_view(strokeOpacity=0).configure_axis(labelColor=MUTED,titleColor=MUTED,gridColor="#234052",domainColor="#315164",tickColor="#315164").configure_legend(labelColor="#b7cbd3",titleColor="#b7cbd3",orient="bottom")

st.markdown('<div class="vm-kicker">MARKET RESEARCH / INTERACTIVE LAB</div><div class="vm-title">Volatility <span>Mirage</span></div><div class="vm-sub">A股低波动异象交互研究台 · 从风险收益倒挂到可验证的证据</div><span class="vm-tag">界面原型 · 全部数据均为模拟生成</span><div class="vm-rule"></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("实验参数")
    start, end = st.slider("样本年份", 2010, 2025, (2010, 2025))
    board = st.selectbox("板块", ["全市场", "主板", "创业板", "科创板"])
    measure = st.selectbox("波动率口径", ["历史波动率", "特质波动率 IVOL"])
    weight = st.radio("组合权重", ["等权", "市值加权"], horizontal=True)

data = demo_data()
data = data[data.date.dt.year.between(start, end)].copy()
if board != "全市场":
    data = data[data.board == board].copy()
if data.empty:
    st.info("这个筛选组合没有模拟样本，请扩大时间范围。")
    st.stop()
if measure == "特质波动率 IVOL":
    data["decile"] = 11 - data["decile"]
if weight == "市值加权":
    data["ret"] += -.0015 + data["decile"]*.0002
monthly = data.groupby(["date", "decile"], as_index=False)["ret"].mean().sort_values(["decile", "date"])
monthly["value"] = monthly.groupby("decile")["ret"].transform(lambda s: (1+s).cumprod())
monthly["组合"] = monthly.decile.map({1:"低波组合 D1",10:"高波组合 D10"})
wide = monthly.pivot(index="date", columns="decile", values="ret")
spread = wide[1]-wide[10]
ranked = monthly.groupby("decile", as_index=False).ret.mean()
ranked["annual"] = ((1+ranked.ret)**12-1)*100
ranked["组别"] = ranked.decile.map(lambda n:f"D{n}")
ranked["色组"] = ranked.decile.map(lambda n:"低波" if n == 1 else "高波" if n == 10 else "中间组")
heat = spread.rename("spread").reset_index()
heat["年份"] = heat.date.dt.year.astype(str)
heat["季度"] = "Q"+heat.date.dt.quarter.astype(str)
heat = heat.groupby(["年份","季度"],as_index=False).spread.sum()
heat["spread"] *= 100

line_chart = style(alt.Chart(monthly[monthly.decile.isin([1,10])]).mark_line(strokeWidth=2.6).encode(
    x=alt.X("date:T",title="日期"),y=alt.Y("value:Q",title="累计净值（起点=1）",scale=alt.Scale(zero=False)),
    color=alt.Color("组合:N",scale=alt.Scale(domain=["低波组合 D1","高波组合 D10"],range=[CYAN,CORAL])),
    tooltip=[alt.Tooltip("date:T",format="%Y-%m"),"组合:N",alt.Tooltip("value:Q",format=".3f")]).properties(height=320))
bar_chart = style(alt.Chart(ranked).mark_bar().encode(
    x=alt.X("组别:N",sort=[f"D{i}" for i in range(1,11)],title="波动率十分位（D1最低）"),
    y=alt.Y("annual:Q",title="模拟年化收益率（%）"),
    color=alt.Color("色组:N",scale=alt.Scale(domain=["低波","中间组","高波"],range=[CYAN,"#38798b",CORAL]),legend=None),
    tooltip=["组别:N",alt.Tooltip("annual:Q",format=".2f")]).properties(height=220))
heat_chart = style(alt.Chart(heat).mark_rect().encode(
    x=alt.X("季度:N",sort=["Q1","Q2","Q3","Q4"]),y=alt.Y("年份:N",sort="descending"),
    color=alt.Color("spread:Q",title="低波－高波（百分点）",scale=alt.Scale(domainMid=0,range=[CORAL,"#234052",CYAN])),
    tooltip=["年份:N","季度:N",alt.Tooltip("spread:Q",format=".2f")]).properties(height=220))

overview, lab, evidence, audit_tab, ai = st.tabs(["概览", "交互实验", "证据中心", "数据体检", "研究助手"])
with overview:
    st.subheader("风险与收益，真的总是同向吗？")
    st.caption("图表来自固定随机种子的模拟数据，仅用于体验界面和联动，不能据此判断真实 A 股。")
    a,b,c = st.columns(3)
    a.metric("模拟月均收益差",f"{spread.mean()*100:+.2f} 个百分点")
    b.metric("模拟正收益年份",f"{int((spread.groupby(spread.index.year).sum()>0).sum())} / {spread.index.year.nunique()}")
    c.metric("模拟样本月份",f"{len(spread)} 期")
    st.markdown("#### 累计净值走势")
    st.altair_chart(line_chart,width="stretch")
    left,right = st.columns(2,gap="large")
    with left:
        st.markdown("#### 十分位收益梯度")
        st.altair_chart(bar_chart,width="stretch")
    with right:
        st.markdown("#### 分季度稳健性地图")
        st.altair_chart(heat_chart,width="stretch")
with lab:
    st.subheader("改变设定，观察图表如何变化")
    st.write(f"当前参数：{start}—{end} · {board} · {measure} · {weight}。展开左侧参数面板即可切换。")
    st.altair_chart(line_chart,width="stretch")
    st.altair_chart(bar_chart,width="stretch")
with evidence:
    st.subheader("从现象走向证据")
    st.altair_chart(heat_chart,width="stretch")
    st.info("真实数据接入后在此显示显著性检验、风险调整 Alpha、IVOL 回归和稳健性。当前没有实证统计量。")
with audit_tab:
    st.subheader("真实数据小样本体检")
    st.write("先验证字段、日期和缺失，再扩大到全市场。这一页与前面的模拟图表相互独立。")
    audit_path = Path(__file__).parent / "data" / "raw" / "pilot" / "audit.json"
    if audit_path.exists():
        audit_rows = json.loads(audit_path.read_text(encoding="utf-8"))
        st.dataframe(pd.DataFrame(audit_rows), width="stretch", hide_index=True)
        st.caption("来源：本机 Tushare 小样本探针；原始记录保存在 Git 忽略目录。它只能证明所测字段可用，尚不能支持低波异象结论。")
    else:
        st.info("此环境尚无本地探针结果。按 docs/data-sources.md 的步骤配置 TUSHARE_TOKEN 后运行 scripts/probe_tushare.py。")
with ai:
    title_col, clear_col = st.columns([5, 1])
    title_col.subheader("研究助手 · 自由对话")
    if clear_col.button("清空对话", use_container_width=True):
        st.session_state.research_history = []
        st.rerun()
    st.caption("可以自由提问和连续追问。助手会读取左侧实验参数及当前图表指标；这些指标目前全部来自模拟数据。")
    try:
        stored_key = st.secrets.get("OPENROUTER_API_KEY", "")
    except (FileNotFoundError, OSError):
        stored_key = ""
    import os
    with st.expander("连接免费 AI 模型", expanded=not bool(stored_key or os.getenv("OPENROUTER_API_KEY"))):
        st.write("使用 OpenRouter 免费模型路由。密钥仅用于当前浏览器会话；部署者也可通过环境变量或 Streamlit Secrets 配置。")
        entered_key = st.text_input("OpenRouter API Key", type="password", key="openrouter_key", placeholder="粘贴你在 OpenRouter 创建的 API Key")
        st.markdown("[获取免费 API Key](https://openrouter.ai/keys) · [免费模型与额度说明](https://openrouter.ai/collections/free-models/)")
    api_key = entered_key or stored_key or os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        st.info("填写 OpenRouter API Key 后即可发送消息。免费模型有调用次数限制。")
    if "research_history" not in st.session_state:
        st.session_state.research_history = []
    history = st.session_state.research_history
    if not history:
        with st.chat_message("assistant", avatar="📊"):
            st.write("你好，我可以根据当前筛选条件解释图表、讨论低波动异象的检验方法，也能接着你的问题追问。你想从哪里开始？")
    for item in history:
        with st.chat_message(item["role"], avatar="📊" if item["role"] == "assistant" else None):
            st.write(item["content"])
    prompt = st.chat_input("例如：低波组合的优势在当前参数下有多大？", disabled=not bool(api_key))
    if prompt:
        history.append({"role": "user", "content": prompt[:1600]})
        with st.chat_message("user"):
            st.write(prompt)
        evidence_pack = build_evidence(start, end, board, measure, weight, spread, ranked)
        with st.chat_message("assistant", avatar="📊"):
            with st.spinner("正在分析当前实验结果…"):
                try:
                    answer = ask_free_model(api_key, history, evidence_pack)
                except (RuntimeError, ValueError) as exc:
                    st.error(str(exc))
                else:
                    st.write(answer)
                    history.append({"role": "assistant", "content": answer})
