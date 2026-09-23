#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
階段 2: 資料解析 (Data Parsing)
parse_weather.py
解析 weather_data.json 巢狀 JSON 結構，
支援 F-A0010-001 (6大分區) 與 F-D0047-091 (22縣市彙整)，
萃取全台 6 大區域（北部、中部、南部、東部、澎湖、金門馬祖）
未來 7 天預報之 MinT (最低溫)、MaxT (最高溫)、dataDate (日期)。
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

# 6 大分區與縣市對照表
REGION_MAPPING = {
    "北部地區": ["基隆市", "臺北市", "台北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣"],
    "中部地區": ["臺中市", "台中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣"],
    "南部地區": ["臺南市", "台南市", "高雄市", "屏東縣"],
    "東部地區": ["宜蘭縣", "花蓮縣", "臺東縣", "台東縣"],
    "澎湖地區": ["澎湖縣"],
    "金門馬祖地區": ["金門縣", "連江縣", "馬祖"]
}

def extract_date_str(time_obj):
    """從 time 物件中提取 YYYY-MM-DD"""
    for key in ["dataDate", "StartTime", "startTime"]:
        if key in time_obj and time_obj[key]:
            return time_obj[key][:10]
    return None

def extract_temp_num(item):
    """靈活提取溫度數值"""
    # 1. 字典中的各種可能的鍵
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
    解析氣象 JSON 並輸出結構化的 6 大分區 7 天氣象清單：
    [
        {"regionName": "北部地區", "dataDate": "2026-09-23", "mint": 19.0, "maxt": 26.0},
        ...
    ]
    """
    if not os.path.exists(input_path):
        print(f"[ERROR] 找不到檔案: {input_path}")
        return []

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", {})

    # 1. 定位 location 陣列（支援 Records.Locations[0].Location 或 Records.location）
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

    # 2. 判斷是否為 6 大區域直接定義
    direct_regions = set(REGION_MAPPING.keys())
    has_direct_regions = any(
        loc.get("LocationName") in direct_regions or loc.get("locationName") in direct_regions
        for loc in locations
    )

    parsed_records = []

    if has_direct_regions:
        print("[INFO] 偵測到 6 大分區原始資料，直接進行欄位萃取...")
        for loc in locations:
            region_name = loc.get("LocationName") or loc.get("locationName")
            if region_name not in direct_regions:
                if region_name in ["金門地區", "馬祖地區"]:
                    region_name = "金門馬祖地區"
                else:
                    continue

            weather_elements = loc.get("WeatherElement") or loc.get("weatherElement") or []
            mint_dict = {}
            maxt_dict = {}

            for elem in weather_elements:
                elem_name = elem.get("ElementName") or elem.get("elementName")
                times = elem.get("Time") or elem.get("time") or []

                if elem_name in ["MinT", "最低氣溫", "最低溫度", "minTemperature"]:
                    for t in times:
                        d_str = extract_date_str(t)
                        val = extract_temp_num(t)
                        if d_str and val is not None:
                            if d_str not in mint_dict or val < mint_dict[d_str]:
                                mint_dict[d_str] = val

                elif elem_name in ["MaxT", "最高氣溫", "最高溫度", "maxTemperature"]:
                    for t in times:
                        d_str = extract_date_str(t)
                        val = extract_temp_num(t)
                        if d_str and val is not None:
                            if d_str not in maxt_dict or val > maxt_dict[d_str]:
                                maxt_dict[d_str] = val

            all_dates = sorted(list(set(mint_dict.keys()) | set(maxt_dict.keys())))
            for d in all_dates[:7]:
                min_t = mint_dict.get(d)
                max_t = maxt_dict.get(d)
                if min_t is not None and max_t is not None:
                    parsed_records.append({
                        "regionName": region_name,
                        "dataDate": d,
                        "mint": float(min_t),
                        "maxt": float(max_t)
                    })
    else:
        print("[INFO] 偵測到全台 22 縣市詳細資料，依地理分區彙整為 6 大區域 7 天氣溫預報...")
        county_to_region = {}
        for region, counties in REGION_MAPPING.items():
            for c in counties:
                county_to_region[c] = region

        # {region: {date: {"min": [], "max": []}}}
        aggregated = {r: {} for r in REGION_MAPPING.keys()}

        for loc in locations:
            c_name = loc.get("LocationName") or loc.get("locationName")
            target_region = county_to_region.get(c_name)
            if not target_region:
                continue

            weather_elements = loc.get("WeatherElement") or loc.get("weatherElement") or []
            for elem in weather_elements:
                elem_name = elem.get("ElementName") or elem.get("elementName")
                times = elem.get("Time") or elem.get("time") or []

                if elem_name in ["最低溫度", "最低氣溫", "MinT"]:
                    for t in times:
                        d_str = extract_date_str(t)
                        val = extract_temp_num(t)
                        if d_str and val is not None:
                            aggregated[target_region].setdefault(d_str, {"min": [], "max": []})["min"].append(val)

                elif elem_name in ["最高溫度", "最高氣溫", "MaxT"]:
                    for t in times:
                        d_str = extract_date_str(t)
                        val = extract_temp_num(t)
                        if d_str and val is not None:
                            aggregated[target_region].setdefault(d_str, {"min": [], "max": []})["max"].append(val)

        for region, date_dict in aggregated.items():
            sorted_dates = sorted(date_dict.keys())
            for d in sorted_dates[:7]:
                mins = date_dict[d]["min"]
                maxs = date_dict[d]["max"]
                if mins and maxs:
                    avg_min = round(sum(mins) / len(mins), 1)
                    avg_max = round(sum(maxs) / len(maxs), 1)
                    parsed_records.append({
                        "regionName": region,
                        "dataDate": d,
                        "mint": avg_min,
                        "maxt": avg_max
                    })

    print(f"[SUCCESS] 解析完成！共提取 {len(parsed_records)} 筆結構化氣溫預報資料。")
    return parsed_records

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse weather forecast JSON")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to raw JSON file")
    args = parser.parse_args()

    results = parse_weather_json(args.input)
    if results:
        print(f"\n[預覽前 6 筆解析資料]:")
        for row in results[:6]:
            print(f"  區域: {row['regionName']:<8} 日期: {row['dataDate']}  最低溫: {row['mint']}°C  最高溫: {row['maxt']}°C")
