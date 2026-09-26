-- RANK gives equal returns the same position within each month.
SELECT month, symbol, monthly_return, coverage,
       RANK() OVER (
           PARTITION BY month ORDER BY monthly_return DESC
       ) AS performance_rank
FROM monthly_performance
WHERE monthly_return IS NOT NULL
ORDER BY month, performance_rank, symbol;
