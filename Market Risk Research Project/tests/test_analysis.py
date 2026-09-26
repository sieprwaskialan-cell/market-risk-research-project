from __future__ import annotations

from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import data_pipeline as pipeline
import market_risk_snapshot as risk


PROJECT = Path(__file__).resolve().parents[1]
DATES = ["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02", "2024-02-05"]


def sample_frames() -> dict[str, pd.DataFrame]:
    return {
        symbol: pd.DataFrame({"trade_date": DATES, "adjusted_close": [100.0, 110.0, 99.0, 108.9, 108.9]})
        for symbol in pipeline.ASSETS
    }


class QualityTests(unittest.TestCase):
    def audit(self, frames: dict[str, pd.DataFrame]):
        return pipeline.audit_prices(frames, DATES[0], DATES[-1])

    def test_valid_data_preserves_large_moves(self):
        prices, summary, issues, blockers = self.audit(sample_frames())
        self.assertEqual(blockers, [])
        self.assertEqual(len(prices), 5)
        self.assertEqual(summary["rows_removed"].sum(), 0)
        self.assertIn("large_move_review_only", issues["check"].tolist())

    def test_identical_duplicate_is_logged_and_removed(self):
        frames = sample_frames()
        frames["SPY"] = pd.concat([frames["SPY"], frames["SPY"].iloc[[1]]], ignore_index=True)
        prices, summary, issues, blockers = self.audit(frames)
        self.assertEqual(blockers, [])
        self.assertEqual(len(prices), 5)
        spy = summary.set_index("symbol").loc["SPY"]
        self.assertEqual(spy["identical_duplicates_removed"], 1)
        self.assertEqual(spy["rows_removed"], 1)
        self.assertIn("identical_duplicate_removed", issues["check"].tolist())

    def test_exact_ten_percent_loss_is_flagged_despite_float_rounding(self):
        frames = sample_frames()
        frames["SPY"]["adjusted_close"] = [100.0, 90.0, 90.0, 90.0, 90.0]
        _, summary, _, blockers = self.audit(frames)
        self.assertEqual(blockers, [])
        self.assertEqual(summary.set_index("symbol").loc["SPY", "large_moves_flagged"], 1)

    def test_conflicting_duplicate_blocks_analysis(self):
        frames = sample_frames()
        duplicate = pd.DataFrame({"trade_date": [DATES[1]], "adjusted_close": [111.0]})
        frames["SPY"] = pd.concat([frames["SPY"], duplicate], ignore_index=True)
        _, summary, _, blockers = self.audit(frames)
        self.assertTrue(any("conflicting" in item for item in blockers))
        self.assertEqual(summary.set_index("symbol").loc["SPY", "conflicting_duplicate_dates"], 1)

    def test_missing_price_blocks_multiday_return(self):
        frames = sample_frames()
        frames["SPY"].loc[1, "adjusted_close"] = np.nan
        prices, summary, issues, blockers = self.audit(frames)
        self.assertTrue(blockers)
        self.assertTrue(pd.isna(prices.iloc[1]["SPY"]))
        self.assertEqual(summary.set_index("symbol").loc["SPY", "missing_observed_sessions"], 1)
        self.assertIn("missing_or_nonnumeric_price", issues["check"].tolist())

    def test_absent_row_is_detected_against_other_assets(self):
        frames = sample_frames()
        frames["SPY"] = frames["SPY"].drop(index=2)
        _, summary, _, blockers = self.audit(frames)
        self.assertTrue(blockers)
        self.assertEqual(summary.set_index("symbol").loc["SPY", "missing_observed_sessions"], 1)

    def test_bad_prices_are_flagged_and_blocked(self):
        for value, check in [(0, "nonpositive_price"), (-1, "nonpositive_price"),
                             (np.inf, "nonfinite_price"), ("bad", "missing_or_nonnumeric_price")]:
            with self.subTest(value=value):
                frames = sample_frames()
                frames["SPY"]["adjusted_close"] = frames["SPY"]["adjusted_close"].astype(object)
                frames["SPY"].loc[1, "adjusted_close"] = value
                _, _, issues, blockers = self.audit(frames)
                self.assertTrue(blockers)
                self.assertIn(check, issues["check"].tolist())

    def test_invalid_date_blocks_analysis(self):
        frames = sample_frames()
        frames["SPY"].loc[1, "trade_date"] = "not-a-date"
        _, _, issues, blockers = self.audit(frames)
        self.assertTrue(blockers)
        self.assertIn("invalid_date", issues["check"].tolist())

    def test_outside_requested_range_is_logged(self):
        frames = sample_frames()
        extra = pd.DataFrame({"trade_date": ["2023-12-29"], "adjusted_close": [90.0]})
        frames["SPY"] = pd.concat([extra, frames["SPY"]], ignore_index=True)
        prices, _, issues, blockers = self.audit(frames)
        self.assertEqual(blockers, [])
        self.assertEqual(len(prices), 5)
        self.assertIn("out_of_range", issues["check"].tolist())

    def test_yahoo_shape_errors_are_explicit(self):
        with self.assertRaisesRegex(ValueError, "different lengths"):
            pipeline.read_chart({"chart": {"result": [{"timestamp": [1, 2],
                "indicators": {"adjclose": [{"adjclose": [100]}]}}]}})
        with self.assertRaisesRegex(ValueError, "no usable result"):
            pipeline.read_chart({"chart": {"result": None, "error": {"code": "Not Found"}}})


class SqlTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / "market_risk.sqlite"
        self.prices, _, _, _ = pipeline.audit_prices(sample_frames(), DATES[0], DATES[-1])
        pipeline.build_database(self.prices, self.database, PROJECT / "sql")

    def test_sql_returns_match_price_changes_and_first_return_is_null(self):
        returns = pipeline.export_sql_results(self.database, PROJECT / "sql", self.root)
        expected = self.prices.pct_change(fill_method=None).iloc[1:]
        pd.testing.assert_frame_equal(returns.reindex(columns=expected.columns), expected)
        with closing(sqlite3.connect(self.database)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM daily_returns WHERE daily_return IS NULL").fetchone()[0]
        self.assertEqual(count, 5)

    def test_monthly_returns_compound_and_include_first_day(self):
        with closing(sqlite3.connect(self.database)) as connection:
            values = connection.execute(
                "SELECT month, monthly_return, return_observations, return_start, coverage "
                "FROM monthly_performance WHERE symbol = 'SPY' ORDER BY month").fetchall()
        self.assertAlmostEqual(values[0][1], 0.10)
        self.assertAlmostEqual(values[1][1], -0.01)
        self.assertEqual(values[1][2], 3)
        self.assertEqual(values[1][3], "2024-01-31")
        self.assertEqual(values[1][4], "Sample boundary month")

    def test_worst_days_and_tied_monthly_rankings(self):
        pipeline.export_sql_results(self.database, PROJECT / "sql", self.root)
        worst = pd.read_csv(self.root / "sql_worst_days.csv")
        self.assertTrue((worst.loc[worst["loss_rank"] == 1, "trade_date"] == "2024-02-01").all())
        ranks = pd.read_csv(self.root / "sql_monthly_rankings.csv")
        self.assertTrue((ranks["performance_rank"] == 1).all())

    def test_database_constraints_reject_duplicate_and_invalid_price(self):
        with closing(sqlite3.connect(self.database)) as connection:
            for row in [(DATES[0], "SPY", 100.0), ("2024-02-06", "SPY", 0.0)]:
                with self.subTest(row=row), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO prices VALUES (?, ?, ?)", row)

    def test_rebuilding_database_does_not_accumulate_rows(self):
        pipeline.build_database(self.prices, self.database, PROJECT / "sql")
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM prices").fetchone()[0], 25)


class RiskTests(unittest.TestCase):
    def test_sharpe_uses_mean_excess_return(self):
        values = pd.Series([0.10, -0.08, 0.03, -0.01])
        with patch.object(risk, "RISK_FREE_RATE", 0.04):
            daily_rf = math.pow(1.04, 1 / 252) - 1
            expected = (values.mean() - daily_rf) / values.std(ddof=1) * math.sqrt(252)
            self.assertAlmostEqual(risk.sharpe_ratio(values), expected)

    def test_zero_volatility_sharpe_is_undefined(self):
        self.assertTrue(math.isnan(risk.sharpe_ratio(pd.Series([0.01, 0.01, 0.01]))))

    def test_drawdown_counts_initial_loss(self):
        values = pd.Series([-0.10, 0.05, -0.10])
        expected = pd.Series([-0.10, -0.055, -0.1495])
        pd.testing.assert_series_equal(risk.drawdowns(values), expected)
        pd.testing.assert_series_equal(risk.drawdown_table(pd.DataFrame({"asset": values}))["asset"],
                                       expected.rename("asset"))

    def test_drawdown_resets_after_new_high(self):
        values = pd.Series([-0.10, 0.25, -0.20])
        pd.testing.assert_series_equal(risk.drawdowns(values), pd.Series([-0.10, 0.0, -0.20]))


class SnapshotTests(unittest.TestCase):
    def test_offline_requires_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No saved snapshot"):
                pipeline.load_snapshot(Path(directory), DATES[0], DATES[-1], refresh=False, offline=True)

    def test_cached_snapshot_is_offline_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_dir = root / "data" / "raw"
            raw_dir.mkdir(parents=True)
            raw = b'{"fixture": true}'
            manifest = {"requested_start": DATES[0], "requested_end": DATES[-1], "files": {}}
            for symbol in pipeline.ASSETS:
                (raw_dir / f"{symbol}.json").write_bytes(raw)
                manifest["files"][symbol] = {"sha256": hashlib.sha256(raw).hexdigest()}
            (raw_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(pipeline, "urlopen", side_effect=AssertionError("Network used offline")):
                payloads, _ = pipeline.load_snapshot(root, DATES[0], DATES[-1], refresh=False, offline=True)
            self.assertEqual(len(payloads), 5)
            (raw_dir / "SPY.json").write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, "hash check failed"):
                pipeline.load_snapshot(root, DATES[0], DATES[-1], refresh=False, offline=True)

    def test_quality_failure_does_not_replace_existing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            database = root / "data" / "market_risk.sqlite"
            database.write_bytes(b"previous database")
            frames = sample_frames()
            frames["SPY"].loc[1, "adjusted_close"] = np.nan
            manifest = {"requested_start": DATES[0], "requested_end": DATES[-1],
                        "retrieved_at_utc": "test fixture"}
            with patch.object(pipeline, "load_snapshot", return_value=(dict.fromkeys(pipeline.ASSETS), manifest)), \
                 patch.object(pipeline, "read_chart", side_effect=list(frames.values())):
                with self.assertRaisesRegex(ValueError, "Data quality blocked"):
                    pipeline.prepare_data(root, DATES[0], DATES[-1], offline=True)
            self.assertEqual(database.read_bytes(), b"previous database")
            self.assertIn("BLOCKED", (root / "results" / "data_quality_report.md").read_text())


if __name__ == "__main__":
    unittest.main()
