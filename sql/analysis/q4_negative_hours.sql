-- Q4a. Hours with at least one negative day-ahead price, per country and year.
SELECT country_code,
       extract(year FROM date_local)::int          AS year,
       count(*) FILTER (WHERE has_negative_price)   AS negative_hours,
       round(min(min_price_eur_mwh)::numeric, 1)    AS min_price_eur_mwh,
       round(avg(price_eur_mwh)::numeric, 1)        AS avg_price_eur_mwh
FROM mart.fact_country_hourly
GROUP BY 1, 2
ORDER BY 1, 2;
