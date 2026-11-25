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
from forecast import project_spread, walk_forward_error
from research_chat import build_evidence, explain_without_model, stream_deepseek

st.set_page_config(page_title="Volatility Mirage", page_icon="◈", layout="wide")
with st.sidebar:
    theme_name = st.radio("页面颜色", ["夜航深色", "晨光浅色"], horizontal=True, key="site_theme")
light = theme_name == "晨光浅色"
palette = ({"bg": "#f2ede4", "surface": "#fbf7ef", "surface2": "#e8e2d7", "text": "#273e43", "muted": "#667b78", "border": "#d6cdbf", "accent": "#2d7d82", "coral": "#b96f5d", "grid": "#e1d8c9"} if light else
           {"bg": "#07131f", "surface": "#10283a", "surface2": "#0a1b2a", "text": "#e7f3f5", "muted": "#a0bac5", "border": "#285064", "accent": "#39dce5", "coral": "#f08876", "grid": "#274355"})
CYAN, CORAL, MUTED = palette["accent"], palette["coral"], palette["muted"]
css = """
<style>
.stApp,[data-testid='stAppViewContainer']{background:__BG__;color:__TEXT__}
header[data-testid='stHeader']{background:transparent}
.block-container{max-width:1380px;padding-top:2rem;padding-bottom:4rem}
section[data-testid='stSidebar']{background:__SIDE__;border-right:1px solid __BORDER__}
.stApp p,.stApp label,.stApp li,.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp [data-testid='stCaptionContainer']{color:__TEXT__}
.stApp [data-testid='stCaptionContainer'],.stApp small{opacity:.78}
div[data-testid='stTabs'] button{color:__MUTED__;font-weight:650;letter-spacing:.01em;padding:.75rem 1.1rem}
div[data-testid='stTabs'] button[aria-selected='true']{color:__ACCENT__}
div[data-testid='stMetric']{background:__SURFACE__;border:1px solid __BORDER__;border-radius:16px;padding:.8rem 1rem}
div[data-testid='stMetricValue']{color:__TEXT__}
div[data-baseweb='select']>div,div[data-testid='stChatInput']{background:__SURFACE__;color:__TEXT__;border:1px solid __BORDER__;border-radius:14px}
div[data-testid='stChatInput'] textarea{color:__TEXT__}
div[data-testid='stChatMessage']{background:__SURFACE__;border:1px solid __BORDER__;border-radius:16px;margin:.75rem 0}
div[data-testid='stChatMessageAvatar'] img{border-radius:50%;border:2px solid __BORDER__;background:__SURFACE2__}
.vm-hero{position:relative;overflow:hidden;background:linear-gradient(115deg,__SURFACE__ 55%,__SURFACE2__);border:1px solid __BORDER__;border-radius:22px;padding:1.35rem 1.8rem;margin:.25rem 0 1.8rem;box-shadow:0 14px 35px rgba(0,0,0,.08)}
.vm-hero:before{content:'';position:absolute;left:0;top:0;bottom:0;width:5px;background:__ACCENT__}
.vm-brand{color:__ACCENT__;font:700 .7rem Consolas,monospace;letter-spacing:.22em;margin-bottom:.35rem}
.vm-headline{font-size:clamp(1.55rem,3vw,2.6rem);line-height:1.2;font-weight:760;color:__TEXT__;letter-spacing:-.03em}
.vm-headline em{color:__ACCENT__;font-style:normal}
.vm-sub{color:__MUTED__;margin-top:.55rem;font-size:.91rem}
.vm-tag{display:inline-block;border:1px solid __BORDER__;color:__ACCENT__;background:__SURFACE__;border-radius:999px;padding:.33rem .75rem;font-size:.78rem;margin-bottom:.5rem}
.vm-intro{color:__MUTED__;line-height:1.75;max-width:850px;margin:.25rem 0 1.1rem}
.vm-note{background:__SURFACE__;border:1px solid __BORDER__;border-radius:14px;padding:1rem 1.2rem;color:__TEXT__;line-height:1.7;margin:.8rem 0}
.vm-thinking{display:inline-flex;align-items:center;gap:.35rem;color:__ACCENT__;background:__SURFACE2__;border:1px solid __BORDER__;border-radius:999px;padding:.5rem .9rem;font-size:.85rem}
.vm-dot{width:6px;height:6px;background:__ACCENT__;border-radius:50%;animation:vm-pulse 1.2s infinite ease-in-out}
.vm-dot:nth-child(2){animation-delay:.18s}.vm-dot:nth-child(3){animation-delay:.36s}
@keyframes vm-pulse{0%,70%,100%{opacity:.25;transform:translateY(0)}35%{opacity:1;transform:translateY(-4px)}}
</style>"""
for token, value in {"__BG__": palette["bg"], "__SIDE__": palette["surface2"], "__SURFACE__": palette["surface"], "__SURFACE2__": palette["surface2"], "__TEXT__": palette["text"], "__MUTED__": palette["muted"], "__BORDER__": palette["border"], "__ACCENT__": palette["accent"]}.items():
    css = css.replace(token, value)
st.markdown(css, unsafe_allow_html=True)
if light:
    st.markdown("""<style>
    .stApp button[data-testid='stBaseButton-secondary']{background:#fbf7ef!important;color:#273e43!important;border:1px solid #d6cdbf!important}
    .stApp button[data-testid='stBaseButton-primary']{background:#2d7d82!important;color:#fff!important;border:1px solid #2d7d82!important}
    .stApp [data-rac][role='group'],.stApp [data-testid='stChatInput']>div:first-child{background:#fbf7ef!important;color:#273e43!important;border:1px solid #d6cdbf!important}
    .stApp input[role='combobox'],.stApp [data-testid='stChatInputTextArea']{color:#273e43!important}
    .stApp input::placeholder,.stApp textarea::placeholder{color:#71827d!important;opacity:1}
    .stApp [data-testid='stTooltipIcon']{color:#667b78!important}
    [role='listbox']{background:#fbf7ef!important;color:#273e43!important}
    [role='option']{color:#273e43!important}
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
    return chart.configure(background=palette["bg"]).configure_view(strokeOpacity=0).configure_axis(labelColor=MUTED,titleColor=MUTED,gridColor=palette["grid"],domainColor=palette["border"],tickColor=palette["border"]).configure_legend(labelColor=MUTED,titleColor=MUTED,orient="bottom")

public_dir = Path(__file__).parent / "data" / "public"
real_path = public_dir / "portfolio_monthly.csv"
real_available = real_path.exists()
asset_dir = Path(__file__).parent / "assets"
assistant_avatar = str(asset_dir / "assistant-cat.png")
user_avatar = str(asset_dir / "user-fox.png")
st.markdown('<div class="vm-hero"><div class="vm-brand">A-SHARE INTERACTIVE RESEARCH LAB</div><div class="vm-headline">Volatility <em>Mirage</em></div><div class="vm-sub">A 股低波动异象互动研究平台 · 看走势、做实验、试预测，再和小股一起追问“为什么”。</div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("自己动手试一试")
    source = st.radio("数据模式", ["真实研究样本", "模拟交互演示"] if real_available else ["模拟交互演示"], help="真实模式使用已采集的 100 股探索样本；模拟模式用于练习交互，不是市场结论。")
    is_real = source == "真实研究样本"
    start, end = st.slider("样本年份", 2022, 2025, (2022, 2025)) if is_real else st.slider("样本年份", 2010, 2025, (2010, 2025))
    selected_boards = st.multiselect("板块，可多选", ["主板", "创业板", "科创板"], default=["主板", "创业板", "科创板"], help="可以只看一个板块，也可以组合几个板块；这里的“全部”仍然只是当前样本。")
    if not selected_boards:
        st.info("至少选一个板块，图表才能开始工作。")
        st.stop()
    board = "全部板块" if len(selected_boards) == 3 else "、".join(selected_boards)
    measure = st.selectbox("波动率口径", ["60日历史波动率"] if is_real else ["60日历史波动率", "20日历史波动率（模拟）", "下行波动率（模拟）", "特质波动率 IVOL（模拟）"], help="波动率衡量涨跌起伏。真实样本目前只计算了 60 日口径；其他口径仅作模拟对比。")
    weight = st.selectbox("组合权重", ["等权"] if is_real else ["等权", "规模倾斜（模拟）", "低波偏重（模拟）"], help="等权是每只股票占相近比重；模拟权重只用于观察设定变化。")
    if is_real:
        st.caption("真实数据暂只有一种波动率口径和等权结果；新增口径需要重新处理个股日行情，不能凭现有汇总表补出。")
    else:
        st.caption("模拟口径通过改变风险排序演示敏感性，并非从个股日行情重新计算的真实 IVOL 或下行波动率。")

all_boards_data = pd.read_csv(real_path, parse_dates=["date"]) if is_real else demo_data()
all_boards_data = all_boards_data[all_boards_data.date.dt.year.between(start, end)].copy()
if not is_real and measure != "60日历史波动率":
    noise_scale = {"20日历史波动率（模拟）": 1.2, "下行波动率（模拟）": 2.0, "特质波动率 IVOL（模拟）": 2.8}[measure]
    rng = np.random.default_rng(20261125 + int(noise_scale * 10))
    all_boards_data["signal"] = all_boards_data.decile + rng.normal(0, noise_scale, len(all_boards_data))
    all_boards_data["decile"] = all_boards_data.groupby(["board", "date"]).signal.rank(method="first").astype(int)
if not is_real and weight == "规模倾斜（模拟）":
    all_boards_data["ret"] += -.0015 + all_boards_data.decile * .0002
if not is_real and weight == "低波偏重（模拟）":
    all_boards_data["ret"] += .0012 - all_boards_data.decile * .00018
data = all_boards_data[all_boards_data.board.isin(selected_boards)].copy()
if data.empty:
    st.info("这个组合暂时没有观测，试试扩大年份或换个板块。")
    st.stop()
if "n" not in data:
    data["n"] = 1
source_note = "Tushare Pro · 100 股探索样本" if is_real else "模拟数据 · 用于学习交互"
st.markdown(f'<span class="vm-tag">{source_note}</span>', unsafe_allow_html=True)
if is_real:
    st.caption("真实样本截至 2025 年 12 月；它能帮助我们练习检验问题，不能代替今天的全市场行情。")
else:
    st.caption("这组数字由程序生成，适合试参数、学方法；别把它当作真实 A 股结论。")
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
    color=alt.Color("色组:N",scale=alt.Scale(domain=["低波","中间组","高波"],range=[CYAN,palette["muted"],CORAL]),legend=None),
    tooltip=["组别:N",alt.Tooltip("annual:Q",format=".2f")]).properties(height=220))
heat_chart = style(alt.Chart(heat).mark_rect().encode(
    x=alt.X("季度:N",sort=["Q1","Q2","Q3","Q4"]),y=alt.Y("年份:N",sort="descending"),
    color=alt.Color("spread:Q",title="低波－高波（百分点）",scale=alt.Scale(domainMid=0,range=[CORAL,palette["surface2"],CYAN])),
    tooltip=["年份:N","季度:N",alt.Tooltip("spread:Q",format=".2f")]).properties(height=220))

overview, lab, evidence, ai = st.tabs(["发现与实验", "预测挑战", "证据与数据", "小股研究室"])
with overview:
    st.subheader("先看一眼：低波和高波，谁走得更远？")
    st.markdown('<div class="vm-intro">D1 是过去波动较小的一组，D10 是波动较大的一组。先看两组的路径，再用下面的控件换板块、换对照组，看看结论会不会变。</div>', unsafe_allow_html=True)
    a,b,c = st.columns(3)
    a.metric("月均差（百分点）",f"{spread.mean()*100:+.2f}", help="百分点是两个百分数相减的差，例如 3% 减 2% 等于 1 个百分点。")
    b.metric("D1 领先的年份",f"{int((spread.groupby(spread.index.year).sum()>0).sum())} / {spread.index.year.nunique()}")
    c.metric("可比较的月份",f"{len(spread)} 期")
    st.markdown("#### 两组的累计走势")
    st.altair_chart(line_chart,width="stretch")
    left,right = st.columns(2,gap="large")
    with left:
        st.markdown("#### 十组收益，排成一列")
        st.altair_chart(bar_chart,width="stretch")
    with right:
        st.markdown("#### 哪些季度出现反转？")
        st.altair_chart(heat_chart,width="stretch")
with overview:
    st.subheader("换个设定，答案会变吗？")
    st.caption(f"当前：{start}—{end} · {board} · {measure} · {weight}。左侧还能多选板块。")
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
    st.markdown("#### 三个板块，结果一样吗？")
    comparison = all_boards_data.groupby(["board", "date", "decile"], as_index=False).ret.mean()
    comparison = comparison[comparison.decile.isin([1, 10])].pivot(index=["board", "date"], columns="decile", values="ret").dropna().reset_index()
    comparison["spread"] = (comparison[1] - comparison[10]) * 100
    comparison = comparison.groupby("board", as_index=False).agg(spread=("spread", "mean"), months=("spread", "size"))
    st.altair_chart(style(alt.Chart(comparison).mark_bar().encode(
        x=alt.X("board:N", title="板块"), y=alt.Y("spread:Q", title="月均收益差（百分点）"),
        color=alt.condition(alt.datum.spread >= 0, alt.value(CYAN), alt.value(CORAL)),
        tooltip=["board:N", alt.Tooltip("spread:Q", format="+.2f"), "months:Q"]).properties(height=220)), width="stretch")
    st.caption("板块图比较的是当前年份内各板块的月均差；即使只勾选一个板块，这里也会保留另外两个作参照。")
with lab:
    st.subheader("下一观察期，会怎样？")
    st.markdown('<div class="vm-intro">来做个教学用的预测实验：从已有月份的 D1－D10 收益差里抽样，看看不同未来情景可能落在哪个范围。它研究的是<strong>组合差</strong>，不是今天 A 股指数的涨跌，也不用于买卖决策。</div>', unsafe_allow_html=True)
    fc1, fc2 = st.columns(2)
    horizon = fc1.slider("向前看几个月？", 1, 6, 3)
    lookback = fc2.slider("参考最近多少个月？", 6, min(60, len(spread)), min(24, len(spread)))
    projection = project_spread(spread, horizon, lookback)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("中心值", f"{projection['point_pp']:+.2f}")
    p2.metric("80% 范围下沿", f"{projection['low_pp']:+.2f}")
    p3.metric("80% 范围上沿", f"{projection['high_pp']:+.2f}")
    p4.metric("参考月份", projection["months_used"])
    st.caption("前三个数字的单位都是百分点；范围来自重复抽取历史月份，不是未来结果的保证。")
    samples = pd.DataFrame({"未来收益差": projection["draws"]})
    st.altair_chart(style(alt.Chart(samples).mark_bar(color=CYAN, opacity=.75).encode(
        x=alt.X("未来收益差:Q", bin=alt.Bin(maxbins=30), title=f"未来 {horizon} 个月 D1－D10 累计差（百分点）"),
        y=alt.Y("count():Q", title="抽样次数")).properties(height=260)), width="stretch")
    st.caption(f"做法：只取截至 {projection['last_month']} 的最近 {lookback} 个月，重复抽取 4000 组月度差值。阴影范围不是保证；未来市场可能完全不同。")
    backtest = walk_forward_error(spread)
    if backtest["tests"]:
        st.markdown(f'<div class="vm-note"><b>先检验一下：</b>用过去 12 个月均值猜下个月，在 {backtest["tests"]} 次历史回看中，平均猜错约 <b>{backtest["mae_pp"]:.2f} 个百分点</b>；如果每次都猜 0，平均误差是 <b>{backtest["zero_mae_pp"]:.2f} 个百分点</b>。误差越小越好，但它不保证未来也如此。</div>', unsafe_allow_html=True)
    st.divider()
    st.subheader("小游戏：波动侦探")
    st.write("只看前 3 个月，猜下一月 D1 还是 D10 领先。猜完就揭晓，看看历史走势有多会‘骗人’。")
    game_key = (source, start, end, board, measure, weight)
    if st.session_state.get("game_key") != game_key:
        st.session_state.game_key = game_key
        st.session_state.game_index = 0
        st.session_state.game_score = 0
        st.session_state.game_count = 0
        st.session_state.game_revealed = False
    if len(spread) >= 4:
        index = st.session_state.game_index % (len(spread) - 3)
        recent_three = spread.iloc[index:index + 3]
        target_month = spread.index[index + 3]
        actual_gap = spread.iloc[index + 3] * 100
        st.markdown(f'<div class="vm-note">线索：前 3 个月 D1－D10 合计 <b>{recent_three.sum()*100:+.2f} 个百分点</b>。下一关是 <b>{target_month:%Y 年 %m 月}</b>。</div>', unsafe_allow_html=True)
        guess = st.radio("你的直觉？", ["D1 低波领先", "D10 高波领先"], horizontal=True)
        if not st.session_state.game_revealed and st.button("揭晓答案", type="primary"):
            st.session_state.game_revealed = True
            st.session_state.game_count += 1
            if (actual_gap >= 0 and guess.startswith("D1")) or (actual_gap < 0 and guess.startswith("D10")):
                st.session_state.game_score += 1
        if st.session_state.game_revealed:
            winner = "D1 低波" if actual_gap >= 0 else "D10 高波"
            st.info(f"揭晓：{winner}领先，实际差值 {actual_gap:+.2f} 个百分点。历史的三个月给了线索，却没法保证下一月。你已猜对 {st.session_state.game_score}/{st.session_state.game_count} 题。")
            if st.button("再来一题"):
                st.session_state.game_index += 1
                st.session_state.game_revealed = False
                st.rerun()
    else:
        st.info("这个筛选结果不足 4 个月，换个年份就能玩。")
with evidence:
    st.subheader("证据到底有多强？")
    st.write("一张图看起来很有说服力，但我们还得问：差距有多大、持续了多久、会不会只是样本碰巧如此？")
    s1, s2, s3 = st.columns(3)
    s1.metric("月均差距", f"{spread_stats['mean']*100:+.2f} 个百分点", help="D1 月收益减 D10 月收益，再对月份取平均。")
    s2.metric("统计检验 t 值", f"{spread_stats['t']:+.2f}", help="t 值衡量样本差距相对估计误差的大小；不能单凭它证明因果。")
    s3.metric("95% 近似区间", f"[{spread_stats['ci_low']*100:+.2f}, {spread_stats['ci_high']*100:+.2f}]", help="区间表示估计的不确定性；如果跨过 0，当前样本不足以排除零差异。")
    with st.expander("先读懂这几个词：十分位、区间、滚动窗口"):
        st.write("**十分位**：按波动率从小到大排队，分成十组；D1 最低，D10 最高。")
        st.write("**95% 近似区间**：用一种统计方法给月均差画出可能范围。它不是‘未来有 95% 概率落在这里’。")
        st.write("**滚动 12 个月**：每往后走一个月，重新汇总最近 12 个月；相邻窗口会共享大多数月份。")
        st.write("**Newey–West**：一种修正标准误的方法，考虑月度数据前后可能相关。想深挖可展开下面的统计口径。")
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
        st.markdown("#### 哪些年份 D1 领先？")
        annual_chart = style(alt.Chart(annual_spread).mark_bar().encode(
            x=alt.X("year:O", title="年份"), y=alt.Y("spread:Q", title="低波－高波（百分点）"),
            color=alt.condition(alt.datum.spread >= 0, alt.value(CYAN), alt.value(CORAL)),
            tooltip=["year:O", alt.Tooltip("spread:Q", format="+.2f"), "months:Q"]).properties(height=260))
        st.altair_chart(annual_chart, width="stretch")
    with right:
        st.markdown("#### 优势有没有持续？")
        rolling_chart = style(alt.Chart(rolling_spread).mark_line(color=CYAN, strokeWidth=2).encode(
            x=alt.X("date:T", title="日期"), y=alt.Y("spread:Q", title="12 个月收益差（百分点）"),
            tooltip=[alt.Tooltip("date:T", format="%Y-%m"), alt.Tooltip("spread:Q", format="+.2f")]).properties(height=260))
        st.altair_chart(rolling_chart, width="stretch")
    st.markdown("#### 再缩小到季度看看")
    st.altair_chart(heat_chart, width="stretch")
    with st.expander("想看严谨做法？展开统计口径"):
        st.write("年度和滚动收益差为月度 D1－D10 收益差的算术和；区间为 Newey–West（Bartlett 核、最多 6 阶滞后）标准误构造的正态近似区间。月份重叠会影响滚动曲线的独立性。")
        st.write("全市场结论仍需扩大历史样本、重建历史 ST 状态、风险因子调整及更充分的子样本检验。")
with evidence:
    st.divider()
    if real_available:
        meta = json.loads((public_dir / "metadata.json").read_text(encoding="utf-8"))
        st.subheader("这份数据从哪里来？")
        m1, m2, m3 = st.columns(3)
        m1.metric("原始抽样股票", meta["selected_stocks"])
        m2.metric("用于分组的记录", meta["formation_rows"])
        m3.metric("收益数据截止", meta["last_return_month"])
        st.write("来源是 Tushare Pro。我们从主板、创业板和科创板各抽取一部分股票；每个月末先按过去 60 个交易日的波动率排队，再看下个月收益。这样不会把未来数据偷放进排序。")
        st.info("样本只有 100 只股票，且历史 ST 状态、风险因子和交易成本仍未充分处理；这些结果适合探索，不等于整个 A 股市场的结论。")
        st.download_button("下载月度组合汇总 CSV", real_path.read_bytes(), "volatility_mirage_portfolio_monthly.csv", "text/csv")
    st.markdown("#### 数据体检记录")
    st.write("正式分析前，我们先检查日期、字段和缺失值。这里展示的是本机的小样本探针记录。")
    audit_path = Path(__file__).parent / "data" / "raw" / "pilot" / "audit.json"
    if audit_path.exists():
        audit_rows = json.loads(audit_path.read_text(encoding="utf-8"))
        st.dataframe(pd.DataFrame(audit_rows), width="stretch", hide_index=True)
        st.caption("探针只验证数据能否正确读取；两只股票还不足以研究整个市场。")
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
            st.caption("这张图只看两只股票的价格路径，不能据此判断低波异象。")
    else:
        st.info("这个环境还没有本地探针记录，但上面的公开月度汇总仍可查看。")
with ai:
    if st.session_state.get("research_chat_version") != 3:
        previous_chat = st.session_state.get("research_history", [])
        if previous_chat:
            st.session_state.research_legacy_history = st.session_state.get("research_legacy_history", []) + previous_chat
        st.session_state.research_history = []
        st.session_state.research_chat_version = 3
    title_col, clear_col = st.columns([5, 1])
    title_col.subheader("小股研究室 ✦")
    if clear_col.button("清空对话", use_container_width=True):
        st.session_state.research_history = []
        st.rerun()
    st.write("看到不懂的图，直接问小股；也可以连续追问，或者先点一个灵感问题。")
    try:
        stored_key = st.secrets.get("DEEPSEEK_API_KEY", "")
    except (FileNotFoundError, OSError):
        stored_key = ""
    api_key = stored_key or os.getenv("DEEPSEEK_API_KEY", "")
    st.caption("DeepSeek 对话已开启 · 项目不设消息次数上限" if api_key else "当前为内置解读模式 · 配置模型服务后可自由对话")
    if "research_history" not in st.session_state:
        st.session_state.research_history = []
    if "research_session_id" not in st.session_state:
        st.session_state.research_session_id = uuid.uuid4().hex
    history = st.session_state.research_history
    with st.expander("不认识 D1、IVOL、Newey–West？点这里看一句话解释"):
        st.write("**D1 / D10**：按波动率分成十组后，起伏最小 / 最大的两组。**IVOL**：剔除大盘等共同波动后，股票自身剩下的起伏。**Newey–West**：一种估计误差的统计方法，考虑相邻月份可能有关联。")
    if st.session_state.get("research_legacy_history"):
        with st.expander("查看升级前的对话"):
            for old_item in st.session_state.research_legacy_history:
                st.write(("旧版助手：" if old_item["role"] == "assistant" else "你：") + old_item["content"])
    q1, q2, q3 = st.columns(3)
    quick_prompt = None
    if q1.button("📈 一句话看结论", use_container_width=True):
        quick_prompt = "用一句话概括当前筛选结果，注意数据边界"
    if q2.button("🔎 哪些年份反转？", use_container_width=True):
        quick_prompt = "哪些年份低波没有跑赢高波？请简要解释如何看年度图"
    if q3.button("📋 给我收益表", use_container_width=True):
        quick_prompt = "请展示当前十分位年化收益表，并用一句话说明怎么读"
    conversation = st.container()
    with conversation:
        if not history:
            with st.chat_message("assistant", avatar=assistant_avatar):
                st.write("嗨，我是小股 ✦！看图、试预测、找数据里的反转，都可以问我。")
        for item in history:
            with st.chat_message(item["role"], avatar=assistant_avatar if item["role"] == "assistant" else user_avatar):
                st.write(item["content"])
                if item.get("table"):
                    st.caption(item["table_caption"])
                    st.dataframe(pd.DataFrame(item["table"]), width="stretch", hide_index=True)
    typed_prompt = st.chat_input("在这里接着聊：比如‘这张图稳不稳？’", max_chars=1000)
    prompt = quick_prompt or typed_prompt
    if prompt:
        prompt = prompt[:1000]
        history.append({"role": "user", "content": prompt})
        evidence_pack = build_evidence(start, end, board, measure, weight, spread, ranked, source_note)
        with conversation:
            with st.chat_message("user", avatar=user_avatar):
                st.write(prompt)
            with st.chat_message("assistant", avatar=assistant_avatar):
                loading = st.empty()
                loading.markdown('<div class="vm-thinking">小股正在整理思路 <i class="vm-dot"></i><i class="vm-dot"></i><i class="vm-dot"></i></div>', unsafe_allow_html=True)
                try:
                    if prompt.strip().lower() in {"你好", "您好", "嗨", "哈喽", "hi", "hello", "hey"}:
                        answer = "嗨，我是小股 ✦！今天想先看哪张图？"
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
                        item["table_caption"] = f"生成时的条件：{start}—{end} · {board} · {source_note}"
                        st.caption(item["table_caption"])
                        st.dataframe(table, width="stretch", hide_index=True)
                    history.append(item)
