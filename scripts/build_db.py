#!/usr/bin/env python3
"""Build the SQLite database for the Texas Grid SQL project.

Reads data/ercot_hourly_2024.csv (8,784 hourly ERCO rows for 2024, sourced
from EIA-930 public bulk files) and loads it into texas_grid.db.
Idempotent: drops and recreates the ercot_hourly table.
"""
import sqlite3
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "texas_grid.db"

df = pd.read_csv(ROOT / "data" / "ercot_hourly_2024.csv")

# normalize timestamps to ISO for clean SQL date functions
df["utc_time"] = pd.to_datetime(df["utc_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
df["local_time"] = pd.to_datetime(df["local_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")

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
