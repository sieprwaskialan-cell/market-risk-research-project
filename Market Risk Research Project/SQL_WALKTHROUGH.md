# SQL: First Steps With This Project

SQL stands for Structured Query Language. It lets you ask questions of tables in a database.
SQLite is the database engine we use here. Python handles downloading and checking the data;
SQL works on the accepted observations; Python then calculates risk and draws the charts.

## 1. Understand The Two Tables

`assets` has one row per ETF: its symbol, name and asset class.
`prices` has one row per ETF per date: the date, symbol and adjusted closing price.
The symbol connects the tables. A `JOIN` combines their information without copying the
asset name and class into every price record.

The combination of symbol and date is a primary key in `prices`, so the database will
reject a second record for the same asset and date.

## 2. Run Your First Query

Open the project folder in VS Code and open its terminal. Run:

```powershell
python run_sql.py sql/01_data_coverage.sql
```

Open `sql/01_data_coverage.sql` alongside the output:

```sql
SELECT a.symbol, a.name, a.asset_class,
       MIN(p.trade_date) AS first_date,
       MAX(p.trade_date) AS last_date,
       COUNT(p.trade_date) AS price_observations
FROM assets AS a
LEFT JOIN prices AS p ON p.symbol = a.symbol
GROUP BY a.symbol, a.name, a.asset_class
ORDER BY a.symbol;
```

- `SELECT` chooses what appears in the result.
- `a` and `p` are short names for the two tables.
- `LEFT JOIN` keeps every asset even if it has no matching price rows.
- `MIN` and `MAX` find the earliest and latest dates.
- `COUNT(p.trade_date)` counts matched prices, not the empty side of a join.
- `GROUP BY` gives a separate summary for each asset.
- `ORDER BY` controls the display order.

Check whether all five assets have the same date range and number of observations.
Explain why a comparison could be misleading if one asset had a much shorter history.

## 3. Understand The Return Calculation

The `daily_returns` view is a saved query, defined in `sql/schema.sql`.
`LAG(adjusted_close) OVER (PARTITION BY symbol ORDER BY trade_date)` fetches the previous
price for the same asset. It must not mix SPY's current price with QQQ's previous price.

The formula is:

```text
daily return = current adjusted close / previous adjusted close - 1
```

For example, moving from 100 to 102 gives 102 / 100 - 1 = 0.02, or 2%.
The first price has no previous observation, so its return is `NULL`, not zero.

Monthly returns compound: a gain of 10% followed by a loss of 10% leaves
100 x 1.10 x 0.90 = 99, a loss of 1%. Adding those percentages would incorrectly give zero.
Our monthly query uses the last adjusted price divided by the price before the first
return in that month. This includes the move on the month's first trading day.

## 4. Investigate The Worst Days

```powershell
python run_sql.py sql/03_worst_days.sql
```

`ROW_NUMBER` numbers observations within each asset, starting with its lowest return.
Keeping ranks 1 to 5 gives its five worst days. The date breaks ties consistently.
Find the worst SPY day and compare it with QQQ on the same date in `results/daily_returns.csv`.
Describe the observation without claiming that one caused the other to fall.

## 5. Make A Small Change Yourself

In `sql/03_worst_days.sql`, change `WHERE r.loss_rank <= 5` to `WHERE r.loss_rank <= 3`.
Run the query again. You should get three rows per asset. Change it back afterwards.
This query is read-only: it changes which rows you see, not the stored data.

Then run `python run_sql.py sql/04_monthly_rankings.sql`. Here `RANK` gives tied monthly
returns the same rank. This differs from `ROW_NUMBER`, which assigns a unique row number.

## 6. Explain The Quality Checks

Read `results/data_quality_report.md`. Missing prices, duplicates and large returns are
different problems. An identical duplicate can be removed; two different prices for the
same date need investigation. A large return may be a real event and is retained for review.
Missing sessions block the analysis so a return spanning several days is not presented as
a one-day observation.

Before describing this project in an interview, practise explaining the return formula,
one `JOIN`, one window function and one data-quality decision in your own words.
