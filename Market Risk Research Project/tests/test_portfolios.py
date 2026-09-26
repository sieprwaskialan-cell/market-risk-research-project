from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd

from portfolio_analysis import simulate_portfolio, summarize


class PortfolioTests(unittest.TestCase):
    def test_buy_hold_matches_weighted_asset_wealth(self):
        values = pd.DataFrame({"A": [.1, -.05, .02], "B": [-.03, .01, .08]}, index=pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01"]))
        path = simulate_portfolio(values, {"A": .6, "B": .4}, cost_bps=0, rebalance="buy_hold")
        expected = (1 + values).cumprod() @ np.array([.6, .4])
        np.testing.assert_allclose(path["wealth"], expected)

    def test_monthly_weights_drift_and_then_reset(self):
        values = pd.DataFrame({"A": [.2, .1, .1], "B": [0, 0, 0]}, index=pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01"]))
        path = simulate_portfolio(values, {"A": .5, "B": .5}, cost_bps=0)
        self.assertAlmostEqual(path.iloc[0]["gross_return"], .1)
        self.assertAlmostEqual(path.iloc[1]["gross_return"], .1 * .6 / 1.1)
        self.assertAlmostEqual(path.iloc[2]["gross_return"], .05)
        self.assertEqual(path.iloc[1]["turnover"], 0)
        self.assertGreater(path.iloc[2]["turnover"], 0)

    def test_costs_apply_to_buys_and_sells_including_entry(self):
        values = pd.DataFrame({"A": [.2, 0], "B": [0, 0]}, index=pd.to_datetime(["2024-01-31", "2024-02-01"]))
        path = simulate_portfolio(values, {"A": .5, "B": .5}, cost_bps=10)
        self.assertAlmostEqual(path.iloc[0]["net_return"], .999 * 1.1 - 1)
        turnover = abs(.5 - .6 / 1.1) + abs(.5 - .5 / 1.1)
        self.assertAlmostEqual(path.iloc[1]["turnover"], turnover)
        self.assertAlmostEqual(path.iloc[1]["net_return"], -turnover * .001)

    def test_single_asset_monthly_equals_buy_hold(self):
        values = pd.DataFrame({"A": [.1, -.2, .05]}, index=pd.to_datetime(["2024-01-30", "2024-02-01", "2024-03-01"]))
        monthly = simulate_portfolio(values, {"A": 1.0}, rebalance="monthly")
        held = simulate_portfolio(values, {"A": 1.0}, rebalance="buy_hold")
        pd.testing.assert_frame_equal(monthly, held)

    def test_future_returns_cannot_change_earlier_results(self):
        dates = pd.date_range("2024-01-15", periods=45, freq="B")
        values = pd.DataFrame({"A": np.linspace(-.02, .02, 45), "B": np.linspace(.01, -.01, 45)}, index=dates)
        altered = values.copy()
        altered.iloc[30:] = .4
        first = simulate_portfolio(values, {"A": .7, "B": .3})
        second = simulate_portfolio(altered, {"A": .7, "B": .3})
        pd.testing.assert_frame_equal(first.iloc[:30], second.iloc[:30])

    def test_higher_cost_reduces_terminal_wealth(self):
        values = pd.DataFrame({"A": [.1, -.1, .1], "B": [-.1, .1, -.1]}, index=pd.to_datetime(["2024-01-31", "2024-02-01", "2024-03-01"]))
        wealth = [simulate_portfolio(values, {"A": .5, "B": .5}, cost_bps=c).iloc[-1]["wealth"] for c in [0, 10, 25]]
        self.assertGreater(wealth[0], wealth[1])
        self.assertGreater(wealth[1], wealth[2])

    def test_invalid_weights_and_inputs_fail(self):
        values = pd.DataFrame({"A": [.1, -.1]}, index=pd.to_datetime(["2024-01-30", "2024-01-31"]))
        for weights in [{"A": .8}, {"B": 1}, {"A": -1}, {"A": math.nan}]:
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                simulate_portfolio(values, weights)
        with self.assertRaises(ValueError):
            simulate_portfolio(values.iloc[::-1], {"A": 1})
        values.iloc[0, 0] = np.nan
        with self.assertRaises(ValueError):
            simulate_portfolio(values, {"A": 1})

    def test_subperiod_drawdown_resets_reference_peak(self):
        values = pd.Series([-.5, .1, .2])
        self.assertAlmostEqual(summarize(values)["max_drawdown"], -.5)
        self.assertEqual(summarize(values.iloc[1:])["max_drawdown"], 0)


if __name__ == "__main__":
    unittest.main()
