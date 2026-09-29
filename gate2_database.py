"""
Gate 2 — Database
Reads gate1_output.json, transforms the data (ETL), and loads it into SQLite database (data.db).
Implements a duplicate strategy (UNIQUE on location and forecast time, with REPLACE).
Verifies the data using SQL SELECT queries.
"""

import json
import sqlite3
import pandas as pd
from datetime import datetime
import os

DB_FILE = "data.db"
INPUT_FILE = "gate1_output.json"

print(f"[STEP 1] Database file: {DB_FILE}")
print(f"[STEP 1] Input file   : {INPUT_FILE}")

# ── 1. Database Schema Setup ────────────────────────────────────────────────
def setup_db(conn):
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS weather_forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_name TEXT,
        latitude REAL,
        longitude REAL,
        forecast_start TEXT,
        forecast_end TEXT,
        weather TEXT,
        min_temp REAL,
        max_temp REAL,
        rain_probability REAL,
        source TEXT,
        fetched_at TEXT,
        UNIQUE(location_name, forecast_start)
    );
    ''')
    conn.commit()
    print("[STEP 2] Schema setup complete with UNIQUE constraint on (location_name, forecast_start).")

# ── 2. ETL (Extract, Transform, Load) ──────────────────────────────────────
def run_etl(conn):
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Please run Gate 1 first.")
        return False
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    meta = data.get("meta", {})
    fetched_at = meta.get("fetched_at", datetime.now().isoformat())
    source = meta.get("source", "CWA")
    
    forecasts = data.get("forecasts", [])
    print(f"\n[STEP 3] Extract: Loaded {len(forecasts)} locations from {INPUT_FILE}.")
    
    # Transform
    rows_to_insert = []
    
    for fcast in forecasts:
        loc = fcast["location"]
        lat = fcast.get("lat")
        lon = fcast.get("lon")
        
        # We need to align the times for MaxT, MinT, Wx, PoP.
        # MaxT has 14 periods, we'll use its start/end times as the base.
        elements = fcast.get("elements", {})
        
        period_count = min(
            len(elements.get("MaxT", [])),
            len(elements.get("MinT", [])),
            len(elements.get("Wx", []))
        )
        
        for i in range(period_count):
            start = elements["MaxT"][i].get("start")
            end = elements["MaxT"][i].get("end")
            
            maxt = elements["MaxT"][i].get("value")
            mint = elements["MinT"][i].get("value")
            wx = elements["Wx"][i].get("value")
            
            # PoP might have fewer periods (sometimes) or none
            pop = None
            if elements.get("PoP") and i < len(elements["PoP"]):
                pop_val = elements["PoP"][i].get("value")
                if pop_val and pop_val.strip() and pop_val.strip() not in ("-", ""):
                    try:
                        pop = float(pop_val)
                    except ValueError:
                        pop = None
                    
            rows_to_insert.append((
                loc, lat, lon, start, end, wx, mint, maxt, pop, source, fetched_at
            ))
            
    print(f"[STEP 4] Transform: Generated {len(rows_to_insert)} rows for database insertion.")
    
    # Load (Upsert using INSERT OR REPLACE)
    cursor = conn.cursor()
    cursor.executemany('''
    INSERT OR REPLACE INTO weather_forecasts (
        location_name, latitude, longitude, forecast_start, forecast_end, 
        weather, min_temp, max_temp, rain_probability, source, fetched_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', rows_to_insert)
    
    conn.commit()
    print(f"[STEP 5] Load: Successfully inserted/updated {len(rows_to_insert)} rows into weather_forecasts.")
    return True

# ── 3. Verification & Querying ─────────────────────────────────────────────
def verify_db(conn):
    print("\n[STEP 6] Verifying Database Data (SQL SELECT) ...")
    
    # Verify Total Rows
    df_count = pd.read_sql_query("SELECT COUNT(*) as total_rows FROM weather_forecasts", conn)
    total_rows = df_count['total_rows'].iloc[0]
    print(f"  Total records in DB: {total_rows}")
    
    # Verify distinct locations
    df_loc = pd.read_sql_query("SELECT DISTINCT location_name FROM weather_forecasts", conn)
    loc_count = len(df_loc)
    print(f"  Distinct locations: {loc_count}")
    
    # Verify sample location
    sample_loc = '臺北市' if '臺北市' in df_loc['location_name'].values else df_loc['location_name'].iloc[0]
    df_sample = pd.read_sql_query(f"SELECT forecast_start, forecast_end, weather, min_temp, max_temp, rain_probability FROM weather_forecasts WHERE location_name = '{sample_loc}' LIMIT 5", conn)
    
    print(f"\n  Sample Data for {sample_loc}:")
    print(df_sample.to_string(index=False))
    
    return total_rows > 0 and loc_count >= 20

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_FILE)
    try:
        setup_db(conn)
        if run_etl(conn):
            success = verify_db(conn)
            
            print("\n" + "="*60)
            print("GATE 2 PASS CHECKLIST")
            print("="*60)
            checks = {
                "Read JSON output from Gate 1": True,
                "SQLite schema configured": True,
                "Duplicate strategy (UNIQUE/REPLACE) implemented": True,
                "ETL process successful": True,
                "Verified via SQL SELECT": success,
                "No GIS work started": True
            }
            all_pass = True
            for check, result in checks.items():
                icon = "[PASS]" if result else "[FAIL]"
                print(f"  {icon}  {check}")
                if not result:
                    all_pass = False

            print("="*60)
            if all_pass:
                print("GATE 2 = PASS")
            else:
                print("GATE 2 = FAIL -- check errors")
            print("="*60)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
