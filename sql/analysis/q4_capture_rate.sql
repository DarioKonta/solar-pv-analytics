-- Q4c. Solar capture rate: the price solar actually earns (output-weighted) vs the time-weighted average price
-- over ALL hours. Below 100 % = solar sells at a discount ("cannibalisation"). Serbia uses the estimated profile.
SELECT country_code,
       extract(year FROM date_local)::int AS year,
       round((sum(solar_mwh * price_eur_mwh) / NULLIF(sum(solar_mwh), 0))::numeric, 1) AS solar_capture_price,
       round(avg(price_eur_mwh)::numeric, 1)                                            AS baseload_price,
       round((100 * (sum(solar_mwh * price_eur_mwh) / NULLIF(sum(solar_mwh), 0)) / avg(price_eur_mwh))::numeric, 1)
                                                                                        AS capture_rate_pct
FROM mart.v_solar_hourly
GROUP BY 1, 2
HAVING sum(solar_mwh) > 0
ORDER BY 1, 2;
