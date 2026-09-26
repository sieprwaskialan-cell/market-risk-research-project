PRAGMA foreign_keys = ON;

CREATE TABLE assets (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    asset_class TEXT NOT NULL
);

CREATE TABLE prices (
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL REFERENCES assets(symbol),
    adjusted_close REAL NOT NULL CHECK (adjusted_close > 0),
    PRIMARY KEY (symbol, trade_date)
);

CREATE VIEW daily_returns AS
WITH previous_prices AS (
    SELECT trade_date, symbol, adjusted_close,
           LAG(adjusted_close) OVER (
               PARTITION BY symbol ORDER BY trade_date
           ) AS previous_close,
           LAG(trade_date) OVER (
               PARTITION BY symbol ORDER BY trade_date
           ) AS previous_date
    FROM prices
)
SELECT trade_date, symbol, adjusted_close, previous_close, previous_date,
       adjusted_close / previous_close - 1.0 AS daily_return
FROM previous_prices;

-- Use price ratios to compound monthly returns, including the first day's move.
CREATE VIEW monthly_performance AS
WITH numbered AS (
    SELECT *, SUBSTR(trade_date, 1, 7) AS month,
           ROW_NUMBER() OVER (
               PARTITION BY symbol, SUBSTR(trade_date, 1, 7)
               ORDER BY trade_date
           ) AS first_in_month,
           ROW_NUMBER() OVER (
               PARTITION BY symbol, SUBSTR(trade_date, 1, 7)
               ORDER BY trade_date DESC
           ) AS last_in_month
    FROM daily_returns
)
SELECT month, symbol,
       MIN(trade_date) AS first_observation,
       MAX(trade_date) AS last_observation,
       MAX(CASE WHEN first_in_month = 1
                THEN COALESCE(previous_date, trade_date) END) AS return_start,
       COUNT(daily_return) AS return_observations,
       CASE WHEN COUNT(daily_return) > 0 THEN
           MAX(CASE WHEN last_in_month = 1 THEN adjusted_close END)
           / MAX(CASE WHEN first_in_month = 1
                      THEN COALESCE(previous_close, adjusted_close) END) - 1.0
       END AS monthly_return,
       CASE WHEN month IN (
           (SELECT SUBSTR(MIN(trade_date), 1, 7) FROM prices),
           (SELECT SUBSTR(MAX(trade_date), 1, 7) FROM prices)
       ) THEN 'Sample boundary month' ELSE 'Interior sample month' END AS coverage
FROM numbered
GROUP BY month, symbol;
