#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
階段 2: 資料解析 (Data Parsing)
parse_weather.py
解析 weather_data.json 巢狀 JSON 結構，
支援 全台 22 縣市 與 6 大區域，
萃取全台各縣市未來 7 天預報之 MinT (最低溫)、MaxT (最高溫)、dataDate (日期)。
"""

import os
import sys
import json
import argparse
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_INPUT = "weather_data.json"

REGION_MAPPING = {
    "北部地區": ["基隆市", "臺北市", "台北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣"],
    "中部地區": ["臺中市", "台中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣"],
    "南部地區": ["臺南市", "台南市", "高雄市", "屏東縣"],
    "東部地區": ["宜蘭縣", "花蓮縣", "臺東縣", "台東縣"],
    "澎湖地區": ["澎湖縣"],
    "金門馬祖地區": ["金門縣", "連江縣", "馬祖"]
}

# 台灣 22 縣市標準清單排序（依地理順序）
COUNTY_ORDER = [
    "基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣",
    "臺南市", "高雄市", "屏東縣",
    "宜蘭縣", "花蓮縣", "臺東縣",
    "澎湖縣", "金門縣", "連江縣"
]

def extract_date_str(time_obj):
    for key in ["dataDate", "StartTime", "startTime"]:
        if key in time_obj and time_obj[key]:
            return time_obj[key][:10]
    return None

def extract_temp_num(item):
    if isinstance(item, dict):
        if "ElementValue" in item:
            ev = item["ElementValue"]
            if isinstance(ev, list) and len(ev) > 0 and isinstance(ev[0], dict):
                for val_key in ["MinTemperature", "MaxTemperature", "Temperature", "value"]:
                    if val_key in ev[0] and ev[0][val_key] is not None:
                        try:
                            return float(ev[0][val_key])
                        except ValueError:
                            pass
        elif "elementValue" in item:
            ev = item["elementValue"]
            if isinstance(ev, list) and len(ev) > 0 and isinstance(ev[0], dict):
                for val_key in ["value", "MinTemperature", "MaxTemperature"]:
                    if val_key in ev[0] and ev[0][val_key] is not None:
                        try:
                            return float(ev[0][val_key])
                        except ValueError:
                            pass
        elif "parameter" in item:
            param = item["parameter"]
            if isinstance(param, dict):
                for val_key in ["minTemperature", "maxTemperature", "parameterName"]:
                    if val_key in param:
                        try:
                            return float(str(param[val_key]).split("~")[0].strip())
                        except ValueError:
                            pass
    return None

def parse_weather_json(input_path=DEFAULT_INPUT):
    """
    解析氣象 JSON 並輸出結構化的全台 22 縣市與 6 大區域 7 天氣候預報資料清單
    """
    if not os.path.exists(input_path):
        print(f"[ERROR] 找不到檔案: {input_path}")
        return []

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", {})

    locations = []
    if "Locations" in records and isinstance(records["Locations"], list) and len(records["Locations"]) > 0:
        loc_wrapper = records["Locations"][0]
        locations = loc_wrapper.get("Location") or loc_wrapper.get("location") or []
    elif "locations" in records and isinstance(records["locations"], list) and len(records["locations"]) > 0:
        loc_wrapper = records["locations"][0]
        locations = loc_wrapper.get("location") or loc_wrapper.get("Location") or []
    elif "location" in records:
        locations = records["location"]

    if not locations:
        print("[ERROR] 未在 records 中解析到有效的 location 欄位")
        return []

    parsed_records = []
    county_forecasts = {} # {county: {date: {"min": float, "max": float}}}

    # 解析所有地點
    for loc in locations:
        loc_name = loc.get("LocationName") or loc.get("locationName")
        if not loc_name:
            continue

        weather_elements = loc.get("WeatherElement") or loc.get("weatherElement") or []
        mins = {}
        maxs = {}

        for elem in weather_elements:
            elem_name = elem.get("ElementName") or elem.get("elementName")
            times = elem.get("Time") or elem.get("time") or []

            if elem_name in ["最低溫度", "最低氣溫", "MinT", "minTemperature"]:
                for t in times:
                    d_str = extract_date_str(t)
                    val = extract_temp_num(t)
                    if d_str and val is not None:
                        if d_str not in mins or val < mins[d_str]:
                            mins[d_str] = val

            elif elem_name in ["最高溫度", "最高氣溫", "MaxT", "maxTemperature"]:
                for t in times:
                    d_str = extract_date_str(t)
                    val = extract_temp_num(t)
                    if d_str and val is not None:
                        if d_str not in maxs or val > maxs[d_str]:
                            maxs[d_str] = val

        common_dates = sorted(list(set(mins.keys()) & set(maxs.keys())))
        if common_dates:
            county_forecasts[loc_name] = {}
            for d in common_dates[:7]:
                county_forecasts[loc_name][d] = {
                    "mint": mins[d],
                    "maxt": maxs[d]
                }
                # 將各縣市直接加入結果
                parsed_records.append({
                    "regionName": loc_name,
                    "dataDate": d,
                    "mint": mins[d],
                    "maxt": maxs[d]
                })

    # 若有多個縣市資料，同步計算 6 大區域的平均值並納入資料庫
    if len(county_forecasts) >= 10:
        print("[INFO] 偵測到全台縣市資料，同步計算 6 大區域預報...")
        county_to_region = {}
        for region, counties in REGION_MAPPING.items():
            for c in counties:
                county_to_region[c] = region

        # {region: {date: {"mins": [], "maxs": []}}}
        region_agg = {r: {} for r in REGION_MAPPING.keys()}
        for c_name, date_dict in county_forecasts.items():
            target_r = county_to_region.get(c_name)
            if not target_r:
                continue
            for d, temps in date_dict.items():
                region_agg[target_r].setdefault(d, {"mins": [], "maxs": []})["mins"].append(temps["mint"])
                region_agg[target_r].setdefault(d, {"mins": [], "maxs": []})["maxs"].append(temps["maxt"])

        for r_name, d_dict in region_agg.items():
            for d, vals in sorted(d_dict.items())[:7]:
                if vals["mins"] and vals["maxs"]:
                    parsed_records.append({
                        "regionName": r_name,
                        "dataDate": d,
                        "mint": round(sum(vals["mins"]) / len(vals["mins"]), 1),
                        "maxt": round(sum(vals["maxs"]) / len(vals["maxs"]), 1)
                    })

    print(f"[SUCCESS] 解析完成！共提取 {len(parsed_records)} 筆結構化氣溫預報資料 (涵蓋全台各縣市與大分區)。")
    return parsed_records

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse weather forecast JSON")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to raw JSON file")
    args = parser.parse_args()

    results = parse_weather_json(args.input)
    if results:
        print(f"\n[預覽前 10 筆解析資料]:")
        for row in results[:10]:
            print(f"  縣市/區域: {row['regionName']:<8} 日期: {row['dataDate']}  最低溫: {row['mint']}°C  最高溫: {row['maxt']}°C")
