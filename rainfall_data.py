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
    """計算目前降雨警報等級"""
    if max_rain >= 500:
        return "🚨 超大豪雨警戒", "#EF4444", "24 小時累積雨量達 500 毫米以上，請特別嚴防淹水與土石流！"
    elif max_rain >= 350:
        return "🚨 大豪雨警戒", "#F97316", "24 小時累積雨量達 350 毫米以上，山區及低窪地區請高度戒備。"
    elif max_rain >= 200:
        return "⚠️ 豪雨特報等級", "#FBBF24", "局部地區有豪雨發生，請注意雷擊、強陣風及落石坍方。"
    elif max_rain >= 80:
        return "🌧️ 大雨特報等級", "#38BDF8", "局部地區有大雨發生機率，外出請攜帶雨具並注意行車安全。"
    elif max_rain > 10:
        return "🌦️ 局部零星降雨", "#34D399", "局部山區或沿海有短暫陣雨，多數平地地區天氣大致穩定。"
    else:
        return "🌤️ 全台大致晴朗/少雨", "#10B981", "今日全台各地水氣偏少，僅少數零星微量降雨或無顯著雨勢。"

def fetch_cwa_rainfall_data(api_key=None):
    """
    自中央氣象署抓取最新累積雨量圖與自動雨量站資料
    """
    if not api_key:
        api_key = get_cwa_api_key()

    now_dt = datetime.datetime.now()
    default_period = f"{now_dt.strftime('%Y/%m/%d')} 00:00 ~ {now_dt.strftime('%H:00')}"
    
    # 官方預設日累積雨量圖小間距圖檔與透明 KMZ
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

    # 2. 抓取全台自動雨量站資料 (O-A0002-001)
    stations_ranked = []
    max_rain = 0.0
    max_station = None
    total_rainy_stations = 0

    try:
        url_stations = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001?Authorization={api_key}"
        r_st = requests.get(url_stations, timeout=15, verify=False)
        if r_st.status_code == 200:
            st_data = r_st.json()
            raw_stations = st_data.get("records", {}).get("Station", [])
            
            for s in raw_stations:
                try:
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

                    if now_val > 0:
                        total_rainy_stations += 1

                    s_info = {
                        "name": s.get("StationName", "測站"),
                        "station_id": s.get("StationId", ""),
                        "county": s.get("GeoInfo", {}).get("CountyName", "未分區"),
                        "town": s.get("GeoInfo", {}).get("TownName", ""),
                        "lat": lat,
                        "lon": lon,
                        "rain_today": now_val,
                        "past1hr": past1hr,
                        "past24hr": past24hr,
                        "time": s.get("ObsTime", {}).get("DateTime", "")
                    }
                    stations_ranked.append(s_info)
                except Exception:
                    continue

            stations_ranked.sort(key=lambda x: x["rain_today"], reverse=True)
            if stations_ranked:
                max_station = stations_ranked[0]
                max_rain = max_station["rain_today"]
    except Exception as e:
        print(f"[WARN] 抓取測站雨量失敗: {e}")

    adv_title, adv_color, adv_desc = get_rain_advisory(max_rain)

    return {
        "obs_period": default_period,
        "official_img_url": official_img_url,
        "overlay_data_url": overlay_data_url,
        "overlay_bounds": overlay_bounds,
        "max_rain": max_rain,
        "max_station": max_station,
        "total_rainy_stations": total_rainy_stations,
        "total_stations": len(stations_ranked),
        "top_stations": stations_ranked[:25],
        "advisory_title": adv_title,
        "advisory_color": adv_color,
        "advisory_desc": adv_desc
    }

if __name__ == "__main__":
    data = fetch_cwa_rainfall_data()
    print("Fetched rainfall data successfully!")
    print("Max rain:", data["max_rain"], "mm")
    print("Max station:", data["max_station"])
    print("Top stations count:", len(data["top_stations"]))
    print("Has overlay?:", data["overlay_data_url"] is not None)
