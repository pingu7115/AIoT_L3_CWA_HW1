#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rainfall_data.py
中央氣象署 (CWA) 全台累積雨量與即時雨量觀測站模組
1. 支援自動抓取 CWA O-A0040-002 (日累積雨量圖 - 小間距)
2. 支援從 O-A0040-003.kmz 解析無背景透明雨量色斑熱力圖，供 Folium ImageOverlay 即時套疊
3. 支援解析 O-A0002-001 全台 1,300+ 自動雨量站即時數據 (本日累積雨量、時雨量排行榜)
"""

import os
import io
import json
import base64
import zipfile
import datetime
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from typhoon_data import get_cwa_api_key

def get_rain_color(rain_mm):
    """依照氣象署累積雨量標準圖例色彩映射"""
    if rain_mm <= 0:
        return "#64748B"
    elif rain_mm < 1:
        return "#94A3B8"
    elif rain_mm < 2:
        return "#BBF1FA"
    elif rain_mm < 6:
        return "#38BDF8"
    elif rain_mm < 10:
        return "#0284C7"
    elif rain_mm < 15:
        return "#2563EB"
    elif rain_mm < 20:
        return "#16A34A"
    elif rain_mm < 30:
        return "#22C55E"
    elif rain_mm < 40:
        return "#EAB308"
    elif rain_mm < 50:
        return "#F59E0B"
    elif rain_mm < 70:
        return "#EA580C"
    elif rain_mm < 90:
        return "#EF4444"
    elif rain_mm < 110:
        return "#DC2626"
    elif rain_mm < 130:
        return "#B91C1C"
    elif rain_mm < 150:
        return "#9333EA"
    elif rain_mm < 200:
        return "#C026D3"
    elif rain_mm < 300:
        return "#E11D48"
    else:
        return "#F43F5E"

def get_rain_advisory(max_rain):
    """計算目前降雨警報等級 (Warm Beige & Morandi 色系)"""
    if max_rain >= 500:
        return "🚨 超大豪雨警戒", "#b86b53", "24 小時累積雨量達 500 毫米以上，請特別嚴防淹水與土石流！"
    elif max_rain >= 350:
        return "🚨 大豪雨警戒", "#c47d66", "24 小時累積雨量達 350 毫米以上，山區及低窪地區請高度戒備。"
    elif max_rain >= 200:
        return "⚠️ 豪雨特報等級", "#c49359", "局部地區有豪雨發生，請注意雷擊、強陣風及落石坍方。"
    elif max_rain >= 80:
        return "🌧️ 大雨特報等級", "#5c7c8a", "局部地區有大雨發生機率，外出請攜帶雨具並注意行車安全。"
    elif max_rain > 10:
        return "🌦️ 局部零星降雨", "#6b8e73", "局部山區或沿海有短暫陣雨，多數平地地區天氣大致穩定。"
    elif max_rain > 0:
        return "🌦️ 局部微量飄雨", "#6b8e73", "局部地區偶有微量零星飄雨，天氣整體穩定。"
    else:
        return "🌤️ 全台大致晴朗/少雨", "#6b8e73", "今日全台各地水氣偏少，無顯著雨勢或普遍無降雨。"

ALL_COUNTIES = [
    "基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "臺南市",
    "高雄市", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"
]

def calculate_county_rain_map(stations_list):
    """
    從全台氣象測站觀測資料，計算 22 縣市即時代表當日累積雨量
    """
    county_stations = {}
    for st in stations_list:
        c = st.get("county", "").replace("台北市", "臺北市").replace("台中市", "臺中市").replace("台南市", "臺南市").replace("台東縣", "臺東縣")
        if c:
            county_stations.setdefault(c, []).append(st)

    NEIGHBOR_MAP = {
        "新竹市": "新竹縣",
        "嘉義市": "嘉義縣"
    }

    result = {}
    for c in ALL_COUNTIES:
        target_c = c
        if target_c not in county_stations and target_c in NEIGHBOR_MAP:
            target_c = NEIGHBOR_MAP[target_c]

        st_list = county_stations.get(target_c, [])
        if st_list:
            best_st = max(st_list, key=lambda x: x.get("rain_today", 0.0))
            rain_val = round(float(best_st.get("rain_today", 0.0)), 1)
            past1hr_val = round(float(best_st.get("past1hr", 0.0)), 1)
            past24hr_val = round(float(best_st.get("past24hr", rain_val)), 1)
            color = get_rain_color(rain_val)
            
            if rain_val >= 200:
                status_desc = "局部豪雨"
            elif rain_val >= 80:
                status_desc = "局部大雨"
            elif rain_val >= 10:
                status_desc = "短暫陣雨"
            elif rain_val > 0:
                status_desc = "微量零星"
            else:
                status_desc = "晴朗無雨"

            result[c] = {
                "county": c,
                "rain_today": rain_val,
                "past1hr": past1hr_val,
                "past24hr": past24hr_val,
                "color": color,
                "status": status_desc,
                "primary_station": best_st.get("name", "觀測站"),
                "primary_town": best_st.get("town", ""),
                "station_count": len(st_list),
                "is_interpolated": (target_c != c)
            }
        else:
            result[c] = {
                "county": c,
                "rain_today": 0.0,
                "past1hr": 0.0,
                "past24hr": 0.0,
                "color": "#64748B",
                "status": "晴朗無雨",
                "primary_station": "暫無測站",
                "primary_town": "",
                "station_count": 0,
                "is_interpolated": True
            }
    return result

def fetch_cwa_rainfall_data(api_key=None):
    """
    自中央氣象署抓取最新累積雨量：
    1. 優先從 O-A0003-001 (現在天氣觀測報告-局屬氣象站) 提取局屬站實測雨量 Now.Precipitation
    2. 結合 O-A0002-001 (全台 1300+ 自動雨量站) 補齊全台高密度站點
    3. 解析 O-A0040-003.kmz 提取去背景透明雨量色斑熱力圖供 Leaflet ImageOverlay 套疊
    4. 彙整全台 22 縣市即時代表雨量分布 (Choropleth Map)
    """
    if not api_key:
        api_key = get_cwa_api_key()

    now_dt = datetime.datetime.now()
    default_period = f"{now_dt.strftime('%Y/%m/%d')} 00:00 ~ {now_dt.strftime('%H:00')}"
    latest_obs_time = now_dt.strftime('%Y/%m/%d %H:%M')
    
    official_img_url = "https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0040-002.jpg"
    kmz_url = "https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0040-003.kmz"
    
    overlay_data_url = None
    overlay_bounds = [[21.523313, 119.188024], [25.918078, 123.578233]]

    # 1. 抓取去背景透明雨量色斑圖 (O-A0040-003.kmz)
    try:
        r_kmz = requests.get(kmz_url, timeout=12, verify=False)
        if r_kmz.status_code == 200:
            z = zipfile.ZipFile(io.BytesIO(r_kmz.content))
            for item in z.namelist():
                if item.endswith(".png"):
                    png_bytes = z.read(item)
                    b64 = base64.b64encode(png_bytes).decode("utf-8")
                    overlay_data_url = f"data:image/png;base64,{b64}"
                    break
    except Exception as e:
        print(f"[WARN] 抓取雨量 KMZ 失敗: {e}")

    stations_map = {}
    total_rainy_stations = 0

    # 2. 核心來源：O-A0003-001 (現在天氣觀測報告-局屬氣象站)
    try:
        url_oa3 = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization={api_key}"
        r3 = requests.get(url_oa3, timeout=12, verify=False)
        if r3.status_code == 200:
            d3 = r3.json()
            raw_oa3 = d3.get("records", {}).get("Station", [])
            for s in raw_oa3:
                try:
                    sid = s.get("StationId", "")
                    we = s.get("WeatherElement", {})
                    now_val = float(we.get("Now", {}).get("Precipitation", -99))
                    past1hr = float(we.get("Past1hr", {}).get("Precipitation", 0.0))
                    
                    if now_val < 0:
                        now_val = 0.0

                    coords = s.get("GeoInfo", {}).get("Coordinates", [{}, {}])
                    wgs = coords[1] if len(coords) > 1 and coords[1].get("CoordinateName") == "WGS84" else coords[0]
                    lat = float(wgs.get("StationLatitude", 0))
                    lon = float(wgs.get("StationLongitude", 0))
                    if lat == 0 or lon == 0:
                        continue

                    ot = s.get("ObsTime", {}).get("DateTime", "")
                    if ot and ot > latest_obs_time:
                        latest_obs_time = ot.replace("T", " ")[:16].replace("-", "/")

                    stations_map[sid] = {
                        "name": s.get("StationName", "測站"),
                        "station_id": sid,
                        "county": s.get("GeoInfo", {}).get("CountyName", "未分區"),
                        "town": s.get("GeoInfo", {}).get("TownName", ""),
                        "lat": lat,
                        "lon": lon,
                        "rain_today": now_val,
                        "past1hr": past1hr,
                        "past24hr": now_val,
                        "time": ot.replace("T", " ")[:16].replace("-", "/") if ot else default_period,
                        "source": "O-A0003-001 (局屬站)"
                    }
                except Exception:
                    continue
    except Exception as e:
        print(f"[WARN] 抓取 O-A0003-001 失敗: {e}")

    # 3. 補充來源：O-A0002-001 (全台 1300+ 自動雨量站)
    try:
        url_stations = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001?Authorization={api_key}"
        r_st = requests.get(url_stations, timeout=12, verify=False)
        if r_st.status_code == 200:
            st_data = r_st.json()
            raw_stations = st_data.get("records", {}).get("Station", [])
            for s in raw_stations:
                try:
                    sid = s.get("StationId", "")
                    re = s.get("RainfallElement", {})
                    now_val = float(re.get("Now", {}).get("Precipitation", -99))
                    past1hr = float(re.get("Past1hr", {}).get("Precipitation", 0))
                    past24hr = float(re.get("Past24hr", {}).get("Precipitation", 0))
                    
                    if now_val < 0:
                        continue

                    coords = s.get("GeoInfo", {}).get("Coordinates", [{}, {}])
                    wgs = coords[1] if len(coords) > 1 and coords[1].get("CoordinateName") == "WGS84" else coords[0]
                    lat = float(wgs.get("StationLatitude", 0))
                    lon = float(wgs.get("StationLongitude", 0))
                    if lat == 0 or lon == 0:
                        continue

                    ot = s.get("ObsTime", {}).get("DateTime", "")
                    if ot and ot > latest_obs_time:
                        latest_obs_time = ot.replace("T", " ")[:16].replace("-", "/")

                    stations_map[sid] = {
                        "name": s.get("StationName", "測站"),
                        "station_id": sid,
                        "county": s.get("GeoInfo", {}).get("CountyName", "未分區"),
                        "town": s.get("GeoInfo", {}).get("TownName", ""),
                        "lat": lat,
                        "lon": lon,
                        "rain_today": now_val,
                        "past1hr": past1hr,
                        "past24hr": past24hr,
                        "time": ot.replace("T", " ")[:16].replace("-", "/") if ot else default_period,
                        "source": "O-A0002-001 (自動雨量站)"
                    }
                except Exception:
                    continue
    except Exception as e:
        print(f"[WARN] 抓取 O-A0002-001 失敗: {e}")

    stations_ranked = list(stations_map.values())
    stations_ranked.sort(key=lambda x: x["rain_today"], reverse=True)
    
    total_rainy_stations = sum(1 for s in stations_ranked if s["rain_today"] > 0)
    max_station = stations_ranked[0] if stations_ranked else None
    max_rain = max_station["rain_today"] if max_station else 0.0

    # 4. 計算 22 縣市即時代表雨量分布
    county_rain_map = calculate_county_rain_map(stations_ranked)

    adv_title, adv_color, adv_desc = get_rain_advisory(max_rain)

    return {
        "obs_period": latest_obs_time,
        "obs_time": latest_obs_time,
        "official_img_url": official_img_url,
        "overlay_data_url": overlay_data_url,
        "overlay_bounds": overlay_bounds,
        "max_rain": max_rain,
        "max_station": max_station,
        "total_rainy_stations": total_rainy_stations,
        "total_stations": len(stations_ranked),
        "counties": county_rain_map,
        "stations": stations_ranked,
        "top_stations": stations_ranked[:30],
        "advisory_title": adv_title,
        "advisory_color": adv_color,
        "advisory_desc": adv_desc,
        "is_live": True,
        "dataset_source": "CWA O-A0003-001 & O-A0002-001 & O-A0040-003"
    }

if __name__ == "__main__":
    data = fetch_cwa_rainfall_data()
    print("=" * 60)
    print("Fetched rainfall data successfully!")
    print("Dataset source:", data["dataset_source"])
    print("Total stations:", data["total_stations"])
    print("Max rain:", data["max_rain"], "mm")
    print("Max station:", data["max_station"]["name"] if data["max_station"] else None)
    print("Overlay present:", bool(data["overlay_data_url"]))
    print("Counties mapped:", len(data["counties"]))
    print("=" * 60)

