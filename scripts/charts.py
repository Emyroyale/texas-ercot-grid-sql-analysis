#!/usr/bin/env python3
"""Generate charts for the Texas Grid 2024 SQL project from texas_grid.db."""
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)
conn = sqlite3.connect(ROOT / "texas_grid.db")

plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 150})

# 1. Monthly peak demand -------------------------------------------------
q1 = pd.read_sql("""SELECT strftime('%Y-%m', local_time) AS month,
                           MAX(demand_mw) AS peak_mw
                    FROM ercot_hourly GROUP BY 1 ORDER BY 1""", conn)
fig, ax = plt.subplots(figsize=(10, 4.5))
bars = ax.bar(q1["month"], q1["peak_mw"], color="#2a6fb5", edgecolor="none")
ax.set_title("ERCOT Monthly Peak Demand, 2024", fontweight="bold", loc="left")
ax.set_ylabel("MW")
ax.set_ylim(0, 95000)
for b, v in zip(bars, q1["peak_mw"]):
    if v > 75000:
        ax.text(b.get_x() + b.get_width()/2, v + 1200, f"{v:,.0f}",
                ha="center", fontsize=8, color="#333333")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig(OUT / "monthly_peak_demand.png", bbox_inches="tight")
plt.savefig(OUT / "monthly_peak_demand.svg", bbox_inches="tight")
plt.close()

# 2. Annual fuel mix (donut) ----------------------------------------------
q3 = pd.read_sql("""SELECT fuel, mwh FROM (
    SELECT 'Natural Gas' AS fuel, SUM(gas_mw)     AS mwh FROM ercot_hourly UNION ALL
    SELECT 'Wind',        SUM(wind_mw)    FROM ercot_hourly UNION ALL
    SELECT 'Coal',        SUM(coal_mw)    FROM ercot_hourly UNION ALL
    SELECT 'Solar',       SUM(solar_mw)   FROM ercot_hourly UNION ALL
    SELECT 'Nuclear',     SUM(nuclear_mw) FROM ercot_hourly UNION ALL
    SELECT 'Other',       SUM(other_mw)+SUM(hydro_mw)+SUM(petroleum_mw)+SUM(unknown_mw) FROM ercot_hourly
) ORDER BY mwh DESC""", conn)
colors = {"Natural Gas": "#e07a3f", "Wind": "#4aa8de", "Coal": "#5a5a5a",
          "Solar": "#f2c230", "Nuclear": "#9b59b6", "Other": "#bbbbbb"}
fig, ax = plt.subplots(figsize=(6.5, 5))
wedges, _, autotexts = ax.pie(
    q3["mwh"], labels=q3["fuel"],
    colors=[colors[f] for f in q3["fuel"]],
    autopct=lambda p: f"{p:.1f}%", pctdistance=0.78,
    wedgeprops=dict(width=0.42, edgecolor="white"))
for t in autotexts:
    t.set_fontsize(9); t.set_color("#222222")
ax.set_title("What Powered Texas in 2024\n(share of total generation, GWh)",
             fontweight="bold", loc="center")
plt.tight_layout()
plt.savefig(OUT / "annual_fuel_mix.png", bbox_inches="tight")
plt.savefig(OUT / "annual_fuel_mix.svg", bbox_inches="tight")
plt.close()

# 3. Daily profile: demand vs wind by hour --------------------------------
prof = pd.read_sql("""SELECT hour_ending,
    AVG(demand_mw) AS avg_demand, AVG(wind_mw) AS avg_wind
    FROM ercot_hourly WHERE hour_ending <= 24
    GROUP BY hour_ending ORDER BY hour_ending""", conn)
fig, ax1 = plt.subplots(figsize=(10, 4.5))
ax1.plot(prof["hour_ending"], prof["avg_demand"], color="#2a6fb5",
         linewidth=2.2, label="Avg demand")
ax1.set_xlabel("Hour ending (Central)")
ax1.set_ylabel("Avg demand (MW)", color="#2a6fb5")
ax1.set_xlim(1, 24)
ax2 = ax1.twinx()
ax2.plot(prof["hour_ending"], prof["avg_wind"], color="#4aa8de",
         linewidth=2.2, linestyle="--", label="Avg wind output")
ax2.set_ylabel("Avg wind output (MW)", color="#4aa8de")
ax1.set_title("Texas Wind Blows at Night - Missing the Afternoon Peak",
              fontweight="bold", loc="left")
fig.tight_layout()
plt.savefig(OUT / "daily_profile_wind_vs_demand.png", bbox_inches="tight")
plt.savefig(OUT / "daily_profile_wind_vs_demand.svg", bbox_inches="tight")
plt.close()

print("charts written to", OUT)
for p in sorted(OUT.glob("*.svg")):
    print(" -", p.name)
