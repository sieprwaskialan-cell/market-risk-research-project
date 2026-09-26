# Market Risk Research Project

Price sample: 2018-01-02 to 2026-09-18.
Daily return dates: 2018-01-03 to 2026-09-18 (2189 observations per asset).
Source snapshot retrieved (UTC): 2026-09-26T13:52:58.926914+00:00.

## Data Checks And SQL

Prices passed structural checks for dates, duplicates, valid values and consistent coverage.
Large daily moves are retained and listed for review in [the data-quality report](data_quality_report.md).
SQL daily returns match an independent pandas calculation within a tolerance of 1e-12.

- The worst single asset-day was IWM on 2020-03-16: -13.27%.
- The strongest asset-month excluding sample boundary months was IWM in 2020-11: 18.24%.
- [Monthly results](sql_monthly_performance.csv) include date coverage; boundary months may be incomplete.
- [Monthly rankings](sql_monthly_rankings.csv) compare realised returns, not risk-adjusted performance.

## Frictionless Daily-Rebalanced Reference

The main monthly-rebalanced portfolio comparison with trading costs is in
[the findings brief](findings_brief.md). The figures below are a separate zero-cost reference.

- Annualized return: 12.00%
- Annualized volatility: 13.80%
- Sharpe ratio: 0.89
- Maximum drawdown: -25.55%
- Historical one-day 95% VaR: 1.32%
- Historical one-day 95% CVaR: 2.03%
- Monte Carlo one-day 95% VaR: 1.39%

Weights are 20% per ETF, reset daily before each return. This is a frictionless daily-rebalanced
comparison, with no transaction costs. The annual risk-free rate is assumed to be 0.0%;
it is not a downloaded Treasury rate.

## Asset-Level Takeaways

- Highest annualized volatility: IWM
- Worst maximum drawdown: TLT
- Best Sharpe ratio: QQQ

## Interview Notes

VaR estimates a loss threshold at a chosen confidence level. A one-day 95% VaR of 2% means that, based on the model or history used, the portfolio is expected to lose more than 2% on about 5% of trading days. CVaR looks at the average loss inside that worst 5%, so it gives more information about tail risk.

Beta measures sensitivity to the benchmark. A beta above 1 means the asset has historically moved more than SPY when SPY moves. A beta below 1 means it has historically been less sensitive.

## Method And Limits

Annualized return is compounded growth using 252 trading days per year. Sharpe uses mean daily
excess return divided by its sample standard deviation, scaled by sqrt(252). Maximum drawdown
includes the initial investment, so an initial loss is counted. VaR and CVaR are one-day loss
estimates, not maximum possible losses. Monte Carlo VaR uses 20,000 multivariate normal draws,
sample means/covariances and random seed 42; this distribution can underestimate extreme losses.

The source is Yahoo adjusted closes, used as supplied. The analysis is descriptive and
backward-looking. Full-sample correlations and covariance do not model changing regimes.
Costs, tax, liquidity and out-of-sample validation are not included.
