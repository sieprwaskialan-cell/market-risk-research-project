from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {"__pycache__", ".venv", "venv", ".git", ".pbi", ".schema-cache", "node_modules", "qa"}
EXCLUDED_RESULTS = {"daily_returns.csv", "portfolio_daily.csv", "rolling_beta_vs_spy.csv", "rolling_volatility.csv"}


def main() -> None:
    destination = ROOT.parent.parent / "Market Risk Research Project - GitHub.zip"
    included = []
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(ROOT.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(ROOT)
            if any(part in EXCLUDED_DIRS for part in relative.parts):
                continue
            if relative.parts[0] == "data" or source.suffix in [".pyc", ".sqlite", ".abf"]:
                continue
            if relative.parts[0] == "results" and source.name in EXCLUDED_RESULTS:
                continue
            archive.write(source, Path(ROOT.name) / relative)
            included.append(str(relative))
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert any(name.endswith("dashboard/index.html") for name in names)
        assert any(name.endswith("results/findings_brief.pdf") for name in names)
        assert any(name.endswith("powerbi/Market Risk Research.pbip") for name in names)
    print(f"Created {destination}\n{len(included)} files; {destination.stat().st_size / 1_000_000:.2f} MB")


if __name__ == "__main__":
    main()
