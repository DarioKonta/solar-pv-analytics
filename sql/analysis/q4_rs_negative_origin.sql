-- Q4d. Are Serbia's negative prices home-grown or imported?
-- For every hour Serbia was negative: own solar share of demand, and how many neighbours were negative too.
WITH rs AS (
    SELECT hour_utc, solar_mwh / NULLIF(load_mwh, 0) AS solar_share
    FROM mart.v_solar_hourly
    WHERE country_code = 'rs' AND has_negative_price
),
nb AS (
    SELECT hour_utc, count(*) FILTER (WHERE has_negative_price) AS neighbours_negative
    FROM mart.fact_country_hourly WHERE country_code <> 'rs' GROUP BY 1
)
SELECT count(*)                                                    AS rs_negative_hours,
       round((100 * avg(rs.solar_share))::numeric, 1)              AS rs_avg_solar_pct_of_load,
       round(avg(nb.neighbours_negative)::numeric, 1)              AS avg_neighbours_negative,
       count(*) FILTER (WHERE nb.neighbours_negative >= 1)          AS hours_with_any_neighbour_negative,
       count(*) FILTER (WHERE nb.neighbours_negative = 4)           AS hours_with_all_neighbours_negative
FROM rs JOIN nb USING (hour_utc);
