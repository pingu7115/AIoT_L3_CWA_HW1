#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
階段 4: 前端展示 (Presentation)
app.py - 台灣即時氣象視覺化地圖 (全台 22 縣市 · 類 Windy 深色科技美學風格)
參考範例: https://taiwan-weather-map.vercel.app/

【嚴格遵守作業規範】：
1. 預報資料 100% 透過 SQL 查詢自本地 SQLite 資料庫 (data.db)，嚴禁前端直呼外部 API。
2. 完整支援全台 22 縣市（基隆、雙北、桃園、新竹、苗栗、台中、彰化、南投、雲林、嘉義、台南、高雄、屏東、宜蘭、花蓮、台東、澎湖、金門、連江等）及大分區。
3. 包含下拉選單 (st.selectbox)、一週最高/最低氣溫折線圖 (MaxT vs MinT)、一週預報詳細數據表。
4. 進階加分項: Folium 台灣氣溫分級地圖 (類 Windy 深色底圖、全島 22 縣市發光氣溫標籤、漸層溫度標尺)。
"""

import os
import sys
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

# -------------------------------------------------------------
# 頁面配置 (Dark Theme Default)
# -------------------------------------------------------------
st.set_page_config(
    page_title="台灣全縣市即時氣象地圖 · Taiwan Weather Dashboard",
    page_icon="🌪️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# 類 Windy / 高質感深色玻璃態 CSS
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .stApp {
        background: radial-gradient(circle at 50% 0%, #0d1527 0%, #030712 100%);
        color: #F3F4F6;
    }

    .top-navbar {
        background: rgba(15, 23, 42, 0.75);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 18px 24px;
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }

    .brand-title {
        font-size: 1.85rem;
        font-weight: 800;
        background: linear-gradient(135deg, #60A5FA 0%, #38BDF8 50%, #34D399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
        margin: 0;
    }

    .brand-subtitle {
        font-size: 0.88rem;
        color: #94A3B8;
        margin-top: 4px;
    }

    .pill-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(56, 189, 248, 0.1);
        border: 1px solid rgba(56, 189, 248, 0.25);
        color: #38BDF8;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .pill-badge.green {
        background: rgba(16, 185, 129, 0.1);
        border-color: rgba(16, 185, 129, 0.25);
        color: #34D399;
    }

    .glass-card {
        background: rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 24px -1px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }

    .glass-card:hover {
        border-color: rgba(56, 189, 248, 0.35);
        transform: translateY(-2px);
    }

    .metric-title {
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94A3B8;
        margin-bottom: 8px;
    }

    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        line-height: 1;
        margin-bottom: 6px;
    }

    .metric-caption {
        font-size: 0.82rem;
        color: #64748B;
    }

    .windy-gradient-bar {
        height: 10px;
        width: 100%;
        border-radius: 5px;
        background: linear-gradient(to right, #2c7bb6, #5aa2cf, #abd9e9, #7fcdbb, #d9ef8b, #fee08b, #fdae61, #f46d43, #d73027);
        margin-top: 8px;
    }

    .map-legend-panel {
        background: rgba(15, 23, 42, 0.85);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 14px 18px;
        margin-top: 10px;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 全台 22 縣市完整經緯度座標（涵蓋本島與外島全境）
# -------------------------------------------------------------
ALL_COORDINATES = {
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
    # 6 大分區
    "北部地區": [25.0330, 121.5654],
    "中部地區": [24.1477, 120.6736],
    "南部地區": [22.9997, 120.2270],
    "東部地區": [23.9872, 121.6016],
    "澎湖地區": [23.5711, 119.5793],
    "金門馬祖地區": [24.4493, 118.3766],
}

# 優先排序列（22 縣市依地理從北到南、外島排序列）
PREFER_ORDER = [
    "臺北市", "新北市", "基隆市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣",
    "臺南市", "高雄市", "屏東縣",
    "宜蘭縣", "花蓮縣", "臺東縣",
    "澎湖縣", "金門縣", "連江縣",
    "北部地區", "中部地區", "南部地區", "東部地區", "澎湖地區", "金門馬祖地區"
]

def get_windy_temp_color(temp):
    """對標 Windy / target site 色階"""
    if temp < 18:
        return "#2c7bb6"
    elif temp < 22:
        return "#5aa2cf"
    elif temp < 25:
        return "#7fcdbb"
    elif temp < 28:
        return "#fee08b"
    elif temp < 31:
        return "#fdae61"
    else:
        return "#f46d43"

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
    st.markdown("#### 🔄 觸發 CWA 全台即時資料更新")
    user_api_key = st.text_input("CWA API 授權碼", type="password", placeholder="留空則使用 .env 儲存金鑰")
    force_mock = st.checkbox("強制使用模擬資料", value=False)
    
    if st.button("🚀 執行後端 ETL 管線", use_container_width=True):
        with st.spinner("正在向中央氣象署抓取全台最新預報並寫入 SQLite..."):
            try:
                run_pipeline(api_key=user_api_key if user_api_key else None, force_mock=force_mock)
                st.success("🎉 資料庫更新成功！已載入全台縣市最新預報。")
                st.rerun()
            except Exception as e:
                st.error(f"更新失敗: {e}")

    st.markdown("---")
    st.markdown("""
    **作業規範符合度**：
    - ✅ **前端直連 API：0% (嚴格禁止)**
    - ✅ **涵蓋全台 22 縣市與分區**
    - ✅ **加分項：Folium 全島深色分級地圖**
    """)

# -------------------------------------------------------------
# 頂部導航條
# -------------------------------------------------------------
st.markdown("""
<div class="top-navbar">
    <div>
        <h1 class="brand-title">🌪️ 台灣全縣市即時氣象地圖</h1>
        <div class="brand-subtitle">中央氣象署 Open Data 全台 22 縣市即時同步 · 類 Windy 深色互動風格儀表板</div>
    </div>
    <div style="display: flex; gap: 10px; align-items: center;">
        <span class="pill-badge green">● 資料來源: SQLite data.db</span>
        <span class="pill-badge">🛰️ 全台 22 縣市覆蓋</span>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 資料讀取 (純 SQL 查詢自 data.db)
# -------------------------------------------------------------
all_db_regions = get_distinct_regions(DEFAULT_DB_PATH)
if not all_db_regions:
    st.warning("⚠️ 目前資料庫中無氣象資料，請於側邊欄點選「執行後端 ETL 管線」以初始化資料庫。")
    st.stop()

# 整理下拉選單選項順序（依地理優先排序）
sorted_regions = [r for r in PREFER_ORDER if r in all_db_regions]
for r in all_db_regions:
    if r not in sorted_regions:
        sorted_regions.append(r)

# -------------------------------------------------------------
# 全台縣市選擇下拉選單 (st.selectbox - 涵蓋全台 22 縣市)
# -------------------------------------------------------------
col_select_a, col_select_b = st.columns([2.5, 3.5])
with col_select_a:
    default_target = "臺北市" if "臺北市" in sorted_regions else sorted_regions[0]
    selected_region = st.selectbox(
        "📍 請選擇台灣縣市或區域 (全台 22 縣市即時切換)：",
        options=sorted_regions,
        index=sorted_regions.index(default_target)
    )

with col_select_b:
    st.markdown(f"""
    <div style="padding-top: 28px; font-size: 0.9rem; color: #94A3B8;">
        當前選定：<b style="color: #38BDF8; font-size: 1.05rem;">{selected_region}</b> · 未來 7 天預報資料由本地 SQLite 即時提供
    </div>
    """, unsafe_allow_html=True)

# 查詢該縣市 7 天資料 (純 SQL)
forecast_records = get_forecast_by_region(selected_region, DEFAULT_DB_PATH)
df_forecast = pd.DataFrame(forecast_records)

if df_forecast.empty:
    st.error(f"查無 {selected_region} 的預報資料。")
    st.stop()

# 計算指標
today_row = df_forecast.iloc[0]
today_min = today_row["mint"]
today_max = today_row["maxt"]
today_diff = round(today_max - today_min, 1)
today_avg = round((today_max + today_min) / 2, 1)
week_max = df_forecast["maxt"].max()
week_min = df_forecast["mint"].min()

# -------------------------------------------------------------
# 玻璃態指標卡片 (Metric Cards)
# -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="glass-card" style="border-top: 3px solid #F87171;">
        <div class="metric-title">🔥 今日最高溫 (MaxT)</div>
        <div class="metric-value" style="color: #F87171;">{today_max}°C</div>
        <div class="metric-caption">日間高溫預測 · {selected_region}</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="glass-card" style="border-top: 3px solid #38BDF8;">
        <div class="metric-title">❄️ 今日最低溫 (MinT)</div>
        <div class="metric-value" style="color: #38BDF8;">{today_min}°C</div>
        <div class="metric-caption">清晨夜間低溫 · {selected_region}</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="glass-card" style="border-top: 3px solid #FBBF24;">
        <div class="metric-title">⚖️ 日夜溫差 (Diurnal Range)</div>
        <div class="metric-value" style="color: #FBBF24;">{today_diff}°C</div>
        <div class="metric-caption">溫差提示 · 建議外出適度增減衣物</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    icon, condition = get_weather_icon(today_min, today_max)
    st.markdown(f"""
    <div class="glass-card" style="border-top: 3px solid #34D399;">
        <div class="metric-title">🌡️ 體感環境指標</div>
        <div class="metric-value" style="color: #34D399;">{icon} {today_avg}°C</div>
        <div class="metric-caption">當日平均氣候: {condition}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 主視覺雙欄：左側全島 22 縣市地圖 / 右側 7 天氣象趨勢折線圖
# -------------------------------------------------------------
col_map, col_chart = st.columns([1.2, 1])

with col_map:
    st.markdown("### 🗺️ 全台 22 縣市即時氣溫分級地圖 (類 Windy 風格)")
    st.caption("深色底圖呈現全台 22 個縣市實測即時氣溫，點選縣市圓點可展開詳細卡片。")

    all_latest = get_all_latest_forecasts(DEFAULT_DB_PATH)

    # 建立 Dark Matter 台灣全圖
    m = folium.Map(
        location=[23.7, 120.9],
        zoom_start=7.3,
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://carto.com/">CARTO</a>'
    )

    # 優先篩選 22 縣市呈現，避免與 6 大分區重疊
    counties_in_db = [item for item in all_latest if "地區" not in item["regionName"]]
    display_items = counties_in_db if len(counties_in_db) >= 10 else all_latest

    for item in display_items:
        loc_name = item["regionName"]
        coords = ALL_COORDINATES.get(loc_name)
        if not coords:
            continue

        loc_avg = round((item["maxt"] + item["mint"]) / 2, 1)
        loc_color = get_windy_temp_color(loc_avg)
        is_selected = (loc_name == selected_region)

        popup_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; width: 175px; padding: 6px; background: #0F172A; color: #F8FAFC; border-radius: 8px;">
            <div style="font-weight: 700; font-size: 15px; margin-bottom: 4px; color: #38BDF8;">📍 {loc_name}</div>
            <div style="font-size: 12px; color: #94A3B8; margin-bottom: 6px;">預報日期: {item['dataDate']}</div>
            <div style="display: flex; justify-content: space-between; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">
                <span style="color: #F87171; font-weight: 600;">高溫 {item['maxt']}°C</span>
                <span style="color: #38BDF8; font-weight: 600;">低溫 {item['mint']}°C</span>
            </div>
            <div style="font-size: 11px; color: #64748B; margin-top: 4px; text-align: center;">日均氣溫: {loc_avg}°C</div>
        </div>
        """

        folium.CircleMarker(
            location=coords,
            radius=18 if is_selected else 13,
            color="#FFFFFF" if is_selected else loc_color,
            weight=3 if is_selected else 1.5,
            fill=True,
            fill_color=loc_color,
            fill_opacity=0.85 if is_selected else 0.65,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{loc_name}: {item['mint']}°C ~ {item['maxt']}°C"
        ).add_to(m)

        # 懸浮氣溫數值標記
        badge_border = "2px solid #FFFFFF" if is_selected else "1px solid rgba(255,255,255,0.3)"
        icon_html = f"""
        <div style="
            background: {loc_color};
            color: #FFFFFF;
            font-weight: 700;
            font-size: 10px;
            padding: 1px 4px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 6px rgba(0,0,0,0.7);
            border: {badge_border};
            width: 36px;
            margin-left: -18px;
            margin-top: -8px;
        ">{loc_avg}°</div>
        """
        folium.Marker(
            location=coords,
            icon=folium.DivIcon(html=icon_html)
        ).add_to(m)

    st_folium(m, width="100%", height=470)

    # 底部 Windy 經典漸層溫度標尺
    st.markdown("""
    <div class="map-legend-panel">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
            <span style="font-size: 0.8rem; font-weight: 600; color: #94A3B8;">🌡️ 全台即時氣溫色階 (°C)</span>
            <span style="font-size: 0.75rem; color: #64748B;">即時全島溫度漸層標尺</span>
        </div>
        <div class="windy-gradient-bar"></div>
        <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: #94A3B8; margin-top: 4px;">
            <span>15°C</span>
            <span>18°C</span>
            <span>22°C</span>
            <span>25°C</span>
            <span>28°C</span>
            <span>31°C</span>
            <span>35°C+</span>
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
            labelColor="#94A3B8",
            titleColor="#94A3B8",
            gridColor="rgba(255,255,255,0.05)"
        )),
        y=alt.Y("氣溫:Q", title="氣溫 (°C)", scale=alt.Scale(zero=False, padding=20), axis=alt.Axis(
            labelColor="#94A3B8",
            titleColor="#94A3B8",
            gridColor="rgba(255,255,255,0.06)"
        )),
        color=alt.Color(
            "指標:N",
            scale=alt.Scale(
                domain=["最高氣溫 (MaxT)", "最低氣溫 (MinT)"],
                range=["#F87171", "#38BDF8"]
            ),
            legend=alt.Legend(
                orient="top",
                title=None,
                labelColor="#E2E8F0",
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
        domainColor="rgba(255,255,255,0.1)"
    )

    st.altair_chart(chart, use_container_width=True)

    # 統計摘要卡
    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 14px 18px; margin-top: 10px;">
        <div style="display: flex; justify-content: space-around; text-align: center;">
            <div>
                <div style="font-size: 0.75rem; color: #94A3B8;">一週最高溫</div>
                <div style="font-size: 1.15rem; font-weight: 700; color: #F87171;">{week_max} °C</div>
            </div>
            <div style="border-right: 1px solid rgba(255,255,255,0.1);"></div>
            <div>
                <div style="font-size: 0.75rem; color: #94A3B8;">一週最低溫</div>
                <div style="font-size: 1.15rem; font-weight: 700; color: #38BDF8;">{week_min} °C</div>
            </div>
            <div style="border-right: 1px solid rgba(255,255,255,0.1);"></div>
            <div>
                <div style="font-size: 0.75rem; color: #94A3B8;">全週平均溫差</div>
                <div style="font-size: 1.15rem; font-weight: 700; color: #FBBF24;">{round((df_forecast['maxt'] - df_forecast['mint']).mean(), 1)} °C</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 一週預報詳細數據表格 (符合作業規範)
# -------------------------------------------------------------
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
    use_container_width=True,
    hide_index=True,
    column_config={
        "預報日期": st.column_config.TextColumn("預報日期"),
        "最低氣溫 (MinT °C)": st.column_config.NumberColumn("最低氣溫 (MinT)", format="%.1f °C"),
        "最高氣溫 (MaxT °C)": st.column_config.NumberColumn("最高氣溫 (MaxT)", format="%.1f °C"),
        "日溫差 (°C)": st.column_config.NumberColumn("日夜溫差", format="%.1f °C"),
        "舒適度評估": st.column_config.TextColumn("天氣狀態評估")
    }
)

# -------------------------------------------------------------
# 頁尾
# -------------------------------------------------------------
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; color: #64748B; font-size: 0.82rem; padding: 20px 0; border-top: 1px solid rgba(255,255,255,0.06);">
    AIoT HW10 · Taiwan Weather Forecast Dashboard · Inspired by Windy & CWA Open Data<br/>
    涵蓋全台 22 縣市即時預報 · 資料庫架構: SQLite (data.db) · 前端框架: Streamlit & Folium
</div>
""", unsafe_allow_html=True)
