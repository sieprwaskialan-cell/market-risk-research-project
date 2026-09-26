-- Boundary months can cover less than a full month; keep the coverage label.
SELECT m.month, a.symbol, a.name, a.asset_class,
       m.return_start, m.first_observation, m.last_observation,
       m.return_observations, m.monthly_return, m.coverage
FROM monthly_performance AS m
JOIN assets AS a ON a.symbol = m.symbol
ORDER BY m.month, a.symbol;
