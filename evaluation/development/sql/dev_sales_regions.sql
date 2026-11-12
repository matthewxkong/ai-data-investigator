SELECT region, SUM(quantity * unit_price) AS revenue_usd
FROM sales GROUP BY region ORDER BY region;
