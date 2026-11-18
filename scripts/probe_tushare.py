"""Fetch two A-share pilot samples; results stay in git-ignored data/raw."""

import argparse
import json
import os
from pathlib import Path

import pandas as pd
import tushare as ts


def checked(frame: pd.DataFrame, required: set[str], label: str) -> pd.DataFrame:
    missing = required - set(frame.columns)
    if frame.empty or missing:
        raise ValueError(f"{label}: empty or missing {sorted(missing)}")
    if frame.duplicated(["ts_code", "trade_date"]).any():
        raise ValueError(f"{label}: duplicate stock-date keys")
    return frame


def fetch_stock(pro, code: str, start: str, end: str):
    kwargs = dict(ts_code=code, start_date=start, end_date=end)
    keys = ["ts_code", "trade_date"]
    daily = checked(pro.daily(**kwargs), set(keys + ["close"]), "daily")
    factor = checked(pro.adj_factor(**kwargs), set(keys + ["adj_factor"]), "adj_factor")
    basic = checked(pro.daily_basic(**kwargs), set(keys + ["turnover_rate", "circ_mv", "pb"]), "daily_basic")
    data = daily.merge(factor[keys + ["adj_factor"]], on=keys, how="left", validate="one_to_one")
    data = data.merge(basic[keys + ["turnover_rate", "circ_mv", "pb"]], on=keys, how="left", validate="one_to_one")
    data["trade_date"] = pd.to_datetime(data.trade_date, format="%Y%m%d", errors="raise")
    data = data.sort_values("trade_date").reset_index(drop=True)
    data["adjusted_close"] = data.close * data.adj_factor
    data["adjusted_return"] = data.adjusted_close.pct_change(fill_method=None)
    audit = {
        "code": code, "rows": len(data),
        "first_date": data.trade_date.min().date().isoformat(),
        "last_date": data.trade_date.max().date().isoformat(),
        "missing_factor": int(data.adj_factor.isna().sum()),
        "missing_turnover": int(data.turnover_rate.isna().sum()),
        "missing_pb": int(data.pb.isna().sum()),
        "return_non_null": int(data.adjusted_return.notna().sum()),
    }
    return data, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes", nargs="+", default=["000001.SZ", "603603.SH"])
    parser.add_argument("--start", default="20240101")
    parser.add_argument("--end", default="20240430")
    parser.add_argument("--out", type=Path, default=Path("data/raw/pilot"))
    args = parser.parse_args()
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise SystemExit("Set TUSHARE_TOKEN in the local environment first.")
    pro = ts.pro_api(token)
    args.out.mkdir(parents=True, exist_ok=True)
    audits = []
    for code in args.codes:
        frame, audit = fetch_stock(pro, code, args.start, args.end)
        frame.to_csv(args.out / f"{code.replace('.', '_')}.csv", index=False, encoding="utf-8-sig")
        audits.append(audit)
    (args.out / "audit.json").write_text(json.dumps(audits, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audits, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
