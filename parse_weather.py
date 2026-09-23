#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
階段 2: 資料解析 (Data Parsing)
parse_weather.py
解析 weather_data.json 巢狀 JSON 結構，
萃取全台 6 大區域（北部、中部、南部、東部、澎湖、金門馬祖）
7 天預報之 MinT (最低溫)、MaxT (最高溫)、dataDate (日期)。
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

# 6 大分區與縣市對照表（若遇到縣市級資料時使用）
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
    if "dataDate" in time_obj:
        return time_obj["dataDate"][:10]
    elif "startTime" in time_obj:
        return time_obj["startTime"][:10]
    return None

def extract_element_val(item):
    """解析溫度數值"""
    if "elementValue" in item:
        ev = item["elementValue"]
        if isinstance(ev, list) and len(ev) > 0:
            if isinstance(ev[0], dict) and "value" in ev[0]:
                return float(ev[0]["value"])
            elif isinstance(ev[0], (int, float, str)):
                return float(ev[0])
        elif isinstance(ev, (int, float, str)):
            return float(ev)
    elif "parameter" in item:
        param = item["parameter"]
        if isinstance(param, dict):
            if "parameterName" in param:
                try:
                    return float(param["parameterName"].split("~")[0].strip())
                except ValueError:
                    pass
            if "minTemperature" in param:
                return float(param["minTemperature"])
            if "maxTemperature" in param:
                return float(param["maxTemperature"])
    return None

def parse_weather_json(input_path=DEFAULT_INPUT):
    """
    解析氣象 JSON 並輸出結構化的氣象清單：
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
    
    locations = records.get("location")
    if not locations and "locations" in records:
        locs_wrapper = records["locations"]
        if isinstance(locs_wrapper, list) and len(locs_wrapper) > 0:
            locations = locs_wrapper[0].get("location", [])

    if not locations:
        print("[ERROR] 未在 records 中解析到有效的 location 欄位")
        return []

    direct_regions = set(REGION_MAPPING.keys())
    has_direct_regions = any(loc.get("locationName") in direct_regions for loc in locations)

    parsed_records = []

    if has_direct_regions:
        print("[INFO] 偵測到 6 大分區格式資料，直接解析各分區預報...")
        for loc in locations:
            region_name = loc.get("locationName")
            if region_name not in direct_regions:
                if region_name in ["金門地區", "馬祖地區"]:
                    region_name = "金門馬祖地區"
                else:
                    continue

            weather_elements = loc.get("weatherElement", [])
            mint_dict = {}
            maxt_dict = {}

            for elem in weather_elements:
                elem_name = elem.get("elementName")
                times = elem.get("time", [])

                if elem_name in ["MinT", "最低氣溫", "minTemperature"]:
                    for t in times:
                        d_str = extract_date_str(t)
                        val = extract_element_val(t)
                        if d_str and val is not None:
                            if d_str not in mint_dict or val < mint_dict[d_str]:
                                mint_dict[d_str] = val

                elif elem_name in ["MaxT", "最高氣溫", "maxTemperature"]:
                    for t in times:
                        d_str = extract_date_str(t)
                        val = extract_element_val(t)
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
        print("[INFO] 偵測到各縣市細部資料，正在彙整為 6 大區域平均溫度...")
        county_to_region = {}
        for region, counties in REGION_MAPPING.items():
            for c in counties:
                county_to_region[c] = region

        aggregated = {r: {} for r in REGION_MAPPING.keys()}

        for loc in locations:
            c_name = loc.get("locationName")
            target_region = county_to_region.get(c_name)
            if not target_region:
                continue

            weather_elements = loc.get("weatherElement", [])
            for elem in weather_elements:
                elem_name = elem.get("elementName")
                times = elem.get("time", [])
                
                if elem_name in ["MinT", "最低氣溫"]:
                    for t in times:
                        d_str = extract_date_str(t)
                        val = extract_element_val(t)
                        if d_str and val is not None:
                            aggregated[target_region].setdefault(d_str, {"min": [], "max": []})["min"].append(val)

                elif elem_name in ["MaxT", "最高氣溫"]:
                    for t in times:
                        d_str = extract_date_str(t)
                        val = extract_element_val(t)
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

    print(f"[SUCCESS] 解析完成！共提取 {len(parsed_records)} 筆結構化氣候預報資料。")
    return parsed_records

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse weather forecast JSON")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to raw JSON file")
    args = parser.parse_args()

    results = parse_weather_json(args.input)
    if results:
        print(f"\n[預覽前 5 筆解析資料]:")
        for row in results[:5]:
            print(f"  區域: {row['regionName']:<8} 日期: {row['dataDate']}  最低溫: {row['mint']}°C  最高溫: {row['maxt']}°C")
