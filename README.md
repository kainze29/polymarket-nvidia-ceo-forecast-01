# Polymarket Next CEO of NVIDIA forecast

Entry for make.fun competition `polymarket-nvidia-ceo-forecast-01`.

`main.py` (Python 3.13, standard library only, no network) reads one case
file at a time from `$MAKEFUN_INPUT_DIR` (default `/input`) and writes one
forecast file per case to `$MAKEFUN_OUTPUT_DIR` (default `/output`): for
every market and each of the 240 minutes after the checkpoint, five
quantiles (5%, 25%, 50%, 75%, 95%) of that minute's Yes price.

## Approach

- **Median: persistence.** The last price at the checkpoint. Recent trends
  and mean reversion toward longer-run means were tested on the practice
  cases and both made the pinball loss worse, so the median does not drift.
- **Spread: random-walk band**, `q_tau(h) = x + z_tau * sigma * sqrt(h)`.
  `sigma` is per-market: the winsorized (clipped at +/-0.05) standard
  deviation of 1-minute price changes over the last 120 minutes, clamped
  to [0.0008, 0.006] and scaled by 0.65. Short windows win because
  volatility clusters and these prices move in bursts; longer windows
  (720 / 4320 min) and the house baseline's fixed 0.0025 both scored
  worse. Winsorizing keeps single jumps (e.g. a market jumping 0.35 to
  0.59 in a minute) from blowing up sigma.
- **No cross-market normalization.** Scaling medians so they sum to 1 was
  tested and made the practice loss slightly worse.
- Quantiles are clipped to [0, 1], rounded to 6 decimals, non-decreasing,
  and the program is fully deterministic.

## Local test results

Run on all six kit practice cases: valid output for every case
(240 rows x 5 quantiles per market, monotone, in [0, 1], each file well
under the 1 MiB cap), 0.46 s for all six cases, byte-identical on repeat
runs.

Practice pinball loss, scoring cases p00-p04 against the following
practice case's recorded prices as ground truth: **0.3024**
(median error 0.8795, 90% coverage 0.9103), vs **0.3925** for the house
baseline replayed the same way. The house baseline scores 0.363589 on
all six practice cases per the kit's RULES.txt (p05's future is not in
the kit, so it cannot be scored locally).

## License

MIT (see LICENSE).
