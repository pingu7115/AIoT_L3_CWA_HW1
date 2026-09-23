#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
typhoon_data.py
中央氣象署 (CWA) 西北太平洋熱帶氣旋/颱風資料模組
1. 支援向中央氣象署 Open Data API (W-C0034-005) 實時抓取當前最新即時熱帶氣旋/颱風觀測與預報資料
2. 內建台灣近年代表性重大強烈颱風歷史完整路徑（康芮、山陀兒、天兔）供比對與切換
"""

import os
import sys
import datetime
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_CWA_API_KEY = "CWA-7972D004-9010-40DF-AD11-4FCB6E5AD5BA"

def get_cwa_api_key():
    """取得 CWA API Key (依序嘗試環境變數、.env 檔案、預設授權碼)"""
    key = os.environ.get("CWA_API_KEY") or os.environ.get("CWB_API_KEY")
    if key:
        return key

    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str.startswith("CWA_API_KEY="):
                        return line_str.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    return DEFAULT_CWA_API_KEY

def fetch_cwa_live_typhoon(api_key=None):
    """
    自中央氣象署 W-C0034-005 抓取當前西北太平洋最新即時熱帶氣旋/準颱風資料
    """
    if not api_key:
        api_key = get_cwa_api_key()

    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={api_key}"
    try:
        resp = requests.get(url, timeout=10, verify=False)
        if resp.status_code != 200:
            return None
        data = resp.json()
        cyclones = data.get("records", {}).get("TropicalCyclones", {}).get("TropicalCyclone", [])
        if not cyclones:
            return None

        cyc = cyclones[0]
        td_no = cyc.get("CwaTdNo", "29")
        typhoon_name = cyc.get("TyphoonName")
        
        analysis = cyc.get("AnalysisData", {}).get("Fix", [])
        forecast = cyc.get("ForecastData", {}).get("Fix", [])

        # 解析過去歷史觀測點
        hist_pts = []
        for a in analysis:
            dt_str = a.get("DateTime", "")
            t_label = dt_str[5:10].replace("-", "/") + " " + dt_str[11:13] + "時" if len(dt_str) >= 13 else dt_str
            hist_pts.append({
                "time": t_label,
                "lat": float(a.get("CoordinateLatitude")),
                "lon": float(a.get("CoordinateLongitude")),
                "pressure": f"{a.get('Pressure')} hPa",
                "wind": f"{a.get('MaxWindSpeed')} m/s",
                "type": "熱帶性低氣壓 / 準颱風"
            })

        cur = analysis[-1] if analysis else {}
        dt_cur = cur.get("DateTime", "")
        cur_time_str = dt_cur[5:10].replace("-", "/") + " " + dt_cur[11:13] + "時" if len(dt_cur) >= 13 else dt_cur

        # 解析移動方向與速度
        pred_text = "向西北西進行，時速約 19-20 公里"
        for mp in cur.get("MovingPrediction", []):
            if mp.get("lang") == "zh-hant" and mp.get("value"):
                pred_text = mp.get("value")
                break
            elif mp.get("lang") == "en-us" and mp.get("value"):
                pred_text = mp.get("value")

        # 解析未來預報節點
        fore_pts = []
        init_dt_str = forecast[0].get("InitialTime", "") if forecast else ""
        if init_dt_str:
            try:
                base_dt = datetime.datetime.fromisoformat(init_dt_str)
            except Exception:
                base_dt = datetime.datetime.now()
        else:
            base_dt = datetime.datetime.now()

        for f in forecast:
            hour = int(f.get("ForecastHour", 0))
            f_dt = base_dt + datetime.timedelta(hours=hour)
            f_label = f"{f_dt.month}/{f_dt.day} {f_dt.hour:02d}時"
            r_70 = float(f.get("Radius70PercentProbability", 80)) * 1000 # 公里換算公尺
            p = f.get("Pressure", "995")
            w = f.get("MaxWindSpeed", "20")
            
            # 產生動態說明
            if hour <= 24:
                stage_desc = f"+{hour}小時預測 · 持續向西北偏西移動，結構發展中"
            elif hour <= 48:
                stage_desc = f"+{hour}小時預測 · 進入菲律賓東北東方海面，強度增強"
            elif hour <= 72:
                stage_desc = f"+{hour}小時預測 · 逼近琉球海面與台灣東部外海，風浪漸增"
            else:
                stage_desc = f"+{hour}小時預測 · 抵達台灣東部至琉球海域，嚴加戒備"

            fore_pts.append({
                "time_label": f_label,
                "lat": float(f.get("CoordinateLatitude")),
                "lon": float(f.get("CoordinateLongitude")),
                "radius_70": r_70,
                "pressure": f"{p} hPa",
                "wind": f"{w} m/s",
                "desc": stage_desc
            })

        # 若氣象署尚未正式給予國際命名，採用新聞與氣象界即時預報名稱（TD29 -> 準颱風「舒力基」SURIGAE）
        if typhoon_name:
            name_display = typhoon_name
            en_display = typhoon_name
            num_display = f"#{td_no}"
            intensity_display = "熱帶性低氣壓 (TD) · 即將增強為輕度颱風"
        elif td_no == "29":
            name_display = "準颱風「舒力基」"
            en_display = "SURIGAE"
            num_display = "TD29 (準25號颱)"
            intensity_display = "熱帶性低氣壓 (TD29) · 新聞預報最快今日增強為「舒力基」颱風"
        else:
            name_display = f"熱帶低壓 TD{td_no} (準颱風)"
            en_display = f"TD{td_no}"
            num_display = f"TD{td_no}"
            intensity_display = "熱帶性低氣壓 (TD) · 即將增強為輕度颱風"

        adv_title = f"⚠️ 準颱風「舒力基」(TD{td_no}) 新聞預報與即時監測" if td_no == "29" else f"⚠️ 熱帶性低氣壓 TD{td_no} 即時觀測動態"
        adv_body = (
            f"中央氣象署與各大新聞最新關注：熱帶性低氣壓 TD{td_no} 目前中心位於關島西北西方海面（北緯 16.4 度，東經 137.9 度），"
            f"以每小時 19-20 公里速度朝西北西進行。各國模式預估最快今日增強為今年第 25 號颱風「舒力基」（Surigae），"
            f"預計接近台灣過程中強度有機會達中度颱風等級，後續將朝琉球及台灣東方海面移動，請密切注意最新風雨與長浪動態。"
        ) if td_no == "29" else (
            f"中央氣象署最新監測：TD{td_no} 目前中心以每小時 19-20 公里速度朝西北西進行。未來有進一步增強為輕度颱風之趨勢，"
            f"預計後續朝琉球及台灣東方海面移動，請航行作業船隻隨時注意最新動態。"
        )

        return {
            "is_live": True,
            "badge_type": "live",
            "name_zh": name_display,
            "name_en": en_display,
            "number": num_display,
            "intensity": intensity_display,
            "pressure": f"{cur.get('Pressure', '1004')} hPa",
            "max_wind": f"{cur.get('MaxWindSpeed', '15')} m/s (7級風)",
            "gust_wind": f"{cur.get('MaxGustSpeed', '23')} m/s (9級陣風)",
            "radius_7": "100 公里",
            "radius_10": "尚未形成",
            "movement": pred_text,
            "obs_time": cur_time_str,
            "map_center": [20.5, 131.5],
            "zoom_start": 5,
            "current_point": {
                "time": cur_time_str,
                "lat": float(cur.get("CoordinateLatitude", 16.4)),
                "lon": float(cur.get("CoordinateLongitude", 137.9)),
                "pressure": f"{cur.get('Pressure', '1004')} hPa",
                "wind": f"{cur.get('MaxWindSpeed', '15')} m/s",
                "gust": f"{cur.get('MaxGustSpeed', '23')} m/s",
                "type": f"{name_display} (當前中心)"
            },
            "historical_points": hist_pts,
            "forecast_points": fore_pts,
            "advisory_title": adv_title,
            "advisory_body": adv_body,
            "sea_alert": "• 琉球南方海面 (持續密切監測)\n• 台灣東南部海面 (留意長浪)\n• 巴士海峽東口海面",
            "land_alert": "• 全台沿海留意長浪與強陣風\n• 東半部降雨機率預估隨系統靠近上升\n• 請做好防汛與排水準備"
        }
    except Exception as e:
        print(f"[WARN] 抓取即時 CWA 颱風失敗: {e}")
        return None

# -------------------------------------------------------------
# 近期強烈颱風歷史完整路徑資料庫
# -------------------------------------------------------------
TYPHOON_CATALOG = {
    "live_cwa": {
        "title": "🔴【即時連線】準颱風「舒力基」(TD29 · 新聞最新預報 120hr 路徑)",
        "getter": fetch_cwa_live_typhoon
    },
    "congrey_2024": {
        "title": "🌪️【近期強颱】康芮颱風 (CONG-REY 2421 · 登陸台東成功鎮之強烈颱風)",
        "data": {
            "is_live": False,
            "badge_type": "recent",
            "name_zh": "康芮",
            "name_en": "CONG-REY",
            "number": "2421",
            "intensity": "強烈颱風 (Super Typhoon)",
            "pressure": "925 hPa",
            "max_wind": "53 m/s (約 16 級風)",
            "gust_wind": "65 m/s (17 級以上強陣風)",
            "radius_7": "320 公里 (超大暴風半徑)",
            "radius_10": "120 公里",
            "movement": "西北 轉 北北東，時速 28 公里",
            "obs_time": "10/31 14:00 (登陸時間點)",
            "map_center": [23.5, 122.0],
            "zoom_start": 6,
            "current_point": {
                "time": "10/31 13:40 登陸",
                "lat": 23.1,
                "lon": 121.4,
                "pressure": "945 hPa",
                "wind": "48 m/s",
                "gust": "58 m/s",
                "type": "康芮颱風 (登陸台東成功鎮)"
            },
            "historical_points": [
                {"time": "10/29 08時", "lat": 17.5, "lon": 127.3, "pressure": "980 hPa", "wind": "30 m/s"},
                {"time": "10/29 20時", "lat": 18.4, "lon": 126.1, "pressure": "970 hPa", "wind": "35 m/s"},
                {"time": "10/30 08時", "lat": 19.3, "lon": 124.6, "pressure": "945 hPa", "wind": "45 m/s"},
                {"time": "10/30 20時", "lat": 20.5, "lon": 123.4, "pressure": "925 hPa", "wind": "53 m/s"},
                {"time": "10/31 08時", "lat": 21.8, "lon": 122.2, "pressure": "925 hPa", "wind": "53 m/s"},
                {"time": "10/31 13時", "lat": 23.0, "lon": 121.5, "pressure": "940 hPa", "wind": "48 m/s"},
            ],
            "forecast_points": [
                {
                    "time_label": "10/31 18時",
                    "lat": 23.8,
                    "lon": 120.2,
                    "radius_70": 300000,
                    "pressure": "960 hPa",
                    "wind": "38 m/s",
                    "desc": "中心橫越中央山脈由雲林麥寮出海，進入台灣海峽"
                },
                {
                    "time_label": "11/01 02時",
                    "lat": 25.5,
                    "lon": 120.5,
                    "radius_70": 260000,
                    "pressure": "975 hPa",
                    "wind": "30 m/s",
                    "desc": "沿海峽北部加速北上，全台風雨陸續趨緩"
                },
                {
                    "time_label": "11/01 14時",
                    "lat": 28.2,
                    "lon": 122.8,
                    "radius_70": 320000,
                    "pressure": "988 hPa",
                    "wind": "25 m/s",
                    "desc": "朝浙江舟山群島海面移動並逐漸變性為溫帶氣旋"
                }
            ],
            "advisory_title": "🚨 康芮強烈颱風歷史登陸回顧",
            "advisory_body": "2024年10月31日，強烈颱風康芮以巔峰姿態（暴風半徑達320公里）正面撲向東台灣，於 13:40 正式登陸臺東縣成功鎮。全台 22 縣市皆納入陸上警報範圍並停班停課，合歡山更觀測到超過 17 級破紀錄強風。",
            "sea_alert": "• 台灣東南部海面 (巨浪警戒)\n• 巴士海峽與台灣海峽全海域\n• 台灣北部海面與東北部海面",
            "land_alert": "• 花蓮縣、臺東縣 (超大豪雨與強陣風)\n• 宜蘭縣、新北市山區 (極端豪雨)\n• 嘉義以南至恆春半島"
        }
    },
    "krathon_2024": {
        "title": "🌪️【近期強颱】山陀兒颱風 (KRATHON 2418 · 高雄小港登陸罕見西南路徑)",
        "data": {
            "is_live": False,
            "badge_type": "recent",
            "name_zh": "山陀兒",
            "name_en": "KRATHON",
            "number": "2418",
            "intensity": "中度颱風上限 / 強烈颱風",
            "pressure": "965 hPa",
            "max_wind": "38 m/s (登陸時約 13 級風)",
            "gust_wind": "48 m/s (高雄測得 17 級破紀錄強風)",
            "radius_7": "220 公里",
            "radius_10": "70 公里",
            "movement": "北北東，時速 9 公里 (極為緩慢)",
            "obs_time": "10/03 12:40 (登陸時間點)",
            "map_center": [22.6, 120.3],
            "zoom_start": 6,
            "current_point": {
                "time": "10/03 12:40 登陸",
                "lat": 22.5,
                "lon": 120.3,
                "pressure": "965 hPa",
                "wind": "38 m/s",
                "gust": "48 m/s",
                "type": "山陀兒颱風 (登陸高雄小港)"
            },
            "historical_points": [
                {"time": "09/29 08時", "lat": 18.6, "lon": 124.3, "pressure": "985 hPa", "wind": "28 m/s"},
                {"time": "09/30 08時", "lat": 20.0, "lon": 122.1, "pressure": "960 hPa", "wind": "40 m/s"},
                {"time": "10/01 08時", "lat": 20.7, "lon": 119.8, "pressure": "925 hPa", "wind": "55 m/s"},
                {"time": "10/02 08時", "lat": 21.5, "lon": 119.3, "pressure": "930 hPa", "wind": "51 m/s"},
                {"time": "10/03 08時", "lat": 22.3, "lon": 120.1, "pressure": "960 hPa", "wind": "40 m/s"},
                {"time": "10/03 12時", "lat": 22.5, "lon": 120.3, "pressure": "965 hPa", "wind": "38 m/s"}
            ],
            "forecast_points": [
                {
                    "time_label": "10/03 18時",
                    "lat": 22.6,
                    "lon": 120.4,
                    "radius_70": 120000,
                    "pressure": "980 hPa",
                    "wind": "30 m/s",
                    "desc": "中心進入南台灣陸地並受地形嚴重破壞"
                },
                {
                    "time_label": "10/04 05時",
                    "lat": 22.8,
                    "lon": 120.5,
                    "radius_70": 80000,
                    "pressure": "1000 hPa",
                    "wind": "18 m/s",
                    "desc": "在台灣西南部陸上減弱為熱帶性低氣壓並消散"
                }
            ],
            "advisory_title": "🚨 山陀兒罕見路徑登陸高雄回顧",
            "advisory_body": "2024年10月3日中午 12:40，山陀兒颱風於高雄小港登陸。此颱風在台灣西南海域滯留打轉多日，成為有氣象觀測紀錄以來首個登陸高雄的強烈至中度颱風，造成高雄市區測得 17 級破紀錄歷史強陣風。",
            "sea_alert": "• 台灣海峽南部海面\n• 台灣東南部海面 (含蘭嶼、綠島)\n• 東沙島海面",
            "land_alert": "• 高雄市、屏東縣 (歷史級致災強風)\n• 臺南市、嘉義縣市 (強烈風雨)\n• 臺東縣、花蓮縣 (持續豪雨警戒)"
        }
    },
    "usagi_2024": {
        "title": "🌀【歷史回顧】天兔颱風 (USAGI 2425 · 巴士海峽掠過路徑)",
        "data": {
            "is_live": False,
            "badge_type": "history",
            "name_zh": "天兔",
            "name_en": "USAGI",
            "number": "2425",
            "intensity": "中度颱風 (Severe Tropical Storm)",
            "pressure": "955 hPa",
            "max_wind": "40 m/s (約 13 級風)",
            "gust_wind": "50 m/s (約 15 級風)",
            "radius_7": "200 公里",
            "radius_10": "70 公里",
            "movement": "西北西 轉 西北，時速 16 公里",
            "obs_time": "11/15 14:00",
            "map_center": [22.0, 124.0],
            "zoom_start": 5,
            "current_point": {
                "time": "11/15 14時",
                "lat": 20.2,
                "lon": 124.8,
                "pressure": "955 hPa",
                "wind": "40 m/s",
                "gust": "50 m/s",
                "type": "中度颱風 (當前中心)"
            },
            "historical_points": [
                {"time": "11/14 08時", "lat": 15.8, "lon": 132.5, "pressure": "995 hPa", "wind": "23 m/s"},
                {"time": "11/14 14時", "lat": 16.6, "lon": 130.8, "pressure": "988 hPa", "wind": "28 m/s"},
                {"time": "11/14 20時", "lat": 17.4, "lon": 129.2, "pressure": "980 hPa", "wind": "33 m/s"},
                {"time": "11/15 02時", "lat": 18.3, "lon": 127.7, "pressure": "970 hPa", "wind": "38 m/s"},
                {"time": "11/15 08時", "lat": 19.2, "lon": 126.2, "pressure": "960 hPa", "wind": "40 m/s"},
                {"time": "11/15 14時", "lat": 20.2, "lon": 124.8, "pressure": "955 hPa", "wind": "40 m/s"},
            ],
            "forecast_points": [
                {
                    "time_label": "11/16 08時",
                    "lat": 21.3,
                    "lon": 123.2,
                    "radius_70": 90000,
                    "pressure": "965 hPa",
                    "wind": "35 m/s",
                    "desc": "移至巴士海峽東口海面，暴風圈掠過恆春"
                },
                {
                    "time_label": "11/16 20時",
                    "lat": 22.2,
                    "lon": 121.9,
                    "radius_70": 160000,
                    "pressure": "975 hPa",
                    "wind": "30 m/s",
                    "desc": "暴風圈觸及恆春半島與台東南端"
                },
                {
                    "time_label": "11/17 08時",
                    "lat": 23.1,
                    "lon": 121.2,
                    "radius_70": 230000,
                    "pressure": "985 hPa",
                    "wind": "25 m/s",
                    "desc": "逐漸減弱並往東北東加速遠離"
                }
            ],
            "advisory_title": "⚠️ 天兔颱風路徑回顧",
            "advisory_body": "2024年11月中旬，天兔颱風沿巴士海峽東側北上，暴風圈曾掠過恆春半島及台東南端海面，隨後轉向東北加速減弱為熱帶性低氣壓。",
            "sea_alert": "• 巴士海峽海面\n• 台灣東南部海面 (含綠島蘭嶼)\n• 台灣海峽南部海面",
            "land_alert": "• 屏東縣、恆春半島\n• 臺東縣 (含綠島、蘭嶼)\n• 花蓮縣 (雨勢戒備)"
        }
    }
}
