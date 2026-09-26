-- ROW_NUMBER returns exactly five observations per asset (when available).
WITH ranked_days AS (
    SELECT symbol, trade_date, daily_return,
           ROW_NUMBER() OVER (
               PARTITION BY symbol ORDER BY daily_return, trade_date
           ) AS loss_rank
    FROM daily_returns
    WHERE daily_return IS NOT NULL
)
SELECT r.symbol, a.asset_class, r.loss_rank, r.trade_date, r.daily_return
FROM ranked_days AS r
JOIN assets AS a ON a.symbol = r.symbol
WHERE r.loss_rank <= 5
ORDER BY r.symbol, r.loss_rank;
