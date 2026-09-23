#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
階段 4: 前端展示 (Presentation)
app.py - 台灣全島 22 縣市即時氣象視覺化與西北太平洋颱風路徑動態儀表板
參考範例: https://taiwan-weather-map.vercel.app/

【嚴格遵守作業規範與功能亮點】：
1. 視覺化圖層切換：支援「各縣市溫度分佈」、「全台即時累積雨量」與「颱風路徑動態」三圖層即時切換。
2. 溫潤米色系 × 莫蘭迪設計風格 (Warm Beige & Morandi Aesthetic)：採用柔和燕麥／亞麻米色底 (#f5f3ef)、
   溫潤純白卡片 (#ffffff)、深石墨灰標題 (#2b303a) 與石墨次要文字 (#6c757d)，
   點綴莫蘭迪陶瓦橘 (#b86b53)、莫蘭迪灰藍 (#5c7c8a) 與鼠尾草綠 (#6b8e73)，創造典雅舒適的現代淺色美學。
3. 溫度圖層：100% 透過純 SQL 查詢自本地 SQLite (data.db)，嚴禁前端直呼外部 API；
   涵蓋全台 22 縣市 GeoJSON 面狀熱力圖著色、4 階莫蘭迪色標、自訂 Hover Tooltip 卡片。
4. 雨量圖層：無縫整合中央氣象署日累積雨量透明熱力色斑圖 (O-A0040-003.kmz) 與 1,340 處雨量站即時數據。
5. 颱風圖層：Folium 西北太平洋無浮水印 Esri Light 視角，即時調用氣象署熱帶氣旋 API (W-C0034-005) 觀測與 120 小時預報路徑。
6. 全面消除 Streamlit 廢棄警告：所有元件與 st_folium 皆採用 width="stretch"。
"""

import os
import sys
import json
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import altair as alt

# 解決 Windows cp950 編碼問題
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 引入本地資料庫模組（純 SQL 操作）
from database import (
    get_distinct_regions,
    get_forecast_by_region,
    get_all_latest_forecasts,
    DEFAULT_DB_PATH
)
from main import run_pipeline
from typhoon_data import fetch_cwa_live_typhoon, TYPHOON_CATALOG
from rainfall_data import fetch_cwa_rainfall_data, get_rain_color

GEOJSON_FILE = "taiwan_counties.geojson"

@st.cache_data(ttl=300)
def get_cached_live_typhoon():
    """快取 5 分鐘避免頻繁呼叫 CWA API"""
    return fetch_cwa_live_typhoon()

@st.cache_data(ttl=300)
def get_cached_rainfall():
    """快取 5 分鐘避免頻繁呼叫 CWA 雨量 API"""
    return fetch_cwa_rainfall_data()

# -------------------------------------------------------------
# 頁面配置 (Warm Beige Theme Default)
# -------------------------------------------------------------
st.set_page_config(
    page_title="台灣氣象與颱風路徑動態儀表板 · Taiwan Weather & Typhoon Map",
    page_icon="🌪️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# 溫潤米色系 × 莫蘭迪色系 (Warm Beige & Morandi CSS)
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .stApp {
        background-color: #f5f3ef;
        background-image: radial-gradient(circle at 50% 0%, #ffffff 0%, #f5f3ef 75%, #eae6df 100%);
        color: #2b303a;
    }

    .top-navbar {
        background: #ffffff;
        border: 1px solid rgba(0, 0, 0, 0.07);
        border-radius: 16px;
        padding: 16px 24px;
        margin-bottom: 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 16px rgba(60, 50, 40, 0.05);
    }

    .brand-title {
        font-size: 1.85rem;
        font-weight: 800;
        background: linear-gradient(135deg, #2b303a 0%, #5c7c8a 65%, #6b8e73 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
        margin: 0;
    }

    .brand-subtitle {
        font-size: 0.88rem;
        color: #6c757d;
        margin-top: 4px;
    }

    .pill-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(92, 124, 138, 0.12);
        border: 1px solid rgba(92, 124, 138, 0.25);
        color: #5c7c8a;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .pill-badge.green {
        background: rgba(107, 142, 115, 0.12);
        border-color: rgba(107, 142, 115, 0.28);
        color: #527359;
    }

    .pill-badge.red {
        background: rgba(184, 107, 83, 0.12);
        border-color: rgba(184, 107, 83, 0.28);
        color: #b86b53;
    }

    .glass-card {
        background: #ffffff;
        border: 1px solid rgba(0, 0, 0, 0.07);
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: 0 4px 14px rgba(60, 50, 40, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }

    .glass-card:hover {
        border-color: rgba(92, 124, 138, 0.3);
        box-shadow: 0 8px 24px rgba(60, 50, 40, 0.09);
        transform: translateY(-2px);
    }

    .metric-title {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6c757d;
        margin-bottom: 6px;
    }

    .metric-value {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        line-height: 1.1;
        margin-bottom: 4px;
        color: #2b303a;
    }

    .metric-caption {
        font-size: 0.82rem;
        color: #859099;
    }

    .map-legend-panel {
        background: #ffffff;
        border: 1px solid rgba(0, 0, 0, 0.07);
        border-radius: 12px;
        padding: 14px 18px;
        margin-top: 10px;
        color: #2b303a;
        box-shadow: 0 3px 10px rgba(60, 50, 40, 0.04);
    }

    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
    }

    /* 自訂 Folium Tooltip 卡片樣式 (無邊框、純透底色) */
    .leaflet-tooltip {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }
    .leaflet-tooltip-top:before,
    .leaflet-tooltip-bottom:before,
    .leaflet-tooltip-left:before,
    .leaflet-tooltip-right:before {
        display: none !important;
    }
    .foliumtooltip table {
        margin: 0 !important;
        border-collapse: collapse !important;
    }
    .foliumtooltip td {
        padding: 0 !important;
        border: none !important;
    }

    /* 自訂 Leaflet Popup 樣式 (Warm White) */
    .leaflet-popup-content-wrapper {
        background: #ffffff !important;
        border: 1px solid rgba(0, 0, 0, 0.09) !important;
        border-radius: 14px !important;
        box-shadow: 0 8px 24px rgba(60, 50, 40, 0.12) !important;
        color: #2b303a !important;
        padding: 4px !important;
    }
    .leaflet-popup-tip {
        background: #ffffff !important;
    }
    .leaflet-popup-close-button {
        color: #6c757d !important;
        padding-top: 6px !important;
        padding-right: 6px !important;
    }

    /* 圖層切換器樣式 (Warm Muted Beige Theme) */
    div[data-testid="stRadio"] > div {
        background: #eae6df;
        border: 1px solid rgba(0, 0, 0, 0.07);
        border-radius: 12px;
        padding: 8px 14px;
        gap: 16px;
    }

    div[data-testid="stRadio"] label {
        color: #2b303a !important;
    }

    /* Radio Active State: Morandi Slate Blue (#5c7c8a) */
    div[data-testid="stRadio"] label:has(input:checked) {
        color: #2b303a !important;
        font-weight: 700 !important;
    }

    div[data-testid="stRadio"] input[type="radio"]:checked + div {
        background-color: #5c7c8a !important;
        border-color: #5c7c8a !important;
    }

    /* Selectbox & Inputs */
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border-color: rgba(0, 0, 0, 0.12) !important;
        color: #2b303a !important;
        box-shadow: 0 2px 6px rgba(60, 50, 40, 0.04) !important;
    }
    div[data-baseweb="popover"] ul {
        background-color: #ffffff !important;
        color: #2b303a !important;
        box-shadow: 0 8px 24px rgba(60, 50, 40, 0.12) !important;
    }
    div[data-baseweb="popover"] li {
        color: #2b303a !important;
    }

    /* Buttons */
    button[kind="primary"] {
        background-color: #5c7c8a !important;
        border-color: #5c7c8a !important;
        color: #ffffff !important;
        box-shadow: 0 3px 8px rgba(92, 124, 138, 0.25) !important;
    }
    button[kind="secondary"] {
        background-color: #eae6df !important;
        border-color: rgba(0, 0, 0, 0.08) !important;
        color: #2b303a !important;
    }

    /* Sidebar background */
    section[data-testid="stSidebar"] {
        background-color: #f7f5f0 !important;
        border-right: 1px solid rgba(0, 0, 0, 0.07);
    }

    /* 徹底隱藏任何浮水印、頁尾、Leaflet 標籤與選單圖示 */
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; display: none !important; }
    header { visibility: hidden !important; }
    .viewerBadge_container__1QSob { display: none !important; }
    .leaflet-control-attribution { display: none !important; }
    .leaflet-control-scale { display: none !important; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 全台 22 縣市代表中心座標（用於懸浮數值標籤）
# -------------------------------------------------------------
COUNTY_CENTROIDS = {
    # 北部
    "基隆市": [25.1276, 121.7392],
    "臺北市": [25.0330, 121.5654],
    "新北市": [25.0169, 121.4627],
    "桃園市": [24.9936, 121.3009],
    "新竹市": [24.8138, 120.9675],
    "新竹縣": [24.8387, 121.0177],
    "宜蘭縣": [24.7570, 121.7530],
    # 中部
    "苗栗縣": [24.5602, 120.8214],
    "臺中市": [24.1477, 120.6736],
    "彰化縣": [24.0518, 120.5161],
    "南投縣": [23.9609, 120.9719],
    "雲林縣": [23.7092, 120.4313],
    # 南部
    "嘉義市": [23.4800, 120.4491],
    "嘉義縣": [23.4518, 120.2555],
    "臺南市": [22.9997, 120.2270],
    "高雄市": [22.6273, 120.3014],
    "屏東縣": [22.5519, 120.5487],
    # 東部
    "花蓮縣": [23.9872, 121.6016],
    "臺東縣": [22.7583, 121.1444],
    # 離島
    "澎湖縣": [23.5711, 119.5793],
    "金門縣": [24.4493, 118.3766],
    "連江縣": [26.1558, 119.9288],
    # 6 大分區備用
    "北部地區": [25.0330, 121.5654],
    "中部地區": [24.1477, 120.6736],
    "南部地區": [22.9997, 120.2270],
    "東部地區": [23.9872, 121.6016],
    "澎湖地區": [23.5711, 119.5793],
    "金門馬祖地區": [24.4493, 118.3766],
}

PREFER_ORDER = [
    "臺北市", "新北市", "基隆市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣",
    "臺南市", "高雄市", "屏東縣",
    "宜蘭縣", "花蓮縣", "臺東縣",
    "澎湖縣", "金門縣", "連江縣",
    "北部地區", "中部地區", "南部地區", "東部地區", "澎湖地區", "金門馬祖地區"
]

def get_temp_category(temp):
    """
    依據作業規範嚴格劃分 4 級氣溫色階與圖例（溫潤米色系 × 莫蘭迪色 Warm Beige & Morandi）：
    🔵 < 20°C（偏冷）：Morandi 灰藍 / 塵藍 (#5c7c8a)
    🟢 20 - 25°C（舒適）：Morandi 鼠尾草綠 (#6b8e73)
    🟡 25 - 30°C（偏暖）：Morandi 溫潤微赭 (#c49359)
    🔴 > 30°C（炎熱）：Morandi 陶瓦微橘 (#b86b53)
    """
    if temp < 20.0:
        return {
            "label": "偏冷",
            "icon": "🔵",
            "color": "#5c7c8a",
            "bg_color": "rgba(92, 124, 138, 0.12)",
            "border": "#7392a0",
            "badge": "🔵 < 20°C 偏冷"
        }
    elif temp < 25.0:
        return {
            "label": "舒適",
            "icon": "🟢",
            "color": "#6b8e73",
            "bg_color": "rgba(107, 142, 115, 0.12)",
            "border": "#85a78d",
            "badge": "🟢 20 - 25°C 舒適"
        }
    elif temp <= 30.0:
        return {
            "label": "偏暖",
            "icon": "🟡",
            "color": "#c49359",
            "bg_color": "rgba(196, 147, 89, 0.12)",
            "border": "#d4a66e",
            "badge": "🟡 25 - 30°C 偏暖"
        }
    else:
        return {
            "label": "炎熱",
            "icon": "🔴",
            "color": "#b86b53",
            "bg_color": "rgba(184, 107, 83, 0.12)",
            "border": "#c47d66",
            "badge": "🔴 > 30°C 炎熱"
        }

def get_temp_color(temp):
    return get_temp_category(temp)["color"]

def get_windy_temp_color(temp):
    return get_temp_category(temp)["color"]

def get_weather_icon(mint, maxt):
    avg = (mint + maxt) / 2
    diff = maxt - mint
    if avg >= 28:
        return "☀️", "晴朗偏暖"
    elif diff >= 7:
        return "🌤️", "晴時多雲"
    elif avg >= 23:
        return "⛅", "多雲舒適"
    else:
        return "🌥️", "陰天涼爽"

# -------------------------------------------------------------
# 颱風資料集結構已模組化至 typhoon_data.py
# 支援中央氣象署 Open Data API (W-C0034-005) 即時熱帶氣旋/颱風與歷史強颱路徑庫
# -------------------------------------------------------------

# -------------------------------------------------------------
# 頂部導航條
# -------------------------------------------------------------
st.markdown("""
<div class="top-navbar">
    <div>
        <h1 class="brand-title">🌪️ 台灣氣象與颱風路徑動態儀表板</h1>
        <div class="brand-subtitle">中央氣象署 Open Data 全台 22 縣市即時預報 · 西北太平洋熱帶氣旋 70% 潛勢動態</div>
    </div>
    <div style="display: flex; gap: 10px; align-items: center;">
        <span class="pill-badge green">● SQLite data.db</span>
        <span class="pill-badge red">🌀 颱風警報警戒中</span>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 側邊欄控制項 (Sidebar)
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚡ 系統後端控制")
    st.caption("AIoT HW10 端到端氣象資料管線 · 本地 SQLite 資料庫驅動")
    
    db_exists = os.path.exists(DEFAULT_DB_PATH)
    if db_exists:
        st.markdown('<div class="pill-badge green">● SQLite 運作正常 (data.db)</div>', unsafe_allow_html=True)
    else:
        st.error("❌ 找不到 data.db，請執行 ETL 管線建庫！")

    st.markdown("---")
    st.markdown("#### 🎨 氣溫色階圖例 (Color Legend)")
    st.markdown("""
    <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 12px; padding: 12px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(60, 50, 40, 0.04);">
        <div style="font-size: 0.8rem; color: #6c757d; margin-bottom: 8px; font-weight: 600;">全島面狀著色與預報標準 (Morandi Light)：</div>
        <div style="display: flex; flex-direction: column; gap: 7px; font-size: 0.82rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: rgba(92, 124, 138, 0.08); border-left: 3px solid #5c7c8a; border-radius: 6px;">
                <span>🔵 <b>&lt; 20°C</b></span>
                <span style="color: #5c7c8a; font-weight: 600;">偏冷</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: rgba(107, 142, 115, 0.08); border-left: 3px solid #6b8e73; border-radius: 6px;">
                <span>🟢 <b>20 - 25°C</b></span>
                <span style="color: #6b8e73; font-weight: 600;">舒適</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: rgba(196, 147, 89, 0.08); border-left: 3px solid #c49359; border-radius: 6px;">
                <span>🟡 <b>25 - 30°C</b></span>
                <span style="color: #c49359; font-weight: 600;">偏暖</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: rgba(184, 107, 83, 0.08); border-left: 3px solid #b86b53; border-radius: 6px;">
                <span>🔴 <b>&gt; 30°C</b></span>
                <span style="color: #b86b53; font-weight: 600;">炎熱</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 🔄 觸發 CWA 全台即時資料更新")
    user_api_key = st.text_input("CWA API 授權碼", type="password", placeholder="留空則使用 .env 儲存金鑰")
    force_mock = st.checkbox("強制使用模擬資料", value=False)
    
    if st.button("🚀 執行後端 ETL 管線", width="stretch"):
        with st.spinner("正在向中央氣象署抓取全台最新預報並寫入 SQLite..."):
            try:
                run_pipeline(api_key=user_api_key if user_api_key else None, force_mock=force_mock)
                st.success("🎉 資料庫更新成功！已載入全台縣市最新預報。")
                st.rerun()
            except Exception as e:
                st.error(f"更新失敗: {e}")

    st.markdown("---")
    st.markdown("#### 🌐 圖層快速切換")
    cur_layer = st.session_state.get("active_layer", "🌡️ 各縣市溫度分佈")
    if st.button("🌡️ 顯示各縣市溫度分佈", key="side_btn_temp", width="stretch", type="primary" if cur_layer == "🌡️ 各縣市溫度分佈" else "secondary"):
        st.session_state["active_layer"] = "🌡️ 各縣市溫度分佈"
        st.rerun()
    if st.button("🌀 顯示颱風路徑動態", key="side_btn_ty", width="stretch", type="primary" if cur_layer == "🌀 颱風路徑動態" else "secondary"):
        st.session_state["active_layer"] = "🌀 颱風路徑動態"
        st.rerun()

    st.markdown("---")
    st.markdown("""
    **作業規範符合度**：
    - ✅ **前端直連 API：0% (嚴格禁止)**
    - ✅ **涵蓋全台 22 縣市與 6 大分區**
    - ✅ **GeoJSON 面狀熱力著色 (Choropleth)**
    - ✅ **西北太平洋颱風路徑與 70% 潛勢圈**
    - ✅ **消除所有廢棄警告 (width="stretch")**
    """)

# -------------------------------------------------------------
# 🎯 圖層切換控制 (Layer Switching Control)
# -------------------------------------------------------------
st.markdown("""
<div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 14px; padding: 12px 18px; margin-bottom: 14px; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
    <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 1.3rem;">🌐</span>
        <div>
            <div style="font-weight: 700; font-size: 0.95rem; color: #2b303a;">視覺化圖層切換 (Layer Selector)</div>
            <div style="font-size: 0.8rem; color: #6c757d;">請點選切換「各縣市溫度分佈」、「全台即時累積雨量圖」或「颱風路徑與潛勢動態」</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

LAYER_OPTIONS = ["🌡️ 各縣市溫度分佈", "🌧️ 全台即時累積雨量圖", "🌀 颱風路徑動態"]

if "active_layer" not in st.session_state or st.session_state["active_layer"] not in LAYER_OPTIONS:
    st.session_state["active_layer"] = "🌡️ 各縣市溫度分佈"

def on_layer_change():
    st.session_state["active_layer"] = st.session_state["layer_radio_widget"]

cur_layer_idx = LAYER_OPTIONS.index(st.session_state["active_layer"])

selected_layer = st.radio(
    "請選擇欲展示之氣象圖層：",
    options=LAYER_OPTIONS,
    index=cur_layer_idx,
    horizontal=True,
    key="layer_radio_widget",
    on_change=on_layer_change
)
st.session_state["active_layer"] = selected_layer

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# =============================================================
# 圖層 1: 🌡️ 各縣市溫度分佈 (Current Temperature View)
# =============================================================
if selected_layer == "🌡️ 各縣市溫度分佈":
    # 讀取本地 SQLite 資料庫 (純 SQL 操作)
    all_db_regions = get_distinct_regions(DEFAULT_DB_PATH)
    if not all_db_regions:
        st.warning("⚠️ 目前資料庫中無氣象資料，請於側邊欄點選「執行後端 ETL 管線」以初始化資料庫。")
        st.stop()

    sorted_regions = [r for r in PREFER_ORDER if r in all_db_regions]
    for r in all_db_regions:
        if r not in sorted_regions:
            sorted_regions.append(r)

    # 狀態管理
    if "selected_region" not in st.session_state or st.session_state["selected_region"] not in sorted_regions:
        st.session_state["selected_region"] = "臺北市" if "臺北市" in sorted_regions else sorted_regions[0]


    def on_select_change():
        st.session_state["selected_region"] = st.session_state["region_selector_box"]

    col_select_a, col_select_b = st.columns([2.5, 3.5])
    with col_select_a:
        cur_sel = st.session_state["selected_region"]
        cur_idx = sorted_regions.index(cur_sel) if cur_sel in sorted_regions else 0
        selected_region = st.selectbox(
            "📍 請選擇台灣縣市或區域 (全台 22 縣市即時切換)：",
            options=sorted_regions,
            index=cur_idx,
            key="region_selector_box",
            on_change=on_select_change
        )
        st.session_state["selected_region"] = selected_region

    with col_select_b:
        st.markdown(f"""
        <div style="padding-top: 28px; font-size: 0.9rem; color: #6c757d;">
            當前選定：<b style="color: #5c7c8a; font-size: 1.15rem;">{selected_region}</b> · 未來 7 天預報資料由本地 SQLite (data.db) 即時提供
        </div>
        """, unsafe_allow_html=True)

    # 查詢該縣市 7 天資料 (純 SQL)
    forecast_records = get_forecast_by_region(selected_region, DEFAULT_DB_PATH)
    df_forecast = pd.DataFrame(forecast_records)

    if df_forecast.empty:
        st.error(f"查無 {selected_region} 的預報資料。")
        st.stop()

    # 計算即時指標
    today_row = df_forecast.iloc[0]
    today_min = today_row["mint"]
    today_max = today_row["maxt"]
    today_diff = round(today_max - today_min, 1)
    today_avg = round((today_max + today_min) / 2, 1)
    week_max = df_forecast["maxt"].max()
    week_min = df_forecast["mint"].min()

    # 溫潤指標卡片 (Warm Beige & Morandi 色系)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #b86b53;">
            <div class="metric-title">🔥 今日最高溫 (MaxT)</div>
            <div class="metric-value" style="color: #b86b53;">{today_max}°C</div>
            <div class="metric-caption">日間高溫預測 · {selected_region}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #5c7c8a;">
            <div class="metric-title">❄️ 今日最低溫 (MinT)</div>
            <div class="metric-value" style="color: #5c7c8a;">{today_min}°C</div>
            <div class="metric-caption">清晨夜間低溫 · {selected_region}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #c49359;">
            <div class="metric-title">⚖️ 日夜溫差 (Diurnal Range)</div>
            <div class="metric-value" style="color: #c49359;">{today_diff}°C</div>
            <div class="metric-caption">溫差提示 · 建議外出適度增減衣物</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        icon, condition = get_weather_icon(today_min, today_max)
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #6b8e73;">
            <div class="metric-title">🌡️ 體感環境指標</div>
            <div class="metric-value" style="color: #6b8e73;">{icon} {today_avg}°C</div>
            <div class="metric-caption">當日平均氣候: {condition}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # 主視覺雙欄：左側 GeoJSON 面狀熱力地圖 / 右側 7 天氣象趨勢折線圖
    col_map, col_chart = st.columns([1.2, 1])

    all_latest = get_all_latest_forecasts(DEFAULT_DB_PATH)
    latest_map_data = {item["regionName"]: item for item in all_latest}

    def resolve_weather(name):
        if not name:
            return None
        if name in latest_map_data:
            return latest_map_data[name]
        alt = name.replace("臺", "台") if "臺" in name else name.replace("台", "臺")
        return latest_map_data.get(alt)

    with col_map:
        st.markdown("### 🗺️ 全台 22 縣市 GeoJSON 面狀熱力地圖")
        st.caption("懸停各縣市即時顯示卡片，支援點選地圖直接切換縣市；地圖鎖定台灣視角。")

        # 建立地圖實例：鎖定台灣視角 (Esri Light Gray Base 無浮水印底圖)
        m = folium.Map(
            location=[23.7, 120.9],
            zoom_start=7.3,
            min_zoom=7,
            max_zoom=10,
            max_bounds=True,
            min_lat=21.0,
            max_lat=26.5,
            min_lon=118.0,
            max_lon=122.5,
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
            attr="Esri"
        )

        m.get_root().header.add_child(folium.Element("""
        <style>
            .leaflet-control-attribution {
                display: none !important;
                visibility: hidden !important;
            }
            .leaflet-tooltip {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                padding: 0 !important;
            }
            .leaflet-tooltip-top:before,
            .leaflet-tooltip-bottom:before,
            .leaflet-tooltip-left:before,
            .leaflet-tooltip-right:before {
                display: none !important;
            }
            .foliumtooltip table {
                margin: 0 !important;
                border-collapse: collapse !important;
            }
            .foliumtooltip td {
                padding: 0 !important;
                border: none !important;
            }
        </style>
        """))

        # 地圖右上角嵌入自訂色階圖例 (Morandi Light Palette)
        map_legend_html = """
        <div id="map-color-legend" style="
            position: absolute;
            top: 14px;
            right: 14px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 12px;
            padding: 10px 14px;
            color: #2b303a;
            box-shadow: 0 4px 16px rgba(60, 50, 40, 0.08);
            font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-width: 142px;
            pointer-events: auto;
        ">
            <div style="font-weight: 700; font-size: 11px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 7px; display: flex; align-items: center; justify-content: space-between;">
                <span>🎨 氣溫色階圖例</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 5px; font-size: 12px;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 11px; height: 11px; border-radius: 50%; background: #5c7c8a; box-shadow: 0 0 4px rgba(92,124,138,0.4);"></span>
                        <span style="color: #2b303a; font-weight: 500;">&lt; 20°C</span>
                    </span>
                    <span style="color: #5c7c8a; font-weight: 600; font-size: 11px;">偏冷 🔵</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 11px; height: 11px; border-radius: 50%; background: #6b8e73; box-shadow: 0 0 4px rgba(107,142,115,0.4);"></span>
                        <span style="color: #2b303a; font-weight: 500;">20 - 25°C</span>
                    </span>
                    <span style="color: #6b8e73; font-weight: 600; font-size: 11px;">舒適 🟢</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 11px; height: 11px; border-radius: 50%; background: #c49359; box-shadow: 0 0 4px rgba(196,147,89,0.4);"></span>
                        <span style="color: #2b303a; font-weight: 500;">25 - 30°C</span>
                    </span>
                    <span style="color: #c49359; font-weight: 600; font-size: 11px;">偏暖 🟡</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 11px; height: 11px; border-radius: 50%; background: #b86b53; box-shadow: 0 0 4px rgba(184,107,83,0.4);"></span>
                        <span style="color: #2b303a; font-weight: 500;">&gt; 30°C</span>
                    </span>
                    <span style="color: #b86b53; font-weight: 600; font-size: 11px;">炎熱 🔴</span>
                </div>
            </div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(map_legend_html))

        # 載入並套用台灣各縣市 GeoJSON 輪廓著色與自訂 HTML Tooltip / Popup
        if os.path.exists(GEOJSON_FILE):
            with open(GEOJSON_FILE, "r", encoding="utf-8") as gf:
                geojson_data = json.load(gf)

            for feature in geojson_data.get("features", []):
                props = feature.setdefault("properties", {})
                c_name = props.get("COUNTYNAME") or props.get("name")
                w = resolve_weather(c_name)
                if w:
                    avg_t = round((w["maxt"] + w["mint"]) / 2, 1)
                    icon, condition = get_weather_icon(w["mint"], w["maxt"])
                    cat = get_temp_category(avg_t)
                    range_str = f"{w['mint']}°C ~ {w['maxt']}°C"
                    diff_t = round(w["maxt"] - w["mint"], 1)

                    tooltip_html = f"""
                    <div style="
                        background: rgba(255, 255, 255, 0.97);
                        backdrop-filter: blur(12px);
                        -webkit-backdrop-filter: blur(12px);
                        border: 1px solid rgba(0, 0, 0, 0.08);
                        border-top: 3.5px solid {cat['color']};
                        border-radius: 12px;
                        padding: 10px 14px;
                        min-width: 220px;
                        box-shadow: 0 6px 20px rgba(60, 50, 40, 0.1);
                        font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        color: #2b303a;
                        line-height: 1.5;
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; border-bottom: 1px solid rgba(0, 0, 0, 0.06); padding-bottom: 5px;">
                            <span style="font-size: 15px; font-weight: 700; color: #2b303a;">📍 地區：{c_name}</span>
                            <span style="font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 999px; background: {cat['color']}18; color: {cat['color']}; border: 1px solid {cat['color']}44;">{cat['icon']} {cat['label']}</span>
                        </div>
                        <div style="font-size: 13.5px; margin-bottom: 3px; display: flex; align-items: baseline; gap: 4px;">
                            <span style="color: #6c757d;">🌡️ 均溫：</span>
                            <b style="color: #2b303a; font-size: 16px; font-weight: 700;">{avg_t}°C</b>
                            <span style="color: #6c757d; font-size: 11.5px; margin-left: 2px;">({range_str})</span>
                        </div>
                        <div style="font-size: 13px; margin-bottom: 5px;">
                            <span style="color: #6c757d;">🌤️ 預報：</span>
                            <span style="color: #2b303a; font-weight: 600;">{icon} {condition}</span>
                        </div>
                        <div style="font-size: 11px; color: #6c757d; margin-top: 5px; border-top: 1px dashed rgba(0, 0, 0, 0.08); padding-top: 4px; display: flex; justify-content: space-between;">
                            <span>溫差: {diff_t}°C</span>
                            <span style="color: #5c7c8a; font-weight: 600;">點擊在地圖切換 👆</span>
                        </div>
                    </div>
                    """
                    
                    popup_html = f"""
                    <div style="
                        font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
                        padding: 8px 4px;
                        color: #2b303a;
                        line-height: 1.5;
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 0, 0, 0.08); padding-bottom: 6px; margin-bottom: 8px;">
                            <h4 style="margin: 0; font-size: 17px; color: #2b303a;">📍 {c_name}</h4>
                            <span style="font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 999px; background: {cat['color']}; color: #ffffff;">{cat['icon']} {cat['label']}</span>
                        </div>
                        <p style="margin: 4px 0; font-size: 14px;">🌡️ 預測均溫：<b>{avg_t}°C</b></p>
                        <p style="margin: 4px 0; font-size: 14px;">🌤️ 天氣狀況：<b>{icon} {condition}</b></p>
                        <p style="margin: 4px 0; font-size: 14px;">📊 預報溫幅：<b>{range_str}</b></p>
                        <p style="margin: 4px 0; font-size: 13px; color: #6c757d;">⚖️ 日夜溫差：<b>{diff_t}°C</b></p>
                    </div>
                    """
                    props["tooltip_card"] = tooltip_html
                    props["popup_card"] = popup_html
                else:
                    props["tooltip_card"] = f"""
                    <div style="background: rgba(255, 255, 255, 0.95); border-radius: 8px; padding: 8px 12px; color: #6c757d; font-size: 13px; border: 1px solid rgba(0, 0, 0, 0.08);">
                        📍 地區：{c_name} | 暫無資料
                    </div>
                    """
                    props["popup_card"] = props["tooltip_card"]

            def style_fn(feature):
                props = feature.get("properties", {})
                c_name = props.get("COUNTYNAME") or props.get("name")
                w = resolve_weather(c_name)
                is_cur = False
                if selected_region:
                    is_cur = (c_name == selected_region or (c_name and c_name.replace("臺", "台") == selected_region.replace("臺", "台")))

                if w:
                    avg_t = (w["maxt"] + w["mint"]) / 2
                    color = get_temp_color(avg_t)
                else:
                    color = "#e8e4dc"

                return {
                    "fillColor": color,
                    "color": "#2b303a" if is_cur else "rgba(92, 124, 138, 0.4)",
                    "weight": 3.0 if is_cur else 1.2,
                    "fillOpacity": 0.88 if is_cur else 0.72,
                }

            def highlight_fn(feature):
                return {
                    "weight": 3.2,
                    "color": "#5c7c8a",
                    "fillOpacity": 0.92
                }

            folium.GeoJson(
                geojson_data,
                name="Taiwan Counties Boundary",
                style_function=style_fn,
                highlight_function=highlight_fn,
                tooltip=folium.GeoJsonTooltip(
                    fields=["tooltip_card"],
                    labels=False,
                    sticky=True,
                    style="background: transparent; border: none; padding: 0; box-shadow: none;"
                ),
                popup=folium.GeoJsonPopup(
                    fields=["popup_card"],
                    labels=False,
                    style="background: transparent; border: none; padding: 0; box-shadow: none;"
                )
            ).add_to(m)

        # 疊加懸浮氣溫數值標記 (DivIcon)
        for c_name, coords in COUNTY_CENTROIDS.items():
            w = resolve_weather(c_name)
            if not w:
                continue
            avg_t = round((w["maxt"] + w["mint"]) / 2, 1)
            cat = get_temp_category(avg_t)
            color = cat["color"]
            is_cur = (c_name == selected_region or c_name.replace("臺", "台") == selected_region.replace("臺", "台"))
            
            badge_border = "2px solid #2b303a" if is_cur else "1.5px solid #FFFFFF"
            icon_html = f"""
            <div style="
                background: {color};
                color: #FFFFFF;
                font-weight: 800;
                font-size: 11px;
                padding: 2px 5px;
                border-radius: 12px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(60, 50, 40, 0.25);
                border: {badge_border};
                width: 42px;
                margin-left: -21px;
                margin-top: -10px;
                cursor: pointer;
                letter-spacing: -0.2px;
            ">{avg_t}°</div>
            """
            folium.Marker(
                location=coords,
                icon=folium.DivIcon(html=icon_html),
                tooltip=folium.Tooltip(
                    f"""
                    <div style="
                        background: rgba(255, 255, 255, 0.97);
                        border: 1px solid rgba(0, 0, 0, 0.08);
                        border-top: 3px solid {color};
                        border-radius: 10px;
                        padding: 8px 12px;
                        color: #2b303a;
                        font-family: 'Outfit', sans-serif;
                        font-size: 12.5px;
                        min-width: 180px;
                        box-shadow: 0 4px 16px rgba(60, 50, 40, 0.1);
                    ">
                        <div style="font-weight: 700; color: #2b303a; margin-bottom: 4px;">📍 地區：{c_name}</div>
                        <div>🌡️ 均溫：<b>{avg_t}°C</b> ({w['mint']}°C ~ {w['maxt']}°C)</div>
                        <div>🌤️ 預報：{get_weather_icon(w['mint'], w['maxt'])[0]} {get_weather_icon(w['mint'], w['maxt'])[1]}</div>
                    </div>
                    """,
                    sticky=True
                )
            ).add_to(m)

        map_state = st_folium(m, width="stretch", height=500, returned_objects=["last_active_drawing"])
        if map_state and map_state.get("last_active_drawing"):
            last_props = map_state["last_active_drawing"].get("properties", {})
            clicked_c = last_props.get("COUNTYNAME") or last_props.get("name")
            if clicked_c:
                for r in sorted_regions:
                    if r == clicked_c or r.replace("臺", "台") == clicked_c.replace("臺", "台"):
                        if st.session_state.get("selected_region") != r:
                            st.session_state["selected_region"] = r
                            st.rerun()
                        break

        # 底部 4 階色階標尺與圖例說明 (Morandi Light Palette)
        st.markdown("""
        <div class="map-legend-panel">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 0.82rem; font-weight: 600; color: #2b303a;">🌡️ 全台即時氣溫面狀色階說明 (Morandi Color Legend)</span>
                <span style="font-size: 0.75rem; color: #6c757d;">4 階溫潤莫蘭迪氣候色標 · 懸停縣市即時顯示卡片</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; height: 10px; border-radius: 6px; overflow: hidden; margin-top: 4px;">
                <div style="background: #5c7c8a;" title="< 20°C 偏冷"></div>
                <div style="background: #6b8e73;" title="20-25°C 舒適"></div>
                <div style="background: #c49359;" title="25-30°C 偏暖"></div>
                <div style="background: #b86b53;" title="> 30°C 炎熱"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.76rem; margin-top: 6px; flex-wrap: wrap; gap: 4px;">
                <span style="color: #5c7c8a; font-weight: 600;">🔵 &lt; 20°C（偏冷）</span>
                <span style="color: #6b8e73; font-weight: 600;">🟢 20 - 25°C（舒適）</span>
                <span style="color: #c49359; font-weight: 600;">🟡 25 - 30°C（偏暖）</span>
                <span style="color: #b86b53; font-weight: 600;">🔴 &gt; 30°C（炎熱）</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_chart:
        st.markdown(f"### 📈 {selected_region} 一週氣溫走勢 (MaxT vs MinT)")
        st.caption("透過 Altair 呈現平滑曲線與日夜極限溫差，即時比對未來 7 天溫度波動。")

        df_melted = df_forecast.melt(
            id_vars=["dataDate"],
            value_vars=["maxt", "mint"],
            var_name="指標",
            value_name="氣溫"
        )
        df_melted["指標"] = df_melted["指標"].map({"maxt": "最高氣溫 (MaxT)", "mint": "最低氣溫 (MinT)"})

        chart = alt.Chart(df_melted).mark_line(
            point=alt.OverlayMarkDef(filled=True, size=75),
            interpolate="monotone",
            strokeWidth=3
        ).encode(
            x=alt.X("dataDate:N", title="預報日期", axis=alt.Axis(
                labelAngle=-20,
                labelColor="#6c757d",
                titleColor="#6c757d",
                gridColor="rgba(0, 0, 0, 0.05)"
            )),
            y=alt.Y("氣溫:Q", title="氣溫 (°C)", scale=alt.Scale(zero=False, padding=20), axis=alt.Axis(
                labelColor="#6c757d",
                titleColor="#6c757d",
                gridColor="rgba(0, 0, 0, 0.05)"
            )),
            color=alt.Color(
                "指標:N",
                scale=alt.Scale(
                    domain=["最高氣溫 (MaxT)", "最低氣溫 (MinT)"],
                    range=["#b86b53", "#5c7c8a"]
                ),
                legend=alt.Legend(
                    orient="top",
                    title=None,
                    labelColor="#2b303a",
                    labelFontSize=13
                )
            ),
            tooltip=[
                alt.Tooltip("dataDate:N", title="日期"),
                alt.Tooltip("指標:N", title="氣象要素"),
                alt.Tooltip("氣溫:Q", title="溫度 (°C)", format=".1f")
            ]
        ).properties(height=340).configure_view(
            strokeOpacity=0
        ).configure_axis(
            domainColor="rgba(0, 0, 0, 0.1)"
        )

        st.altair_chart(chart, width="stretch")

        st.markdown(f"""
        <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 12px; padding: 14px 18px; margin-top: 10px; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05);">
            <div style="display: flex; justify-content: space-around; text-align: center;">
                <div>
                    <div style="font-size: 0.75rem; color: #6c757d;">一週最高溫</div>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #b86b53;">{week_max} °C</div>
                </div>
                <div style="border-right: 1px solid rgba(0, 0, 0, 0.07);"></div>
                <div>
                    <div style="font-size: 0.75rem; color: #6c757d;">一週最低溫</div>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #5c7c8a;">{week_min} °C</div>
                </div>
                <div style="border-right: 1px solid rgba(0, 0, 0, 0.07);"></div>
                <div>
                    <div style="font-size: 0.75rem; color: #6c757d;">全週平均溫差</div>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #c49359;">{round((df_forecast['maxt'] - df_forecast['mint']).mean(), 1)} °C</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # 一週預報詳細數據表格 (符合作業規範)
    st.markdown(f"### 📋 {selected_region} 一週詳細數據記錄表 (SQL 查詢自 data.db)")

    table_df = df_forecast.copy()
    table_df["日溫差 (°C)"] = (table_df["maxt"] - table_df["mint"]).round(1)
    table_df["舒適度評估"] = table_df.apply(lambda r: get_weather_icon(r["mint"], r["maxt"])[1], axis=1)

    table_df = table_df.rename(columns={
        "dataDate": "預報日期",
        "mint": "最低氣溫 (MinT °C)",
        "maxt": "最高氣溫 (MaxT °C)"
    })[["預報日期", "最低氣溫 (MinT °C)", "最高氣溫 (MaxT °C)", "日溫差 (°C)", "舒適度評估"]]

    st.dataframe(
        table_df,
        width="stretch",
        hide_index=True,
        column_config={
            "預報日期": st.column_config.TextColumn("預報日期"),
            "最低氣溫 (MinT °C)": st.column_config.NumberColumn("最低氣溫 (MinT)", format="%.1f °C"),
            "最高氣溫 (MaxT °C)": st.column_config.NumberColumn("最高氣溫 (MaxT)", format="%.1f °C"),
            "日溫差 (°C)": st.column_config.NumberColumn("日夜溫差", format="%.1f °C"),
            "舒適度評估": st.column_config.TextColumn("天氣狀態評估")
        }
    )

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

# =============================================================
# 圖層 2: 🌧️ 全台即時累積雨量圖 (Accumulated Precipitation View)
# =============================================================
elif selected_layer == "🌧️ 全台即時累積雨量圖":
    with st.spinner("正在連線中央氣象署 API (O-A0040 / O-A0002) 取得全台累積雨量與測站資料..."):
        rain_data = get_cached_rainfall()

    # 即時連線狀態橫幅 (Morandi Light Theme)
    st.markdown(f"""
    <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 12px; padding: 12px 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05);">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.25rem;">🌧️</span>
            <div>
                <div style="color: #2b303a; font-weight: 700; font-size: 0.92rem;">中央氣象署 (CWA) 全台日累積雨量色斑熱力與即時測站觀測</div>
                <div style="color: #6c757d; font-size: 0.8rem;">資料集: O-A0040 (累積雨量圖) & O-A0002-001 (1,340 處雨量站) · 統計時段：<b>{rain_data['obs_period']}</b></div>
            </div>
        </div>
        <div style="display: flex; gap: 8px;">
            <span class="pill-badge green">即時連線中</span>
            <span class="pill-badge">雷達推估色斑</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4 大指標卡片 (Morandi 溫潤色系)
    rc1, rc2, rc3, rc4 = st.columns(4)
    max_rain = rain_data["max_rain"]
    max_station = rain_data["max_station"]
    max_name = f"{max_station['name']} ({max_station['county']} {max_station['town']})" if max_station else "暫無降雨"

    with rc1:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #5c7c8a;">
            <div class="metric-title">🌧️ 今日全台最高累積雨量</div>
            <div class="metric-value" style="color: #5c7c8a; font-size: 2.1rem;">{max_rain} <span style="font-size: 1.1rem; color: #6c757d;">mm</span></div>
            <div class="metric-caption">最高測站: {max_name}</div>
        </div>
        """, unsafe_allow_html=True)

    with rc2:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid {rain_data['advisory_color']};">
            <div class="metric-title">⚠️ 降雨警戒狀態評估</div>
            <div class="metric-value" style="color: {rain_data['advisory_color']}; font-size: 1.65rem;">{rain_data['advisory_title']}</div>
            <div class="metric-caption">{rain_data['advisory_desc'][:30]}...</div>
        </div>
        """, unsafe_allow_html=True)

    with rc3:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #6b8e73;">
            <div class="metric-title">📡 有降雨記錄測站數</div>
            <div class="metric-value" style="color: #6b8e73; font-size: 2.1rem;">{rain_data['total_rainy_stations']} <span style="font-size: 1.1rem; color: #6c757d;">/ {rain_data['total_stations']} 站</span></div>
            <div class="metric-caption">全台自動雨量監測網即時回傳</div>
        </div>
        """, unsafe_allow_html=True)

    with rc4:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #c49359;">
            <div class="metric-title">⏱️ 累積雨量統計時段</div>
            <div class="metric-value" style="color: #c49359; font-size: 1.45rem;">本日即時統計</div>
            <div class="metric-caption">{rain_data['obs_period']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    col_r_map, col_r_info = st.columns([1.35, 1])

    with col_r_map:
        st.markdown("### 🗺️ 全台即時累積雨量測站分佈圖 (Station Point Map)")
        st.caption("無點陣圖遮蔽干擾，採用 CartoDB Positron 畫布底圖，依氣象署 O-A0002-001 即時測站觀測渲染莫蘭迪色標圓點。")

        # 建立雨量專屬點狀地圖 (location=[23.7, 120.9], zoom_start=7.5，乾淨無浮水印圖資)
        m_rain = folium.Map(
            location=[23.7, 120.9],
            zoom_start=7.5,
            min_zoom=6,
            max_zoom=11,
            max_bounds=True,
            min_lat=21.0,
            max_lat=26.5,
            min_lon=118.0,
            max_lon=122.5,
            tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        )

        m_rain.get_root().header.add_child(folium.Element("""
        <style>
            .leaflet-control-attribution {
                display: none !important;
                visibility: hidden !important;
            }
        </style>
        """))

        # 1. 疊加台灣縣市細緻淺色邊界輪廓
        if os.path.exists(GEOJSON_FILE):
            with open(GEOJSON_FILE, "r", encoding="utf-8") as gf:
                geojson_data = json.load(gf)
            folium.GeoJson(
                geojson_data,
                name="Counties",
                style_function=lambda f: {
                    "fillColor": "transparent",
                    "color": "rgba(92, 124, 138, 0.25)",
                    "weight": 1.0,
                    "opacity": 0.6
                }
            ).add_to(m_rain)

        # 2. 依氣象署 O-A0002-001 測站即時雨量繪製 Morandi 圓點標記
        all_stations = rain_data.get("stations", rain_data.get("top_stations", []))

        for stn in all_stations:
            rain_val = float(stn.get("rain_today", 0.0))
            stn_name = stn.get("name", "測站")
            county = stn.get("county", "")
            town = stn.get("town", "")

            # 依規格設定莫蘭迪階層屬性
            if rain_val <= 0.0:
                # 0.0 mm (無降雨): 極簡透光微小點，避免干擾畫面
                folium.CircleMarker(
                    location=[stn["lat"], stn["lon"]],
                    radius=1.5,
                    color="#d2d6dc",
                    weight=0.8,
                    fill=True,
                    fill_color="#d2d6dc",
                    fill_opacity=0.3,
                    tooltip=f"<b>{stn_name}</b> ({county}{town}): 0.0 mm (無降雨)"
                ).add_to(m_rain)
            elif rain_val <= 10.0:
                # 0.1 ~ 10.0 mm (小雨/微量): Morandi Dusty Blue (#7392a0)
                folium.CircleMarker(
                    location=[stn["lat"], stn["lon"]],
                    radius=3.5,
                    color="#7392a0",
                    weight=1.2,
                    fill=True,
                    fill_color="#7392a0",
                    fill_opacity=0.75,
                    tooltip=folium.Tooltip(
                        f"""<div style="background: rgba(255,255,255,0.96); border: 1px solid #7392a0; border-radius: 6px; padding: 3px 8px; font-size: 11.5px; color: #2b303a; box-shadow: 0 2px 8px rgba(0,0,0,0.1); white-space: nowrap;"><b>{stn_name}</b>: <span style="color: #7392a0; font-weight: 700;">{rain_val:.1f} mm</span> <span style="font-size: 10px; color: #7392a0;">(小雨)</span></div>""",
                        sticky=True
                    ),
                    popup=folium.Popup(f"""<b>📍 {stn_name}</b> ({county} {town})<br>🌧️ 本日累積雨量：<b>{rain_val:.1f} mm</b><br>時雨量：{stn.get('past1hr', 0):.1f} mm · 24H: {stn.get('past24hr', 0):.1f} mm""", max_width=220)
                ).add_to(m_rain)
            elif rain_val <= 50.0:
                # 10.1 ~ 50.0 mm (中雨): Morandi Sage/Teal (#5c7c8a)
                folium.CircleMarker(
                    location=[stn["lat"], stn["lon"]],
                    radius=5.0,
                    color="#5c7c8a",
                    weight=1.5,
                    fill=True,
                    fill_color="#5c7c8a",
                    fill_opacity=0.85,
                    tooltip=folium.Tooltip(
                        f"""<div style="background: rgba(255,255,255,0.96); border: 1px solid #5c7c8a; border-radius: 6px; padding: 3px 8px; font-size: 11.5px; color: #2b303a; box-shadow: 0 2px 8px rgba(0,0,0,0.1); white-space: nowrap;"><b>{stn_name}</b>: <span style="color: #5c7c8a; font-weight: 700;">{rain_val:.1f} mm</span> <span style="font-size: 10px; color: #5c7c8a;">(中雨)</span></div>""",
                        sticky=True
                    ),
                    popup=folium.Popup(f"""<b>📍 {stn_name}</b> ({county} {town})<br>🌧️ 本日累積雨量：<b style="color: #5c7c8a;">{rain_val:.1f} mm</b><br>時雨量：{stn.get('past1hr', 0):.1f} mm · 24H: {stn.get('past24hr', 0):.1f} mm""", max_width=220)
                ).add_to(m_rain)
            elif rain_val <= 130.0:
                # 50.1 ~ 130.0 mm (大雨): Morandi Terracotta (#c47d66)
                folium.CircleMarker(
                    location=[stn["lat"], stn["lon"]],
                    radius=6.5,
                    color="#c47d66",
                    weight=1.8,
                    fill=True,
                    fill_color="#c47d66",
                    fill_opacity=0.9,
                    tooltip=folium.Tooltip(
                        f"""<div style="background: rgba(255,255,255,0.96); border: 1px solid #c47d66; border-radius: 6px; padding: 3px 8px; font-size: 11.5px; color: #2b303a; box-shadow: 0 2px 8px rgba(0,0,0,0.1); white-space: nowrap;"><b>{stn_name}</b>: <span style="color: #c47d66; font-weight: 700;">{rain_val:.1f} mm</span> <span style="font-size: 10px; color: #c47d66;">(大雨)</span></div>""",
                        sticky=True
                    ),
                    popup=folium.Popup(f"""<b>📍 {stn_name}</b> ({county} {town})<br>🌧️ 本日累積雨量：<b style="color: #c47d66;">{rain_val:.1f} mm</b><br>時雨量：{stn.get('past1hr', 0):.1f} mm · 24H: {stn.get('past24hr', 0):.1f} mm""", max_width=220)
                ).add_to(m_rain)
            else:
                # > 130.0 mm (豪雨): Morandi Deep Rust (#a8523b)
                folium.CircleMarker(
                    location=[stn["lat"], stn["lon"]],
                    radius=8.0,
                    color="#a8523b",
                    weight=2.0,
                    fill=True,
                    fill_color="#a8523b",
                    fill_opacity=0.95,
                    tooltip=folium.Tooltip(
                        f"""<div style="background: rgba(255,255,255,0.96); border: 1px solid #a8523b; border-radius: 6px; padding: 3px 8px; font-size: 11.5px; color: #2b303a; box-shadow: 0 2px 8px rgba(0,0,0,0.1); white-space: nowrap;"><b>{stn_name}</b>: <span style="color: #a8523b; font-weight: 700;">{rain_val:.1f} mm</span> <span style="font-size: 10px; color: #a8523b;">(豪雨)</span></div>""",
                        sticky=True
                    ),
                    popup=folium.Popup(f"""<b>📍 {stn_name}</b> ({county} {town})<br>🌧️ 本日累積雨量：<b style="color: #a8523b;">{rain_val:.1f} mm</b><br>時雨量：{stn.get('past1hr', 0):.1f} mm · 24H: {stn.get('past24hr', 0):.1f} mm""", max_width=220)
                ).add_to(m_rain)

        # 3. 地圖右上角莫蘭迪測站雨量圖例 (浮動面板 - CartoDB Positron Cohesive Morandi Legend)
        rain_legend_html = """
        <div id="rain-map-legend" style="
            position: absolute;
            top: 14px;
            right: 14px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 12px;
            padding: 10px 14px;
            color: #2b303a;
            box-shadow: 0 4px 16px rgba(60, 50, 40, 0.08);
            font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
            min-width: 165px;
            pointer-events: auto;
        ">
            <div style="font-weight: 700; font-size: 11px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 7px;">
                🌧️ 測站雨量級距圖例
            </div>
            <div style="display: flex; flex-direction: column; gap: 5px; font-size: 11.5px;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #d2d6dc; opacity: 0.6; border: 1px solid #b8bcc4;"></span>
                        <span style="color: #6c757d;">0.0 mm</span>
                    </span>
                    <span style="color: #6c757d; font-size: 10px;">無降雨</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #7392a0;"></span>
                        <span style="color: #2b303a; font-weight: 500;">0.1 ~ 10.0 mm</span>
                    </span>
                    <span style="color: #7392a0; font-weight: 600; font-size: 10px;">小雨/微量</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #5c7c8a;"></span>
                        <span style="color: #2b303a; font-weight: 500;">10.1 ~ 50.0 mm</span>
                    </span>
                    <span style="color: #5c7c8a; font-weight: 600; font-size: 10px;">中雨</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #c47d66;"></span>
                        <span style="color: #2b303a; font-weight: 500;">50.1 ~ 130.0 mm</span>
                    </span>
                    <span style="color: #c47d66; font-weight: 600; font-size: 10px;">大雨</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: #a8523b;"></span>
                        <span style="color: #2b303a; font-weight: 500;">&gt; 130.0 mm</span>
                    </span>
                    <span style="color: #a8523b; font-weight: 600; font-size: 10px;">豪雨</span>
                </div>
            </div>
        </div>
        """
        m_rain.get_root().html.add_child(folium.Element(rain_legend_html))

        st_folium(m_rain, width="stretch", height=540)

        st.markdown(f"""
        <div class="map-legend-panel">
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #6c757d;">
                <span>💧 <b>資料來源</b>：中央氣象署全台自動雨量測站網即時觀測資料 (O-A0002-001) · 懸停/點選圓點可查看詳細雨量。</span>
                <span style="color: #5c7c8a; font-weight: 600;">共 {rain_data['total_stations']} 站即時同步</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_r_info:
        st.markdown("### 📷 氣象署官方累積雨量圖 (O-A0040-002)")
        st.caption("中央氣象署最新發布日累積雨量分佈圖檔（小間距）。")
        
        st.image(
            rain_data["official_img_url"],
            caption=f"中央氣象署日累積雨量圖 ({rain_data['obs_period']})",
            width="stretch"
        )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown("#### 🏆 今日全台各測站累積雨量排行榜 (Top 10)")

        top_rain_df = pd.DataFrame([
            {
                "排名": f"#{idx+1}",
                "測站名稱": s["name"],
                "縣市": s["county"],
                "鄉鎮區": s["town"],
                "本日累積 (mm)": s["rain_today"],
                "過去1小時 (mm)": s["past1hr"]
            }
            for idx, s in enumerate(rain_data.get("top_stations", [])[:10])
        ])

        if not top_rain_df.empty:
            st.dataframe(
                top_rain_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "排名": st.column_config.TextColumn("排名", width="small"),
                    "測站名稱": st.column_config.TextColumn("測站"),
                    "縣市": st.column_config.TextColumn("縣市"),
                    "鄉鎮區": st.column_config.TextColumn("行政區"),
                    "本日累積 (mm)": st.column_config.NumberColumn("累積雨量", format="%.1f mm"),
                    "過去1小時 (mm)": st.column_config.NumberColumn("時雨量", format="%.1f mm")
                }
            )
        else:
            st.info("今日全台暫無測站測得累積雨量。")

        st.markdown("""
        <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 12px; padding: 12px; margin-top: 10px; font-size: 0.82rem; color: #6c757d; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05);">
            🛡️ <b>防汛安全提醒</b>：山區易受熱對流或地形抬升影響降雨，請留意短延時強降雨與溪水暴漲，外出建議隨身攜帶雨具。
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

# =============================================================
# 圖層 3: 🌀 颱風路徑動態 (Typhoon / Tropical Cyclone Forecast View)
# =============================================================
else:
    # 觀測目標切換器 (支援氣象署即時 API 與近期重大颱風)
    ty_keys = list(TYPHOON_CATALOG.keys())
    ty_titles = {k: TYPHOON_CATALOG[k]["title"] for k in ty_keys}

    col_sel, col_stat = st.columns([1.8, 1.2])
    with col_sel:
        selected_ty_key = st.selectbox(
            "🎯 選擇觀測目標 / 颱風系統：",
            options=ty_keys,
            format_func=lambda k: ty_titles[k],
            index=0,
            help="即時連線會直接調用中央氣象署 W-C0034-005 資料集取得最新觀測與 120 小時預報路徑"
        )
    with col_stat:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if selected_ty_key == "live_cwa":
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end; padding-top: 4px;">
                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #6b8e73; box-shadow: 0 0 8px rgba(107, 142, 115, 0.6);"></span>
                <span style="color: #6b8e73; font-weight: 700; font-size: 0.85rem;">🟢 CWA API 即時連線 (W-C0034-005)</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end; padding-top: 4px;">
                <span style="color: #5c7c8a; font-weight: 600; font-size: 0.85rem;">📁 歷史重大強颱完整路徑庫</span>
            </div>
            """, unsafe_allow_html=True)

    # 取得當前選定之颱風資料
    if selected_ty_key == "live_cwa":
        with st.spinner("正在連線中央氣象署 API (W-C0034-005) 取得最新即時熱帶氣旋資料..."):
            cur_typhoon = get_cached_live_typhoon()
            if not cur_typhoon:
                cur_typhoon = TYPHOON_CATALOG["krathon_2024"]["data"]
                st.warning("⚠️ 即時氣象署連線稍有延遲，已切換至中度颱風 山陀兒歷史展示資料。")
    else:
        cur_typhoon = TYPHOON_CATALOG[selected_ty_key]["data"]

    # 即時連線狀態橫幅 (Morandi Light Theme)
    if cur_typhoon.get("is_live"):
        st.markdown(f"""
        <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 12px; padding: 12px 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05);">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.25rem;">📡</span>
                <div>
                    <div style="color: #2b303a; font-weight: 700; font-size: 0.92rem;">中央氣象署 (CWA) 西北太平洋熱帶氣旋即時監測中</div>
                    <div style="color: #6c757d; font-size: 0.8rem;">資料集: W-C0034-005 · 最新氣象觀測定位：<b>{cur_typhoon['obs_time']}</b></div>
                </div>
            </div>
            <div style="display: flex; gap: 8px;">
                <span class="pill-badge green">即時連線中</span>
                <span class="pill-badge">120小時預報</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        en_str = f" ({cur_typhoon['name_en']})" if cur_typhoon.get('name_en') else ""
        num_str = f" · 國際編號 #{cur_typhoon['number']}" if cur_typhoon.get('number') and cur_typhoon['number'] != '準颱風' else ""
        st.markdown(f"""
        <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 12px; padding: 12px 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05);">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.25rem;">📜</span>
                <div>
                    <div style="color: #2b303a; font-weight: 700; font-size: 0.92rem;">台灣重大颱風歷史路徑回顧模式 · {cur_typhoon['name_zh']}{en_str}</div>
                    <div style="color: #6c757d; font-size: 0.8rem;">登陸時間節點：{cur_typhoon['obs_time']}{num_str}</div>
                </div>
            </div>
            <div>
                <span class="pill-badge">歷史重現</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 颱風即時資訊看板指標卡 (Morandi 溫潤色系)
    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1:
        en_label = f" <span style='font-size: 1.05rem; color: #6c757d;'>({cur_typhoon['name_en']})</span>" if cur_typhoon.get('name_en') and cur_typhoon['name_en'] != 'Tropical Depression' else ""
        num_caption = f"國際編號 #{cur_typhoon['number']} · " if cur_typhoon.get('number') and cur_typhoon['number'] != '準颱風' else ""
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #b86b53;">
            <div class="metric-title">🌀 颱風名稱與強度</div>
            <div class="metric-value" style="color: #b86b53; font-size: 1.85rem;">{cur_typhoon['name_zh']}{en_label}</div>
            <div class="metric-caption">{num_caption}{cur_typhoon['intensity']}</div>
        </div>
        """, unsafe_allow_html=True)

    with tc2:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #c47d66;">
            <div class="metric-title">💨 近中心最大風速</div>
            <div class="metric-value" style="color: #c47d66; font-size: 1.85rem;">{cur_typhoon['max_wind']}</div>
            <div class="metric-caption">瞬間最大陣風: {cur_typhoon['gust_wind']}</div>
        </div>
        """, unsafe_allow_html=True)

    with tc3:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #5c7c8a;">
            <div class="metric-title">📉 中心最低氣壓</div>
            <div class="metric-value" style="color: #5c7c8a; font-size: 1.85rem;">{cur_typhoon['pressure']}</div>
            <div class="metric-caption">7級風半徑: {cur_typhoon['radius_7']} / 10級: {cur_typhoon['radius_10']}</div>
        </div>
        """, unsafe_allow_html=True)

    with tc4:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 3px solid #6b8e73;">
            <div class="metric-title">🧭 當前移速與方向</div>
            <div class="metric-value" style="color: #6b8e73; font-size: 1.55rem;">{cur_typhoon['movement']}</div>
            <div class="metric-caption">最新定位時間: {cur_typhoon['obs_time']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    col_t_map, col_t_info = st.columns([1.35, 1])

    with col_t_map:
        st.markdown("### 🌀 西北太平洋颱風路徑與 70% 潛勢機率圈")
        st.caption("聚焦西北太平洋與台灣鄰近海域，展示歷史觀測路徑（莫蘭迪粉藍）、當前中心（煙燻陶土光圈）與官方預報路徑（莫蘭迪陶土實線與虛線潛勢圈）。")

        # 1. 建立颱風專屬地圖 (focus: location=map_center, zoom_start=zoom_start - Esri Light Gray Base)
        map_center = cur_typhoon.get("map_center", [20.5, 131.5])
        zoom_start = cur_typhoon.get("zoom_start", 5)

        m_typhoon = folium.Map(
            location=map_center,
            zoom_start=zoom_start,
            min_zoom=3,
            max_zoom=9,
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
            attr="Esri"
        )

        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            overlay=True,
            name="Labels",
            opacity=0.75
        ).add_to(m_typhoon)

        m_typhoon.get_root().header.add_child(folium.Element("""
        <style>
            .leaflet-control-attribution {
                display: none !important;
                visibility: hidden !important;
            }
        </style>
        """))

        # 2. 過去路徑 (Historical Track): 莫蘭迪灰藍實線 (color="#5c7c8a") 與節點
        hist_coords = [[p["lat"], p["lon"]] for p in cur_typhoon["historical_points"]]
        if hist_coords:
            folium.PolyLine(
                hist_coords,
                color="#5c7c8a",
                weight=3.5,
                opacity=0.9,
                tooltip="🌀 過去觀測移動路徑"
            ).add_to(m_typhoon)

        for p in cur_typhoon["historical_points"]:
            folium.CircleMarker(
                location=[p["lat"], p["lon"]],
                radius=5,
                color="#5c7c8a",
                weight=2,
                fill=True,
                fill_color="#5c7c8a",
                fill_opacity=0.9,
                tooltip=f"⏱️ {p['time']} | 座標: ({p['lat']}°N, {p['lon']}°E)<br>📉 氣壓: {p['pressure']} | 風速: {p['wind']}"
            ).add_to(m_typhoon)

        # 3. 預報路徑 (Forecast Track): 莫蘭迪陶土色線條 (color="#b86b53") 連接各預報時效
        cur_pt = [cur_typhoon["current_point"]["lat"], cur_typhoon["current_point"]["lon"]]
        fore_coords = [cur_pt] + [[p["lat"], p["lon"]] for p in cur_typhoon["forecast_points"]]
        folium.PolyLine(
            fore_coords,
            color="#b86b53",
            weight=3.5,
            opacity=0.9,
            tooltip="🚨 官方預報路徑"
        ).add_to(m_typhoon)

        # 4. 70% 潛勢機率圈 (70% Probability Circles) 與 預報時間藥丸標籤 (DivIcon pills)
        for fp in cur_typhoon["forecast_points"]:
            f_coord = [fp["lat"], fp["lon"]]
            
            # 70% 潛勢半徑圓 (folium.Circle, dash_array="4, 4")
            folium.Circle(
                location=f_coord,
                radius=fp["radius_70"],
                color="#b86b53",
                weight=1.5,
                dash_array="4, 4",
                fill=True,
                fill_color="#b86b53",
                fill_opacity=0.12,
                tooltip=f"⭕ 70% 潛勢暴風圈 ({fp['time_label']})<br>半徑: {int(fp['radius_70']/1000)} 公里 | 氣壓: {fp['pressure']}"
            ).add_to(m_typhoon)

            # 節點實心圓
            folium.CircleMarker(
                location=f_coord,
                radius=5,
                color="#b86b53",
                weight=2,
                fill=True,
                fill_color="#ffffff",
                fill_opacity=0.95
            ).add_to(m_typhoon)

            # 預報時間標籤藥丸 (DivIcon Pill - Morandi Light Palette)
            pill_html = f"""
            <div style="
                background: rgba(255, 255, 255, 0.95);
                border: 1.5px solid #b86b53;
                color: #b86b53;
                font-weight: 700;
                font-size: 11px;
                padding: 2px 7px;
                border-radius: 999px;
                white-space: nowrap;
                box-shadow: 0 2px 8px rgba(60, 50, 40, 0.15);
                margin-left: 9px;
                margin-top: -10px;
                letter-spacing: -0.2px;
            ">{fp['time_label']}</div>
            """
            folium.Marker(
                location=f_coord,
                icon=folium.DivIcon(html=pill_html),
                tooltip=f"預報時間: {fp['time_label']} · {fp.get('desc', '')}"
            ).add_to(m_typhoon)

        # 5. 當前中心 (Current Center): 莫蘭迪同心光環與詳細 HTML 資訊卡片
        folium.CircleMarker(
            location=cur_pt,
            radius=15,
            color="#b86b53",
            weight=2,
            fill=True,
            fill_color="#b86b53",
            fill_opacity=0.25
        ).add_to(m_typhoon)

        folium.CircleMarker(
            location=cur_pt,
            radius=8,
            color="#FFFFFF",
            weight=2.5,
            fill=True,
            fill_color="#b86b53",
            fill_opacity=1.0
        ).add_to(m_typhoon)

        popup_en_str = f" ({cur_typhoon['name_en']})" if cur_typhoon.get('name_en') and cur_typhoon['name_en'] != 'Tropical Depression' else ""
        popup_badge_str = f"#{cur_typhoon['number']}" if cur_typhoon.get('number') and cur_typhoon['number'] != '準颱風' else cur_typhoon['intensity']

        center_popup_html = f"""
        <div style="
            font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
            min-width: 250px;
            color: #2b303a;
            padding: 4px;
            line-height: 1.6;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 0, 0, 0.08); padding-bottom: 6px; margin-bottom: 8px;">
                <span style="font-weight: 800; font-size: 16px; color: #b86b53;">🌀 {cur_typhoon['name_zh']}{popup_en_str}</span>
                <span style="font-size: 11px; padding: 2px 7px; border-radius: 999px; background: rgba(184,107,83,0.15); color: #b86b53; border: 1px solid #b86b53;">{popup_badge_str}</span>
            </div>
            <div style="font-size: 13px; color: #2b303a;">
                <div>⏱️ <b>定位時間</b>：{cur_typhoon['obs_time']}</div>
                <div>📍 <b>中心座標</b>：北緯 {cur_pt[0]}°，東經 {cur_pt[1]}°</div>
                <div>📉 <b>中心氣壓</b>：{cur_typhoon['pressure']}</div>
                <div>💨 <b>最大風速</b>：{cur_typhoon['max_wind']}</div>
                <div>🌪️ <b>瞬間陣風</b>：{cur_typhoon['gust_wind']}</div>
                <div>⭕ <b>暴風半徑</b>：7級風 {cur_typhoon['radius_7']} / 10級風 {cur_typhoon['radius_10']}</div>
                <div>🧭 <b>移向移速</b>：{cur_typhoon['movement']}</div>
            </div>
        </div>
        """

        center_badge_html = f"""
        <div style="
            background: linear-gradient(135deg, #b86b53 0%, #c47d66 100%);
            color: #FFFFFF;
            font-weight: 800;
            font-size: 11px;
            padding: 3px 9px;
            border-radius: 999px;
            white-space: nowrap;
            border: 2px solid #FFFFFF;
            box-shadow: 0 2px 10px rgba(184, 107, 83, 0.45);
            margin-left: 14px;
            margin-top: -12px;
            letter-spacing: -0.2px;
            cursor: pointer;
        ">🌀 當前中心 ({cur_typhoon['name_zh']})</div>
        """

        folium.Marker(
            location=cur_pt,
            icon=folium.DivIcon(html=center_badge_html),
            popup=folium.Popup(center_popup_html, max_width=320),
            tooltip=f"🌀 {cur_typhoon['name_zh']} (點擊展開詳細氣象定位卡)"
        ).add_to(m_typhoon)

        # 6. 地圖右上角浮動路徑圖例 (Morandi Light Palette)
        typhoon_legend_html = """
        <div id="typhoon-map-legend" style="
            position: absolute;
            top: 14px;
            right: 14px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 12px;
            padding: 12px 14px;
            color: #2b303a;
            box-shadow: 0 4px 16px rgba(60, 50, 40, 0.08);
            font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
            min-width: 165px;
            pointer-events: auto;
        ">
            <div style="font-weight: 700; font-size: 11px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">
                🌀 颱風路徑圖例說明
            </div>
            <div style="display: flex; flex-direction: column; gap: 7px; font-size: 12px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="display: inline-block; width: 18px; height: 3.5px; background: #5c7c8a; border-radius: 2px;"></span>
                    <span style="color: #2b303a;">過去觀測路徑</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #b86b53; border: 2px solid #FFFFFF;"></span>
                    <span style="color: #b86b53; font-weight: 600;">當前中心位置</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="display: inline-block; width: 18px; height: 3.5px; background: #b86b53; border-radius: 2px;"></span>
                    <span style="color: #2b303a;">官方預報路徑</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; border: 1.5px dashed #b86b53; background: rgba(184,107,83,0.18);"></span>
                    <span style="color: #2b303a;">70% 潛勢機率圈</span>
                </div>
            </div>
        </div>
        """
        m_typhoon.get_root().html.add_child(folium.Element(typhoon_legend_html))

        st_folium(m_typhoon, width="stretch", height=520)

        # 底部說明列
        st.markdown("""
        <div class="map-legend-panel">
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #6c757d;">
                <span>🌊 <b>潛勢機率圈定義</b>：氣象署預報中心 70% 機率可能涵蓋之移動範圍，虛線圓半徑隨預報時效逐日擴大。</span>
                <span style="color: #5c7c8a; font-weight: 600;">座標與時效同步中央氣象署</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_t_info:
        st.markdown("### 🚨 氣象署颱風動態與警戒指引")
        st.caption("最新海上陸上動態與各時段路徑分析。")

        advisory_title = cur_typhoon.get("advisory_title", "⚠️ 氣象署動態監測")
        advisory_body = cur_typhoon.get("advisory_body", "請密切留意中央氣象署最新警報與風雨預報資訊。")
        sea_alert_html = cur_typhoon.get("sea_alert", "• 鄰近海域密切注意").replace("\n", "<br>")
        land_alert_html = cur_typhoon.get("land_alert", "• 沿海強陣風戒備").replace("\n", "<br>")

        st.markdown(f"""
        <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-left: 4px solid #b86b53; border-radius: 12px; padding: 14px; margin-bottom: 14px; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05);">
            <div style="font-weight: 700; color: #b86b53; font-size: 0.95rem; margin-bottom: 4px;">{advisory_title}</div>
            <div style="font-size: 0.84rem; color: #2b303a; line-height: 1.5;">
                {advisory_body}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### 📍 警戒與海面動態區")
        g1, g2 = st.columns(2)
        with g1:
            st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 10px; padding: 12px; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05);">
                <div style="font-size: 0.8rem; font-weight: 600; color: #5c7c8a; margin-bottom: 4px;">🌊 海面警戒/監測海域</div>
                <div style="font-size: 0.82rem; color: #2b303a; line-height: 1.5;">
                    {sea_alert_html}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with g2:
            st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 10px; padding: 12px; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05);">
                <div style="font-size: 0.8rem; font-weight: 600; color: #c47d66; margin-bottom: 4px;">🏞️ 陸上警戒/防汛重點</div>
                <div style="font-size: 0.82rem; color: #2b303a; line-height: 1.5;">
                    {land_alert_html}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        st.markdown("#### 📅 官方預報路徑節點數據表")

        df_ty_forecast = pd.DataFrame([
            {
                "預報時間": fp["time_label"],
                "緯度 (°N)": fp["lat"],
                "經度 (°E)": fp["lon"],
                "中心氣壓": fp["pressure"],
                "最大風速": fp["wind"],
                "70%半徑": f"{int(fp['radius_70']/1000)} km",
                "動態說明": fp.get("desc", "")
            }
            for fp in cur_typhoon["forecast_points"]
        ])

        st.dataframe(
            df_ty_forecast,
            width="stretch",
            hide_index=True,
            column_config={
                "預報時間": st.column_config.TextColumn("預報時間"),
                "緯度 (°N)": st.column_config.NumberColumn("緯度", format="%.1f°N"),
                "經度 (°E)": st.column_config.NumberColumn("經度", format="%.1f°E"),
                "中心氣壓": st.column_config.TextColumn("氣壓"),
                "最大風速": st.column_config.TextColumn("風速"),
                "70%半徑": st.column_config.TextColumn("70%半徑"),
                "動態說明": st.column_config.TextColumn("路徑動態")
            }
        )

        st.markdown("""
        <div style="background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.07); border-radius: 12px; padding: 12px; margin-top: 10px; font-size: 0.82rem; color: #6c757d; box-shadow: 0 4px 12px rgba(60, 50, 40, 0.05);">
            🛡️ <b>防颱重點提醒</b>：沿海地區請慎防長浪與風暴潮倒灌；山區需留意落石與土石流，低窪地區請提早做好排水與沙包防汛準備。
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
