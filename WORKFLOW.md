# 🔄 系統工作流程規範書 (System Workflow)

> **專案名稱**：Taiwan Weather Forecast (從氣象資料到互動式天氣預報應用)  
> **專案倉庫**：[AIoT_L3_CWA_HW1](https://github.com/pingu7115/AIoT_L3_CWA_HW1.git)  
> **技術架構**：CWA API × JSON × Python × SQLite × Streamlit × Folium

---

## 1. 系統整體架構圖 (Mermaid Architecture Flow)

```mermaid
flowchart TD
    %% 節點定義
    subgraph Data_Source ["階段 1: 外部資料源"]
        CWA["中央氣象署 Open Data API<br/>(資料集代號: F-A0010-001)"]
    end

    subgraph Pipeline ["後端資料處理管線 (Data Pipeline)"]
        F1["fetch_weather.py<br/>發送 HTTP GET 請求 (帶入 API Key)"]
        RawJSON[("原始預報 JSON 檔案<br/>weather_data.json")]
        P1["parse_weather.py<br/>解析巢狀 JSON 結構"]
        CleanData["清洗後的結構化氣溫資料<br/>(6 大分區 × 7 天預報)"]
        DB_Script["database.py<br/>寫入資料庫與防重複邏輯"]
        SQLiteDB[("SQLite 本地資料庫<br/>data.db: TemperatureForecasts")]
    end

    subgraph Presentation ["前端視覺化展示 (Streamlit Web App)"]
        App["app.py<br/>Streamlit 應用程式"]
        UI_Select["地區選擇器<br/>(st.selectbox)"]
        UI_Chart["一週最高/最低溫折線圖<br/>(MaxT vs MinT)"]
        UI_Table["氣溫數據表格<br/>(Data Table)"]
        UI_Map["進階加分項: 台灣地圖<br/>(Folium 溫標顏色標註)"]
    end

    %% 資料流走向
    CWA -->|HTTP 200 回傳| F1
    F1 -->|存檔 / 傳遞| RawJSON
    RawJSON -->|讀取| P1
    P1 -->|萃取 MinT, MaxT, dataDate| CleanData
    CleanData -->|寫入 / 更新| DB_Script
    DB_Script -->|儲存| SQLiteDB

    SQLiteDB -.->|SQL 查詢讀取 (禁止前端直呼 API)| App
    App --> UI_Select
    UI_Select --> UI_Chart
    UI_Select --> UI_Table
    App --> UI_Map

    %% 樣式設定
    classDef highlight fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    class CWA,SQLiteDB highlight;
