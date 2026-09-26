from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from build_powerbi import build_powerbi


def conclusions(data: dict) -> list[str]:
    rows = {r["portfolio"]: r for r in data["summary"]}
    diversified, equity, spy = (rows[key] for key in ["diversified", "equity", "spy"])
    reduction = (1 - diversified["annualized_volatility"] / equity["annualized_volatility"]) * 100
    verb = "lower" if reduction >= 0 else "higher"
    result = [
        f"The stocks, bonds and gold mix had {diversified['annualized_volatility']:.1%} annualized volatility, "
        f"{abs(reduction):.1f}% {verb} than the equity mix's {equity['annualized_volatility']:.1%}.",
        f"Its maximum drawdown was {diversified['max_drawdown']:.1%}, compared with {equity['max_drawdown']:.1%} "
        f"for the equity mix and {spy['max_drawdown']:.1%} for SPY alone.",
        f"The diversified mix returned {diversified['annualized_return']:.1%} annualized, versus "
        f"{equity['annualized_return']:.1%} for the equity mix. The risk and return trade-off both matter.",
    ]
    year = next((r for r in data["periods"] if r["period"] == "2022 calendar year" and r["portfolio"] == "diversified"), None)
    if year:
        result.append(f"In 2022 the diversified mix returned {year['total_return']:.1%}. Diversification did not guarantee a positive return in that window.")
    return result


def build_brief(root: Path, data: dict) -> None:
    output = root / "results"
    findings = conclusions(data)
    sample = f"{data['metadata']['actual_first_price_date']} to {data['metadata']['actual_last_price_date']}"
    rows = data["summary"]
    lines = ["# Market Risk Research Project", "", "Alan Sieprawski | Contributor: Conor McMillan", "", f"Sample: {sample}. USD.", "",
             "## Question", "", "How did adding bonds and gold change the risk and return of a US equity portfolio?", "",
             "## Findings", "", *[f"- {item}" for item in findings], "",
             "## Comparison", "", "| Portfolio | Annualized return | Volatility | Max drawdown | Sharpe |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for r in rows:
        lines.append(f"| {r['name']} | {r['annualized_return']:.1%} | {r['annualized_volatility']:.1%} | {r['max_drawdown']:.1%} | {r['sharpe_ratio']:.2f} |")
    method = ("Fixed weights: SPY only (100% SPY); equity mix (one-third SPY, QQQ and IWM); diversified mix "
              "(20% each in SPY, QQQ, IWM, TLT and GLD). Weights drift between monthly resets. Costs are 10 bps "
              "per dollar bought or sold, including entry; no terminal liquidation. Risk-free rate: assumed 0%. "
              "Annualization: 252 trading days. Adjusted closes: Yahoo Finance.")
    limitations = ("This is a descriptive comparison with chosen assets and periods, not an optimized strategy or a predictive test. "
                   "Taxes, liquidity and market impact are excluded. Large price moves are retained for review, not independently verified. "
                   "Results depend on the sample and assumptions.")
    recommendation = "For risk reporting, compare losses, volatility and returns together, and show how conclusions change across periods and cost assumptions."
    lines += ["", "## Interpretation", "", recommendation, "", "## Method", "", method, "", "## Limits", "", limitations, ""]
    (output / "findings_brief.md").write_text("\n".join(lines), encoding="utf-8")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ResearchTitle", fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=colors.HexColor("#253d3a"), spaceAfter=6))
    styles.add(ParagraphStyle(name="ResearchBody", fontName="Helvetica", fontSize=9, leading=12.5, spaceAfter=6))
    styles.add(ParagraphStyle(name="ResearchSmall", fontName="Helvetica", fontSize=7.5, leading=10, textColor=colors.HexColor("#54645f"), spaceAfter=5))
    styles.add(ParagraphStyle(name="ResearchHeading", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=8, spaceAfter=5))
    story = [Paragraph("Market Risk Research Project", styles["ResearchTitle"]),
             Paragraph(f"Alan Sieprawski | Contributor: Conor McMillan &nbsp;&nbsp; / &nbsp;&nbsp; {sample}", styles["ResearchSmall"]),
             Paragraph("How did adding bonds and gold change portfolio risk?", styles["ResearchHeading"])]
    for item in findings[:3]:
        story.append(Paragraph(escape(item), styles["ResearchBody"]))
    cells = [["Portfolio", "Ann. return", "Volatility", "Drawdown", "Sharpe"]] + [
        [r["name"], f"{r['annualized_return']:.1%}", f"{r['annualized_volatility']:.1%}", f"{r['max_drawdown']:.1%}", f"{r['sharpe_ratio']:.2f}"] for r in rows]
    comparison = Table(cells, colWidths=[63*mm, 29*mm, 28*mm, 28*mm, 24*mm])
    comparison.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6efeb")),
                                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
                                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
                                    ("LINEBELOW", (0, 0), (-1, -1), .35, colors.HexColor("#d9e2dd"))]))
    story += [Spacer(1, 6), comparison, Spacer(1, 7), Image(str(output / "portfolio_comparison.png"), width=172*mm, height=110.7*mm)]
    if len(findings) > 3:
        story.append(Paragraph(escape(findings[3]), styles["ResearchBody"]))
    story += [Paragraph("Method and limits", styles["ResearchHeading"]), Paragraph(escape(method), styles["ResearchSmall"]),
              Paragraph(escape(limitations), styles["ResearchSmall"])]
    SimpleDocTemplate(str(output / "findings_brief.pdf"), pagesize=A4, leftMargin=19*mm, rightMargin=19*mm,
                      topMargin=16*mm, bottomMargin=15*mm, title="Market Risk Research Project", author="Alan Sieprawski; Conor McMillan").build(story)


def write_linkedin_post(root: Path, data: dict) -> None:
    rows = {row["portfolio"]: row for row in data["summary"]}
    mixed, equity = rows["diversified"], rows["equity"]
    reduction = (1 - mixed["annualized_volatility"] / equity["annualized_volatility"]) * 100
    risk_direction = "lower" if reduction >= 0 else "higher"
    return_direction = "lower" if mixed["annualized_return"] < equity["annualized_return"] else "higher"
    year = next((row for row in data["periods"]
                 if row["period"] == "2022 calendar year" and row["portfolio"] == "diversified"), None)
    year_note = ""
    if year is not None and year["total_return"] < 0:
        year_note = f" It still lost about {abs(year['total_return']):.0%} in 2022."
    post = (
        "# LinkedIn Post Draft\n\n"
        "I've been working on a market risk project with Conor McMillan alongside my Maths with Economics degree.\n\n"
        "We looked at whether adding bonds and gold to an equity portfolio reduced risk, and what happened to returns.\n\n"
        f"Using data from {data['metadata']['actual_first_price_date'][:4]} to "
        f"{data['metadata']['actual_last_price_date'][:4]}, the mix with bonds and gold had about "
        f"{abs(reduction):.0f}% {risk_direction} volatility than the equity-only mix, but also a "
        f"{return_direction} annualized return.{year_note}\n\n"
        "The project uses Python and SQL, with a dashboard to compare the portfolios across different periods and trading costs. "
        "The results depend on the dates and assumptions used.\n\n"
        "I'm still learning, so feedback on the approach or anything I've missed would be appreciated.\n\n"
        "Code and results: [add GitHub link]\n\n"
        "<!-- Before posting: tag Conor McMillan, replace the link placeholder, and keep only wording you are comfortable explaining. -->\n"
    )
    (root / "linkedin_post.md").write_text(post, encoding="utf-8")


def build_deliverables(root: Path, data: dict) -> None:
    build_brief(root, data)
    build_powerbi(root, data)
    write_linkedin_post(root, data)
