#!/usr/bin/env python3
"""Build the SQLite database for the Texas Grid SQL project.

End-to-end ETL from the public source, no checked-in dataset needed:

1. Downloads the two U.S. EIA Form EIA-930 bulk files for 2024
   (cached in data/raw/, which is git-ignored).
2. Filters to balancing authority ERCO (ERCOT).
3. Harmonizes the mid-year EIA schema change: H2 2024 split hydro, solar,
   wind and storage into sub-columns, which are summed back into the
   stable project schema. Reported values are used throughout
   (not the imputed or adjusted variants).
4. Writes data/ercot_hourly_2024.csv and loads it into texas_grid.db.

Idempotent: re-running reuses the cached downloads and rebuilds the table.
"""
import sqlite3
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
CSV = ROOT / "data" / "ercot_hourly_2024.csv"
DB = ROOT / "texas_grid.db"

EIA_FILES = {
    "EIA930_BALANCE_2024_Jan_Jun.csv":
        "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_BALANCE_2024_Jan_Jun.csv",
    "EIA930_BALANCE_2024_Jul_Dec.csv":
        "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_BALANCE_2024_Jul_Dec.csv",
}


def download_raw():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for fname, url in EIA_FILES.items():
        dest = RAW_DIR / fname
        if dest.exists():
            print(f"using cached {fname}")
            continue
        print(f"downloading {fname} ...")
        urllib.request.urlretrieve(url, dest)
        print(f"saved {fname} ({dest.stat().st_size / 1e6:.1f} MB)")


def harmonize(path, half):
    """Read one raw EIA half-year file, keep ERCO, map to project schema."""
    df = pd.read_csv(path, low_memory=False)
    df = df[df["Balancing Authority"] == "ERCO"].copy()

    def col(name):
        return df[f"Net Generation (MW) from {name}"]

    def total(*names):
        return pd.concat([col(n) for n in names], axis=1).sum(axis=1)

    out = pd.DataFrame({
        "utc_time": pd.to_datetime(df["UTC Time at End of Hour"],
                                   format="%m/%d/%Y %I:%M:%S %p"),
        "local_time": pd.to_datetime(df["Local Time at End of Hour"],
                                     format="%m/%d/%Y %I:%M:%S %p"),
        "hour_ending": df["Hour Number"].astype(int),
        "demand_forecast_mw": df["Demand Forecast (MW)"],
        "demand_mw": df["Demand (MW)"],
        "net_generation_mw": df["Net Generation (MW)"],
        "interchange_mw": df["Total Interchange (MW)"],
        "coal_mw": col("Coal"),
        "gas_mw": col("Natural Gas"),
        "nuclear_mw": col("Nuclear"),
        "petroleum_mw": col("All Petroleum Products"),
        "other_mw": col("Other Fuel Sources"),
        "unknown_mw": col("Unknown Fuel Sources"),
    })
    if half == "H1":
        out["hydro_mw"] = col("Hydropower and Pumped Storage")
        out["solar_mw"] = col("Solar")
        out["wind_mw"] = col("Wind")
        out["battery_mw"] = 0.0
    else:  # H2: EIA split these into sub-columns; sum them back together
        out["hydro_mw"] = total("Hydropower Excluding Pumped Storage",
                               "Pumped Storage")
        out["solar_mw"] = total("Solar without Integrated Battery Storage",
                                "Solar with Integrated Battery Storage")
        out["wind_mw"] = total("Wind without Integrated Battery Storage",
                               "Wind with Integrated Battery Storage")
        out["battery_mw"] = col("Battery Storage").fillna(0)
        out["other_mw"] = total("Other Fuel Sources", "Geothermal",
                                "Other Energy Storage", "Unknown Energy Storage")
    cols = ["utc_time", "local_time", "hour_ending", "demand_forecast_mw",
            "demand_mw", "net_generation_mw", "interchange_mw", "coal_mw",
            "gas_mw", "nuclear_mw", "petroleum_mw", "hydro_mw", "solar_mw",
            "wind_mw", "battery_mw", "other_mw", "unknown_mw"]
    return out[cols]


def main():
    download_raw()
    df = pd.concat([
        harmonize(RAW_DIR / "EIA930_BALANCE_2024_Jan_Jun.csv", "H1"),
        harmonize(RAW_DIR / "EIA930_BALANCE_2024_Jul_Dec.csv", "H2"),
    ]).sort_values("utc_time").reset_index(drop=True)

    # normalize timestamps to ISO for clean SQL date functions
    df["utc_time"] = df["utc_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["local_time"] = df["local_time"].dt.strftime("%Y-%m-%d %H:%M:%S")

    df.to_csv(CSV, index=False)
    print(f"wrote {CSV} ({len(df)} rows)")

    # keep exactly the hours belonging to 2024 Central Time (drop the single
    # Jan-1-midnight straggler so monthly rollups are clean)
    df = df[df["local_time"] < "2025-01-01"].reset_index(drop=True)

    # single missing interchange hour + always-null fuel columns -> 0
    df["interchange_mw"] = df["interchange_mw"].fillna(0)
    for c in ["petroleum_mw", "unknown_mw"]:
        df[c] = df[c].fillna(0)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS ercot_hourly")
    cur.execute((ROOT / "sql" / "schema.sql").read_text())
    df.to_sql("ercot_hourly", conn, if_exists="append", index=False)
    conn.commit()

    n = cur.execute("SELECT COUNT(*) FROM ercot_hourly").fetchone()[0]
    mn = cur.execute("SELECT MIN(utc_time), MAX(utc_time) FROM ercot_hourly").fetchone()
    pk = cur.execute("SELECT MAX(demand_mw) FROM ercot_hourly").fetchone()[0]
    print(f"loaded {n} rows into {DB}")
    print(f"range: {mn[0]} -> {mn[1]}")
    print(f"annual peak demand: {pk:,.0f} MW")
    conn.close()


if __name__ == "__main__":
    main()
