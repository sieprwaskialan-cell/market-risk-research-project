# Market Risk Research Project

Alan Sieprawski | Contributor: Conor McMillan

Sample: 2018-01-02 to 2026-09-18. USD.

## Question

How did adding bonds and gold change the risk and return of a US equity portfolio?

## Findings

- The stocks, bonds and gold mix had 13.6% annualized volatility, 35.6% lower than the equity mix's 21.2%.
- Its maximum drawdown was -26.1%, compared with -34.1% for the equity mix and -33.7% for SPY alone.
- The diversified mix returned 11.6% annualized, versus 14.4% for the equity mix. The risk and return trade-off both matter.
- In 2022 the diversified mix returned -20.8%. Diversification did not guarantee a positive return in that window.

## Comparison

| Portfolio | Annualized return | Volatility | Max drawdown | Sharpe |
| --- | ---: | ---: | ---: | ---: |
| SPY only | 14.5% | 19.0% | -33.7% | 0.81 |
| Equity mix | 14.4% | 21.2% | -34.1% | 0.74 |
| Stocks, bonds & gold | 11.6% | 13.6% | -26.1% | 0.87 |

## Interpretation

For risk reporting, compare losses, volatility and returns together, and show how conclusions change across periods and cost assumptions.

## Method

Fixed weights: SPY only (100% SPY); equity mix (one-third SPY, QQQ and IWM); diversified mix (20% each in SPY, QQQ, IWM, TLT and GLD). Weights drift between monthly resets. Costs are 10 bps per dollar bought or sold, including entry; no terminal liquidation. Risk-free rate: assumed 0%. Annualization: 252 trading days. Adjusted closes: Yahoo Finance.

## Limits

This is a descriptive comparison with chosen assets and periods, not an optimized strategy or a predictive test. Taxes, liquidity and market impact are excluded. Large price moves are retained for review, not independently verified. Results depend on the sample and assumptions.
