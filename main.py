#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIoT HW10 一鍵式 ETL Pipeline (Main Script)
串聯 Stage 1 (Fetch) -> Stage 2 (Parse) -> Stage 3 (Database Storage & Verify)
"""

import sys
import os
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fetch_weather import fetch_cwa_weather
from parse_weather import parse_weather_json
from database import insert_forecasts, verify_database

def run_pipeline(api_key=None, force_mock=False):
    print("=" * 65)
    print("[START] 啟動 AIoT HW10 台灣氣象預報系統 ETL 流程")
    print("=" * 65)

    # 1. 抓取資料
    print("\n[階段 1: 資料獲取 Data Ingestion]")
    if force_mock:
        from fetch_weather import generate_mock_data
        import json
        m_data = generate_mock_data()
        with open("weather_data.json", "w", encoding="utf-8") as f:
            json.dump(m_data, f, ensure_ascii=False, indent=2)
        print("[SUCCESS] 強制生成模擬預報資料成功。")
    else:
        fetch_cwa_weather(api_key=api_key)

    # 2. 解析資料
    print("\n[階段 2: 資料解析 Data Parsing]")
    clean_data = parse_weather_json("weather_data.json")
    if not clean_data:
        print("[ERROR] 解析失敗，終止流程！")
        sys.exit(1)

    # 3. 存入資料庫
    print("\n[階段 3: 資料庫存儲 Data Storage]")
    insert_forecasts(clean_data, "data.db")

    # 4. 驗證資料庫
    print("\n[階段 3.1: 資料庫驗證]")
    verify_database("data.db")

    print("\n[FINISH] ETL 流程順利完成！資料已就緒，可啟動 Streamlit 前端 (app.py) 進行展示。")
    print("=" * 65)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run complete Weather ETL Pipeline")
    parser.add_argument("--api-key", type=str, default=None, help="CWA API Key")
    parser.add_argument("--mock", action="store_true", help="Force mock data")
    args = parser.parse_args()

    run_pipeline(api_key=args.api_key, force_mock=args.mock)
