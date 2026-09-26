from __future__ import annotations

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one read-only SQL query against the project database.")
    parser.add_argument("query", nargs="?", default="sql/01_data_coverage.sql", help="Path to a SELECT query file.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    database = root / "data" / "market_risk.sqlite"
    if not database.exists():
        parser.error("Run market_risk_snapshot.py first to create the database.")
    query = root / args.query
    with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only = ON")
        results = pd.read_sql_query(query.read_text(encoding="utf-8"), connection)
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
