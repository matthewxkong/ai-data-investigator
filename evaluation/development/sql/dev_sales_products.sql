SELECT product, SUM(quantity) AS units_sold
FROM sales GROUP BY product ORDER BY units_sold DESC, product ASC LIMIT 3;
