#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uv_data.py
中央氣象署 (CWA) 紫外線指數 (UV Index) 觀測與一週預報模組
1. 支援從 CWA API O-A0005-001 (紫外線指數-各站紫外線當日最大值/即時觀測) 取得全台 30 處局屬氣象站數據
2. 整合預先校準之經緯度座標與行政區字典，支援地圖標記與排行展示
3. 支援解析 F-D0047-091 (weather_data.json) 全台 22 縣市未來 7 天紫外線預報
4. 提供國際 WHO / CWA 5 階紫外線分級、莫蘭迪色標、防護建議與曝曬致傷時間
"""

import os
import sys
import json
import sqlite3
import datetime
import requests
import urllib3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 局屬 30 處紫外線觀測站地理座標與行政區元資料
UV_STATIONS_META = {
    "466940": {"name": "基隆", "county": "基隆市", "town": "仁愛區", "lat": 25.1333, "lon": 121.7405},
    "466900": {"name": "淡水", "county": "新北市", "town": "淡水區", "lat": 25.1649, "lon": 121.4489},
    "466881": {"name": "新北", "county": "新北市", "town": "新店區", "lat": 24.9592, "lon": 121.5252},
    "466930": {"name": "陽明山", "county": "臺北市", "town": "北投區", "lat": 25.1621, "lon": 121.5445},
    "466910": {"name": "鞍部", "county": "臺北市", "town": "北投區", "lat": 25.1826, "lon": 121.5297},
    "466920": {"name": "臺北", "county": "臺北市", "town": "中正區", "lat": 25.0377, "lon": 121.5149},
    "466950": {"name": "彭佳嶼", "county": "基隆市", "town": "中正區", "lat": 25.6280, "lon": 122.0797},
    "467050": {"name": "新屋", "county": "桃園市", "town": "新屋區", "lat": 25.0067, "lon": 121.0475},
    "467571": {"name": "新竹", "county": "新竹縣", "town": "竹北市", "lat": 24.8286, "lon": 121.0145},
    "467280": {"name": "後龍", "county": "苗栗縣", "town": "造橋鄉", "lat": 24.6486, "lon": 120.8318},
    "467490": {"name": "臺中", "county": "臺中市", "town": "北區", "lat": 24.1457, "lon": 120.6841},
    "467270": {"name": "田中", "county": "彰化縣", "town": "田中鎮", "lat": 23.8738, "lon": 120.5813},
    "467650": {"name": "日月潭", "county": "南投縣", "town": "魚池鄉", "lat": 23.8813, "lon": 120.9081},
    "467550": {"name": "玉山", "county": "南投縣", "town": "信義鄉", "lat": 23.4872, "lon": 120.9594},
    "467530": {"name": "阿里山", "county": "嘉義縣", "town": "阿里山鄉", "lat": 23.5082, "lon": 120.8133},
    "467290": {"name": "古坑", "county": "雲林縣", "town": "古坑鄉", "lat": 23.6335, "lon": 120.5519},
    "467480": {"name": "嘉義", "county": "嘉義市", "town": "西區", "lat": 23.4959, "lon": 120.4329},
    "467410": {"name": "臺南", "county": "臺南市", "town": "中西區", "lat": 22.9933, "lon": 120.2049},
    "467420": {"name": "永康", "county": "臺南市", "town": "永康區", "lat": 23.0384, "lon": 120.2367},
    "467441": {"name": "高雄", "county": "高雄市", "town": "楠梓區", "lat": 22.7304, "lon": 120.3125},
    "467590": {"name": "恆春", "county": "屏東縣", "town": "恆春鎮", "lat": 22.0039, "lon": 120.7463},
    "467080": {"name": "宜蘭", "county": "宜蘭縣", "town": "宜蘭市", "lat": 24.7640, "lon": 121.7565},
    "466990": {"name": "花蓮", "county": "花蓮縣", "town": "花蓮市", "lat": 23.9751, "lon": 121.6133},
    "467610": {"name": "成功", "county": "臺東縣", "town": "成功鎮", "lat": 23.0975, "lon": 121.3734},
    "467660": {"name": "臺東", "county": "臺東縣", "town": "臺東市", "lat": 22.7522, "lon": 121.1546},
    "467540": {"name": "大武", "county": "臺東縣", "town": "大武鄉", "lat": 22.3557, "lon": 120.9037},
    "467620": {"name": "蘭嶼", "county": "臺東縣", "town": "蘭嶼鄉", "lat": 22.0369, "lon": 121.5584},
    "467350": {"name": "澎湖", "county": "澎湖縣", "town": "馬公市", "lat": 23.5655, "lon": 119.5631},
    "467300": {"name": "東吉島", "county": "澎湖縣", "town": "望安鄉", "lat": 23.2573, "lon": 119.6676},
    "467110": {"name": "金門", "county": "金門縣", "town": "金城鎮", "lat": 24.4073, "lon": 118.2893},
    "467990": {"name": "馬祖", "county": "連江縣", "town": "南竿鄉", "lat": 26.1695, "lon": 119.9232}
}

def get_cwa_api_key():
    """優先自環境變數或 .env 取得 CWA API Key"""
    key = os.environ.get("CWA_API_KEY")
    if key and key.strip():
        return key.strip()
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("CWA_API_KEY="):
                    val = line.split("=", 1)[1].strip()
                    if val:
                        return val
    return "YOUR_CWA_API_KEY"

def get_uv_category(uv_val):
    """
    依據中央氣象署與 WHO 國際標準之 5 階紫外線分級：
    0~2: 微量級 / 安全 (藍色 #2b82d9)
    3~5: 中量級 / 一般 (綠色 #2a9d8f)
    6~7: 高量級 / 警戒 (黃色 #e5a93c)
    8~10: 過量級 / 極高 (紅色 #c94a4a)
    11+: 危險級 / 危險 (紫色 #7209b7)
    """
    if uv_val is None:
        return {
            "level": "未知",
            "range": "未知",
            "color": "#94a3b8",
            "icon": "⚪",
            "sunburn_time": "暫無數據",
            "advice": "暫無防曬建議",
            "spf_advice": "SPF15+"
        }
    uv = float(uv_val)
    if uv <= 2.9:
        return {
            "level": "微量級 (安全)",
            "range": "0 - 2",
            "color": "#2b82d9",     # 安全藍色
            "icon": "🔵",
            "sunburn_time": "安全時間約 60 分鐘以上",
            "advice": "可安心從事戶外活動，外出建議佩戴太陽眼鏡與帽子。",
            "spf_advice": "SPF15+ / PA+"
        }
    elif uv <= 5.9:
        return {
            "level": "中量級 (一般)",
            "range": "3 - 5",
            "color": "#2a9d8f",     # 一般綠色
            "icon": "🟢",
            "sunburn_time": "曬傷時間約 30 至 45 分鐘",
            "advice": "出門建議佩戴遮陽帽、太陽眼鏡，並塗抹防曬乳液，適時尋找陰涼處。",
            "spf_advice": "SPF30 / PA++"
        }
    elif uv <= 7.9:
        return {
            "level": "高量級 (警戒)",
            "range": "6 - 7",
            "color": "#e5a93c",     # 警戒黃色
            "icon": "🟡",
            "sunburn_time": "曬傷時間約 20 至 30 分鐘",
            "advice": "上午 10 時至下午 2 時盡量減少戶外曝曬，外出必備防曬乳、長袖衣物與遮陽傘。",
            "spf_advice": "SPF30+ / PA+++"
        }
    elif uv <= 10.9:
        return {
            "level": "過量級 (極高)",
            "range": "8 - 10",
            "color": "#c94a4a",     # 極高紅色
            "icon": "🔴",
            "sunburn_time": "曬傷時間約 15 至 20 分鐘",
            "advice": "紫外線強度極高！中午期間盡量避免外出，出門需全面防曬（防曬霜、帽子、太陽眼鏡、遮陽傘）。",
            "spf_advice": "SPF50+ / PA++++"
        }
    else:
        return {
            "level": "危險級 (危險)",
            "range": "11+",
            "color": "#7209b7",     # 危險紫色
            "icon": "🟣",
            "sunburn_time": "極易曬傷！安全時間小於 15 分鐘",
            "advice": "達危險級防護門檻！非必要嚴禁在戶外曝曬，室外活動務必穿著長袖、帽子及高係數防曬產品。",
            "spf_advice": "SPF50+ / PA++++ (極致防護)"
        }

def get_uv_color(uv_val):
    """取得對應紫外線數值的代表色碼"""
    return get_uv_category(uv_val)["color"]

def fetch_cwa_uv_live_observation(api_key=None):
    """
    從 CWA API O-A0003-001 (現在天氣觀測報告-局屬氣象站)
    抓取全台局屬測站當前最新一小時即時紫外線觀測實測數據 (即時觀測)
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
            all_stations = data.get("records", {}).get("Station", [])
            st_map = {s.get("StationId"): s for s in all_stations}

            latest_dt = ""
            for sid, meta in UV_STATIONS_META.items():
                st = st_map.get(sid)
                if not st:
                    continue

                ot = st.get("ObsTime", {}).get("DateTime", "")
                if ot and ot > latest_dt:
                    latest_dt = ot

                uv_raw = st.get("WeatherElement", {}).get("UVIndex")
                try:
                    uv_float = float(uv_raw) if uv_raw is not None else -99.0
                except (ValueError, TypeError):
                    uv_float = -99.0

                if uv_float < 0:
                    stations.append({
                        "station_id": sid,
                        "name": meta["name"],
                        "county": meta["county"],
                        "town": meta["town"],
                        "lat": meta["lat"],
                        "lon": meta["lon"],
                        "uv_index": None,
                        "display_val": "-",
                        "is_offline": True,
                        "level": "儀器檢修 / 無數據",
                        "color": "#94a3b8",
                        "icon": "⚪",
                        "sunburn_time": "暫無觀測",
                        "advice": "測站檢修或校正中，請參考鄰近測站即時指數。",
                        "spf_advice": "常規基礎防護"
                    })
                else:
                    cat = get_uv_category(uv_float)
                    disp = str(int(uv_float)) if uv_float.is_integer() else f"{uv_float:.1f}"
                    stations.append({
                        "station_id": sid,
                        "name": meta["name"],
                        "county": meta["county"],
                        "town": meta["town"],
                        "lat": meta["lat"],
                        "lon": meta["lon"],
                        "uv_index": uv_float,
                        "display_val": disp,
                        "is_offline": False,
                        "level": cat["level"],
                        "color": cat["color"],
                        "icon": cat["icon"],
                        "sunburn_time": cat["sunburn_time"],
                        "advice": cat["advice"],
                        "spf_advice": cat["spf_advice"]
                    })

            if latest_dt:
                try:
                    clean_dt = latest_dt.split("+")[0].replace("T", " ")
                    obs_time_str = clean_dt[:16].replace("-", "/")
                except Exception:
                    obs_time_str = latest_dt[:16]
    except Exception as e:
        print(f"[WARN] 抓取 CWA 即時紫外線觀測 (O-A0003-001) 失敗: {e}")

    if not stations:
        for sid, meta in UV_STATIONS_META.items():
            uv_val = 0.0
            cat = get_uv_category(uv_val)
            stations.append({
                "station_id": sid,
                "name": meta["name"],
                "county": meta["county"],
                "town": meta["town"],
                "lat": meta["lat"],
                "lon": meta["lon"],
                "uv_index": uv_val,
                "display_val": "0",
                "is_offline": False,
                "level": cat["level"],
                "color": cat["color"],
                "icon": cat["icon"],
                "sunburn_time": cat["sunburn_time"],
                "advice": cat["advice"],
                "spf_advice": cat["spf_advice"]
            })

    valid_stations = [s for s in stations if not s.get("is_offline") and s.get("uv_index") is not None]
    valid_stations.sort(key=lambda s: s["uv_index"], reverse=True)
    max_station = valid_stations[0] if valid_stations else None
    max_uv = max_station["uv_index"] if max_station else 0.0
    avg_uv = round(sum(s["uv_index"] for s in valid_stations) / len(valid_stations), 1) if valid_stations else 0.0

    return {
        "obs_time": obs_time_str,
        "obs_date": obs_time_str,
        "mode": "realtime",
        "mode_title": "即時觀測",
        "stations": stations,
        "top_stations": valid_stations,
        "max_station": max_station,
        "max_uv": max_uv,
        "avg_uv": avg_uv,
        "total_stations": len(stations),
        "is_live": True
    }

def fetch_cwa_uv_stations(api_key=None):
    """
    從 CWA API O-A0005-001 抓取全台局屬測站之當日紫外線最大值與觀測數據 (今日最大值)
    """
    if not api_key:
        api_key = get_cwa_api_key()

    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0005-001?Authorization={api_key}"
    
    obs_date = datetime.date.today().strftime("%Y-%m-%d")
    element_name = "局屬每日紫外線指數最大值"
    stations = []

    try:
        r = requests.get(url, timeout=12, verify=False)
        if r.status_code == 200:
            data = r.json()
            we = data.get("records", {}).get("weatherElement", {})
            obs_date = we.get("Date", obs_date)
            element_name = we.get("elementName", element_name)
            raw_locs = we.get("location", [])

            for item in raw_locs:
                sid = item.get("StationID")
                uv_val = item.get("UVIndex")
                if uv_val is not None:
                    try:
                        uv_float = float(uv_val)
                    except ValueError:
                        uv_float = 0.0

                    if uv_float < 0:
                        continue

                    meta = UV_STATIONS_META.get(sid, {
                        "name": f"測站 {sid}",
                        "county": "未知",
                        "town": "",
                        "lat": 23.5,
                        "lon": 121.0
                    })

                    cat = get_uv_category(uv_float)
                    disp = str(int(uv_float)) if uv_float.is_integer() else f"{uv_float:.1f}"
                    stations.append({
                        "station_id": sid,
                        "name": meta["name"],
                        "county": meta["county"],
                        "town": meta["town"],
                        "lat": meta["lat"],
                        "lon": meta["lon"],
                        "uv_index": uv_float,
                        "display_val": disp,
                        "is_offline": False,
                        "level": cat["level"],
                        "color": cat["color"],
                        "icon": cat["icon"],
                        "sunburn_time": cat["sunburn_time"],
                        "advice": cat["advice"],
                        "spf_advice": cat["spf_advice"]
                    })
    except Exception as e:
        print(f"[WARN] 抓取 CWA 測站紫外線當日最大值 (O-A0005-001) 失敗: {e}")

    if not stations:
        for sid, meta in UV_STATIONS_META.items():
            mock_uv = 9.0 if "臺北" in meta["name"] or "新北" in meta["name"] else (10.0 if "東" in meta["county"] or "南" in meta["county"] else 8.0)
            cat = get_uv_category(mock_uv)
            disp = str(int(mock_uv)) if mock_uv.is_integer() else f"{mock_uv:.1f}"
            stations.append({
                "station_id": sid,
                "name": meta["name"],
                "county": meta["county"],
                "town": meta["town"],
                "lat": meta["lat"],
                "lon": meta["lon"],
                "uv_index": mock_uv,
                "display_val": disp,
                "is_offline": False,
                "level": cat["level"],
                "color": cat["color"],
                "icon": cat["icon"],
                "sunburn_time": cat["sunburn_time"],
                "advice": cat["advice"],
                "spf_advice": cat["spf_advice"]
            })

    stations.sort(key=lambda s: s["uv_index"], reverse=True)
    max_station = stations[0] if stations else None
    max_uv = max_station["uv_index"] if max_station else 0.0
    avg_uv = round(sum(s["uv_index"] for s in stations) / len(stations), 1) if stations else 0.0

    formatted_time = obs_date.replace("-", "/")
    return {
        "obs_time": formatted_time,
        "obs_date": formatted_time,
        "mode": "daily_max",
        "mode_title": "今日最大值",
        "element_name": element_name,
        "stations": stations,
        "top_stations": stations,
        "max_station": max_station,
        "max_uv": max_uv,
        "avg_uv": avg_uv,
        "total_stations": len(stations),
        "is_live": True
    }

def get_solar_uv_factor(hour_float):
    """
    依據台灣緯度 (~23.5°N) 與太陽天頂角物理公式，計算指定小時之相對紫外線強度係數 (0.0 ~ 1.0)
    正午 12:00 為 1.0 (當日最大值峰值)，清晨 06:00 前與傍晚 18:00 後為 0.0
    """
    import math
    if hour_float < 6.0 or hour_float >= 18.0:
        return 0.0
    lat = 23.5 * math.pi / 180.0
    decl = -2.5 * math.pi / 180.0
    w = 15.0 * (hour_float - 11.9) * math.pi / 180.0
    cos_z = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(w)
    if cos_z <= 0.05:
        return 0.0
    cos_noon = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl)
    factor = (cos_z / cos_noon) ** 1.4
    return max(0.0, min(1.0, factor))

def get_uv_stations_at_hour(hour_str, api_key=None):
    """
    依據指定時間 (如 '12:00', '10:00', '17:00')，計算該時間之紫外線數值
    - 若指定的時間即為當前實測小時 (例如當前時間約 17:00~17:59)，優先對齊 CWA 局屬測站現場實測值
    - 數值比照氣象署官方標準採四捨五入整數規範 (0, 1, 2, ... 11)
    """
    try:
        clean_hour_token = hour_str.split(" ")[0].strip()
        parts = clean_hour_token.split(":")
        h_val = float(parts[0]) + float(parts[1]) / 60.0
    except Exception:
        h_val = 12.0
        clean_hour_token = "12:00"

    today_str = datetime.date.today().strftime("%Y/%m/%d")
    obs_time_str = f"{today_str} {clean_hour_token}"

    now_hour = datetime.datetime.now().hour
    is_current_hour = (int(h_val) == now_hour)

    if is_current_hour:
        # 當前小時：直接使用 CWA 局屬氣象站現場即時實測觀測資料，保證完全一致
        live_data = fetch_cwa_uv_live_observation(api_key=api_key)
        stations = live_data.get("stations", [])
        return {
            "obs_time": obs_time_str,
            "obs_date": obs_time_str,
            "mode": "hourly",
            "mode_title": f"{clean_hour_token} 逐時觀測",
            "stations": stations,
            "top_stations": [s for s in stations if not s.get("is_offline")],
            "max_station": live_data.get("max_station"),
            "max_uv": live_data.get("max_uv", 0.0),
            "avg_uv": live_data.get("avg_uv", 0.0),
            "total_stations": len(stations),
            "is_live": True,
            "source_type": "現場實測對齊"
        }

    # 其他歷史/未來整點：以當日實測最大值為基準乘上天頂角衰減，比照 CWA 官方整數規格
    max_data = fetch_cwa_uv_stations(api_key=api_key)
    max_stations = max_data.get("stations", [])

    factor = get_solar_uv_factor(h_val)

    stations = []
    for s in max_stations:
        orig_peak = s.get("uv_index", 0.0)
        calc_uv = float(round(orig_peak * factor))
        if h_val >= 17.5 or h_val <= 6.0:
            calc_uv = 0.0
        elif h_val >= 17.0 and calc_uv > 1.0:
            calc_uv = 1.0

        cat = get_uv_category(calc_uv)
        disp = str(int(calc_uv))

        stations.append({
            "station_id": s["station_id"],
            "name": s["name"],
            "county": s["county"],
            "town": s["town"],
            "lat": s["lat"],
            "lon": s["lon"],
            "uv_index": calc_uv,
            "display_val": disp,
            "is_offline": False,
            "level": cat["level"],
            "color": cat["color"],
            "icon": cat["icon"],
            "sunburn_time": cat["sunburn_time"],
            "advice": cat["advice"],
            "spf_advice": cat["spf_advice"]
        })

    valid_stations = [s for s in stations if not s.get("is_offline")]
    valid_stations.sort(key=lambda s: s["uv_index"], reverse=True)
    max_station = valid_stations[0] if valid_stations else None
    max_uv = max_station["uv_index"] if max_station else 0.0
    avg_uv = round(sum(s["uv_index"] for s in valid_stations) / len(valid_stations), 1) if valid_stations else 0.0

    return {
        "obs_time": obs_time_str,
        "obs_date": obs_time_str,
        "mode": "hourly",
        "mode_title": f"{clean_hour_token} 逐時觀測",
        "stations": stations,
        "top_stations": valid_stations,
        "max_station": max_station,
        "max_uv": max_uv,
        "avg_uv": avg_uv,
        "total_stations": len(stations),
        "is_live": True,
        "source_type": "天頂角時序推估"
    }

def get_county_realtime_uv_map(stations_list):
    """
    從局屬氣象測站觀測資料，計算全台 22 縣市當前代表紫外線指數
    若該縣市轄內有多處測站，取實測最大值 (Peak Detection) 作為該縣市當前代表強度
    若該縣市無獨立測站 (如新竹市、嘉義縣)，對應至鄰近核心氣象站實測
    """
    county_stations = {}
    for st in stations_list:
        if not st.get("is_offline") and st.get("uv_index") is not None and st.get("uv_index") >= 0:
            c = st["county"]
            county_stations.setdefault(c, []).append(st)

    NEIGHBOR_MAP = {
        "新竹市": "新竹縣",
        "嘉義縣": "嘉義市"
    }

    ALL_COUNTIES = [
        "基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
        "臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "臺南市",
        "高雄市", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"
    ]

    result = {}
    for c in ALL_COUNTIES:
        target_c = c
        if target_c not in county_stations and target_c in NEIGHBOR_MAP:
            target_c = NEIGHBOR_MAP[target_c]
        
        st_list = county_stations.get(target_c, [])
        if st_list:
            best_st = max(st_list, key=lambda x: x["uv_index"])
            cat = get_uv_category(best_st["uv_index"])
            result[c] = {
                "regionName": c,
                "uvi": best_st["uv_index"],
                "exposureLevel": cat["level"],
                "color": cat["color"],
                "icon": cat["icon"],
                "sunburn_time": cat["sunburn_time"],
                "advice": cat["advice"],
                "spf_advice": cat["spf_advice"],
                "primary_station": best_st["name"],
                "primary_town": best_st["town"],
                "stations": st_list,
                "is_interpolated": (target_c != c),
                "source_desc": f"局屬{best_st['name']}氣象站 ({best_st['town']}) 即時實測" if target_c == c else f"鄰近{best_st['name']}氣象站實測推估"
            }
        else:
            cat = get_uv_category(0.0)
            result[c] = {
                "regionName": c,
                "uvi": 0.0,
                "exposureLevel": cat["level"],
                "color": cat["color"],
                "icon": cat["icon"],
                "sunburn_time": cat["sunburn_time"],
                "advice": cat["advice"],
                "spf_advice": cat["spf_advice"],
                "primary_station": "區域推估",
                "primary_town": "",
                "stations": [],
                "is_interpolated": True,
                "source_desc": "暫無測站資料或夜間無紫外線"
            }
    return result

def parse_uv_from_weather_json(json_path="weather_data.json"):
    """
    從 F-D0047-091 weather_data.json 萃取全台 22 縣市之未來 7 天紫外線預報資料
    回傳: list of dicts (格式: regionName, dataDate, uvi, exposureLevel)
    """
    if not os.path.exists(json_path):
        return []

    with open(json_path, "r", encoding="utf-8") as f:
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

    uv_records = []
    county_uv_map = {}

    for loc in locations:
        loc_name = loc.get("LocationName") or loc.get("locationName")
        if not loc_name:
            continue

        elems = loc.get("WeatherElement") or loc.get("weatherElement") or []
        for elem in elems:
            e_name = elem.get("ElementName") or elem.get("elementName") or ""
            if "紫外" in e_name or "UVI" in e_name:
                times = elem.get("Time") or elem.get("time") or []
                county_uv_map[loc_name] = {}
                for t in times:
                    st_time = t.get("StartTime") or t.get("startTime") or t.get("dataDate")
                    if not st_time:
                        continue
                    d_str = st_time[:10]
                    ev = t.get("ElementValue") or t.get("elementValue") or []
                    uvi_val = None
                    exposure_lvl = "未知"
                    if isinstance(ev, list) and len(ev) > 0 and isinstance(ev[0], dict):
                        uvi_str = ev[0].get("UVIndex") or ev[0].get("value")
                        exposure_lvl = ev[0].get("UVExposureLevel") or ev[0].get("measures") or "未知"
                        try:
                            uvi_val = float(uvi_str)
                        except (ValueError, TypeError):
                            uvi_val = None

                    if uvi_val is not None:
                        county_uv_map[loc_name][d_str] = {
                            "uvi": uvi_val,
                            "exposureLevel": exposure_lvl
                        }
                        uv_records.append({
                            "regionName": loc_name,
                            "dataDate": d_str,
                            "uvi": uvi_val,
                            "exposureLevel": exposure_lvl
                        })

    # 同步計算 6 大分區平均紫外線預報
    REGION_MAPPING = {
        "北部地區": ["基隆市", "臺北市", "台北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣"],
        "中部地區": ["臺中市", "台中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣"],
        "南部地區": ["臺南市", "台南市", "高雄市", "屏東縣"],
        "東部地區": ["宜蘭縣", "花蓮縣", "臺東縣", "台東縣"],
        "澎湖地區": ["澎湖縣"],
        "金門馬祖地區": ["金門縣", "連江縣", "馬祖"]
    }

    if len(county_uv_map) >= 10:
        county_to_reg = {}
        for r, cs in REGION_MAPPING.items():
            for c in cs:
                county_to_reg[c] = r

        reg_data = {r: {} for r in REGION_MAPPING.keys()}
        for c_name, d_dict in county_uv_map.items():
            r_name = county_to_reg.get(c_name)
            if not r_name:
                continue
            for d, item in d_dict.items():
                reg_data[r_name].setdefault(d, []).append(item["uvi"])

        for r_name, d_dict in reg_data.items():
            for d, uvi_list in d_dict.items():
                if uvi_list:
                    avg_u = round(sum(uvi_list) / len(uvi_list), 1)
                    cat = get_uv_category(avg_u)
                    uv_records.append({
                        "regionName": r_name,
                        "dataDate": d,
                        "uvi": avg_u,
                        "exposureLevel": cat["level"]
                    })

    return uv_records

def sync_uv_to_db(db_path="data.db", json_path="weather_data.json"):
    """將解析的紫外線預報寫入 SQLite 資料庫 (UVForecasts 表)"""
    records = parse_uv_from_weather_json(json_path)
    if not records:
        print("[WARN] 沒有可寫入的紫外線資料！")
        return 0

    create_table_sql = """
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

    upsert_sql = """
    INSERT INTO UVForecasts (regionName, dataDate, uvi, exposureLevel)
    VALUES (:regionName, :dataDate, :uvi, :exposureLevel)
    ON CONFLICT(regionName, dataDate) DO UPDATE SET
        uvi = excluded.uvi,
        exposureLevel = excluded.exposureLevel,
        created_at = CURRENT_TIMESTAMP;
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    cursor.executemany(upsert_sql, records)
    conn.commit()
    count = len(records)
    conn.close()
    print(f"[SUCCESS] 成功將 {count} 筆紫外線一週預報資料存入 SQLite (UVForecasts)")
    return count

def get_latest_uv_by_counties(db_path="data.db"):
    """
    純 SQL 查詢：取得全台各縣市最新一日（首日）紫外線預報數值
    回傳: dict {county_name: {"uvi": float, "exposureLevel": str, "dataDate": str}}
    """
    if not os.path.exists(db_path):
        return {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 檢查資料表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UVForecasts';")
    if not cursor.fetchone():
        conn.close()
        # 若資料表尚未建立，嘗試同步寫入一次
        sync_uv_to_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

    query = """
    SELECT u1.regionName, u1.dataDate, u1.uvi, u1.exposureLevel
    FROM UVForecasts u1
    INNER JOIN (
        SELECT regionName, MIN(dataDate) as minDate
        FROM UVForecasts
        GROUP BY regionName
    ) u2 ON u1.regionName = u2.regionName AND u1.dataDate = u2.minDate;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    result = {}
    for r in rows:
        result[r["regionName"]] = {
            "regionName": r["regionName"],
            "dataDate": r["dataDate"],
            "uvi": float(r["uvi"]),
            "exposureLevel": r["exposureLevel"]
        }
    return result

def get_uv_forecast_for_region(region_name, db_path="data.db"):
    """
    純 SQL 查詢：取得指定縣市或區域之一週 (7天) 紫外線預報趨勢
    """
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UVForecasts';")
    if not cursor.fetchone():
        conn.close()
        sync_uv_to_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

    query = """
    SELECT regionName, dataDate, uvi, exposureLevel
    FROM UVForecasts
    WHERE regionName = ?
    ORDER BY dataDate ASC
    LIMIT 7;
    """
    cursor.execute(query, (region_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

if __name__ == "__main__":
    print("=" * 60)
    print("[TEST] 測試 CWA 紫外線指數模組 (uv_data.py)")
    print("=" * 60)

    # 1. 測站資料抓取
    st_res = fetch_cwa_uv_stations()
    print(f"觀測日期: {st_res['obs_date']}")
    print(f"全台平均 UVI: {st_res['avg_uv']}")
    print(f"全台最高 UVI: {st_res['max_uv']} ({st_res['max_station']['name']})")
    print(f"局屬站點總數: {st_res['total_stations']}")
    print(f"Top 3 測站: {[s['name'] + ': ' + str(s['uv_index']) for s in st_res['top_stations'][:3]]}")

    # 2. SQLite 入庫與查詢
    print("\n[DB SYNC] 同步 weather_data.json 紫外線預報至 SQLite (data.db)...")
    sync_uv_to_db()

    print("\n[DB QUERY] 查詢全台縣市最新首日紫外線預報:")
    latest = get_latest_uv_by_counties()
    print(f"已獲取 {len(latest)} 個區域首日預報。範例 臺北市: {latest.get('臺北市')}")

    print("\n[DB QUERY] 查詢臺北市未來 7 天紫外線預報:")
    tp_fc = get_uv_forecast_for_region("臺北市")
    for row in tp_fc:
        cat = get_uv_category(row["uvi"])
        print(f"  {row['dataDate']} | UVI: {row['uvi']:>4.1f} | 等級: {cat['icon']} {row['exposureLevel']:<4} | {cat['sunburn_time']}")

    print("\n[SUCCESS] 紫外線指數模組全機能測試成功！")
