-- Q5b. How variable is solar from day to day in each month? (Hungary, published data)
-- Coefficient of variation of daily output, and the ratio of the best to the worst day.
WITH daily AS (
    SELECT date_local, sum(solar_mwh) AS mwh
    FROM mart.fact_country_hourly WHERE country_code = 'hu' AND date_local BETWEEN '2025-01-01' AND '2025-12-31'
    GROUP BY 1
)
SELECT extract(month FROM date_local)::int              AS month,
       round((avg(mwh) / 1e3)::numeric, 1)               AS avg_daily_gwh,
       round((100 * stddev(mwh) / avg(mwh))::numeric)     AS cv_pct,
       round((max(mwh) / NULLIF(min(mwh), 0))::numeric, 1) AS best_to_worst_day
FROM daily GROUP BY 1 ORDER BY 1;
