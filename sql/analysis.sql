-- =====================================================================
-- Texas Grid 2024 - Analytical SQL
-- Database: texas_grid.db (SQLite) | Table: ercot_hourly
-- Source: U.S. EIA Form 930 public bulk files, balancing authority ERCO
-- Queries are written in portable SQL (run on SQLite and PostgreSQL).
-- =====================================================================

-- Q1: When did demand peak each month, and how high did it get?
-- Business question: which months stress the Texas grid the most?
SELECT
    strftime('%Y-%m', local_time) AS month,
    ROUND(MAX(demand_mw))       AS peak_demand_mw,
    (SELECT local_time FROM ercot_hourly h2
      WHERE strftime('%Y-%m', h2.local_time) = strftime('%Y-%m', h.local_time)
      ORDER BY demand_mw DESC LIMIT 1) AS peak_time_central
FROM ercot_hourly h
GROUP BY 1
ORDER BY 1;

-- Q2: What does a typical Texas day look like? (average demand by hour)
-- Business question: when should time-of-use pricing push usage away from?
SELECT
    hour_ending,
    ROUND(AVG(demand_mw)) AS avg_demand_mw,
    ROUND(MIN(demand_mw)) AS min_demand_mw,
    ROUND(MAX(demand_mw)) AS max_demand_mw
FROM ercot_hourly
GROUP BY hour_ending
ORDER BY hour_ending;

-- Q3: What powered Texas in 2024? (annual generation share by fuel)
SELECT
    fuel,
    ROUND(SUM(mwh) / 1000.0, 1)            AS total_gwh,
    ROUND(100.0 * SUM(mwh) / SUM(SUM(mwh)) OVER (), 1) AS share_pct
FROM (
    SELECT 'Natural Gas' AS fuel, SUM(gas_mw)     AS mwh FROM ercot_hourly UNION ALL
    SELECT 'Coal',        SUM(coal_mw)     FROM ercot_hourly UNION ALL
    SELECT 'Nuclear',     SUM(nuclear_mw)  FROM ercot_hourly UNION ALL
    SELECT 'Wind',        SUM(wind_mw)     FROM ercot_hourly UNION ALL
    SELECT 'Solar',       SUM(solar_mw)    FROM ercot_hourly UNION ALL
    SELECT 'Hydro',       SUM(hydro_mw)    FROM ercot_hourly UNION ALL
    SELECT 'Other',       SUM(other_mw) + SUM(petroleum_mw) + SUM(unknown_mw) FROM ercot_hourly
)
GROUP BY fuel
ORDER BY total_gwh DESC;

-- Q4: How did the renewable share move through the year?
-- (wind + solar as % of net generation, by month)
SELECT
    strftime('%Y-%m', local_time) AS month,
    ROUND(100.0 * SUM(wind_mw + solar_mw) / SUM(net_generation_mw), 1) AS renewable_share_pct,
    ROUND(100.0 * SUM(wind_mw)  / SUM(net_generation_mw), 1) AS wind_share_pct,
    ROUND(100.0 * SUM(solar_mw) / SUM(net_generation_mw), 1) AS solar_share_pct
FROM ercot_hourly
GROUP BY 1
ORDER BY 1;

-- Q5: What was the fuel mix during the 10 highest-demand hours of the year?
-- Business question: what actually keeps the lights on when Texas needs it most?
SELECT
    local_time AS peak_time_central,
    ROUND(demand_mw) AS demand_mw,
    ROUND(100.0 * gas_mw     / net_generation_mw, 1) AS gas_pct,
    ROUND(100.0 * wind_mw    / net_generation_mw, 1) AS wind_pct,
    ROUND(100.0 * solar_mw   / net_generation_mw, 1) AS solar_pct,
    ROUND(100.0 * coal_mw    / net_generation_mw, 1) AS coal_pct,
    ROUND(100.0 * nuclear_mw / net_generation_mw, 1) AS nuclear_pct
FROM ercot_hourly
ORDER BY demand_mw DESC
LIMIT 10;

-- Q6: When does Texas wind actually blow? (average wind output by hour)
-- Business question: does wind show up for the afternoon peak?
SELECT
    hour_ending,
    ROUND(AVG(wind_mw)) AS avg_wind_mw,
    ROUND(AVG(100.0 * wind_mw / NULLIF(net_generation_mw, 0)), 1) AS avg_wind_share_pct
FROM ercot_hourly
GROUP BY hour_ending
ORDER BY hour_ending;

-- Q7: Which months deliver the most solar? (average solar output by month)
SELECT
    strftime('%Y-%m', local_time) AS month,
    ROUND(AVG(solar_mw)) AS avg_solar_mw,
    ROUND(MAX(solar_mw)) AS max_solar_mw
FROM ercot_hourly
GROUP BY 1
ORDER BY 1;

-- Q8: How accurate is ERCOT's day-ahead demand forecast?
-- (monthly MAPE - mean absolute percentage error)
SELECT
    strftime('%Y-%m', local_time) AS month,
    COUNT(*) AS hours,
    ROUND(100.0 * AVG(ABS(demand_forecast_mw - demand_mw) / demand_mw), 2) AS mape_pct,
    ROUND(AVG(demand_forecast_mw - demand_mw)) AS mean_bias_mw
FROM ercot_hourly
WHERE demand_forecast_mw IS NOT NULL AND demand_mw > 0
GROUP BY 1
ORDER BY 1;

-- Q9: Is Texas a net importer or exporter of power? (monthly avg interchange)
-- Positive = importing; negative = exporting.
SELECT
    strftime('%Y-%m', local_time) AS month,
    ROUND(AVG(interchange_mw)) AS avg_interchange_mw,
    ROUND(100.0 * AVG(interchange_mw) / AVG(demand_mw), 2) AS interchange_share_of_demand_pct
FROM ercot_hourly
GROUP BY 1
ORDER BY 1;

-- Q10: Weekday vs weekend demand - how much does the workweek move the needle?
SELECT
    CASE WHEN CAST(strftime('%w', local_time) AS INTEGER) IN (0, 6)
         THEN 'Weekend' ELSE 'Weekday' END AS day_type,
    COUNT(*) / 24            AS days,
    ROUND(AVG(demand_mw))    AS avg_demand_mw,
    ROUND(MAX(demand_mw))    AS peak_demand_mw
FROM ercot_hourly
GROUP BY 1;

-- Q11: In how many hours did wind + solar cover over 40% of demand?
-- Business question: how often do renewables carry the grid?
SELECT
    strftime('%Y-%m', local_time) AS month,
    COUNT(*) AS high_renewable_hours,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_of_year_pct
FROM ercot_hourly
WHERE 1.0 * (wind_mw + solar_mw) / NULLIF(net_generation_mw, 0) > 0.40
GROUP BY 1
ORDER BY 1;

-- Q12: Summer vs winter - which season peaks harder, and with what mix?
SELECT
    CASE
        WHEN CAST(strftime('%m', local_time) AS INTEGER) IN (6, 7, 8)  THEN 'Summer (Jun-Aug)'
        WHEN CAST(strftime('%m', local_time) AS INTEGER) IN (12, 1, 2) THEN 'Winter (Dec-Feb)'
        ELSE 'Shoulder'
    END AS season,
    ROUND(MAX(demand_mw)) AS season_peak_mw,
    ROUND(AVG(demand_mw)) AS season_avg_mw,
    ROUND(100.0 * SUM(gas_mw)   / SUM(net_generation_mw), 1) AS gas_share_pct,
    ROUND(100.0 * SUM(wind_mw)  / SUM(net_generation_mw), 1) AS wind_share_pct,
    ROUND(100.0 * SUM(solar_mw) / SUM(net_generation_mw), 1) AS solar_share_pct
FROM ercot_hourly
GROUP BY 1
ORDER BY season_peak_mw DESC;
