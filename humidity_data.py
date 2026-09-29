#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
humidity_data.py
中央氣象署 (CWA) 全台即時相對濕度 (Relative Humidity) 與體感舒適度 (THI) 觀測模組
1. 支援自動抓取 CWA API O-A0003-001 全台 360+ 處局屬氣象測站即時相對濕度實測值
2. 計算溫濕度指數 (THI) 與人體舒適度等級、露點溫度 (Dew Point)
3. 提供全台 22 縣市平均濕度空間熱力分布、轄內各站實測比對與即時除濕健康指引
4. 支援全台測站極值排行 (Top 10 最潮濕 vs Top 10 最乾燥)
"""

import os
import sys
import json
import datetime
import requests
import urllib3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from uv_data import get_cwa_api_key

# 濕度 5 階分級標準與莫蘭迪水氣色標
HUMIDITY_LEVELS = [
    {
        "range_min": 0,
        "range_max": 39,
        "name": "極度乾燥",
        "level": "極度乾燥 (乾燥)",
        "color": "#e07a5f",       # 暖陶磚橘色
        "icon": "🌵",
        "feeling": "乾癢不適 · 靜電好發",
        "description": "空氣過於乾燥，皮膚角質容易缺水發癢，呼吸道黏膜防禦力減弱。",
        "advice": "建議使用室內加濕器維持 50% 濕度，多補充水分與身體保濕乳液，避免長時間直吹暖氣或空調。",
        "dehumidifier_advice": "🚫 無需除濕，請加強室內保濕",
        "window_advice": "可適度開窗，或放置水盆增加濕度"
    },
    {
        "range_min": 40,
        "range_max": 59,
        "name": "舒適宜人",
        "level": "舒適宜人 (適中)",
        "color": "#2a9d8f",       # 莫蘭迪翡翠綠
        "icon": "🍃",
        "feeling": "清爽舒適 · 黃金濕度",
        "description": "人體最理想的黃金濕度區間，體感乾爽平衡，不易滋生黴菌與塵蟎。",
        "advice": "目前濕度環境極為理想，適合各類戶外運動、衣物晾曬及居家休閒。",
        "dehumidifier_advice": "✅ 環境優良，除濕機可待機",
        "window_advice": "維持自然通風對流即可"
    },
    {
        "range_min": 60,
        "range_max": 74,
        "name": "略偏潮濕",
        "level": "略偏潮濕 (稍潮)",
        "color": "#457b9d",       # 海青水藍
        "icon": "💧",
        "feeling": "輕微悶黏 · 水氣漸增",
        "description": "稍微偏高但多數人尚可適應，厚重衣物晾曬需較長時間風乾。",
        "advice": "保持室內良好對流通風；若為過敏體質或有收納皮革衣物，可適度開啟除濕機弱風運轉。",
        "dehumidifier_advice": "ℹ️ 敏感族群可開啟弱風除濕",
        "window_advice": "晴天開窗通風，雨天建議關窗"
    },
    {
        "range_min": 75,
        "range_max": 84,
        "name": "潮濕悶熱",
        "level": "潮濕悶熱 (潮濕)",
        "color": "#2b82d9",       # 曜石水藍
        "icon": "🌧️",
        "feeling": "明顯濕黏 · 排汗不易",
        "description": "塵蟎與黴菌繁殖活跃警戒線，容易引發過敏性鼻炎、氣喘與皮膚濕疹。",
        "advice": "建議關閉迎風面門窗，開啟除濕機將室內目標濕度設定在 55%~60%，並定期清潔濾網。",
        "dehumidifier_advice": "⚠️ 建議開啟除濕機 (目標 55%)",
        "window_advice": "關閉迎風門窗，防止水氣倒灌"
    },
    {
        "range_min": 85,
        "range_max": 100,
        "name": "極度潮濕",
        "level": "極度潮濕 (極濕)",
        "color": "#5e548e",       # 暮色深紫藍
        "icon": "🌊",
        "feeling": "極度黏膩 · 沉重悶滯",
        "description": "空氣水氣接近飽和，牆面壁面極易結露發霉，體感沉重黏膩，換季衣物容易泛黃發臭。",
        "advice": "強烈建議全天候開啟除濕機，密閉衣櫃抽屜置放乾燥劑，洗滌衣物建議搭配烘乾機徹底乾燥。",
        "dehumidifier_advice": "🚨 強烈建議強力除濕 (全天運轉)",
        "window_advice": "嚴密關窗，避免戶外濃重濕氣進入"
    }
]

def get_humidity_category(rh_val):
    """依據相對濕度百分比 (%) 判定等級"""
    if rh_val is None or rh_val < 0:
        return {
            "name": "暫無數據",
            "level": "暫無數據",
            "color": "#94a3b8",
            "icon": "⚪",
            "feeling": "儀器檢修中",
            "description": "該測站感測器目前檢修或數據校驗中。",
            "advice": "請參考鄰近測站之觀測數值。",
            "dehumidifier_advice": "參考鄰近區域建議",
            "window_advice": "依室外天氣狀況調整"
        }
    
    val = round(float(rh_val))
    if val < 40:
        return HUMIDITY_LEVELS[0]
    elif val < 60:
        return HUMIDITY_LEVELS[1]
    elif val < 75:
        return HUMIDITY_LEVELS[2]
    elif val < 85:
        return HUMIDITY_LEVELS[3]
    else:
        return HUMIDITY_LEVELS[4]

def calculate_dew_point(temp_c, rh_percent):
    """
    計算露點溫度 (Dew Point, °C) - Magnus 近似法
    """
    if temp_c is None or rh_percent is None or rh_percent <= 0:
        return None
    try:
        # 近似公式: Td = T - ((100 - RH) / 5)
        td = temp_c - ((100.0 - float(rh_percent)) / 5.0)
        return round(td, 1)
    except Exception:
        return None

def calculate_thi(temp_c, rh_percent):
    """
    計算溫濕度舒適度指數 (THI - Temperature-Humidity Index)
    公式: THI = 0.81 * T + 0.01 * RH * (0.99 * T - 14.3) + 46.3
    """
    if temp_c is None or rh_percent is None:
        return None, "暫無", "#94a3b8"
    try:
        t = float(temp_c)
        rh = float(rh_percent)
        thi = 0.81 * t + 0.01 * rh * (0.99 * t - 14.3) + 46.3
        thi_val = round(thi, 1)

        if thi_val < 65:
            return thi_val, "涼爽舒適", "#457b9d"
        elif thi_val < 70:
            return thi_val, "舒適宜人", "#2a9d8f"
        elif thi_val < 75:
            return thi_val, "稍暖適中", "#e5a93c"
        elif thi_val < 80:
            return thi_val, "悶熱稍黏", "#e07a5f"
        else:
            return thi_val, "極度悶熱", "#c94a4a"
    except Exception:
        return None, "未知", "#94a3b8"

def generate_mock_humidity_stations():
    """當無網路或 API 連線失敗時的離線備援資料"""
    today_str = datetime.datetime.now().strftime("%Y/%m/%d %H:00")
    sample_cities = [
        ("466920", "臺北", "臺北市", "中正區", 25.0377, 121.5149, 78, 28.5),
        ("466930", "陽明山", "臺北市", "北投區", 25.1621, 121.5445, 92, 22.1),
        ("466881", "新北", "新北市", "新店區", 24.9592, 121.5252, 79, 28.2),
        ("466940", "基隆", "基隆市", "仁愛區", 25.1333, 121.7405, 86, 27.8),
        ("467050", "新屋", "桃園市", "新屋區", 25.0067, 121.0475, 75, 29.0),
        ("467571", "新竹", "新竹縣", "竹北市", 24.8286, 121.0145, 73, 29.2),
        ("467280", "後龍", "苗栗縣", "造橋鄉", 24.6486, 120.8318, 71, 29.5),
        ("467490", "臺中", "臺中市", "北區", 24.1457, 120.6841, 68, 30.1),
        ("467270", "田中", "彰化縣", "田中鎮", 23.8738, 120.5813, 72, 29.8),
        ("467650", "日月潭", "南投縣", "魚池鄉", 23.8813, 120.9081, 88, 23.5),
        ("467290", "古坑", "雲林縣", "古坑鄉", 23.6335, 120.5519, 74, 29.4),
        ("467480", "嘉義", "嘉義市", "西區", 23.4959, 120.4329, 70, 30.2),
        ("467530", "阿里山", "嘉義縣", "阿里山鄉", 23.5082, 120.8133, 95, 16.4),
        ("467410", "臺南", "臺南市", "中西區", 22.9933, 120.2049, 72, 30.4),
        ("467441", "高雄", "高雄市", "楠梓區", 22.7304, 120.3125, 69, 31.0),
        ("467590", "恆春", "屏東縣", "恆春鎮", 22.0039, 120.7463, 76, 29.6),
        ("467080", "宜蘭", "宜蘭縣", "宜蘭市", 24.7640, 121.7565, 84, 27.5),
        ("466990", "花蓮", "花蓮縣", "花蓮市", 23.9751, 121.6133, 81, 28.0),
        ("467660", "臺東", "臺東縣", "臺東市", 22.7522, 121.1546, 75, 29.1),
        ("467350", "澎湖", "澎湖縣", "馬公市", 23.5655, 119.5631, 74, 28.9),
        ("467110", "金門", "金門縣", "金城鎮", 24.4073, 118.2893, 70, 28.7),
        ("467990", "馬祖", "連江縣", "南竿鄉", 26.1695, 119.9232, 82, 26.5)
    ]
    stations = []
    for sid, name, county, town, lat, lon, rh, temp in sample_cities:
        cat = get_humidity_category(rh)
        thi, thi_text, thi_color = calculate_thi(temp, rh)
        dp = calculate_dew_point(temp, rh)
        stations.append({
            "station_id": sid,
            "name": name,
            "county": county,
            "town": town,
            "lat": lat,
            "lon": lon,
            "rh": rh,
            "temp": temp,
            "dew_point": dp,
            "thi": thi,
            "thi_text": thi_text,
            "thi_color": thi_color,
            "weather": "多雲",
            "is_offline": False,
            "category": cat
        })
    return {
        "obs_time": today_str,
        "stations": stations,
        "is_mock": True
    }

def fetch_cwa_humidity_live_observation(api_key=None):
    """
    從中央氣象署 CWA API O-A0003-001 (局屬氣象站-現在天氣觀測報告)
    取得全台 360+ 處測站之即時相對濕度實測、氣溫與氣象資料
    """
    if not api_key:
        api_key = get_cwa_api_key()

    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization={api_key}"
    obs_time_str = datetime.datetime.now().strftime("%Y/%m/%d %H:00")
    stations = []

    try:
        r = requests.get(url, timeout=12, verify=False)
        if r.status_code == 200:
            data = r.json()
            raw_stations = data.get("records", {}).get("Station", [])
            latest_dt = ""

            for s in raw_stations:
                sid = s.get("StationId", "")
                sname = s.get("StationName", "")
                geo = s.get("GeoInfo", {})
                county = geo.get("CountyName", "")
                town = geo.get("TownName", "")

                # 提取 WGS84 座標
                coords = geo.get("Coordinates", [])
                lat, lon = None, None
                for c in coords:
                    if c.get("CoordinateName") == "WGS84":
                        try:
                            lat = float(c.get("StationLatitude"))
                            lon = float(c.get("StationLongitude"))
                            break
                        except (ValueError, TypeError):
                            pass
                if lat is None and coords:
                    try:
                        lat = float(coords[0].get("StationLatitude"))
                        lon = float(coords[0].get("StationLongitude"))
                    except (ValueError, TypeError):
                        pass

                if lat is None or lon is None:
                    continue

                # 觀測時間
                ot = s.get("ObsTime", {}).get("DateTime", "")
                if ot and ot > latest_dt:
                    latest_dt = ot

                # 提取氣象因子
                we = s.get("WeatherElement", {})
                rh_raw = we.get("RelativeHumidity")
                temp_raw = we.get("AirTemperature")
                weather_desc = we.get("Weather", "晴")

                # 解析濕度
                try:
                    rh_val = int(round(float(rh_raw))) if rh_raw is not None and float(rh_raw) >= 0 else None
                except (ValueError, TypeError):
                    rh_val = None

                # 解析溫度
                try:
                    temp_val = round(float(temp_raw), 1) if temp_raw is not None and float(temp_raw) > -90 else None
                except (ValueError, TypeError):
                    temp_val = None

                is_off = (rh_val is None)
                cat = get_humidity_category(rh_val)
                thi, thi_text, thi_color = calculate_thi(temp_val, rh_val)
                dp = calculate_dew_point(temp_val, rh_val)

                stations.append({
                    "station_id": sid,
                    "name": sname,
                    "county": county,
                    "town": town,
                    "lat": lat,
                    "lon": lon,
                    "rh": rh_val,
                    "temp": temp_val,
                    "dew_point": dp,
                    "thi": thi,
                    "thi_text": thi_text,
                    "thi_color": thi_color,
                    "weather": weather_desc if weather_desc else "多雲",
                    "is_offline": is_off,
                    "category": cat
                })

            if latest_dt:
                try:
                    clean_dt = latest_dt.split("+")[0].replace("T", " ")
                    obs_time_str = clean_dt[:16].replace("-", "/")
                except Exception:
                    pass

    except Exception as e:
        print(f"[WARN] CWA 濕度 API 請求失敗，啟用備援資料: {e}")
        mock_data = generate_mock_humidity_stations()
        return mock_data

    if not stations:
        return generate_mock_humidity_stations()

    # 排序與統計
    valid_stations = [s for s in stations if not s.get("is_offline") and s.get("rh") is not None]
    
    # 依濕度降序 (最潮濕)
    sorted_by_rh_desc = sorted(valid_stations, key=lambda s: s["rh"], reverse=True)
    # 依濕度升序 (最乾燥)
    sorted_by_rh_asc = sorted(valid_stations, key=lambda s: s["rh"])

    max_station = sorted_by_rh_desc[0] if sorted_by_rh_desc else None
    min_station = sorted_by_rh_asc[0] if sorted_by_rh_asc else None
    avg_rh = round(sum(s["rh"] for s in valid_stations) / len(valid_stations), 1) if valid_stations else 0.0

    return {
        "obs_time": obs_time_str,
        "stations": stations,
        "valid_count": len(valid_stations),
        "total_count": len(stations),
        "max_station": max_station,
        "min_station": min_station,
        "avg_rh": avg_rh,
        "top_humid_stations": sorted_by_rh_desc[:10],
        "top_dry_stations": sorted_by_rh_asc[:10],
        "is_mock": False
    }

def get_county_realtime_humidity_map(stations_list):
    """
    以縣市為單位彙整轄內測站實測濕度與人體舒適度指標
    回傳字典格式: { "臺北市": { "rh": 82, "avg_temp": 28.1, "category": {...}, ... } }
    """
    county_buckets = {}
    for s in stations_list:
        if s.get("is_offline") or s.get("rh") is None:
            continue
        c = s.get("county", "")
        if not c:
            continue
        c_std = c.replace("台", "臺")
        if c_std not in county_buckets:
            county_buckets[c_std] = []
        county_buckets[c_std].append(s)

    result = {}
    for county, sts in county_buckets.items():
        rhs = [s["rh"] for s in sts]
        temps = [s["temp"] for s in sts if s.get("temp") is not None]
        avg_rh = int(round(sum(rhs) / len(rhs)))
        avg_temp = round(sum(temps) / len(temps), 1) if temps else None

        cat = get_humidity_category(avg_rh)
        thi, thi_text, thi_color = calculate_thi(avg_temp, avg_rh)
        dp = calculate_dew_point(avg_temp, avg_rh)

        sorted_local = sorted(sts, key=lambda s: s["rh"], reverse=True)
        max_local = sorted_local[0]
        min_local = sorted_local[-1]

        info = {
            "county": county,
            "rh": avg_rh,
            "avg_temp": avg_temp,
            "dew_point": dp,
            "thi": thi,
            "thi_text": thi_text,
            "thi_color": thi_color,
            "category": cat,
            "station_count": len(sts),
            "max_local_station": max_local,
            "min_local_station": min_local,
            "local_stations": sts,
            "source_desc": f"CWA 局屬測站實測 (轄內 {len(sts)} 處測站平均)"
        }
        result[county] = info
        result[county.replace("臺", "台")] = info

    return result
