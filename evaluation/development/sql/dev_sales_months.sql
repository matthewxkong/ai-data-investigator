SELECT strftime(order_date, '%Y-%m') AS month, SUM(quantity * unit_price) AS revenue_usd
FROM sales GROUP BY month ORDER BY month;
