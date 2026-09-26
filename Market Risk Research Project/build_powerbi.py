from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path


SCHEMAS = "https://developer.microsoft.com/json-schemas/fabric/"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def m_value(value, kind: str) -> str:
    if value is None:
        return "null"
    if kind == "dateTime":
        parts = str(value)[:10].split("-")
        return "#date(" + ",".join(str(int(part)) for part in parts) + ")"
    if kind == "string":
        return '"' + str(value).replace('"', '""') + '"'
    return repr(value)


def table(name: str, columns: list[tuple[str, str]], rows: list[list]) -> dict:
    types = {"dateTime": "date", "string": "text", "double": "number", "int64": "Int64.Type"}
    fields = ", ".join(f"{column} = {types[kind]}" for column, kind in columns)
    expression = [f"#table(type table [{fields}], {{"]
    expression += ["{" + ",".join(m_value(value, kind) for value, (_, kind) in zip(row, columns)) + "}" +
                   ("," if i < len(rows) - 1 else "") for i, row in enumerate(rows)]
    expression += ["})"]
    return {
        "name": name,
        "columns": [{"name": column, "dataType": kind, "sourceColumn": column,
                     "summarizeBy": "none", **({"formatString": "yyyy-MM-dd"} if kind == "dateTime" else {})}
                    for column, kind in columns],
        "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": expression}}],
    }


def field(entity: str, name: str, measure: bool = False) -> dict:
    return {"Measure" if measure else "Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": name}}


def projection(entity: str, name: str, measure: bool = False) -> dict:
    return {"field": field(entity, name, measure), "queryRef": f"{entity}.{name}", "nativeQueryRef": name}


def visual(name: str, kind: str, title: str, x: int, y: int, width: int, height: int, roles: dict) -> dict:
    return {
        "$schema": SCHEMAS + "item/report/definition/visualContainer/1.0.0/schema.json",
        "name": name, "position": {"x": x, "y": y, "width": width, "height": height, "z": 0, "tabOrder": y + x},
        "visual": {"visualType": kind,
                   "query": {"queryState": {role: {"projections": fields} for role, fields in roles.items()}},
                   "visualContainerObjects": {"title": [{"properties": {
                       "show": {"expr": {"Literal": {"Value": "true"}}},
                       "text": {"expr": {"Literal": {"Value": "'" + title.replace("'", "''") + "'"}}},
                   }}]}, "drillFilterOtherVisuals": True},
    }


def build_powerbi(root: Path, data: dict) -> None:
    output = root / "powerbi"
    model_dir = output / "MarketRisk.SemanticModel"
    report_dir = output / "MarketRisk.Report"
    write_json(output / "Market Risk Research.pbip", {
        "$schema": SCHEMAS + "pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": "MarketRisk.Report"}}], "settings": {"enableAutoRecovery": True},
    })
    write_json(model_dir / "definition.pbism", {
        "$schema": SCHEMAS + "item/semanticModel/definitionProperties/1.0.0/schema.json", "version": "1.0",
    })
    write_json(report_dir / "definition.pbir", {
        "$schema": SCHEMAS + "item/report/definitionProperties/2.0.0/schema.json", "version": "4.0",
        "datasetReference": {"byPath": {"path": "../MarketRisk.SemanticModel"}},
    })
    portfolio = table("Portfolio", [("Portfolio", "string"), ("Name", "string")],
                      [[key, value["name"]] for key, value in data["portfolios"].items()])
    start, end = date.fromisoformat(data["dates"][0]), date.fromisoformat(data["dates"][-1])
    dates = table("Date", [("Date", "dateTime")], [[str(start + timedelta(days=i))] for i in range((end - start).days + 1)])
    daily = table("Daily", [("Date", "dateTime"), ("Portfolio", "string"), ("NetReturn", "double")],
                  [[day, key, value] for key, values in data["scenarios"]["monthly_10"].items()
                   for day, value in zip(data["dates"], values)])
    expressions = {
        "Observations": "IF(HASONEVALUE(Portfolio[Portfolio]), COUNTROWS(Daily))",
        "Total Return": "IF(HASONEVALUE(Portfolio[Portfolio]) && COUNTROWS(Daily)>0, PRODUCTX(Daily, 1+Daily[NetReturn])-1)",
        "Annualized Return": "IF([Observations]>1, POWER(1+[Total Return], 252/[Observations])-1)",
        "Volatility": "IF([Observations]>1, STDEVX.S(Daily, Daily[NetReturn])*SQRT(252))",
        "Sharpe": "DIVIDE(AVERAGEX(Daily, Daily[NetReturn])*252, [Volatility])",
        "Max Drawdown": """IF([Observations]>1,
VAR Points = SELECTCOLUMNS(Daily, "Day", Daily[Date], "Ret", Daily[NetReturn])
VAR Wealths = ADDCOLUMNS(Points, "W", VAR Today = [Day] RETURN PRODUCTX(FILTER(Points, [Day]<=Today), 1+[Ret]))
RETURN MINX(Wealths, VAR Today = [Day] VAR Peak = MAX(1, MAXX(FILTER(Wealths, [Day]<=Today), [W])) RETURN [W]/Peak-1))""",
        "Growth of 10000": """VAR Today = MAX('Date'[Date])
RETURN CALCULATE(10000*(1+[Total Return]), FILTER(ALLSELECTED('Date'), 'Date'[Date]<=Today))""",
    }
    daily["measures"] = [{"name": name, "expression": expression.splitlines(),
                           "formatString": "0.00" if name == "Sharpe" else "#,0" if name in ["Observations", "Growth of 10000"] else "0.0%;-0.0%;0.0%"}
                          for name, expression in expressions.items()]
    monthly = table("Monthly", [("Month", "string"), ("Symbol", "string"), ("MonthlyReturn", "double"), ("Coverage", "string")],
                    [[r["month"], r["symbol"], r["monthly_return"] if r["monthly_return"] != "" else None, r["coverage"]] for r in data["monthly"]])
    monthly["columns"][2]["formatString"] = "0.0%;-0.0%;0.0%"
    quality = table("Quality", [("Symbol", "string"), ("Prices", "int64"), ("Removed", "int64"), ("Missing", "int64"), ("LargeMoves", "int64")],
                    [[r["symbol"], r["raw_rows"], r["rows_removed"], r["missing_observed_sessions"], r["large_moves_flagged"]] for r in data["quality"]])
    write_json(model_dir / "model.bim", {
        "name": "MarketRisk", "compatibilityLevel": 1567,
        "model": {"culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3",
                  "tables": [portfolio, dates, daily, monthly, quality],
                  "relationships": [
                      {"name": "Daily_Portfolio", "fromTable": "Daily", "fromColumn": "Portfolio", "toTable": "Portfolio", "toColumn": "Portfolio"},
                      {"name": "Daily_Date", "fromTable": "Daily", "fromColumn": "Date", "toTable": "Date", "toColumn": "Date"},
                  ]},
    })
    definition = report_dir / "definition"
    write_json(definition / "version.json", {"$schema": SCHEMAS + "item/report/definition/versionMetadata/1.0.0/schema.json", "version": "4.0.0"})
    write_json(definition / "report.json", {"$schema": SCHEMAS + "item/report/definition/report/1.0.0/schema.json",
                                            "layoutOptimization": "None", "themeCollection": {}})
    write_json(definition / "pages" / "pages.json", {"$schema": SCHEMAS + "item/report/definition/pagesMetadata/1.0.0/schema.json",
                                                        "pageOrder": ["PortfolioComparison", "DataEvidence"], "activePageName": "PortfolioComparison"})
    for name, title in [("PortfolioComparison", "Portfolios | monthly, 10 bps"), ("DataEvidence", "SQL results & data quality")]:
        write_json(definition / "pages" / name / "page.json", {
            "$schema": SCHEMAS + "item/report/definition/page/1.0.0/schema.json",
            "name": name, "displayName": title, "displayOption": "FitToPage", "width": 1280, "height": 800,
        })
    visuals = [
        visual("DateFilter", "slicer", "Return dates", 20, 15, 390, 110, {"Values": [projection("Date", "Date")]}),
        visual("PortfolioFilter", "slicer", "Portfolios", 440, 15, 820, 110, {"Values": [projection("Portfolio", "Name")]}),
        visual("Growth", "lineChart", "Growth of $10,000 | net of costs", 20, 145, 1240, 350, {
            "Category": [projection("Date", "Date")], "Series": [projection("Portfolio", "Name")],
            "Y": [projection("Daily", "Growth of 10000", True)]}),
        visual("Comparison", "tableEx", "Selected-window metrics | 0% assumed risk-free rate", 20, 515, 1240, 260, {
            "Values": [projection("Portfolio", "Name"), *[projection("Daily", name, True)
                       for name in ["Total Return", "Annualized Return", "Volatility", "Max Drawdown", "Sharpe", "Observations"]]]}),
    ]
    for item in visuals:
        write_json(definition / "pages" / "PortfolioComparison" / "visuals" / item["name"] / "visual.json", item)
    evidence = [
        visual("MonthlySQL", "tableEx", "Monthly returns from SQL | boundary months labelled", 20, 20, 760, 750, {
            "Values": [projection("Monthly", column) for column in ["Month", "Symbol", "MonthlyReturn", "Coverage"]]}),
        visual("QualityAudit", "tableEx", "Full-sample quality checks | flags retained", 805, 20, 455, 350, {
            "Values": [projection("Quality", column) for column in ["Symbol", "Prices", "Removed", "Missing", "LargeMoves"]]}),
        visual("AssetFilter", "slicer", "Monthly results: asset", 805, 395, 455, 180, {"Values": [projection("Monthly", "Symbol")]}),
        visual("MonthFilter", "slicer", "Monthly results: month", 805, 600, 455, 170, {"Values": [projection("Monthly", "Month")]}),
    ]
    for item in evidence:
        write_json(definition / "pages" / "DataEvidence" / "visuals" / item["name"] / "visual.json", item)
    (output / "measures.dax").write_text("\n\n".join(f"{name} =\n{expr}" for name, expr in expressions.items()) + "\n", encoding="utf-8")
