-- Q4b. The "solar dip": average price by hour of day, April-September, per country and year.
SELECT country_code,
       extract(year FROM date_local)::int AS year,
       hour_local,
       round(avg(price_eur_mwh)::numeric, 1) AS avg_price_eur_mwh
FROM mart.fact_country_hourly
WHERE extract(month FROM date_local) BETWEEN 4 AND 9
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
