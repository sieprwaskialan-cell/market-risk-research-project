# Data Quality Report

PASS: structural checks passed

Requested dates: 2018-01-01 to 2026-09-18.
Source snapshot retrieved (UTC): 2026-09-26T13:52:58.926914+00:00.

| Asset | Raw rows | Removed | Clean rows | Missing sessions | Large moves |
| --- | ---: | ---: | ---: | ---: | ---: |
| SPY | 2190 | 0 | 2190 | 0 | 2 |
| QQQ | 2190 | 0 | 2190 | 0 | 2 |
| IWM | 2190 | 0 | 2190 | 0 | 2 |
| TLT | 2190 | 0 | 2190 | 0 | 0 |
| GLD | 2190 | 0 | 2190 | 0 | 1 |

## Policy

- Identical duplicate observations are removed and logged. Conflicting duplicates block analysis.
- Missing, nonnumeric, nonfinite and nonpositive prices are rejected and logged.
- Missing sessions block analysis, preventing a multi-day return being labelled as a daily return.
- Sessions are the union of dates in the five source series, not an official exchange calendar. A date missing from every source cannot be detected by this check.
- Absolute daily moves of 10% or more are flagged and retained. A flag is not proof of bad data.
- Check counts can overlap; rows_removed counts each discarded row once.
- Adjusted prices are used as supplied. No prices are forward-filled or interpolated.
- A structural pass does not independently verify the vendor's prices.

## Moves To Review

| Asset | Date | Daily return |
| --- | --- | ---: |
| SPY | 2020-03-16 | -10.94% |
| SPY | 2025-04-09 | 10.50% |
| QQQ | 2020-03-16 | -11.98% |
| QQQ | 2025-04-09 | 12.00% |
| IWM | 2020-03-12 | -11.05% |
| IWM | 2020-03-16 | -13.27% |
| GLD | 2026-01-30 | -10.27% |
