SELECT warehouse, COUNT(*) AS reorder_count
FROM inventory WHERE on_hand - reserved < reorder_point
GROUP BY warehouse ORDER BY warehouse;
