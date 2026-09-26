# Power BI Project

Open `Market Risk Research.pbip` in a recent version of Power BI Desktop, then choose **Refresh**
to load the embedded snapshot. The model uses Power Query tables containing the checked data;
there are no personal file paths, credentials or external data-source settings to configure.
If Desktop requests it, enable the Power BI Project preview option and restart Desktop.

Microsoft's [project documentation](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview)
describes opening PBIP/PBIR files and the required preview settings. A local Desktop refresh
does not fetch current market prices: it loads the snapshot included in this project.
To download a new snapshot, rerun the Python project with `--refresh` first.

## Pages

- **Portfolios | monthly, 10 bps**: date and portfolio slicers, a growth chart and a comparison
  table with total return, annualized return, volatility, drawdown, Sharpe and observation counts.
- **SQL results & data quality**: monthly return records with coverage labels, asset/month slicers,
  and a separate full-sample quality table. These tables are independent: monthly slicers do not filter the audit.

## Model

`Portfolio` and `Date` are dimension tables, each with a one-to-many relationship into `Daily`.
`Monthly` and `Quality` hold independently reported SQL outputs and the source audit.

The default portfolio model uses monthly rebalancing with 10 bps per dollar bought or sold,
including entry. The browser dashboard contains the additional cost and buy-and-hold scenarios.
Measures in `measures.dax` are also embedded in the model. Measures return blank where a combined
result across different portfolios would be meaningless. The risk-free rate is assumed to be zero.

## Validation Status

The report definitions pass Microsoft's JSON schemas. Field and relationship references,
visual bounds and non-overlapping layouts are checked by `tools/validate_powerbi.py`.
The result is recorded in `validation.json`.

**Power BI Desktop is not installed on the build machine. The Power Query snapshot, DAX measures
and rendered report have therefore not been executed or visually checked in Desktop.** Schema
validation is not a substitute for that check. Use the tested offline browser dashboard until
you have performed the checks below. Do not describe the native report as Desktop-tested yet.

## Checks After Opening

1. Refresh and confirm that `Daily` has 6,567 rows (2,189 return dates for each of three portfolios)
   for the included 2018-2026 snapshot.
2. With no date filter, compare all three table rows against `../results/portfolio_summary.csv`.
3. For Stocks, bonds & gold, the default sample should show about 159.2% total return, 11.6%
   annualized return, 13.6% volatility, -26.1% maximum drawdown and a Sharpe ratio of 0.87.
4. Filter to 2022. The diversified portfolio's total return should be about -20.8%.
5. Confirm the growth chart and table respond to date/portfolio selections. The first plotted
   point includes the first selected return; the browser chart additionally shows a $10,000 baseline point.
6. Save a `.pbix` copy after checking the results. Keep the PBIP source folders together.

Regenerating the Python project overwrites the generated model, measures and report definitions.
Save your own edited report in a separate folder before rebuilding.
