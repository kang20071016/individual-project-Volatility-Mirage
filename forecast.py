"""Small, reproducible scenario projection for a monthly portfolio spread."""

import numpy as np
import pandas as pd


def project_spread(spread: pd.Series, horizon: int = 3, lookback: int = 24) -> dict:
    """Resample observed monthly D1-D10 gaps; report a range, not a market call."""
    values = pd.Series(spread, dtype=float).dropna().sort_index().tail(lookback)
    if len(values) < 6:
        raise ValueError("至少需要 6 个月的样本才能做情景推演。")
    if not 1 <= horizon <= 6:
        raise ValueError("观察期应为 1～6 个月。")
    rng = np.random.default_rng(20261125)
    draws = rng.choice(values.to_numpy(), size=(4000, horizon), replace=True).sum(axis=1) * 100
    low, high = np.quantile(draws, [.1, .9])
    return {
        "point_pp": round(float(values.mean() * horizon * 100), 2),
        "low_pp": round(float(low), 2),
        "high_pp": round(float(high), 2),
        "months_used": int(len(values)),
        "last_month": str(values.index.max().date()),
        "draws": draws,
    }


def walk_forward_error(spread: pd.Series, window: int = 12) -> dict:
    """Compare prior-window mean forecasts with the next observed month."""
    values = pd.Series(spread, dtype=float).dropna().sort_index().to_numpy()
    if len(values) <= window:
        return {"tests": 0, "mae_pp": None, "zero_mae_pp": None}
    predictions = np.array([values[i - window:i].mean() for i in range(window, len(values))])
    actual = values[window:]
    return {
        "tests": int(len(actual)),
        "mae_pp": round(float(np.mean(np.abs(predictions - actual)) * 100), 2),
        "zero_mae_pp": round(float(np.mean(np.abs(actual)) * 100), 2),
    }
