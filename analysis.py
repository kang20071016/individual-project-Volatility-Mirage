"""Transparent diagnostics for a monthly low-minus-high return series."""

import math

import numpy as np
import pandas as pd


def newey_west_mean(series: pd.Series, lags: int = 6) -> dict:
    """Bartlett-kernel HAC standard error for the sample mean."""
    values = pd.Series(series, dtype=float).dropna().to_numpy()
    n = len(values)
    if n < 3:
        return {"n": n, "mean": math.nan, "se": math.nan, "t": math.nan, "ci_low": math.nan, "ci_high": math.nan}
    mean = float(np.mean(values))
    residual = values - mean
    lag_count = min(lags, n - 1)
    long_run = float(np.dot(residual, residual) / n)
    for lag in range(1, lag_count + 1):
        covariance = float(np.dot(residual[lag:], residual[:-lag]) / n)
        long_run += 2 * (1 - lag / (lag_count + 1)) * covariance
    se = math.sqrt(max(long_run, 0) / n)
    return {
        "n": n,
        "mean": mean,
        "se": se,
        "t": mean / se if se else math.nan,
        "ci_low": mean - 1.96 * se,
        "ci_high": mean + 1.96 * se,
    }


def spread_diagnostics(spread: pd.Series) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Return HAC summary, annual arithmetic spreads and rolling 12-month spread."""
    spread = spread.dropna().sort_index()
    summary = newey_west_mean(spread)
    annual = spread.groupby(spread.index.year).agg(["sum", "count"]).reset_index()
    annual.columns = ["year", "spread", "months"]
    annual["spread"] *= 100
    rolling = spread.rolling(12, min_periods=12).sum().mul(100).rename("spread").reset_index()
    rolling.columns = ["date", "spread"]
    return summary, annual, rolling.dropna()
