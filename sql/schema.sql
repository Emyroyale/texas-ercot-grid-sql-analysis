-- =====================================================================
-- texas_grid.db schema
-- One row per hour of ERCOT (ERCO balancing authority) operations in 2024.
-- Source: U.S. EIA Form 930 public bulk files (EIA930_BALANCE_2024_*.csv).
-- Timestamps are stored ISO-8601; local_time is Central Time.
-- hour_ending 1..24 (25 = the repeated 2 a.m. hour on Nov 3, 2024, DST fallback).
-- =====================================================================
CREATE TABLE ercot_hourly (
    utc_time            TEXT PRIMARY KEY,
    local_time          TEXT NOT NULL,
    hour_ending         INTEGER NOT NULL,
    demand_forecast_mw  REAL,               -- ERCOT day-ahead demand forecast
    demand_mw           REAL NOT NULL,      -- actual metered demand
    net_generation_mw   REAL,               -- total net generation
    interchange_mw      REAL,               -- net imports (+) / exports (-)
    coal_mw             REAL,
    gas_mw              REAL,               -- natural gas
    nuclear_mw          REAL,
    petroleum_mw        REAL,
    hydro_mw            REAL,               -- hydro incl. pumped storage
    solar_mw            REAL,               -- utility-scale solar
    wind_mw             REAL,
    battery_mw          REAL,               -- battery storage discharge
    other_mw            REAL,
    unknown_mw          REAL
);
