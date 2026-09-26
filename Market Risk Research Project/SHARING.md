# Sharing The Project

## GitHub

Suggested repository name: `market-risk-research-project`.

The prepared GitHub ZIP contains the project source, tests, documentation, dashboard,
Power BI definitions and selected outputs. Extract it and upload the contents of its
`Market Risk Research Project` folder so `README.md` is at the repository root.
Do not upload the ZIP itself as the repository's only file.

The ZIP excludes raw downloads, local databases, intermediate daily/rolling CSVs, temporary
test screenshots and Power BI caches. These exclusions also appear in `.gitignore` for Git
users. A manual browser upload does not apply `.gitignore` automatically.

The dashboard can be opened after downloading the repository. GitHub's normal file viewer
shows HTML source; it does not run the dashboard. Hosting it with GitHub Pages would be a
separate publishing step. This project has not been uploaded or published automatically.

## LinkedIn

Use `linkedin_post.md` as a draft and adapt it to how you would actually describe the work.
Tag Conor McMillan and add the real GitHub repository link after creating it.

Recommended attachments:

1. `results/findings_brief.pdf`: one page with the question, findings, comparison and limitations.
2. `results/portfolio_comparison.png`: the return and drawdown comparison.
3. `results/dashboard_preview.png`: the interactive dashboard's portfolio view.

The post should explain the question and one or two findings, not list every acronym.
The main result is a trade-off: lower volatility and a smaller full-period drawdown came with
lower annualized returns for the diversified allocation in this sample.

The native Power BI project is provided but has not been run in Desktop on this machine.
Do not claim a finished, tested Power BI dashboard or Power BI proficiency until you have
opened it, refreshed it and checked the results yourself.

## Interview Preparation

Be able to explain these decisions in your own words:

- Why calculate returns rather than correlating price levels?
- Why does a missing price create a problem for a daily return?
- What do `JOIN`, `LAG`, `ROW_NUMBER` and `RANK` do in these queries?
- Why do portfolio weights drift, and when does this simulation rebalance?
- What does a cost of 10 bps mean, and why is it charged on buys and sells?
- Why did adding bonds and gold reduce full-sample volatility without preventing a loss in 2022?
- Why are these historical comparisons not evidence of future returns?

Be accurate about your contribution and Conor's contribution. If asked about AI assistance,
explain how it was used and focus on the calculations, checks and interpretation you can verify.
