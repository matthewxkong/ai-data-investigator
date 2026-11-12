SELECT warehouse, SUM(on_hand * unit_cost) AS stock_value_usd
FROM inventory GROUP BY warehouse ORDER BY warehouse;
