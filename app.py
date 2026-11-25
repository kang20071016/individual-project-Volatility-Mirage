"""Volatility Mirage interactive A-share research experience."""

import json
import os
import uuid
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from analysis import spread_diagnostics
from research_chat import build_evidence, explain_without_model, stream_deepseek

st.set_page_config(page_title="Volatility Mirage", page_icon="📈", layout="wide")
CYAN, CORAL, MUTED = "#39dce5", "#f08876", "#91a7b6"

st.markdown("""
<style>
.stApp {background-color:#07131f;background-image:radial-gradient(circle at 86% 5%,rgba(25,176,189,.13),transparent 31%),linear-gradient(rgba(58,133,151,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(58,133,151,.035) 1px,transparent 1px);background-size:auto,36px 36px,36px 36px;color:#e7f3f5}
.block-container {max-width:1540px;padding-top:1.5rem}
section[data-testid='stSidebar'] {background:#0a1b2a;border-right:1px solid #254255}
div[data-testid='stTabs'] button {font-weight:600;letter-spacing:.02em;border-radius:12px 12px 0 0}
h1,h2,h3 {color:#e7f3f5;font-family:'Segoe UI','Microsoft YaHei',sans-serif}
div[data-testid='stMetric'] {background:linear-gradient(135deg,#102235,#0c1b2b);border:1px solid #254255;border-radius:16px;padding:.85rem 1rem;box-shadow:0 12px 35px rgba(0,0,0,.14)}
div[data-testid='stMetricLabel'] {color:#a2b9c5}
.vm-kicker {color:#39dce5;font:600 .72rem Consolas,monospace;letter-spacing:.2em}
.vm-title {font-size:clamp(2rem,4vw,3.5rem);font-weight:700;letter-spacing:-.045em;margin:.1rem 0}
.vm-title span {color:#39dce5}
.vm-sub {color:#a3b9c5;margin-bottom:1rem}
.vm-tag {display:inline-block;border:1px solid #27707b;color:#8fe8e9;border-radius:20px;padding:.28rem .7rem;font-size:.72rem}
.vm-tag {box-shadow:0 0 22px rgba(57,220,229,.13)}
.vm-rule {border-top:1px solid #254255;margin:1.1rem 0}
.vm-answer {border-left:2px solid #39dce5;padding:.2rem 0 .2rem 1rem;line-height:1.8;color:#d4e5eb}
.vm-hero {position:relative;overflow:hidden;border:1px solid #256575;border-radius:24px;padding:1.6rem 2rem;background:radial-gradient(circle at 85% 30%,rgba(53,212,221,.16),transparent 31%),linear-gradient(115deg,#10283d 0%,#0b1b2d 70%);box-shadow:0 20px 60px rgba(0,0,0,.22)}
.vm-hero:after {content:'';position:absolute;right:-90px;top:-110px;width:340px;height:340px;border:1px solid rgba(57,220,229,.22);border-radius:50%;box-shadow:0 0 0 42px rgba(57,220,229,.035),0 0 0 90px rgba(57,220,229,.025);pointer-events:none}
.vm-hero .vm-title {position:relative;z-index:1}
.vm-hero .vm-sub {position:relative;z-index:1;margin-bottom:0}
.vm-step {border:1px solid #244456;border-radius:15px;padding:.75rem 1rem;background:#0d2131;color:#a8c5ce;font-size:.82rem}
.vm-step b {color:#39dce5;margin-right:.35rem}
div[data-testid='stChatMessage'] {background:linear-gradient(135deg,#0e2232,#0b1b2a);border:1px solid #244456;border-radius:18px;box-shadow:0 12px 30px rgba(0,0,0,.12)}
div[data-testid='stChatMessageAvatar'] img {border-radius:50%;border:2px solid #34727b;background:#0b1b2a}
div[data-testid='stChatInput'] {border:1px solid #28717a;border-radius:16px;box-shadow:0 0 28px rgba(57,220,229,.08)}
.vm-thinking {display:inline-flex;align-items:center;gap:.35rem;color:#9be9e7;background:#102b3a;border:1px solid #2c7880;border-radius:999px;padding:.5rem .9rem;font-size:.85rem;box-shadow:0 0 22px rgba(57,220,229,.14)}
.vm-dot {width:6px;height:6px;background:#39dce5;border-radius:50%;animation:vm-pulse 1.2s infinite ease-in-out}
.vm-dot:nth-child(2) {animation-delay:.18s}.vm-dot:nth-child(3) {animation-delay:.36s}
@keyframes vm-pulse {0%,70%,100%{opacity:.25;transform:translateY(0)}35%{opacity:1;transform:translateY(-4px)}}
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

public_dir = Path(__file__).parent / "data" / "public"
real_path = public_dir / "portfolio_monthly.csv"
real_available = real_path.exists()
asset_dir = Path(__file__).parent / "assets"
assistant_avatar = str(asset_dir / "assistant-cat.png")
user_avatar = str(asset_dir / "user-fox.png")
st.markdown('<div class="vm-hero"><div class="vm-kicker">MARKET RESEARCH / INTERACTIVE LAB</div><div class="vm-title">Volatility <span>Mirage</span></div><div class="vm-sub">A 股低波动异象交互研究台 · 探索现象，检验证据，和波波一起追问答案</div></div>', unsafe_allow_html=True)
step_a, step_b, step_c = st.columns(3)
step_a.markdown('<div class="vm-step"><b>01</b> 观察 · 发现异常走势</div>', unsafe_allow_html=True)
step_b.markdown('<div class="vm-step"><b>02</b> 实验 · 改变筛选条件</div>', unsafe_allow_html=True)
step_c.markdown('<div class="vm-step"><b>03</b> 对话 · 追问研究证据</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("实验参数")
    source = st.radio("数据模式", ["真实研究样本", "模拟交互演示"] if real_available else ["模拟交互演示"])
    is_real = source == "真实研究样本"
    start, end = st.slider("样本年份", 2022, 2025, (2022, 2025)) if is_real else st.slider("样本年份", 2010, 2025, (2010, 2025))
    board = st.selectbox("板块", ["全市场", "主板", "创业板", "科创板"])
    measure = st.selectbox("波动率口径", ["历史波动率"] if is_real else ["历史波动率", "特质波动率 IVOL"])
    weight = st.radio("组合权重", ["等权"] if is_real else ["等权", "市值加权"], horizontal=True)

data = pd.read_csv(real_path, parse_dates=["date"]) if is_real else demo_data()
data = data[data.date.dt.year.between(start, end)].copy()
all_boards_data = data.copy()
if board != "全市场":
    data = data[data.board == board].copy()
if data.empty:
    st.info("这个筛选组合没有模拟样本，请扩大时间范围。")
    st.stop()
if not is_real and measure == "特质波动率 IVOL":
    data["decile"] = 11 - data["decile"]
    all_boards_data["decile"] = 11 - all_boards_data["decile"]
if not is_real and weight == "市值加权":
    data["ret"] += -.0015 + data["decile"]*.0002
    all_boards_data["ret"] += -.0015 + all_boards_data["decile"]*.0002
if "n" not in data:
    data["n"] = 1
source_note = "Tushare Pro · 100 只股票分层抽样 · 探索性实证" if is_real else "固定随机种子生成 · 模拟演示"
st.markdown(f'<span class="vm-tag">{source_note}</span>', unsafe_allow_html=True)
if is_real:
    st.caption("真实样本采用 60 交易日历史波动率排序、下月等权收益；它是分层抽样研究，不代表全 A 股总体。")
else:
    st.caption("模拟模式仅用于体验交互和方法，不能推断真实 A 股市场。")
data["weighted_return"] = data.ret * data.n
monthly = data.groupby(["date", "decile"], as_index=False).agg(weighted_return=("weighted_return", "sum"), n=("n", "sum"))
monthly["ret"] = monthly.weighted_return / monthly.n
monthly = monthly.sort_values(["decile", "date"])
monthly["value"] = monthly.groupby("decile")["ret"].transform(lambda s: (1+s).cumprod())
monthly["组合"] = monthly.decile.map({1:"低波组合 D1",10:"高波组合 D10"})
wide = monthly.pivot(index="date", columns="decile", values="ret")
spread = (wide[1]-wide[10]).dropna()
spread_stats, annual_spread, rolling_spread = spread_diagnostics(spread)
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
    y=alt.Y("annual:Q",title="年化收益率（%）"),
    color=alt.Color("色组:N",scale=alt.Scale(domain=["低波","中间组","高波"],range=[CYAN,"#38798b",CORAL]),legend=None),
    tooltip=["组别:N",alt.Tooltip("annual:Q",format=".2f")]).properties(height=220))
heat_chart = style(alt.Chart(heat).mark_rect().encode(
    x=alt.X("季度:N",sort=["Q1","Q2","Q3","Q4"]),y=alt.Y("年份:N",sort="descending"),
    color=alt.Color("spread:Q",title="低波－高波（百分点）",scale=alt.Scale(domainMid=0,range=[CORAL,"#234052",CYAN])),
    tooltip=["年份:N","季度:N",alt.Tooltip("spread:Q",format=".2f")]).properties(height=220))

overview, lab, evidence, audit_tab, ai = st.tabs(["概览", "交互实验", "证据中心", "数据体检", "研究助手"])
with overview:
    st.subheader("风险与收益，真的总是同向吗？")
    st.caption("图表来源：" + source_note + "。实际研究结果请结合样本限制解读。")
    a,b,c = st.columns(3)
    a.metric("月均收益差",f"{spread.mean()*100:+.2f} 个百分点")
    b.metric("正收益年份",f"{int((spread.groupby(spread.index.year).sum()>0).sum())} / {spread.index.year.nunique()}")
    c.metric("样本月份",f"{len(spread)} 期")
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
    st.caption(f"当前参数：{start}—{end} · {board} · {measure} · {weight}。左侧面板可切换数据和筛选范围。")
    choice_col, window_col = st.columns(2)
    compare_decile = choice_col.selectbox("拿低波 D1 与哪一组比较？", list(range(2, 11)), index=8, format_func=lambda n: f"D{n}" + (" · 高波" if n == 10 else ""))
    roll_window = window_col.slider("观察窗口（月）", 3, 24, 12)
    pair = monthly[monthly.decile.isin([1, compare_decile])].copy()
    pair["组合"] = pair.decile.map({1: "低波 D1", compare_decile: f"对照 D{compare_decile}"})
    pair_chart = style(alt.Chart(pair).mark_line(strokeWidth=2.7).encode(
        x=alt.X("date:T", title="日期"), y=alt.Y("value:Q", title="累计净值（起点=1）", scale=alt.Scale(zero=False)),
        color=alt.Color("组合:N", scale=alt.Scale(domain=["低波 D1", f"对照 D{compare_decile}"], range=[CYAN, CORAL])),
        tooltip=[alt.Tooltip("date:T", format="%Y-%m"), "组合:N", alt.Tooltip("value:Q", format=".3f")]).properties(height=300))
    pair_spread = (wide[1] - wide[compare_decile]).dropna()
    roll_values = pair_spread.rolling(roll_window, min_periods=roll_window).sum().mul(100).dropna().rename("spread").reset_index()
    l1, l2 = st.columns(2, gap="large")
    with l1:
        st.markdown("#### 组合路径")
        st.altair_chart(pair_chart, width="stretch")
    with l2:
        st.markdown(f"#### 滚动 {roll_window} 个月收益差")
        if roll_values.empty:
            st.info("当前样本不足这个观察窗口，试试缩短月份或扩大年份。")
        else:
            st.altair_chart(style(alt.Chart(roll_values).mark_area(line={"color": CYAN}, color=CYAN, opacity=.2).encode(
                x=alt.X("date:T", title="日期"), y=alt.Y("spread:Q", title="D1－对照组（百分点）"),
                tooltip=[alt.Tooltip("date:T", format="%Y-%m"), alt.Tooltip("spread:Q", format="+.2f")]).properties(height=300)), width="stretch")
    st.caption(f"D1 对 D{compare_decile}：月均差 {pair_spread.mean()*100:+.2f} 个百分点。滚动窗口会重叠，曲线只用于观察时段变化。")
    st.markdown("#### 板块对照 · D1－D10 月均收益差")
    comparison = all_boards_data.groupby(["board", "date", "decile"], as_index=False).ret.mean()
    comparison = comparison[comparison.decile.isin([1, 10])].pivot(index=["board", "date"], columns="decile", values="ret").dropna().reset_index()
    comparison["spread"] = (comparison[1] - comparison[10]) * 100
    comparison = comparison.groupby("board", as_index=False).agg(spread=("spread", "mean"), months=("spread", "size"))
    st.altair_chart(style(alt.Chart(comparison).mark_bar().encode(
        x=alt.X("board:N", title="板块"), y=alt.Y("spread:Q", title="月均收益差（百分点）"),
        color=alt.condition(alt.datum.spread >= 0, alt.value(CYAN), alt.value(CORAL)),
        tooltip=["board:N", alt.Tooltip("spread:Q", format="+.2f"), "months:Q"]).properties(height=220)), width="stretch")
with evidence:
    st.subheader("收益差与稳健性诊断")
    st.caption("当前数据：" + source_note + "。统计量描述当前筛选样本，不可外推为全市场因果结论。")
    s1, s2, s3 = st.columns(3)
    s1.metric("低波－高波月均差", f"{spread_stats['mean']*100:+.2f} 个百分点")
    s2.metric("Newey–West t 值", f"{spread_stats['t']:+.2f}")
    s3.metric("95% 近似区间", f"[{spread_stats['ci_low']*100:+.2f}, {spread_stats['ci_high']*100:+.2f}] pp")
    report_md = f"""# Volatility Mirage · 筛选结果摘要

- 数据：{source_note}
- 筛选：{start}—{end}；{board}；{measure}；{weight}
- D1－D10 月均收益差：{spread_stats['mean']*100:+.3f} 个百分点
- Newey–West t 值：{spread_stats['t']:+.3f}
- 95% 正态近似区间：[{spread_stats['ci_low']*100:+.3f}, {spread_stats['ci_high']*100:+.3f}] 个百分点
- 有效月数：{spread_stats['n']}

方法：月末用历史波动率排序，比较低波与高波组合的下月收益；均值标准误采用 Bartlett 核、最多 6 阶滞后的 Newey–West 估计。

限制：{'100 股分层探索样本，不代表全 A 股；历史 ST 状态、风险因子和交易成本未完整处理。' if is_real else '本模式为模拟数据，不构成真实市场证据。'}
"""
    st.download_button("导出当前研究摘要", report_md, "volatility_mirage_summary.md", "text/markdown")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### 年度收益差")
        annual_chart = style(alt.Chart(annual_spread).mark_bar().encode(
            x=alt.X("year:O", title="年份"), y=alt.Y("spread:Q", title="低波－高波（百分点）"),
            color=alt.condition(alt.datum.spread >= 0, alt.value(CYAN), alt.value(CORAL)),
            tooltip=["year:O", alt.Tooltip("spread:Q", format="+.2f"), "months:Q"]).properties(height=260))
        st.altair_chart(annual_chart, width="stretch")
    with right:
        st.markdown("#### 滚动 12 个月收益差")
        rolling_chart = style(alt.Chart(rolling_spread).mark_line(color=CYAN, strokeWidth=2).encode(
            x=alt.X("date:T", title="日期"), y=alt.Y("spread:Q", title="12 个月收益差（百分点）"),
            tooltip=[alt.Tooltip("date:T", format="%Y-%m"), alt.Tooltip("spread:Q", format="+.2f")]).properties(height=260))
        st.altair_chart(rolling_chart, width="stretch")
    st.markdown("#### 分季度稳健性地图")
    st.altair_chart(heat_chart, width="stretch")
    with st.expander("统计口径与待完成检验"):
        st.write("年度和滚动收益差为月度 D1－D10 收益差的算术和；区间为 Newey–West（Bartlett 核、最多 6 阶滞后）标准误构造的正态近似区间。月份重叠会影响滚动曲线的独立性。")
        st.write("全市场结论仍需扩大历史样本、重建历史 ST 状态、风险因子调整及更充分的子样本检验。")
with audit_tab:
    if real_available:
        meta = json.loads((public_dir / "metadata.json").read_text(encoding="utf-8"))
        st.subheader("100 只股票探索样本 · 数据说明")
        m1, m2, m3 = st.columns(3)
        m1.metric("成功采集股票", meta["fetched_stocks"])
        m2.metric("形成组合的观测", meta["formation_rows"])
        m3.metric("组合收益月份", f"{meta['first_return_month']} 至 {meta['last_return_month']}")
        st.caption("Tushare Pro；固定种子 REDACTED 分层随机抽样（主板 50、创业板 25、科创板 25）。60 个交易日历史波动率在月末排序，使用下月复权收益，避免未来信息进入排序。")
        st.warning("限制：100 只股票不是全市场；当前名称筛选无法还原历史 ST 时段；仅等权、未做因子调整。故结果是探索性证据。")
        st.download_button("下载月度组合汇总 CSV", real_path.read_bytes(), "volatility_mirage_portfolio_monthly.csv", "text/csv")
    st.subheader("真实数据小样本体检")
    st.write("先验证字段、日期和缺失，再扩大到全市场。这一页与前面的模拟图表相互独立。")
    audit_path = Path(__file__).parent / "data" / "raw" / "pilot" / "audit.json"
    if audit_path.exists():
        audit_rows = json.loads(audit_path.read_text(encoding="utf-8"))
        st.dataframe(pd.DataFrame(audit_rows), width="stretch", hide_index=True)
        st.caption("来源：本机 Tushare 小样本探针；原始记录保存在 Git 忽略目录。它只能证明所测字段可用，尚不能支持低波异象结论。")
        pilot_frames = []
        for path in sorted(audit_path.parent.glob("*_*.csv")):
            frame = pd.read_csv(path, usecols=["trade_date", "ts_code", "adjusted_close"], parse_dates=["trade_date"])
            frame = frame.dropna(subset=["adjusted_close"]).sort_values("trade_date")
            if not frame.empty and frame.adjusted_close.iloc[0] != 0:
                frame["relative_close"] = frame.adjusted_close / frame.adjusted_close.iloc[0]
                pilot_frames.append(frame)
        if pilot_frames:
            st.markdown("#### 两只股票的复权价格路径（真实小样本）")
            pilot = pd.concat(pilot_frames, ignore_index=True)
            pilot_chart = style(alt.Chart(pilot).mark_line(strokeWidth=2).encode(
                x=alt.X("trade_date:T", title="交易日"), y=alt.Y("relative_close:Q", title="区间首日归一化价格（=1）", scale=alt.Scale(zero=False)),
                color=alt.Color("ts_code:N", title="股票代码"),
                tooltip=["ts_code:N", alt.Tooltip("trade_date:T", format="%Y-%m-%d"), alt.Tooltip("relative_close:Q", format=".3f")]).properties(height=260))
            st.altair_chart(pilot_chart, width="stretch")
            st.caption("只展示本机 Tushare 探针采集的个股价格路径；两只股票不能构造有效的十分位组合或支持总体推断。")
    else:
        st.info("此环境尚无本地探针结果。按 docs/data-sources.md 的步骤配置 TUSHARE_TOKEN 后运行 scripts/probe_tushare.py。")
with ai:
    if st.session_state.get("research_chat_version") != 2:
        previous_chat = st.session_state.get("research_history", [])
        if previous_chat:
            st.session_state.research_legacy_history = previous_chat
        st.session_state.research_history = []
        st.session_state.research_chat_version = 2
    title_col, clear_col = st.columns([5, 1])
    title_col.subheader("和波波一起研究 🐱")
    if clear_col.button("清空对话", use_container_width=True):
        st.session_state.research_history = []
        st.session_state.research_legacy_history = []
        st.rerun()
    st.caption("自由提问、连续追问，或者点一个灵感问题。波波会结合当前筛选结果回答。")
    try:
        stored_key = st.secrets.get("DEEPSEEK_API_KEY", "")
    except (FileNotFoundError, OSError):
        stored_key = ""
    api_key = stored_key or os.getenv("DEEPSEEK_API_KEY", "")
    st.caption("✨ DeepSeek 对话已开启" if api_key else "内置证据解读模式 · 配置模型服务后可开放式对话")
    if "research_history" not in st.session_state:
        st.session_state.research_history = []
    if "research_session_id" not in st.session_state:
        st.session_state.research_session_id = uuid.uuid4().hex
    history = st.session_state.research_history
    if not history:
        with st.chat_message("assistant", avatar=assistant_avatar):
            st.write("嗨，我是波波 🐱！想先看走势、找反转年份，还是问问数据靠不靠谱？")
    for item in history:
        with st.chat_message(item["role"], avatar=assistant_avatar if item["role"] == "assistant" else user_avatar):
            st.write(item["content"])
            if item.get("table"):
                st.caption(item["table_caption"])
                st.dataframe(pd.DataFrame(item["table"]), width="stretch", hide_index=True)
    q1, q2, q3 = st.columns(3)
    quick_prompt = None
    if q1.button("📈 一句话看结论", use_container_width=True):
        quick_prompt = "用一句话概括当前筛选结果，注意数据边界"
    if q2.button("🔎 哪些年份反转？", use_container_width=True):
        quick_prompt = "哪些年份低波没有跑赢高波？请简要解释如何看年度图"
    if q3.button("📋 给我收益表", use_container_width=True):
        quick_prompt = "请展示当前十分位年化收益表，并用一句话说明怎么读"
    prompt = quick_prompt or st.chat_input("问波波：比如‘这个结果稳不稳？’", max_chars=1000)
    if prompt:
        prompt = prompt[:1000]
        history.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=user_avatar):
            st.write(prompt)
        evidence_pack = build_evidence(start, end, board, measure, weight, spread, ranked, source_note)
        with st.chat_message("assistant", avatar=assistant_avatar):
            loading = st.empty()
            loading.markdown('<div class="vm-thinking">波波正在想 <i class="vm-dot"></i><i class="vm-dot"></i><i class="vm-dot"></i></div>', unsafe_allow_html=True)
            try:
                if prompt.strip().lower() in {"你好", "您好", "嗨", "哈喽", "hi", "hello", "hey"}:
                    answer = "嗨，我是波波 🐱！今天想一起研究哪张图？"
                    loading.empty()
                    st.write(answer)
                elif api_key:
                    def answer_chunks():
                        first = True
                        for chunk in stream_deepseek(api_key, history, evidence_pack, st.session_state.research_session_id):
                            if first:
                                loading.empty()
                                first = False
                            yield chunk
                    answer = st.write_stream(answer_chunks())
                else:
                    answer = explain_without_model(history, evidence_pack)
                    loading.empty()
                    st.write(answer)
            except (RuntimeError, ValueError) as exc:
                loading.empty()
                history.pop()
                st.error(str(exc))
            else:
                item = {"role": "assistant", "content": answer}
                if any(word in prompt for word in ("表格", "收益表", "收益率表", "年度表", "数据表", "列表")):
                    if any(word in prompt for word in ("年度", "年份", "逐年")):
                        table = annual_spread[["year", "spread", "months"]].rename(columns={"year": "年份", "spread": "D1－D10 收益差（百分点）", "months": "样本月数"}).round(2)
                    else:
                        table = ranked[["组别", "annual"]].rename(columns={"annual": "年化收益率（%）"}).round(2)
                    item["table"] = table.to_dict("records")
                    item["table_caption"] = f"按生成时筛选条件计算：{start}—{end} · {board} · {source_note}"
                    st.caption(item["table_caption"])
                    st.dataframe(table, width="stretch", hide_index=True)
                history.append(item)
    if st.session_state.get("research_legacy_history"):
        with st.expander("查看升级前的对话"):
            for old_item in st.session_state.research_legacy_history:
                st.write(("波波：" if old_item["role"] == "assistant" else "你：") + old_item["content"])
