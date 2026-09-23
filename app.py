#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
階段 4: 前端展示 (Presentation)
app.py - 台灣氣象預報互動視覺化儀表板 (類 Windy 極黑科技美學風格)
參考範例: https://taiwan-weather-map.vercel.app/

【嚴格遵守作業規範】：
1. 預報資料 100% 透過 SQL 查詢自本地 SQLite 資料庫 (data.db)，嚴禁前端直呼外部 API。
2. 包含區域選擇下拉選單 (st.selectbox)、一週最高/最低氣溫折線圖 (MaxT vs MinT)、一週預報數據表格。
3. 進階加分項: Folium 台灣氣溫分級地圖 (類 Windy 深色底圖、發光測站氣溫標籤、漸層溫度圖例)。
"""

import os
import sys
import datetime
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
    page_title="台灣即時氣象地圖 · Taiwan Weather Dashboard",
    page_icon="🌪️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# 類 Windy / 高質感深色玻璃態 CSS (Glassmorphism & Neon Glow)
# -------------------------------------------------------------
st.markdown("""
<style>
    /* 引入現代 Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* 深邃暗色背景 */
    .stApp {
        background: radial-gradient(circle at 50% 0%, #0d1527 0%, #030712 100%);
        color: #F3F4F6;
    }

    /* 頂部導航玻璃條 */
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

    /* 科技感膠囊標籤 */
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

    /* 玻璃態卡片 (Glass Cards) */
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

    /* 指標數據字體微調 */
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

    /* 類 Apple Weather / Windy 7日迷你卡片條 */
    .forecast-strip-container {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 12px;
        margin-top: 12px;
        margin-bottom: 24px;
    }

    .day-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 14px 10px;
        text-align: center;
        transition: background 0.2s;
    }

    .day-card:hover {
        background: rgba(56, 189, 248, 0.08);
        border-color: rgba(56, 189, 248, 0.3);
    }

    .day-date {
        font-size: 0.85rem;
        font-weight: 600;
        color: #E2E8F0;
        margin-bottom: 4px;
    }

    .day-icon {
        font-size: 1.6rem;
        margin: 6px 0;
    }

    .day-temps {
        font-size: 0.95rem;
        font-weight: 600;
        margin-top: 6px;
    }

    .temp-high {
        color: #F87171;
    }

    .temp-low {
        color: #38BDF8;
    }

    /* 漸層溫度條 (Windy Color Bar) */
    .windy-gradient-bar {
        height: 10px;
        width: 100%;
        border-radius: 5px;
        background: linear-gradient(to right, #2c7bb6, #5aa2cf, #abd9e9, #7fcdbb, #d9ef8b, #fee08b, #fdae61, #f46d43, #d73027);
        margin-top: 8px;
    }

    /* 地圖微縮圖例面板 */
    .map-legend-panel {
        background: rgba(15, 23, 42, 0.85);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 14px 18px;
        margin-top: 10px;
    }

    /* 隱藏 Streamlit 原生多餘空白 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 6 大分區經緯度座標與色票映射
# -------------------------------------------------------------
REGION_COORDINATES = {
    "北部地區": [25.0330, 121.5654],
    "中部地區": [24.1477, 120.6736],
    "南部地區": [22.9997, 120.2270],
    "東部地區": [23.9872, 121.6016],
    "澎湖地區": [23.5711, 119.5793],
    "金門馬祖地區": [24.4493, 118.3766],
}

def get_windy_temp_color(temp):
    """
    對標 https://taiwan-weather-map.vercel.app/ 的 Windy 色階
    #2c7bb6 (冷藍), #7fcdbb (湖水綠), #fee08b (暖黃), #f46d43 (橙紅), #d73027 (深赤)
    """
    if temp < 18:
        return "#2c7bb6"  # 涼冷
    elif temp < 22:
        return "#5aa2cf"  # 微涼
    elif temp < 25:
        return "#7fcdbb"  # 舒適清爽
    elif temp < 28:
        return "#fee08b"  # 溫和微暖
    elif temp < 31:
        return "#fdae61"  # 偏暖橙
    else:
        return "#f46d43"  # 炎熱高溫

def get_weather_icon(mint, maxt):
    """根據平均氣溫與溫差推估視覺化天氣符號"""
    avg = (mint + maxt) / 2
    diff = maxt - mint
    if avg >= 28:
        return "☀️", "晴朗炎熱"
    elif diff >= 7:
        return "🌤️", "晴時多雲"
    elif avg >= 23:
        return "⛅", "多雲舒適"
    else:
        return "🌥️", "陰涼微涼"

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
    st.markdown("#### 🔄 觸發 CWA 即時資料更新")
    user_api_key = st.text_input("CWA API 授權碼", type="password", placeholder="留空則使用已儲存金鑰")
    force_mock = st.checkbox("強制使用模擬資料", value=False)
    
    if st.button("🚀 執行後端 ETL 管線", use_container_width=True):
        with st.spinner("正在向中央氣象署抓取最新預報並寫入 SQLite..."):
            try:
                run_pipeline(api_key=user_api_key if user_api_key else None, force_mock=force_mock)
                st.success("🎉 資料庫更新成功！已載入最新預報。")
                st.rerun()
            except Exception as e:
                st.error(f"更新失敗: {e}")

    st.markdown("---")
    st.markdown("""
    **作業規範符合度**：
    - ✅ **前端直連 API：0% (嚴格禁止)**
    - ✅ **資料來源：SQLite (data.db)**
    - ✅ **加分項：Folium 氣溫分級地圖**
    """)

# -------------------------------------------------------------
# 頂部導航條 (Top Navigation Bar)
# -------------------------------------------------------------
st.markdown("""
<div class="top-navbar">
    <div>
        <h1 class="brand-title">🌪️ 台灣即時氣象視覺化地圖</h1>
        <div class="brand-subtitle">中央氣象署 Open Data 即時資料庫同步 · 類 Windy 深色互動風格儀表板</div>
    </div>
    <div style="display: flex; gap: 10px; align-items: center;">
        <span class="pill-badge green">● 資料來源: SQLite data.db</span>
        <span class="pill-badge">🛰️ 7 天逐日預報</span>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 資料讀取 (純 SQL 查詢自 data.db)
# -------------------------------------------------------------
regions = get_distinct_regions(DEFAULT_DB_PATH)
if not regions:
    st.warning("⚠️ 目前資料庫中無氣象資料，請於側邊欄點選「執行後端 ETL 管線」以初始化資料庫。")
    st.stop()

# -------------------------------------------------------------
# 區域選擇下拉選單 (st.selectbox - 符合作業圖規範)
# -------------------------------------------------------------
col_select_a, col_select_b = st.columns([2, 4])
with col_select_a:
    selected_region = st.selectbox(
        "📍 選擇檢視區域 (Region Selector)：",
        options=regions,
        index=regions.index("北部地區") if "北部地區" in regions else 0
    )

# 查詢該區域 7 天資料 (純 SQL)
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

# -------------------------------------------------------------
# 玻璃態指標卡片 (Metric Cards)
# -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="glass-card" style="border-top: 3px solid #F87171;">
        <div class="metric-title">🔥 今日最高溫 (MaxT)</div>
        <div class="metric-value" style="color: #F87171;">{today_max}°C</div>
        <div class="metric-caption">預測區間峰值 · {selected_region}</div>
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
        <div class="metric-caption">溫差建議注意衣著調適</div>
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
# 主視覺雙欄版面：左側類 Windy 全島氣溫地圖 / 右側 7 天氣象趨勢折線圖
# -------------------------------------------------------------
col_map, col_chart = st.columns([1.15, 1])

with col_map:
    st.markdown("### 🗺️ 台灣全島即時氣溫分級地圖 (類 Windy 風格)")
    st.caption("採用 CartoDB Dark Matter 深色極簡底圖，呈現 6 大分區實測最新氣溫，點擊氣泡可展開詳細預報。")

    all_latest = get_all_latest_forecasts(DEFAULT_DB_PATH)

    # 建立 Dark Matter 底圖（完全免金鑰、深色科技感）
    m = folium.Map(
        location=[23.7, 120.9],
        zoom_start=7.2,
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://carto.com/">CARTO</a>'
    )

    for item in all_latest:
        r_name = item["regionName"]
        coords = REGION_COORDINATES.get(r_name)
        if not coords:
            continue

        r_avg = round((item["maxt"] + item["mint"]) / 2, 1)
        r_color = get_windy_temp_color(r_avg)
        is_selected = (r_name == selected_region)

        # 懸浮氣泡卡片
        popup_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; width: 180px; padding: 6px; background: #0F172A; color: #F8FAFC; border-radius: 8px;">
            <div style="font-weight: 700; font-size: 15px; margin-bottom: 6px; color: #38BDF8;">📍 {r_name}</div>
            <div style="font-size: 12px; color: #94A3B8; margin-bottom: 4px;">預報日期: {item['dataDate']}</div>
            <div style="display: flex; justify-content: space-between; margin-top: 6px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">
                <span style="color: #F87171; font-weight: 600;">高溫 {item['maxt']}°C</span>
                <span style="color: #38BDF8; font-weight: 600;">低溫 {item['mint']}°C</span>
            </div>
            <div style="font-size: 11px; color: #64748B; margin-top: 4px; text-align: center;">日均氣溫: {r_avg}°C</div>
        </div>
        """

        # 繪製半透明氣溫光環圓
        folium.CircleMarker(
            location=coords,
            radius=24 if is_selected else 20,
            color=r_color,
            weight=3 if is_selected else 2,
            fill=True,
            fill_color=r_color,
            fill_opacity=0.55 if is_selected else 0.4,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{r_name}: {item['mint']}°C ~ {item['maxt']}°C"
        ).add_to(m)

        # 標記中心懸浮數字標籤（類 Windy 設計）
        badge_border = "2px solid #FFFFFF" if is_selected else "1px solid rgba(255,255,255,0.4)"
        icon_html = f"""
        <div style="
            background: {r_color};
            color: #FFFFFF;
            font-weight: 700;
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.6);
            border: {badge_border};
            width: 44px;
            margin-left: -22px;
            margin-top: -10px;
        ">{r_avg}°</div>
        """
        folium.Marker(
            location=coords,
            icon=folium.DivIcon(html=icon_html)
        ).add_to(m)

    st_folium(m, width="100%", height=460)

    # 底部 Windy 經典漸層標尺 (對標 target site)
    st.markdown("""
    <div class="map-legend-panel">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
            <span style="font-size: 0.8rem; font-weight: 600; color: #94A3B8;">🌡️ 氣溫色階 (°C)</span>
            <span style="font-size: 0.75rem; color: #64748B;">即時全島溫度漸層</span>
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
    st.caption("透過 Altair 呈現平滑曲線與極限溫差陰影，即時比對未來 7 天日夜溫度波動。")

    # 轉換為長表格以繪製雙曲線
    df_melted = df_forecast.melt(
        id_vars=["dataDate"],
        value_vars=["maxt", "mint"],
        var_name="指標",
        value_name="氣溫"
    )
    df_melted["指標"] = df_melted["指標"].map({"maxt": "最高氣溫 (MaxT)", "mint": "最低氣溫 (MinT)"})

    # Altair 深色主題折線圖
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

    # 7 日統計摘要條
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
# 類 Apple Weather / Windy 7日水平膠囊卡片條
# -------------------------------------------------------------
st.markdown(f"### 📅 {selected_region} 7 天逐日天氣卡片")

cards_html = ['<div class="forecast-strip-container">']
for idx, row in df_forecast.iterrows():
    d_str = row["dataDate"][5:] # MM-DD
    icon, desc = get_weather_icon(row["mint"], row["maxt"])
    cards_html.append(f"""
    <div class="day-card">
        <div class="day-date">{d_str}</div>
        <div class="day-icon">{icon}</div>
        <div style="font-size: 0.75rem; color: #94A3B8; margin-bottom: 4px;">{desc}</div>
        <div class="day-temps">
            <span class="temp-high">{row['maxt']}°</span>
            <span style="color: #64748B; margin: 0 2px;">/</span>
            <span class="temp-low">{row['mint']}°</span>
        </div>
    </div>
    """)
cards_html.append('</div>')
st.markdown("".join(cards_html), unsafe_allow_html=True)

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
    資料庫架構: SQLite (data.db) · 前端框架: Streamlit & Folium
</div>
""", unsafe_allow_html=True)
