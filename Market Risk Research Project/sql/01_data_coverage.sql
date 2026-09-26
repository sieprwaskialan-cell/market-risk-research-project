-- Does each asset have the same usable date range and number of observations?
SELECT a.symbol, a.name, a.asset_class,
       MIN(p.trade_date) AS first_date,
       MAX(p.trade_date) AS last_date,
       COUNT(p.trade_date) AS price_observations
FROM assets AS a
LEFT JOIN prices AS p ON p.symbol = a.symbol
GROUP BY a.symbol, a.name, a.asset_class
ORDER BY a.symbol;
