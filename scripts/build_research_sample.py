"""Rebuild a documented, stratified A-share research sample with Tushare Pro.

Only monthly group aggregates and metadata are published. Individual records stay
under data/raw/, which is ignored by Git.
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import tushare as ts

BOARD_TARGETS = {"主板": 50, "创业板": 25, "科创板": 25}


def board_of(code):
    number = code.split(".")[0]
    if number.startswith(("300", "301")):
        return "创业板"
    if number.startswith(("688", "689")):
        return "科创板"
    if number.startswith(("000", "001", "002", "003", "600", "601", "603", "605")):
        return "主板"
    return None


def choose_universe(pro, seed=REDACTED):
    frames = [pro.stock_basic(exchange="", list_status=status, fields="ts_code,name,list_date,delist_date") for status in ("L", "D")]
    stocks = pd.concat(frames, ignore_index=True).drop_duplicates("ts_code")
    stocks["board"] = stocks.ts_code.map(board_of)
    stocks = stocks[stocks.board.notna() & (stocks.list_date <= "20211231")].copy()
    stocks = stocks[(stocks.delist_date.fillna("").eq("")) | (stocks.delist_date >= "20220101")]
    stocks = stocks[~stocks.name.fillna("").str.contains("ST", case=False, regex=False)]
    selected = []
    for board, target in BOARD_TARGETS.items():
        pool = stocks[stocks.board.eq(board)]
        if len(pool) < target:
            raise ValueError(f"{board} eligible stock count {len(pool)} < {target}")
        selected.append(pool.sample(n=target, random_state=seed))
    return pd.concat(selected, ignore_index=True)[["ts_code", "board", "list_date", "delist_date"]]


def fetch_one(pro, code, start, end):
    args = dict(ts_code=code, start_date=start, end_date=end)
    daily = pro.daily(**args)
    factor = pro.adj_factor(**args)
    if daily.empty or factor.empty:
        return pd.DataFrame()
    keys = ["ts_code", "trade_date"]
    daily = daily[keys + ["close", "vol"]]
    factor = factor[keys + ["adj_factor"]]
    frame = daily.merge(factor, on=keys, how="inner", validate="one_to_one")
    frame["date"] = pd.to_datetime(frame.trade_date, format="%Y%m%d")
    frame["adjusted_close"] = frame.close * frame.adj_factor
    return frame[["ts_code", "date", "adjusted_close", "vol"]].sort_values("date")


def build_monthly_panel(daily, universe):
    daily = daily.merge(universe[["ts_code", "board"]], on="ts_code", validate="many_to_one")
    daily = daily.dropna(subset=["adjusted_close"])
    daily = daily[(daily.adjusted_close > 0) & (daily.vol > 0)].sort_values(["ts_code", "date"]).copy()
    # A 60-session signal uses only information known at the formation date.
    daily["daily_return"] = daily.groupby("ts_code").adjusted_close.pct_change(fill_method=None)
    daily["volatility"] = daily.groupby("ts_code").daily_return.transform(
        lambda x: x.rolling(60, min_periods=45).std() * np.sqrt(252))
    daily["month"] = daily.date.dt.to_period("M")
    monthend = daily.groupby(["ts_code", "month"], as_index=False).tail(1).copy()
    monthend["next_month"] = monthend.groupby("ts_code").month.shift(-1)
    monthend["next_price"] = monthend.groupby("ts_code").adjusted_close.shift(-1)
    monthend["next_return"] = monthend.next_price / monthend.adjusted_close - 1
    monthend = monthend[(monthend.next_month == monthend.month + 1) & monthend.volatility.notna()].copy()
    monthend = monthend[monthend.next_return.between(-.9, 5)]
    # Monthly breakpoints are formed within each board; ten groups need at least 20 names.
    groups = []
    for _, group in monthend.groupby(["month", "board"]):
        if len(group) < 20:
            continue
        group = group.copy()
        group["decile"] = pd.qcut(group.volatility.rank(method="first"), 10, labels=False) + 1
        groups.append(group)
    if not groups:
        raise ValueError("No board-month has enough names for ten portfolios")
    monthend = pd.concat(groups, ignore_index=True)
    return monthend.dropna(subset=["decile"])


def aggregate(panel):
    portfolio = panel.groupby(["month", "board", "decile"]).agg(ret=("next_return", "mean"), n=("ts_code", "size")).reset_index()
    portfolio["decile"] = portfolio.decile.astype(int)
    portfolio["date"] = (portfolio.month + 1).dt.to_timestamp()
    portfolio["source"] = "Tushare Pro · deterministic 100-stock exploratory sample"
    return portfolio[["date", "board", "decile", "ret", "n", "source"]].sort_values(["date", "board", "decile"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="20220101")
    parser.add_argument("--end", default="20251231")
    parser.add_argument("--output", type=Path, default=Path("data/public"))
    args = parser.parse_args()
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise SystemExit("TUSHARE_TOKEN is required in the local environment")
    pro = ts.pro_api(token)
    universe = choose_universe(pro)
    frames, failures = [], []
    for i, code in enumerate(universe.ts_code, 1):
        try:
            frame = fetch_one(pro, code, args.start, args.end)
            if not frame.empty:
                frames.append(frame)
            else:
                failures.append(code)
        except Exception:
            failures.append(code)
        if i % 10 == 0:
            print(f"Fetched {i}/{len(universe)} stocks; successful {len(frames)}", flush=True)
    if len(frames) < 70:
        raise RuntimeError(f"Insufficient successful stocks: {len(frames)}")
    daily = pd.concat(frames, ignore_index=True)
    panel = build_monthly_panel(daily, universe)
    portfolio = aggregate(panel)
    if portfolio.empty:
        raise RuntimeError("No monthly portfolios were formed")
    args.output.mkdir(parents=True, exist_ok=True)
    portfolio.to_csv(args.output / "portfolio_monthly.csv", index=False, encoding="utf-8")
    meta = {"source": "Tushare Pro", "download_date": pd.Timestamp.now().date().isoformat(),
            "seed": REDACTED, "target_by_board": BOARD_TARGETS, "selected_stocks": len(universe),
            "fetched_stocks": len(frames), "failed_stocks": failures, "daily_rows": len(daily),
            "formation_rows": len(panel), "portfolio_rows": len(portfolio),
            "first_return_month": portfolio.date.min().date().isoformat(),
            "last_return_month": portfolio.date.max().date().isoformat(),
            "limitations": ["Stratified 100-stock exploratory cohort, not full A-share universe",
                            "Current name filter cannot reconstruct historical ST periods",
                            "Equal weight only; no market-cap weights or factor-adjusted alpha"]}
    (args.output / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("fetched_stocks", "daily_rows", "formation_rows", "portfolio_rows")}), flush=True)


if __name__ == "__main__":
    main()
