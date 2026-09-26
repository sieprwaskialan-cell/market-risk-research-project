from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sqlite3
import sys
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


ASSETS = {
    "SPY": ("SPDR S&P 500 ETF Trust", "Equity"),
    "QQQ": ("Invesco QQQ Trust", "Equity"),
    "IWM": ("iShares Russell 2000 ETF", "Equity"),
    "TLT": ("iShares 20+ Year Treasury Bond ETF", "Bonds"),
    "GLD": ("SPDR Gold Shares", "Gold"),
}
LARGE_MOVE_THRESHOLD = 0.10


def chart_url(symbol: str, start: str, end: str) -> str:
    first = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    last = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if first >= last:
        raise ValueError("Start date must be earlier than end date.")
    return (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={int(first.timestamp())}"
        f"&period2={int((last + timedelta(days=1)).timestamp())}"
        "&interval=1d&events=history&includeAdjustedClose=true"
    )


def read_chart(payload: dict) -> pd.DataFrame:
    chart = payload.get("chart", {})
    if chart.get("error") or not chart.get("result"):
        raise ValueError(f"Yahoo returned no usable result: {chart.get('error')}")
    result = chart["result"][0]
    timestamps = result.get("timestamp", [])
    adjusted = result.get("indicators", {}).get("adjclose", [])
    if not timestamps or not adjusted:
        raise ValueError("Yahoo response is missing timestamps or adjusted closes.")
    values = adjusted[0].get("adjclose", [])
    if len(timestamps) != len(values):
        raise ValueError("Yahoo timestamps and adjusted closes have different lengths.")
    dates = pd.to_datetime(timestamps, unit="s", utc=True, errors="coerce")
    return pd.DataFrame({"trade_date": dates.strftime("%Y-%m-%d"), "adjusted_close": values})


def load_snapshot(root: Path, start: str, end: str, *, refresh: bool, offline: bool) -> tuple[dict, dict]:
    raw_dir = root / "data" / "raw"
    manifest_path = raw_dir / "manifest.json"
    if offline and refresh:
        raise ValueError("Choose either --offline or --refresh.")
    manifest = None
    if manifest_path.exists() and not refresh:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["requested_start"] != start or manifest["requested_end"] != end:
            raise ValueError("Cached dates differ. Use --refresh to download the requested sample.")
        if set(manifest["files"]) != set(ASSETS):
            raise ValueError("Cached symbols differ. Use --refresh to rebuild the snapshot.")
    if manifest is not None:
        payloads = {}
        for symbol in ASSETS:
            raw = (raw_dir / f"{symbol}.json").read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest["files"][symbol]["sha256"]:
                raise ValueError(f"Saved {symbol} data changed; hash check failed. Use --refresh.")
            payloads[symbol] = json.loads(raw)
        return payloads, manifest
    if offline:
        raise ValueError("No saved snapshot exists. Run once without --offline to download it.")

    # Complete and validate all downloads before replacing the saved snapshot.
    downloaded = {}
    metadata = {}
    for symbol in ASSETS:
        url = chart_url(symbol, start, end)
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=30) as response:
            raw = response.read()
        read_chart(json.loads(raw))
        downloaded[symbol] = raw
        metadata[symbol] = {"source_url": url, "sha256": hashlib.sha256(raw).hexdigest()}
    manifest = {
        "source": "Yahoo Finance chart endpoint; daily adjusted close",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start": start,
        "requested_end": end,
        "files": metadata,
    }
    raw_dir.mkdir(parents=True, exist_ok=True)
    for symbol, raw in downloaded.items():
        (raw_dir / f"{symbol}.json").write_bytes(raw)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {symbol: json.loads(raw) for symbol, raw in downloaded.items()}, manifest


def audit_prices(frames: dict[str, pd.DataFrame], start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    summaries = []
    issues = []
    cleaned = {}
    observed_dates: set[str] = set()
    blockers = []

    def record(symbol: str, frame: pd.DataFrame, mask: pd.Series, check: str) -> None:
        for row in frame.loc[mask].itertuples(index=False):
            issues.append({"symbol": symbol, "trade_date": row.trade_date,
                           "check": check, "value": str(row.adjusted_close)})

    for symbol, source in frames.items():
        frame = source.copy()
        dates = pd.to_datetime(frame["trade_date"], errors="coerce")
        frame["trade_date"] = dates.dt.strftime("%Y-%m-%d")
        numeric = pd.to_numeric(frame["adjusted_close"], errors="coerce")
        bad_date = dates.isna()
        outside = dates.notna() & ~dates.between(pd.Timestamp(start), pd.Timestamp(end))
        missing = numeric.isna()
        infinite = numeric.notna() & ~np.isfinite(numeric)
        nonpositive = numeric.notna() & np.isfinite(numeric) & (numeric <= 0)
        checks = {
            "invalid_date": bad_date, "out_of_range": outside,
            "missing_or_nonnumeric_price": missing,
            "nonfinite_price": infinite, "nonpositive_price": nonpositive,
        }
        for check, mask in checks.items():
            record(symbol, frame, mask, check)
        observed_dates.update(frame.loc[~bad_date & ~outside, "trade_date"].tolist())
        valid = ~(bad_date | outside | missing | infinite | nonpositive)
        usable = frame.loc[valid].copy()
        usable["adjusted_close"] = numeric.loc[valid].astype(float)
        conflicting = usable.groupby("trade_date")["adjusted_close"].nunique()
        conflict_dates = conflicting[conflicting > 1].index
        conflicts = usable["trade_date"].isin(conflict_dates)
        record(symbol, usable, conflicts, "conflicting_duplicate")
        if len(conflict_dates):
            blockers.append(f"{symbol}: conflicting prices on {len(conflict_dates)} duplicate date(s).")
        usable = usable.loc[~conflicts]
        duplicates = usable.duplicated("trade_date", keep="first")
        record(symbol, usable, duplicates, "identical_duplicate_removed")
        usable = usable.loc[~duplicates].sort_values("trade_date")
        cleaned[symbol] = usable.set_index("trade_date")["adjusted_close"]
        if bad_date.any():
            blockers.append(f"{symbol}: invalid dates need review.")
        if usable.empty:
            blockers.append(f"{symbol}: no valid prices remain.")
        summaries.append({
            "symbol": symbol, "raw_rows": len(source),
            **{f"{check}_rows": int(mask.sum()) for check, mask in checks.items()},
            "identical_duplicates_removed": int(duplicates.sum()),
            "conflicting_duplicate_dates": len(conflict_dates),
            "rows_removed": len(source) - len(usable), "clean_rows": len(usable),
        })

    prices = pd.DataFrame(cleaned).reindex(sorted(observed_dates))
    prices.index = pd.to_datetime(prices.index)
    prices.index.name = "Date"
    changes = prices.pct_change(fill_method=None)
    for row in summaries:
        symbol = row["symbol"]
        missing_dates = prices.index[prices[symbol].isna()]
        row["missing_observed_sessions"] = len(missing_dates)
        row["first_valid_date"] = str(prices[symbol].first_valid_index())[:10]
        row["last_valid_date"] = str(prices[symbol].last_valid_index())[:10]
        for date in missing_dates:
            issues.append({"symbol": symbol, "trade_date": date.strftime("%Y-%m-%d"),
                           "check": "missing_observed_session", "value": ""})
        if len(missing_dates):
            blockers.append(f"{symbol}: {len(missing_dates)} observed session(s) lack a valid price.")
        large = changes[symbol].abs() >= LARGE_MOVE_THRESHOLD - 1e-12
        row["large_moves_flagged"] = int(large.sum())
        for date, value in changes.loc[large, symbol].items():
            issues.append({"symbol": symbol, "trade_date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                           "check": "large_move_review_only", "value": str(value)})
    if len(prices) < 3:
        blockers.append("At least three complete price dates are required.")
    return prices, pd.DataFrame(summaries), pd.DataFrame(
        issues, columns=["symbol", "trade_date", "check", "value"]
    ), blockers


def write_quality_report(output: Path, summary: pd.DataFrame, issues: pd.DataFrame,
                         blockers: list[str], manifest: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output / "data_quality_summary.csv", index=False)
    issues.to_csv(output / "data_quality_issues.csv", index=False)
    status = "BLOCKED: review issues before running analysis" if blockers else "PASS: structural checks passed"
    lines = ["# Data Quality Report", "", status, "",
             f"Requested dates: {manifest['requested_start']} to {manifest['requested_end']}.",
             f"Source snapshot retrieved (UTC): {manifest['retrieved_at_utc']}.", "",
             "| Asset | Raw rows | Removed | Clean rows | Missing sessions | Large moves |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in summary.itertuples(index=False):
        lines.append(f"| {row.symbol} | {row.raw_rows} | {row.rows_removed} | {row.clean_rows} | "
                     f"{row.missing_observed_sessions} | {row.large_moves_flagged} |")
    lines += ["", "## Policy", "",
              "- Identical duplicate observations are removed and logged. Conflicting duplicates block analysis.",
              "- Missing, nonnumeric, nonfinite and nonpositive prices are rejected and logged.",
              "- Missing sessions block analysis, preventing a multi-day return being labelled as a daily return.",
              "- Sessions are the union of dates in the five source series, not an official exchange calendar. "
              "A date missing from every source cannot be detected by this check.",
              "- Absolute daily moves of 10% or more are flagged and retained. A flag is not proof of bad data.",
              "- Check counts can overlap; rows_removed counts each discarded row once.",
              "- Adjusted prices are used as supplied. No prices are forward-filled or interpolated.",
              "- A structural pass does not independently verify the vendor's prices.", ""]
    if blockers:
        lines += ["## Blocking Issues", "", *[f"- {item}" for item in blockers], "",
                  "Existing analytical outputs, if present, belong to an earlier run and were not refreshed.", ""]
    flagged = issues[issues["check"] == "large_move_review_only"]
    if not flagged.empty:
        lines += ["## Moves To Review", "", "| Asset | Date | Daily return |", "| --- | --- | ---: |"]
        for row in flagged.itertuples(index=False):
            lines.append(f"| {row.symbol} | {row.trade_date} | {float(row.value):.2%} |")
    (output / "data_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_database(prices: pd.DataFrame, database_path: Path, sql_dir: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_suffix(".building.sqlite")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript((sql_dir / "schema.sql").read_text(encoding="utf-8"))
        connection.executemany("INSERT INTO assets VALUES (?, ?, ?)",
                               [(symbol, *ASSETS[symbol]) for symbol in prices.columns])
        connection.executemany("INSERT INTO prices VALUES (?, ?, ?)",
                               [(date.strftime("%Y-%m-%d"), symbol, float(value))
                                for symbol in prices.columns for date, value in prices[symbol].items()])
        connection.commit()
    finally:
        connection.close()
    temporary.replace(database_path)


def export_sql_results(database_path: Path, sql_dir: Path, output: Path) -> pd.DataFrame:
    connection = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
    try:
        for query in sorted(sql_dir.glob("[0-9][0-9]_*.sql")):
            result = pd.read_sql_query(query.read_text(encoding="utf-8"), connection)
            result.to_csv(output / f"sql_{query.stem[3:]}.csv", index=False)
        daily = pd.read_sql_query(
            "SELECT trade_date, symbol, daily_return FROM daily_returns "
            "WHERE daily_return IS NOT NULL ORDER BY trade_date, symbol", connection)
    finally:
        connection.close()
    daily.to_csv(output / "daily_returns.csv", index=False)
    returns = daily.pivot(index="trade_date", columns="symbol", values="daily_return")
    returns.index = pd.to_datetime(returns.index)
    returns.index.name = "Date"
    returns.columns.name = None
    return returns


def prepare_data(root: Path, start: str, end: str, *, refresh: bool = False, offline: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    payloads, manifest = load_snapshot(root, start, end, refresh=refresh, offline=offline)
    prices, summary, issues, blockers = audit_prices(
        {symbol: read_chart(payload) for symbol, payload in payloads.items()}, start, end)
    output = root / "results"
    write_quality_report(output, summary, issues, blockers, manifest)
    if blockers:
        raise ValueError("Data quality blocked analysis. See results/data_quality_report.md.")
    database = root / "data" / "market_risk.sqlite"
    build_database(prices, database, root / "sql")
    returns = export_sql_results(database, root / "sql", output).reindex(columns=prices.columns)
    expected = prices.pct_change(fill_method=None).iloc[1:]
    pd.testing.assert_frame_equal(returns, expected, check_exact=False, rtol=1e-12, atol=1e-12)
    manifest_output = dict(manifest)
    manifest_output.update({
        "analysis_run_at_utc": datetime.now(timezone.utc).isoformat(),
        "actual_first_price_date": prices.index[0].strftime("%Y-%m-%d"),
        "actual_last_price_date": prices.index[-1].strftime("%Y-%m-%d"),
        "prices_per_asset": len(prices), "returns_per_asset": len(returns),
        "sql_python_returns_match": True,
        "runtime": {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                    **{package: version(package) for package in ["pandas", "numpy", "matplotlib"]}},
    })
    (output / "run_metadata.json").write_text(json.dumps(manifest_output, indent=2) + "\n", encoding="utf-8")
    return prices, returns
