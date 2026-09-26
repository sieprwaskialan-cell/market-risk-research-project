from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from data_pipeline import ASSETS, prepare_data

START_DATE = "2018-01-01"
END_DATE = "2026-09-18"
TRADING_DAYS = 252
ROLLING_WINDOW = 60
RISK_FREE_RATE = 0.0
BENCHMARK = "SPY"

SYMBOLS = list(ASSETS)

OUTPUT_DIR = Path(__file__).resolve().parent / "results"


@dataclass(frozen=True)
class PortfolioRisk:
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    historical_var_95: float
    historical_cvar_95: float
    monte_carlo_var_95: float


def annualized_return(returns: pd.Series) -> float:
    cumulative_return = float((1.0 + returns).prod())
    years = len(returns) / TRADING_DAYS
    return math.pow(cumulative_return, 1.0 / years) - 1.0


def annualized_volatility(returns: pd.Series) -> float:
    return float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS))


def sharpe_ratio(returns: pd.Series) -> float:
    daily_risk_free = math.pow(1.0 + RISK_FREE_RATE, 1.0 / TRADING_DAYS) - 1.0
    excess_returns = returns - daily_risk_free
    daily_volatility = float(excess_returns.std(ddof=1))
    if not np.isfinite(daily_volatility) or daily_volatility <= 1e-15:
        return float("nan")
    return float(excess_returns.mean() / daily_volatility * math.sqrt(TRADING_DAYS))


def drawdowns(returns: pd.Series) -> pd.Series:
    wealth_index = (1.0 + returns).cumprod()
    # Initial wealth is 1, including when the first return is negative.
    previous_peak = wealth_index.cummax().clip(lower=1.0)
    return wealth_index / previous_peak - 1.0


def drawdown_table(returns: pd.DataFrame) -> pd.DataFrame:
    wealth_index = (1.0 + returns).cumprod()
    previous_peak = wealth_index.cummax().clip(lower=1.0)
    return wealth_index / previous_peak - 1.0


def rolling_volatility_table(returns: pd.DataFrame) -> pd.DataFrame:
    return returns.rolling(ROLLING_WINDOW).std() * math.sqrt(TRADING_DAYS)


def rolling_beta_table(returns: pd.DataFrame) -> pd.DataFrame:
    benchmark_returns = returns[BENCHMARK]
    benchmark_variance = benchmark_returns.rolling(ROLLING_WINDOW).var()
    beta_values = {}
    for symbol in returns.columns:
        covariance = returns[symbol].rolling(ROLLING_WINDOW).cov(benchmark_returns)
        beta_values[symbol] = covariance / benchmark_variance
    return pd.DataFrame(beta_values)


def beta_to_benchmark(asset_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    covariance = asset_returns.cov(benchmark_returns)
    benchmark_variance = benchmark_returns.var(ddof=1)
    if benchmark_variance == 0:
        return float("nan")
    return float(covariance / benchmark_variance)


def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    return float(-returns.quantile(1.0 - confidence))


def historical_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    cutoff = returns.quantile(1.0 - confidence)
    return float(-returns[returns <= cutoff].mean())


def monte_carlo_portfolio_var(returns: pd.DataFrame, weights: np.ndarray, confidence: float = 0.95) -> float:
    rng = np.random.default_rng(seed=42)
    mean_returns = returns.mean().to_numpy()
    covariance = returns.cov().to_numpy()
    simulations = rng.multivariate_normal(mean_returns, covariance, size=20_000)
    simulated_portfolio_returns = simulations @ weights
    return float(-np.quantile(simulated_portfolio_returns, 1.0 - confidence))


def build_metrics(returns: pd.DataFrame) -> pd.DataFrame:
    benchmark_returns = returns[BENCHMARK]
    rows = []
    for symbol in returns.columns:
        series = returns[symbol]
        rows.append(
            {
                "symbol": symbol,
                "annualized_return": annualized_return(series),
                "annualized_volatility": annualized_volatility(series),
                "sharpe_ratio": sharpe_ratio(series),
                "max_drawdown": float(drawdowns(series).min()),
                "beta_vs_spy": beta_to_benchmark(series, benchmark_returns),
                "historical_var_95": historical_var(series),
                "historical_cvar_95": historical_cvar(series),
            }
        )
    return pd.DataFrame(rows).set_index("symbol")


def portfolio_risk(returns: pd.DataFrame) -> PortfolioRisk:
    weights = np.repeat(1.0 / len(returns.columns), len(returns.columns))
    portfolio_returns = pd.Series(returns.to_numpy() @ weights, index=returns.index, name="portfolio")
    return PortfolioRisk(
        annualized_return=annualized_return(portfolio_returns),
        annualized_volatility=annualized_volatility(portfolio_returns),
        sharpe_ratio=sharpe_ratio(portfolio_returns),
        max_drawdown=float(drawdowns(portfolio_returns).min()),
        historical_var_95=historical_var(portfolio_returns),
        historical_cvar_95=historical_cvar(portfolio_returns),
        monte_carlo_var_95=monte_carlo_portfolio_var(returns, weights),
    )


def save_plots(prices: pd.DataFrame, returns: pd.DataFrame) -> None:
    normalized = prices / prices.iloc[0]
    ax = normalized.plot(figsize=(10, 6), linewidth=1.6)
    ax.set_title("Normalized ETF Prices")
    ax.set_ylabel("Growth of $1")
    ax.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "normalized_prices.png", dpi=160)
    plt.close()

    ax = drawdown_table(returns).plot(figsize=(10, 6), linewidth=1.4)
    ax.set_title("Drawdowns")
    ax.set_ylabel("Drawdown")
    ax.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "drawdowns.png", dpi=160)
    plt.close()

    correlation = returns.corr()
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(correlation.to_numpy(), vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_title("Return Correlation Matrix")
    tick_positions = list(range(len(correlation.columns)))
    tick_labels = correlation.columns.astype(str).tolist()
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_yticks(tick_positions)
    ax.set_yticklabels(tick_labels)
    for row in range(len(correlation.index)):
        for col in range(len(correlation.columns)):
            value = float(correlation.iloc[row, col])
            ax.text(col, row, f"{value:.2f}", ha="center", va="center")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "correlation_heatmap.png", dpi=160)
    plt.close()

    rolling_volatility = rolling_volatility_table(returns).dropna()
    ax = rolling_volatility.plot(figsize=(10, 6), linewidth=1.4)
    ax.set_title(f"{ROLLING_WINDOW}-Day Rolling Annualized Volatility")
    ax.set_ylabel("Annualized Volatility")
    ax.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "rolling_volatility.png", dpi=160)
    plt.close()

    rolling_beta = rolling_beta_table(returns).dropna()
    beta_plot = rolling_beta.drop(columns=[BENCHMARK], errors="ignore")
    ax = beta_plot.plot(figsize=(10, 6), linewidth=1.4)
    ax.axhline(1.0, color="black", linewidth=1.0, linestyle="--", alpha=0.55)
    ax.set_title(f"{ROLLING_WINDOW}-Day Rolling Beta vs {BENCHMARK}")
    ax.set_ylabel(f"Beta vs {BENCHMARK}")
    ax.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "rolling_beta_vs_spy.png", dpi=160)
    plt.close()


def save_monthly_heatmap() -> None:
    monthly = pd.read_csv(OUTPUT_DIR / "sql_monthly_performance.csv")
    interior = monthly[monthly["coverage"] == "Interior sample month"]
    months = sorted(interior["month"].unique())[-12:]
    destination = OUTPUT_DIR / "monthly_returns_heatmap.png"
    if not months:
        if destination.exists():
            destination.unlink()
        return
    values = interior.pivot(index="symbol", columns="month", values="monthly_return")
    values = values.reindex(index=SYMBOLS, columns=months)
    scale = max(float(values.abs().max().max()), 0.01)
    fig, ax = plt.subplots(figsize=(12, 4.8))
    cmap = plt.get_cmap("RdYlGn")
    image = ax.imshow(values.to_numpy(), cmap=cmap, vmin=-scale, vmax=scale, aspect="auto")
    ax.set_title("Monthly ETF Returns", fontsize=17, loc="left", pad=18)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels([pd.Timestamp(f"{month}-01").strftime("%b\n%Y") for month in months])
    ax.set_yticks(range(len(SYMBOLS)))
    ax.set_yticklabels(SYMBOLS)
    ax.tick_params(length=0, pad=10)
    for row in range(len(SYMBOLS)):
        for col in range(len(months)):
            value = float(values.iloc[row, col])
            red, green, blue, _ = cmap((value + scale) / (2 * scale))
            color = "black" if 0.2126 * red + 0.7152 * green + 0.0722 * blue > 0.55 else "white"
            ax.text(col, row, f"{value:+.1%}", ha="center", va="center", color=color, fontsize=9)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.025, format=PercentFormatter(1))
    fig.text(0.065, 0.025, "Source: Yahoo adjusted closes | SQL compounded returns | Latest 12 interior sample months",
             fontsize=9, color="#454545")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(destination, dpi=180)
    plt.close(fig)


def pct(value: float) -> str:
    return f"{value:.2%}"


def write_report(metrics: pd.DataFrame, risk: PortfolioRisk, returns: pd.DataFrame) -> None:
    highest_vol = metrics["annualized_volatility"].idxmax()
    worst_drawdown = metrics["max_drawdown"].idxmin()
    best_sharpe = metrics["sharpe_ratio"].idxmax()
    start = pd.Timestamp(returns.index[0]).date()
    end = pd.Timestamp(returns.index[-1]).date()
    metadata = json.loads((OUTPUT_DIR / "run_metadata.json").read_text(encoding="utf-8"))
    worst_days = pd.read_csv(OUTPUT_DIR / "sql_worst_days.csv")
    worst_day = worst_days.loc[worst_days["daily_return"].idxmin()]
    monthly = pd.read_csv(OUTPUT_DIR / "sql_monthly_performance.csv")
    interior = monthly[monthly["coverage"] == "Interior sample month"].dropna(subset=["monthly_return"])
    monthly_note = "No interior sample months are available for comparison."
    if not interior.empty:
        strongest_month = interior.loc[interior["monthly_return"].idxmax()]
        monthly_note = (
            f"The strongest asset-month excluding sample boundary months was "
            f"{strongest_month['symbol']} in {strongest_month['month']}: "
            f"{pct(float(strongest_month['monthly_return']))}."
        )

    report = f"""# Market Risk Research Project

Price sample: {metadata['actual_first_price_date']} to {end}.
Daily return dates: {start} to {end} ({len(returns)} observations per asset).
Source snapshot retrieved (UTC): {metadata['retrieved_at_utc']}.

## Data Checks And SQL

Prices passed structural checks for dates, duplicates, valid values and consistent coverage.
Large daily moves are retained and listed for review in [the data-quality report](data_quality_report.md).
SQL daily returns match an independent pandas calculation within a tolerance of 1e-12.

- The worst single asset-day was {worst_day['symbol']} on {worst_day['trade_date']}: {pct(float(worst_day['daily_return']))}.
- {monthly_note}
- [Monthly results](sql_monthly_performance.csv) include date coverage; boundary months may be incomplete.
- [Monthly rankings](sql_monthly_rankings.csv) compare realised returns, not risk-adjusted performance.

## Frictionless Daily-Rebalanced Reference

The main monthly-rebalanced portfolio comparison with trading costs is in
[the findings brief](findings_brief.md). The figures below are a separate zero-cost reference.

- Annualized return: {pct(risk.annualized_return)}
- Annualized volatility: {pct(risk.annualized_volatility)}
- Sharpe ratio: {risk.sharpe_ratio:.2f}
- Maximum drawdown: {pct(risk.max_drawdown)}
- Historical one-day 95% VaR: {pct(risk.historical_var_95)}
- Historical one-day 95% CVaR: {pct(risk.historical_cvar_95)}
- Monte Carlo one-day 95% VaR: {pct(risk.monte_carlo_var_95)}

Weights are 20% per ETF, reset daily before each return. This is a frictionless daily-rebalanced
comparison, with no transaction costs. The annual risk-free rate is assumed to be {RISK_FREE_RATE:.1%};
it is not a downloaded Treasury rate.

## Asset-Level Takeaways

- Highest annualized volatility: {highest_vol}
- Worst maximum drawdown: {worst_drawdown}
- Best Sharpe ratio: {best_sharpe}

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
"""
    (OUTPUT_DIR / "risk_report.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit ETF data, run SQL analysis and calculate market risk.")
    parser.add_argument("--start", default=START_DATE, help="First requested price date (YYYY-MM-DD).")
    parser.add_argument("--end", default=END_DATE, help="Last requested price date (YYYY-MM-DD).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--refresh", action="store_true", help="Download a fresh source snapshot.")
    mode.add_argument("--offline", action="store_true", help="Require the saved snapshot; never download.")
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prices, returns = prepare_data(
        Path(__file__).resolve().parent, args.start, args.end,
        refresh=args.refresh, offline=args.offline,
    )

    metrics = build_metrics(returns)
    risk = portfolio_risk(returns)
    correlation = returns.corr()
    rolling_volatility = rolling_volatility_table(returns)
    rolling_beta = rolling_beta_table(returns)

    metrics.to_csv(OUTPUT_DIR / "risk_metrics.csv")
    correlation.to_csv(OUTPUT_DIR / "correlation_matrix.csv")
    rolling_volatility.to_csv(OUTPUT_DIR / "rolling_volatility.csv")
    rolling_beta.to_csv(OUTPUT_DIR / "rolling_beta_vs_spy.csv")
    save_plots(prices, returns)
    save_monthly_heatmap()
    write_report(metrics, risk, returns)
    from portfolio_analysis import build_portfolio_analysis
    from build_deliverables import build_deliverables

    payload = build_portfolio_analysis(Path(__file__).resolve().parent, prices, returns)
    build_deliverables(Path(__file__).resolve().parent, payload)

    print("Market risk analysis complete. Data checks passed; SQL and Python returns agree.")
    print(f"Outputs saved in: {OUTPUT_DIR}")
    print()
    print(metrics.round(4))


if __name__ == "__main__":
    main()
