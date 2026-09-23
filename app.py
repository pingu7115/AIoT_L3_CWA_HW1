#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
階段 4: 前端展示 (Presentation)
app.py
Streamlit 互動式視覺化儀表板
【重要規範】：本應用程式之預報資料 100% 透過 SQL 查詢自本地 SQLite 資料庫 (data.db)，嚴禁直接呼叫外部 API。
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
# 頁面基本配置
# -------------------------------------------------------------
st.set_page_config(
    page_title="AIoT HW10 - 台灣氣象預報儀表板",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# 自訂 CSS 提升介面質感 (Modern Dashboard Style)
# -------------------------------------------------------------
st.markdown("""
<style>
    /* 全域字體與背景優化 */
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1E3A8A, #3B82F6, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #E2E8F0;
        text-align: center;
    }
    .source-badge {
        display: inline-block;
        padding: 4px 10px;
        font-size: 0.85rem;
        border-radius: 6px;
        background-color: #ECFDF5;
        color: #047857;
        font-weight: 600;
        border: 1px solid #A7F3D0;
    }
    .legend-box {
        padding: 10px 14px;
        border-radius: 8px;
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        font-size: 0.85rem;
        margin-top: 8px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 6 大分區經緯度座標（用於 Folium 地圖呈現）
# -------------------------------------------------------------
REGION_COORDINATES = {
    "北部地區": [25.0330, 121.5654],
    "中部地區": [24.1477, 120.6736],
    "南部地區": [22.9997, 120.2270],
    "東部地區": [23.9872, 121.6016],
    "澎湖地區": [23.5711, 119.5793],
    "金門馬祖地區": [24.4493, 118.3766],
}

def get_temp_color(temp):
    """根據溫度分級返回對應色彩"""
    if temp < 20:
        return "#3B82F6"  # 偏涼 (深藍)
    elif temp <= 25:
        return "#10B981"  # 舒適 (綠)
    elif temp <= 30:
        return "#F59E0B"  # 溫暖 (橙黃)
    else:
        return "#EF4444"  # 炎熱 (紅)

# -------------------------------------------------------------
# 側邊欄控制項 (Sidebar)
# -------------------------------------------------------------
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1534088568595-a066f410bcda?w=400&auto=format&fit=crop&q=80", use_container_width=True)
    st.markdown("### ⚙️ 系統控制與管線狀態")
    
    # 檢查資料庫狀態
    db_exists = os.path.exists(DEFAULT_DB_PATH)
    if db_exists:
        st.success(f"✅ SQLite 資料庫已連線 (`{DEFAULT_DB_PATH}`)")
    else:
        st.error(f"❌ 找不到 `{DEFAULT_DB_PATH}`，請先執行 ETL 載入資料！")

    st.markdown("---")
    st.markdown("#### 🔄 手動觸發 ETL 更新資料")
    st.caption("此操作將在背景執行 `main.py` (Fetch -> Parse -> DB Upsert)。")
    
    input_api_key = st.text_input("CWA API Key (選填)", type="password", placeholder="未輸入將使用模擬資料")
    force_mock_check = st.checkbox("強制使用模擬資料 (Mock)", value=False)

    if st.button("🚀 執行完整 ETL 管線", use_container_width=True):
        with st.spinner("正在執行資料抓取、解析與 SQLite 寫入..."):
            try:
                run_pipeline(api_key=input_api_key if input_api_key else None, force_mock=force_mock_check)
                st.success("🎉 資料庫更新成功！")
                st.rerun()
            except Exception as e:
                st.error(f"執行失敗: {e}")

    st.markdown("---")
    st.markdown("""
    **專案規範標章**：
    - 🔒 前端直連 API：**完全禁止**
    - 💾 資料來源：**本地 SQLite (data.db)**
    - 📐 架構：**ETL Pipeline + Streamlit**
    """)

# -------------------------------------------------------------
# 主畫面 Header
# -------------------------------------------------------------
col_header1, col_header2 = st.columns([3, 1])
with col_header1:
    st.markdown('<div class="main-title">🌦️ 台灣未來一週氣溫預報儀表板</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">AIoT HW10 端到端氣象資料管線 | 整合 CWA 預報、SQLite 存儲與互動視覺化</div>', unsafe_allow_html=True)
with col_header2:
    st.markdown('<div style="text-align: right; margin-top: 15px;"><span class="source-badge">🟢 資料來源: SQLite data.db (SQL 查詢)</span></div>', unsafe_allow_html=True)

# -------------------------------------------------------------
# 資料讀取 (純 SQL 查詢)
# -------------------------------------------------------------
regions = get_distinct_regions(DEFAULT_DB_PATH)

if not regions:
    st.warning("⚠️ 目前資料庫中無氣象資料，請點選左側「執行完整 ETL 管線」按鈕以初始化資料庫。")
    st.stop()

# -------------------------------------------------------------
# 區域選擇下拉選單 (st.selectbox)
# -------------------------------------------------------------
st.markdown("### 📍 預報分區檢視")
col_select, col_info = st.columns([2, 3])
with col_select:
    selected_region = st.selectbox(
        "請選擇欲查詢之台灣分區：",
        options=regions,
        index=regions.index("北部地區") if "北部地區" in regions else 0
    )

# 查詢該分區預報 (純 SQL)
forecast_records = get_forecast_by_region(selected_region, DEFAULT_DB_PATH)
df_forecast = pd.DataFrame(forecast_records)

if df_forecast.empty:
    st.error(f"查無 {selected_region} 的預報資料。")
    st.stop()

# -------------------------------------------------------------
# 關鍵指標卡片 (Metric Cards)
# -------------------------------------------------------------
today_row = df_forecast.iloc[0]
avg_week_max = round(df_forecast['maxt'].mean(), 1)
avg_week_min = round(df_forecast['mint'].mean(), 1)
max_week_temp = df_forecast['maxt'].max()
min_week_temp = df_forecast['mint'].min()

col1, col2, col3, col4 = st.columns(4)
col1.metric("今日最高溫", f"{today_row['maxt']} °C", f"最低 {today_row['mint']} °C")
col2.metric("今日溫差", f"{round(today_row['maxt'] - today_row['mint'], 1)} °C", "日夜溫差")
col3.metric("一週最高溫", f"{max_week_temp} °C", f"均溫 {avg_week_max} °C")
col4.metric("一週最低溫", f"{min_week_temp} °C", f"均溫 {avg_week_min} °C")

st.markdown("---")

# -------------------------------------------------------------
# 視覺化區塊：折線圖 (Line Chart) 與 預報數據表格 (Data Table)
# -------------------------------------------------------------
col_chart, col_table = st.columns([3, 2])

with col_chart:
    st.markdown(f"#### 📈 {selected_region} 一週氣溫走勢 (MaxT vs MinT)")
    
    # 轉換長表格格式以利 Altair 繪製高品質雙折線圖
    df_melted = df_forecast.melt(
        id_vars=["dataDate"],
        value_vars=["maxt", "mint"],
        var_name="指標",
        value_name="氣溫 (°C)"
    )
    df_melted["指標"] = df_melted["指標"].map({"maxt": "最高氣溫 (MaxT)", "mint": "最低氣溫 (MinT)"})

    # 使用 Altair 繪製客製化美觀折線圖
    chart = alt.Chart(df_melted).mark_line(point=True, strokeWidth=3).encode(
        x=alt.X("dataDate:N", title="預報日期", axis=alt.Axis(labelAngle=-25)),
        y=alt.Y("氣溫 (°C):Q", title="氣溫 (°C)", scale=alt.Scale(zero=False)),
        color=alt.Color(
            "指標:N",
            scale=alt.Scale(
                domain=["最高氣溫 (MaxT)", "最低氣溫 (MinT)"],
                range=["#EF4444", "#3B82F6"]
            ),
            legend=alt.Legend(orient="top", title=None)
        ),
        tooltip=["dataDate", "指標", "氣溫 (°C)"]
    ).properties(height=350).interactive()

    st.altair_chart(chart, use_container_width=True)

with col_table:
    st.markdown(f"#### 📋 {selected_region} 7 天預報數據表")
    display_df = df_forecast.copy()
    display_df["溫差 (°C)"] = (display_df["maxt"] - display_df["mint"]).round(1)
    display_df = display_df.rename(columns={
        "dataDate": "預報日期",
        "mint": "最低溫 (°C)",
        "maxt": "最高溫 (°C)"
    })[["預報日期", "最低溫 (°C)", "最高溫 (°C)", "溫差 (°C)"]]
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "預報日期": st.column_config.TextColumn("預報日期"),
            "最低溫 (°C)": st.column_config.NumberColumn("最低溫 (°C)", format="%.1f °C"),
            "最高溫 (°C)": st.column_config.NumberColumn("最高溫 (°C)", format="%.1f °C"),
            "溫差 (°C)": st.column_config.NumberColumn("日溫差", format="%.1f °C")
        }
    )

st.markdown("---")

# -------------------------------------------------------------
# 進階加分項: 台灣氣溫分級地圖 (Folium + Streamlit-Folium)
# -------------------------------------------------------------
st.markdown("### 🗺️ 進階加分項: 台灣全島最新氣溫分級互動地圖")
st.caption("透過 Folium 地圖呈現 6 大分區最新預報氣溫，點選標記可查看詳細最高/最低溫資訊。")

col_map, col_legend = st.columns([3, 1])

# 查詢所有區域最近一日預報 (純 SQL)
all_latest = get_all_latest_forecasts(DEFAULT_DB_PATH)

with col_map:
    # 建立 Folium 台灣中心地圖
    m = folium.Map(
        location=[23.7, 120.9],
        zoom_start=7,
        tiles="CartoDB positron",
        control_scale=True
    )

    for item in all_latest:
        r_name = item["regionName"]
        coords = REGION_COORDINATES.get(r_name)
        if not coords:
            continue

        avg_temp = round((item["maxt"] + item["mint"]) / 2, 1)
        marker_color = get_temp_color(avg_temp)

        popup_html = f"""
        <div style="font-family: sans-serif; width: 170px; padding: 4px;">
            <h4 style="margin: 0 0 6px 0; color: #1E3A8A;">📍 {r_name}</h4>
            <p style="margin: 2px 0; font-size: 13px;"><b>日期:</b> {item['dataDate']}</p>
            <p style="margin: 2px 0; font-size: 13px; color: #EF4444;"><b>最高溫:</b> {item['maxt']} °C</p>
            <p style="margin: 2px 0; font-size: 13px; color: #3B82F6;"><b>最低溫:</b> {item['mint']} °C</p>
            <p style="margin: 4px 0 0 0; font-size: 12px; color: #64748B;">平均氣溫: {avg_temp} °C</p>
        </div>
        """

        # 繪製半透明氣溫涵蓋圓
        folium.CircleMarker(
            location=coords,
            radius=22,
            color=marker_color,
            weight=3,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.45,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{r_name}: {item['mint']}°C ~ {item['maxt']}°C"
        ).add_to(m)

        # 標記中心顯示數字
        folium.Marker(
            location=coords,
            icon=folium.DivIcon(
                html=f"""<div style="font-size: 11pt; font-weight: bold; color: #0F172A; text-shadow: 1px 1px 2px white; text-align: center; width: 40px; margin-left: -20px; margin-top: -10px;">{avg_temp}°</div>"""
            )
        ).add_to(m)

    st_folium(m, width="100%", height=450)

with col_legend:
    st.markdown("#### 🎨 氣溫等級圖例")
    st.markdown("""
    <div class="legend-box">
        <div style="margin-bottom: 8px;">
            <span style="display:inline-block; width:14px; height:14px; background:#EF4444; border-radius:50%; margin-right:6px;"></span>
            <b>高溫炎熱</b> (&gt; 30 °C)
        </div>
        <div style="margin-bottom: 8px;">
            <span style="display:inline-block; width:14px; height:14px; background:#F59E0B; border-radius:50%; margin-right:6px;"></span>
            <b>溫暖偏熱</b> (26 ~ 30 °C)
        </div>
        <div style="margin-bottom: 8px;">
            <span style="display:inline-block; width:14px; height:14px; background:#10B981; border-radius:50%; margin-right:6px;"></span>
            <b>氣候舒適</b> (20 ~ 25 °C)
        </div>
        <div>
            <span style="display:inline-block; width:14px; height:14px; background:#3B82F6; border-radius:50%; margin-right:6px;"></span>
            <b>偏涼微冷</b> (&lt; 20 °C)
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("#### 💡 地圖使用小提示")
    st.info("點擊地圖上的各區溫度圓圈，即可展開當日最高溫與最低溫詳細預報卡片！")

# -------------------------------------------------------------
# 頁尾資訊
# -------------------------------------------------------------
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #94A3B8; font-size: 0.85rem;">
    AIoT L3 CWA HW10 · Taiwan Weather Forecast Dashboard · Powered by Python, SQLite & Streamlit
</div>
""", unsafe_allow_html=True)
