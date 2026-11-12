SELECT category, SUM(resolution_hours) AS total_resolution_hours
FROM tickets WHERE status = 'resolved' GROUP BY category ORDER BY category;
