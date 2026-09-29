#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taiwan Weather GIS Dashboard - Flask Serverless Backend
Supports Gate 3 & Gate 5 on Vercel with 5 Full Interactive GIS Layers:
1. 🌡️ 全台即時氣溫與 7 天氣象預報
2. 💧 全台即時濕度與體感舒適度 (THI)
3. ☀️ 全台紫外線即時觀測與預報 (3 大模式)
4. 🌧️ 全台即時雨量監控
5. 🌀 即時颱風動態警報與路徑
"""

import os
import sys
import json
import sqlite3
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, 'static'))
CORS(app)

# 導入專業模組
try:
    import uv_data
    import humidity_data
    import rainfall_data
    import typhoon_data
except ImportError as e:
    print(f"[WARN] Module import notice: {e}")

COORDINATES = {
    "臺北市": [25.0330, 121.5654], "新北市": [25.0112, 121.4617],
    "基隆市": [25.1287, 121.7397], "桃園市": [24.9937, 121.3009],
    "新竹市": [24.8138, 120.9675], "新竹縣": [24.8385, 121.0177],
    "苗栗縣": [24.5601, 120.8234], "臺中市": [24.1477, 120.6736],
    "彰化縣": [24.0820, 120.5385], "南投縣": [23.9037, 120.6698],
    "雲林縣": [23.7092, 120.4313], "嘉義市": [23.4800, 120.4491],
    "嘉義縣": [23.4518, 120.2554], "臺南市": [22.9998, 120.2268],
    "高雄市": [22.6272, 120.3014], "屏東縣": [22.6719, 120.4879],
    "宜蘭縣": [24.7570, 121.7408], "花蓮縣": [23.9871, 121.6015],
    "臺東縣": [22.7583, 121.1444], "澎湖縣": [23.5711, 119.5793],
    "金門縣": [24.4297, 118.3205], "連江縣": [26.1505, 119.9328]
}

def get_db_connection():
    db_path = os.path.join(BASE_DIR, 'data.db')
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def serve_index():
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), path)

@app.route('/api/geojson')
def get_geojson():
    geojson_path = os.path.join(BASE_DIR, 'taiwan_counties.geojson')
    if os.path.exists(geojson_path):
        with open(geojson_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({"type": "FeatureCollection", "features": []})

@app.route('/api/weather')
def get_weather():
    try:
        conn = get_db_connection()
        df = pd.read_sql_query('''
            SELECT location_name, min_temp, max_temp, weather, rain_probability, forecast_start
            FROM weather_forecasts
            WHERE forecast_start = (SELECT MIN(forecast_start) FROM weather_forecasts)
        ''', conn)
        conn.close()
        
        data = []
        for _, row in df.iterrows():
            loc = row['location_name']
            data.append({
                "location": loc,
                "min_temp": row['min_temp'],
                "max_temp": row['max_temp'],
                "weather": row['weather'],
                "pop": row['rain_probability'],
                "lat": COORDINATES.get(loc, [23.5, 121.0])[0],
                "lon": COORDINATES.get(loc, [23.5, 121.0])[1],
                "time": row['forecast_start']
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/forecast/<county>')
def get_county_forecast(county):
    try:
        conn = get_db_connection()
        query = '''
            SELECT forecast_start, min_temp, max_temp, weather, rain_probability
            FROM weather_forecasts
            WHERE location_name = ?
            ORDER BY forecast_start ASC
            LIMIT 14
        '''
        df = pd.read_sql_query(query, conn, params=(county,))
        conn.close()
        return jsonify(df.to_dict(orient='records'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

import re

def parse_radius_km(val_str):
    if not val_str:
        return 0.0
    m = re.search(r'(\d+)', str(val_str))
    if m:
        return float(m.group(1))
    return 0.0

TYPHOON_TARGET_LIST = [
    {"key": "live_cwa", "title": "🔴 即時連線：氣象署最新熱帶系統 (舒力基)", "badge": "即時連線"},
    {"key": "krathon_2024", "title": "🌪️ 歷史展示：中度颱風 山陀兒 (登陸高雄)", "badge": "歷史展示"},
    {"key": "gaemi_2024", "title": "🌪️ 歷史展示：強烈颱風 凱米 (登陸宜蘭)", "badge": "歷史展示"},
    {"key": "congrey_2024", "title": "🌪️ 歷史展示：強烈颱風 康芮 (登陸台東)", "badge": "歷史展示"}
]

def sanitize_typhoon_data(t, current_target="live_cwa"):
    if not t:
        return None
    t_copy = dict(t)
    t_copy['radius_7_km'] = parse_radius_km(t.get('radius_7'))
    t_copy['radius_10_km'] = parse_radius_km(t.get('radius_10'))
    t_copy['current_target'] = current_target
    t_copy['targets'] = TYPHOON_TARGET_LIST
    return t_copy

@app.route('/api/uv')
def get_uv():
    mode = request.args.get('mode', 'realtime')
    hour = request.args.get('hour', None)
    try:
        if mode == 'bundle':
            live_res = uv_data.fetch_cwa_uv_live_observation()
            live_stations = live_res.get("stations", [])
            live_cmap = uv_data.get_county_realtime_uv_map(live_stations)

            max_res = uv_data.fetch_cwa_uv_stations()
            max_stations = max_res.get("stations", [])
            max_cmap = uv_data.get_latest_uv_by_counties()

            return jsonify({
                "realtime": {
                    "mode": "realtime",
                    "mode_title": "即時觀測",
                    "obs_time": live_res.get("obs_time", "") or max_res.get("obs_time", ""),
                    "counties": live_cmap,
                    "stations": live_stations,
                    "max_uv": live_res.get("max_uv", max_res.get("max_uv", 0)),
                    "avg_uv": live_res.get("avg_uv", max_res.get("avg_uv", 0))
                },
                "max": {
                    "mode": "max",
                    "mode_title": "今日最大值預報",
                    "obs_time": max_res.get("obs_time", ""),
                    "counties": max_cmap,
                    "stations": max_stations,
                    "max_uv": max_res.get("max_uv", 0),
                    "avg_uv": max_res.get("avg_uv", 0)
                }
            })

        if mode == 'hourly' and hour is not None:
            h_int = int(hour)
            hour_token = f"{h_int:02d}:00"
            res = uv_data.get_uv_stations_at_hour(hour_token)
            cmap = uv_data.get_county_realtime_uv_map(res.get("stations", []))
            return jsonify({
                "mode": "hourly",
                "mode_title": f"{hour_token} 逐時推估",
                "hour": h_int,
                "obs_time": res.get("obs_time", ""),
                "counties": cmap,
                "stations": res.get("stations", []),
                "max_uv": res.get("max_uv", 0),
                "avg_uv": res.get("avg_uv", 0),
                "source_type": res.get("source_type", "逐時推估")
            })
        elif mode == 'max':
            # Daily max mode
            stations_dict = uv_data.fetch_cwa_uv_stations()
            cmap = uv_data.get_latest_uv_by_counties()
            return jsonify({
                "mode": "max",
                "mode_title": "今日最大值預報",
                "obs_time": stations_dict.get("obs_time", ""),
                "counties": cmap,
                "stations": stations_dict.get("stations", []),
                "max_uv": stations_dict.get("max_uv", 0),
                "avg_uv": stations_dict.get("avg_uv", 0)
            })
        else:
            # Realtime mode
            stations_dict = uv_data.fetch_cwa_uv_stations()
            cmap = uv_data.get_county_realtime_uv_map(stations_dict.get("stations", []))
            return jsonify({
                "mode": "realtime",
                "mode_title": "即時觀測",
                "obs_time": stations_dict.get("obs_time", ""),
                "counties": cmap,
                "stations": stations_dict.get("stations", []),
                "max_uv": stations_dict.get("max_uv", 0),
                "avg_uv": stations_dict.get("avg_uv", 0)
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/humidity')
def get_humidity():
    try:
        hres = humidity_data.fetch_cwa_humidity_live_observation()
        cmap = humidity_data.get_county_realtime_humidity_map(hres.get('stations', []))
        return jsonify({
            "obs_time": hres.get("obs_time", ""),
            "counties": cmap,
            "stations_count": hres.get("stations_count", 0),
            "max_rh": hres.get("max_rh", 0),
            "min_rh": hres.get("min_rh", 0),
            "avg_rh": hres.get("avg_rh", 0)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rainfall')
def get_rainfall():
    try:
        rain_data = rainfall_data.fetch_cwa_rainfall_data()
        return jsonify(rain_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/typhoon')
def get_typhoon():
    target = request.args.get('target', 'live_cwa')
    try:
        typ_data = None
        if target == 'live_cwa':
            try:
                typ_data = typhoon_data.fetch_cwa_live_typhoon()
            except Exception as e:
                print(f"[WARN] Live typhoon fetch error: {e}")
            if not typ_data:
                # Seamless fallback to krathon_2024
                fallback = typhoon_data.TYPHOON_CATALOG.get("krathon_2024", {}).get("data")
                if fallback:
                    typ_data = dict(fallback)
                    typ_data["advisory_body"] = "目前 CWA 即時熱帶系統連線稍有延遲，已切換至歷史中度颱風 山陀兒資料供展示。"
        elif target in typhoon_data.TYPHOON_CATALOG:
            typ_data = typhoon_data.TYPHOON_CATALOG[target].get("data")

        if not typ_data:
            typ_data = typhoon_data.TYPHOON_CATALOG.get("krathon_2024", {}).get("data")

        clean_data = sanitize_typhoon_data(typ_data, current_target=target)
        return jsonify(clean_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
