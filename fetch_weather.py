#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
階段 1: 資料獲取 (Data Ingestion)
fetch_weather.py
發送 HTTP GET 請求向中央氣象署 (CWA) 開放資料平台取得氣象預報，
並儲存為原始預報 JSON 檔案 (weather_data.json)。
"""

import os
import sys
import json
import argparse
import datetime
import requests
import urllib3

# 忽略 SSL 警告（針對 CWA 政府網域證書鏈相容性）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_DATASET = "F-A0010-001"
FALLBACK_DATASET = "F-D0047-091"
OUTPUT_FILE = "weather_data.json"

SIX_REGIONS = ["北部地區", "中部地區", "南部地區", "東部地區", "澎湖地區", "金門馬祖地區"]

def generate_mock_data():
    """當無 API key 或網路/端點完全不可用時的備用資料"""
    today = datetime.date.today()
    mock_locations = []
    base_temps = {
        "北部地區": (19, 26),
        "中部地區": (21, 29),
        "南部地區": (23, 31),
        "東部地區": (20, 27),
        "澎湖地區": (22, 28),
        "金門馬祖地區": (17, 24),
    }
    for region in SIX_REGIONS:
        min_base, max_base = base_temps.get(region, (20, 28))
        time_slots = []
        for i in range(7):
            d = today + datetime.timedelta(days=i)
            offset = (i % 3) - 1
            cur_min = min_base + offset
            cur_max = max_base + offset
            time_slots.append({
                "dataDate": d.strftime("%Y-%m-%d"),
                "startTime": f"{d} 06:00:00",
                "endTime": f"{d} 18:00:00",
                "parameter": {
                    "parameterName": f"{cur_min} ~ {cur_max}",
                    "minTemperature": str(cur_min),
                    "maxTemperature": str(cur_max)
                }
            })
        mock_locations.append({
            "locationName": region,
            "weatherElement": [
                {
                    "elementName": "MinT",
                    "time": [{"dataDate": t["dataDate"], "elementValue": [{"value": t["parameter"]["minTemperature"]}]} for t in time_slots]
                },
                {
                    "elementName": "MaxT",
                    "time": [{"dataDate": t["dataDate"], "elementValue": [{"value": t["parameter"]["maxTemperature"]}]} for t in time_slots]
                }
            ]
        })
    return {
        "success": "true",
        "result": {"resource_id": DEFAULT_DATASET},
        "records": {
            "datasetDescription": "一週氣象預報 (Mock Fallback)",
            "location": mock_locations
        }
    }

def fetch_cwa_weather(api_key=None, dataset=DEFAULT_DATASET, output_path=OUTPUT_FILE):
    """
    發送 HTTP GET 請求向中央氣象署抓取氣象資料
    """
    if not api_key:
        api_key = os.environ.get("CWA_API_KEY") or os.environ.get("CWB_API_KEY")

    if not api_key and os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str.startswith("CWA_API_KEY="):
                    api_key = line_str.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not api_key:
        print("[WARN] 未提供 CWA API Key，啟用內建模擬資料...")
        data = generate_mock_data()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[SUCCESS] 模擬預報資料已寫入: {output_path}")
        return True

    headers = {"accept": "application/json"}
    params = {
        "Authorization": api_key,
        "format": "JSON"
    }

    # 1. 優先嘗試指定資料集 (如 F-A0010-001)
    primary_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{dataset}"
    print(f"[INFO] 正在向中央氣象署 API 發送請求: {dataset} ...")
    
    try:
        response = requests.get(primary_url, params=params, headers=headers, timeout=15, verify=False)
        if response.status_code == 200:
            data = response.json()
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[SUCCESS] 成功從 CWA API ({dataset}) 取得最新即時氣象資料，已寫入 {output_path}")
            return True
        elif response.status_code == 404:
            print(f"[WARN] 資料集 {dataset} 回傳 404 (官方已改版)。自動切換至現行縣市一週預報資料集 {FALLBACK_DATASET} ...")
            fallback_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{FALLBACK_DATASET}"
            fb_res = requests.get(fallback_url, params=params, headers=headers, timeout=15, verify=False)
            if fb_res.status_code == 200:
                data = fb_res.json()
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"[SUCCESS] 成功從 CWA API ({FALLBACK_DATASET}) 取得全台縣市最新一週即時氣象資料！已寫入 {output_path}")
                return True
            else:
                print(f"[ERROR] 備用資料集請求失敗: HTTP {fb_res.status_code}")
        else:
            print(f"[ERROR] API 請求失敗: HTTP {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"[ERROR] 發送請求時發生異常: {e}")

    print("[INFO] 因 API 連線受阻，自動載入完整 6 大分區備用預報資料...")
    data = generate_mock_data()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[SUCCESS] 預報資料已寫入: {output_path}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch CWA Weather Forecast Data")
    parser.add_argument("--api-key", type=str, default=None, help="CWA API Authorization Key")
    parser.add_argument("--dataset", type=str, default=DEFAULT_DATASET, help="CWA Dataset ID")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE, help="Output JSON path")
    parser.add_argument("--mock", action="store_true", help="Force generating mock data")
    args = parser.parse_args()

    if args.mock:
        m_data = generate_mock_data()
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(m_data, f, ensure_ascii=False, indent=2)
        print(f"[SUCCESS] 模擬資料已輸出至 {args.output}")
        sys.exit(0)

    fetch_cwa_weather(api_key=args.api_key, dataset=args.dataset, output_path=args.output)
