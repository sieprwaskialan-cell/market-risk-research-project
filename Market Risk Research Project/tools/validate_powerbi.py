from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import fastjsonschema


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "tools" / ".schema-cache"


def fetch_schema(url: str) -> dict:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if not path.exists():
        with urlopen(url, timeout=30) as response:
            value = json.load(response)
        path.write_text(json.dumps(value), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    compiled = {}
    checked = []
    for path in sorted((ROOT / "powerbi").rglob("*")):
        if not path.is_file() or path.suffix not in [".json", ".pbip", ".pbir", ".pbism"]:
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        schema = value.get("$schema")
        if not schema:
            continue
        if schema not in compiled:
            compiled[schema] = fastjsonschema.compile(fetch_schema(schema), handlers={"https": fetch_schema}, use_default=False)
        compiled[schema](value)
        checked.append(str(path.relative_to(ROOT)))
    model = json.loads((ROOT / "powerbi" / "MarketRisk.SemanticModel" / "model.bim").read_text())
    tables = {table["name"]: table for table in model["model"]["tables"]}
    for relationship in model["model"]["relationships"]:
        for side in ["from", "to"]:
            columns = {c["name"] for c in tables[relationship[side + "Table"]]["columns"]}
            assert relationship[side + "Column"] in columns
    for page in (ROOT / "powerbi" / "MarketRisk.Report" / "definition" / "pages").iterdir():
        if not page.is_dir():
            continue
        geometry = json.loads((page / "page.json").read_text())
        boxes = []
        for path in page.rglob("visual.json"):
            value = json.loads(path.read_text())
            box = value["position"]
            assert box["x"] >= 0 and box["y"] >= 0
            assert box["x"] + box["width"] <= geometry["width"]
            assert box["y"] + box["height"] <= geometry["height"]
            for other in boxes:
                assert (box["x"] + box["width"] <= other["x"] or other["x"] + other["width"] <= box["x"] or
                        box["y"] + box["height"] <= other["y"] or other["y"] + other["height"] <= box["y"])
            boxes.append(box)
            for role in value["visual"]["query"]["queryState"].values():
                for projection in role["projections"]:
                    kind, reference = next(iter(projection["field"].items()))
                    target = tables[reference["Expression"]["SourceRef"]["Entity"]]
                    assert reference["Property"] in {f["name"] for f in target["measures" if kind == "Measure" else "columns"]}
    report = {"report_schema_validation": "passed", "files_checked": len(checked),
              "model_references_and_visual_bounds": "passed", "desktop_runtime_validation": "not run: Power BI Desktop is not installed",
              "scope": "JSON schemas, relationship and field references, and non-overlapping page layout. DAX and Power Query execution require Desktop.",
              "checked_files": checked}
    (ROOT / "powerbi" / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "checked_files"}, indent=2))


if __name__ == "__main__":
    main()
