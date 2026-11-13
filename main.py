#!/usr/bin/env python3
"""Polymarket Next CEO of NVIDIA price forecaster (Python 3.13, stdlib only).

Forecasts, for every market of a case and each of the 240 minutes after the
checkpoint, five quantiles (5%, 25%, 50%, 75%, 95%) of that minute's Yes price.

Approach (tuned on the kit's six practice cases, scoring cases p00-p04
against the following case's recorded prices as ground truth):
  - Median: persistence. The last price at the checkpoint. Recent trends and
    mean reversion toward longer-run means were both tested and made the
    practice pinball loss worse, so the median does not drift.
  - Spread: a random-walk band, q_tau(h) = x + z_tau * sigma * sqrt(h).
    sigma is per-market, estimated from the winsorized standard deviation
    of 1-minute price changes over the last 120 minutes, scaled by 0.65,
    floored at 0.0005 and capped at 0.008 per sqrt-minute. Short windows
    win because volatility clusters and these prices move in bursts; longer
    windows (720 / 4320 min) and the house baseline's fixed 0.0025 both
    scored worse. Winsorizing at +/-0.05 keeps single jumps (e.g. a market
    jumping 0.35 -> 0.59 in a minute) from blowing up sigma.
  - No cross-market normalization: scaling medians so they sum to 1 was
    tested and made the practice loss slightly worse.
  - Quantiles are clipped to [0, 1], rounded to 6 decimals, and forced
    non-decreasing. Deterministic: no randomness, no network, no I/O
    besides the input case files and the output files.

Local practice score (mean pinball loss, p00-p04, ground truth from the
next practice case): about 0.302, vs about 0.393 for the house baseline
replayed the same way (house baseline scores 0.363589 on all six practice
cases per RULES.txt; p05's future is not in the kit).

Usage: MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
Defaults to /input and /output when the env vars are unset.
"""

import json
import math
import os
import statistics
from pathlib import Path

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at the scored levels.
Z = [-1.644854, -0.67449, 0.0, 0.67449, 1.644854]

# Tuned constants (see module docstring).
SIGMA_WINDOW = 120        # minutes of recent 1-min changes used for sigma
SIGMA_SCALE = 0.65        # shrink the raw short-window volatility
SIGMA_FLOOR = 0.0008      # raw per sqrt-minute, before scaling
SIGMA_CAP = 0.006         # raw per sqrt-minute, before scaling
WINSOR_CAP = 0.05         # clip single-minute jumps before the stddev


def price6(x: float) -> float:
    """Clamp to [0, 1] and round to 6 decimals (never -0)."""
    return round(min(1.0, max(0.0, x)), 6) + 0.0


def estimate_sigma(prices) -> float:
    """Per-market 1-minute volatility from the last SIGMA_WINDOW minutes."""
    window = prices[-SIGMA_WINDOW:] if len(prices) > SIGMA_WINDOW else prices
    if len(window) < 2:
        return SIGMA_FLOOR
    diffs = [window[i + 1] - window[i] for i in range(len(window) - 1)]
    clipped = [max(-WINSOR_CAP, min(WINSOR_CAP, d)) for d in diffs]
    sigma = statistics.pstdev(clipped)
    # Clamp the raw estimate first, then shrink: effective band
    # [0.00052, 0.0039] per sqrt-minute, exactly as tuned.
    sigma = max(SIGMA_FLOOR, min(SIGMA_CAP, sigma)) * SIGMA_SCALE
    return sigma


def forecast_market(prices, horizon: int):
    """240 rows of five quantiles around the last price."""
    x = prices[-1] if prices else 0.5
    sigma = estimate_sigma(prices)
    rows = []
    for h in range(1, horizon + 1):
        spread = sigma * math.sqrt(h)
        row = [price6(x + z * spread) for z in Z]
        for j in range(1, len(row)):
            if row[j] < row[j - 1]:
                row[j] = row[j - 1]
        rows.append(row)
    return rows


def main() -> None:
    input_dir = Path(INPUT_DIR)
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = sorted(p for p in input_dir.iterdir() if p.name.endswith(".in"))
    for in_path in inputs:
        case_id = in_path.name[: -len(".in")]
        with open(in_path, "r", encoding="utf-8") as f:
            case = json.load(f)
        if list(case.get("quantiles", [])) != QUANTILES:
            raise ValueError(f"{in_path.name} asks for quantiles "
                             f"{case.get('quantiles')}, not {QUANTILES}")
        horizon = int(case["horizon_minutes"])
        forecasts = [
            {"id": m["id"], "q": forecast_market(m["prices"], horizon)}
            for m in case["markets"]
        ]
        out_path = output_dir / f"{case_id}.out"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"forecasts": forecasts}) + "\n")


if __name__ == "__main__":
    main()
