SELECT priority, COUNT(*) AS ticket_count
FROM tickets GROUP BY priority ORDER BY priority;
