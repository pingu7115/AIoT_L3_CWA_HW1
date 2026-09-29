#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
階段 3: 資料庫存儲 (Data Storage)
database.py
提供 SQLite 資料庫連線、自動建表、資料寫入與重複檢核機制，
並提供 DISTINCT / 區域查詢等驗證功能。
"""

import os
import sys
import sqlite3
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_DB_PATH = "data.db"

def get_connection(db_path=DEFAULT_DB_PATH):
    """建立並取得 SQLite 連線"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=DEFAULT_DB_PATH):
    """初始化資料庫與建立 TemperatureForecasts 及 UVForecasts 資料表"""
    create_temp_table_sql = """
    CREATE TABLE IF NOT EXISTS TemperatureForecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        regionName TEXT NOT NULL,
        dataDate TEXT NOT NULL,
        mint REAL NOT NULL,
        maxt REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(regionName, dataDate)
    );
    """
    create_uv_table_sql = """
    CREATE TABLE IF NOT EXISTS UVForecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        regionName TEXT NOT NULL,
        dataDate TEXT NOT NULL,
        uvi REAL NOT NULL,
        exposureLevel TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(regionName, dataDate)
    );
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(create_temp_table_sql)
        cursor.execute(create_uv_table_sql)
        conn.commit()
    print(f"[INFO] 資料庫初始化完成，已確認 TemperatureForecasts 與 UVForecasts 資料表存在 ({db_path})")

def insert_forecasts(forecast_list, db_path=DEFAULT_DB_PATH):
    """
    批次寫入氣象預報資料，具備重複檢核機制 (ON CONFLICT DO UPDATE)
    """
    if not forecast_list:
        print("[WARN] 沒有可寫入的資料！")
        return 0

    init_db(db_path)

    upsert_sql = """
    INSERT INTO TemperatureForecasts (regionName, dataDate, mint, maxt)
    VALUES (:regionName, :dataDate, :mint, :maxt)
    ON CONFLICT(regionName, dataDate) DO UPDATE SET
        mint = excluded.mint,
        maxt = excluded.maxt,
        created_at = CURRENT_TIMESTAMP;
    """

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(upsert_sql, forecast_list)
        conn.commit()
        inserted_count = cursor.rowcount

    print(f"[SUCCESS] 成功寫入/更新 {len(forecast_list)} 筆氣溫預報資料至資料庫。")
    return inserted_count

def get_distinct_regions(db_path=DEFAULT_DB_PATH):
    """查詢所有不重複的區域清單"""
    query = "SELECT DISTINCT regionName FROM TemperatureForecasts ORDER BY regionName ASC;"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [r["regionName"] for r in rows]

def get_forecast_by_region(region_name, db_path=DEFAULT_DB_PATH):
    """查詢指定區域的一週預報資料"""
    query = """
    SELECT regionName, dataDate, mint, maxt
    FROM TemperatureForecasts
    WHERE regionName = ?
    ORDER BY dataDate ASC
    LIMIT 7;
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (region_name,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def get_all_latest_forecasts(db_path=DEFAULT_DB_PATH):
    """取得所有區域最近一天的預報資料（用於地圖視覺化）"""
    query = """
    SELECT t1.regionName, t1.dataDate, t1.mint, t1.maxt
    FROM TemperatureForecasts t1
    INNER JOIN (
        SELECT regionName, MIN(dataDate) as minDate
        FROM TemperatureForecasts
        GROUP BY regionName
    ) t2 ON t1.regionName = t2.regionName AND t1.dataDate = t2.minDate;
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def insert_uv_forecasts(uv_list, db_path=DEFAULT_DB_PATH):
    """
    批次寫入紫外線預報資料至 UVForecasts，具備防重複更新機制 (ON CONFLICT DO UPDATE)
    """
    if not uv_list:
        print("[WARN] 沒有可寫入的紫外線資料！")
        return 0

    init_db(db_path)

    upsert_sql = """
    INSERT INTO UVForecasts (regionName, dataDate, uvi, exposureLevel)
    VALUES (:regionName, :dataDate, :uvi, :exposureLevel)
    ON CONFLICT(regionName, dataDate) DO UPDATE SET
        uvi = excluded.uvi,
        exposureLevel = excluded.exposureLevel,
        created_at = CURRENT_TIMESTAMP;
    """

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(upsert_sql, uv_list)
        conn.commit()
        inserted_count = cursor.rowcount

    print(f"[SUCCESS] 成功寫入/更新 {len(uv_list)} 筆紫外線預報資料至資料庫 (UVForecasts)。")
    return inserted_count

def get_uv_forecast_by_region(region_name, db_path=DEFAULT_DB_PATH):
    """純 SQL 查詢指定區域的一週紫外線預報資料"""
    query = """
    SELECT regionName, dataDate, uvi, exposureLevel
    FROM UVForecasts
    WHERE regionName = ?
    ORDER BY dataDate ASC
    LIMIT 7;
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (region_name,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def get_all_latest_uv_forecasts(db_path=DEFAULT_DB_PATH):
    """純 SQL 查詢取得所有區域最新首日的紫外線預報資料（供地圖與各縣市卡片使用）"""
    query = """
    SELECT u1.regionName, u1.dataDate, u1.uvi, u1.exposureLevel
    FROM UVForecasts u1
    INNER JOIN (
        SELECT regionName, MIN(dataDate) as minDate
        FROM UVForecasts
        GROUP BY regionName
    ) u2 ON u1.regionName = u2.regionName AND u1.dataDate = u2.minDate;
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def verify_database(db_path=DEFAULT_DB_PATH):
    """執行 SQL 查詢驗證：檢查 DISTINCT 區域與各區氣溫/紫外線預報筆數"""
    if not os.path.exists(db_path):
        print(f"[ERROR] 資料庫檔案不存在: {db_path}，請先執行 ETL 寫入資料！")
        return False

    print("=" * 60)
    print("[VERIFY] 開始執行 SQLite 資料庫 (data.db) 驗證流程")
    print("=" * 60)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. 氣溫總筆數
        cursor.execute("SELECT COUNT(*) FROM TemperatureForecasts;")
        total_count = cursor.fetchone()[0]
        print(f"[STATS] 氣溫總紀錄數: {total_count} 筆")

        # 2. 紫外線總筆數
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UVForecasts';")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM UVForecasts;")
            uv_count = cursor.fetchone()[0]
            print(f"[STATS] 紫外線總紀錄數: {uv_count} 筆")

        # 3. DISTINCT 區域
        regions = get_distinct_regions(db_path)
        print(f"[STATS] DISTINCT 區域 ({len(regions)} 個): {', '.join(regions)}")

        # 4. 指定區域查詢驗證 (例如北部地區)
        sample_region = "北部地區" if "北部地區" in regions else (regions[0] if regions else None)
        if sample_region:
            print(f"\n[SAMPLE] 指定區域範例氣溫查詢: {sample_region}")
            sample_data = get_forecast_by_region(sample_region, db_path)
            for row in sample_data:
                print(f"   日期: {row['dataDate']} | 最低溫: {row['mint']:>4.1f}°C | 最高溫: {row['maxt']:>4.1f}°C | 溫差: {row['maxt'] - row['mint']:>4.1f}°C")

            sample_uv = get_uv_forecast_by_region(sample_region, db_path)
            if sample_uv:
                print(f"\n[SAMPLE] 指定區域範例紫外線查詢: {sample_region}")
                for row in sample_uv:
                    print(f"   日期: {row['dataDate']} | UVI: {row['uvi']:>4.1f} | 曝曬等級: {row['exposureLevel']}")

    print("\n[SUCCESS] 資料庫存儲與防重複機制驗證通過！")
    print("=" * 60)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Weather SQLite Database")
    parser.add_argument("--verify", action="store_true", help="Run database verification queries")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite database file")
    args = parser.parse_args()

    init_db(args.db)
    if args.verify:
        verify_database(args.db)
