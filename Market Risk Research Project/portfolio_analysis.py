from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, StrMethodFormatter
import numpy as np
import pandas as pd

from market_risk_snapshot import annualized_return, annualized_volatility, drawdowns, sharpe_ratio


PORTFOLIOS = {
    "spy": {"name": "SPY only", "weights": {"SPY": 1.0}, "color": "#39464c"},
    "equity": {"name": "Equity mix", "weights": {"SPY": 1 / 3, "QQQ": 1 / 3, "IWM": 1 / 3}, "color": "#157b70"},
    "diversified": {"name": "Stocks, bonds & gold", "weights": {"SPY": .2, "QQQ": .2, "IWM": .2, "TLT": .2, "GLD": .2}, "color": "#b44e41"},
}
COSTS = [0, 10, 25]
REBALANCING = ["monthly", "buy_hold"]
DEFAULT_SCENARIO = "monthly_10"


def simulate_portfolio(returns: pd.DataFrame, weights: dict[str, float], *, cost_bps: float = 10,
                       rebalance: str = "monthly") -> pd.DataFrame:
    if rebalance not in REBALANCING:
        raise ValueError("Rebalancing must be monthly or buy_hold.")
    if not 0 <= cost_bps <= 100:
        raise ValueError("Cost must be between 0 and 100 basis points per dollar traded.")
    if not weights or set(weights) - set(returns.columns):
        raise ValueError("Weights must reference known assets.")
    target = np.array([weights.get(symbol, 0.0) for symbol in returns.columns], dtype=float)
    if not np.isfinite(target).all() or (target < 0).any() or not np.isclose(target.sum(), 1.0):
        raise ValueError("Weights must be finite, nonnegative and sum to one.")
    if returns.empty or returns.isna().any().any() or not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Returns must be nonempty and finite.")
    if not returns.index.is_monotonic_increasing or not returns.index.is_unique or (returns <= -1).any().any():
        raise ValueError("Returns need unique ordered dates and values above -100%.")
    current = target.copy()
    previous_month = None
    rows = []
    for date, values in zip(returns.index, returns.to_numpy()):
        month = (date.year, date.month)
        if previous_month is None:
            turnover = 1.0  # Initial purchase from cash; no terminal liquidation is charged.
        elif rebalance == "monthly" and month != previous_month:
            turnover = float(np.abs(target - current).sum())
            current = target.copy()
        else:
            turnover = 0.0
        cost = turnover * cost_bps / 10_000
        gross = float(current @ values)
        net = (1 - cost) * (1 + gross) - 1
        rows.append((date, gross, net, turnover, cost))
        current = current * (1 + values) / (1 + gross)
        previous_month = month
    result = pd.DataFrame(rows, columns=["date", "gross_return", "net_return", "turnover", "cost_fraction"]).set_index("date")
    result["wealth"] = (1 + result["net_return"]).cumprod()
    result["drawdown"] = result["wealth"] / result["wealth"].cummax().clip(lower=1) - 1
    return result


def summarize(returns: pd.Series) -> dict[str, float]:
    return {
        "observations": len(returns),
        "total_return": float((1 + returns).prod() - 1),
        "annualized_return": annualized_return(returns),
        "annualized_volatility": annualized_volatility(returns),
        "sharpe_ratio": sharpe_ratio(returns),
        "max_drawdown": float(drawdowns(returns).min()),
        "worst_day": float(returns.min()),
    }


def make_comparison_chart(prices: pd.DataFrame, paths: dict[str, pd.DataFrame], destination: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 7.4), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    for key, path in paths.items():
        spec = PORTFOLIOS[key]
        wealth = pd.concat([pd.Series([1.0], index=prices.index[:1]), path["wealth"]])
        dd = pd.concat([pd.Series([0.0], index=prices.index[:1]), path["drawdown"]])
        axes[0].plot(wealth.index, wealth * 10_000, label=spec["name"], color=spec["color"], linewidth=1.7)
        axes[1].plot(dd.index, dd, color=spec["color"], linewidth=1.3)
    axes[0].set_title("What changed when bonds and gold were added?", loc="left", fontsize=17, pad=16)
    axes[0].set_ylabel("Value of $10,000")
    axes[0].yaxis.set_major_formatter(StrMethodFormatter("${x:,.0f}"))
    axes[0].legend(loc="upper left", frameon=False)
    axes[1].set_ylabel("Drawdown")
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.18)
    fig.text(.075, .015, "Monthly rebalancing | 10 bps per dollar bought or sold, including entry | Yahoo adjusted closes | Historical comparison", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(destination, dpi=180)
    plt.close(fig)


def build_portfolio_analysis(root: Path, prices: pd.DataFrame, returns: pd.DataFrame) -> dict:
    output = root / "results"
    scenarios = {}
    summaries = []
    default_paths = {}
    for rebalance in REBALANCING:
        for cost in COSTS:
            scenario = f"{rebalance}_{cost}"
            scenarios[scenario] = {}
            for key, spec in PORTFOLIOS.items():
                path = simulate_portfolio(returns, spec["weights"], cost_bps=cost, rebalance=rebalance)
                scenarios[scenario][key] = path["net_return"].tolist()
                summaries.append({"scenario": scenario, "portfolio": key, "name": spec["name"],
                                  "rebalance": rebalance, "cost_bps": cost, **summarize(path["net_return"])})
                if scenario == DEFAULT_SCENARIO:
                    default_paths[key] = path
    all_summaries = pd.DataFrame(summaries)
    all_summaries.to_csv(output / "cost_sensitivity.csv", index=False)
    baseline = all_summaries[all_summaries["scenario"] == DEFAULT_SCENARIO].copy()
    baseline.to_csv(output / "portfolio_summary.csv", index=False)
    daily = pd.concat([path.reset_index().assign(portfolio=key) for key, path in default_paths.items()], ignore_index=True)
    daily.to_csv(output / "portfolio_daily.csv", index=False)
    periods = [
        ("Full sample", str(returns.index[0].date()), str(returns.index[-1].date())),
        ("2020 sell-off (hindsight window)", "2020-02-20", "2020-03-23"),
        ("2020 calendar year", "2020-01-01", "2020-12-31"),
        ("2022 calendar year", "2022-01-01", "2022-12-31"),
        ("2023 onwards", "2023-01-01", str(returns.index[-1].date())),
    ]
    period_rows = []
    for label, start, end in periods:
        for key, path in default_paths.items():
            selected = path.loc[start:end, "net_return"]
            if len(selected) < 2:
                continue
            period_rows.append({"period": label, "portfolio": key, "name": PORTFOLIOS[key]["name"],
                                "first_return_date": str(selected.index[0].date()),
                                "last_return_date": str(selected.index[-1].date()), **summarize(selected)})
    pd.DataFrame(period_rows).to_csv(output / "period_comparison.csv", index=False)
    make_comparison_chart(prices, default_paths, output / "portfolio_comparison.png")

    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    metadata["portfolio_assumptions"] = {
        "default_scenario": DEFAULT_SCENARIO, "cost_bps_options": COSTS,
        "rebalance_options": REBALANCING, "portfolios": PORTFOLIOS,
        "initial_purchase_cost": True, "terminal_liquidation_cost": False,
        "risk_free_rate": 0.0, "trading_days_per_year": 252,
    }
    (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    quality = pd.read_csv(output / "data_quality_summary.csv")
    issues = pd.read_csv(output / "data_quality_issues.csv").fillna("")
    payload = {
        "metadata": metadata, "defaultScenario": DEFAULT_SCENARIO,
        "priceDates": prices.index.strftime("%Y-%m-%d").tolist(),
        "dates": returns.index.strftime("%Y-%m-%d").tolist(),
        "assets": {symbol: prices[symbol].tolist() for symbol in prices.columns},
        "portfolios": PORTFOLIOS, "scenarios": scenarios,
        "summary": baseline.to_dict(orient="records"), "sensitivity": summaries,
        "periods": period_rows, "quality": quality.to_dict(orient="records"),
        "issues": issues.to_dict(orient="records"),
        "monthly": pd.read_csv(output / "sql_monthly_performance.csv").fillna("").to_dict(orient="records"),
    }
    dashboard = root / "dashboard"
    dashboard.mkdir(exist_ok=True)
    (dashboard / "data.js").write_text("window.RESEARCH_DATA = " + json.dumps(payload, separators=(",", ":"), allow_nan=False) + ";\n", encoding="utf-8")
    return payload
