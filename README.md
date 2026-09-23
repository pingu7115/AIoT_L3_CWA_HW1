# 🌦️ AIoT HW10: Taiwan Weather Forecast 系統工作流程 (Workflow)

本專案實現了從中央氣象署 (CWA) 開放資料平台取得氣象資料，經由 Python 進行 ETL 清洗、入庫 SQLite，最後於 Streamlit 與 Folium 建立互動式視覺化儀表板的完整端到端流程。

---

## 1. 系統整體架構圖 (Architecture Pipeline)

```mermaid
flowchart TD
    %% 階段定義
    subgraph S1 [階段 1: 資料獲取 Data Ingestion]
        API["中央氣象署 CWA Open Data API<br/>(資料集: F-A0010-001 / F-D0047-091)"]
        F1["fetch_weather.py<br/>發送 HTTP GET 請求 (含 API Key)"]
        RawJSON[("weather_data.json<br/>(原始預報 JSON)")]
    end

    subgraph S2 [階段 2: 資料解析 Data Parsing]
        P1["parse_weather.py<br/>解析巢狀 JSON 結構"]
        CleanData["結構化氣溫資料<br/>(全台 6 大區域 × 7 天預報)"]
    end

    subgraph S3 [階段 3: 資料庫存儲 Data Storage]
        DB["database.py<br/>SQLite 連線與重複檢核機制"]
        SQLite[("data.db<br/>Table: TemperatureForecasts")]
        Verify["SQL 查詢驗證<br/>(DISTINCT / 指定區域查詢)"]
    end

    subgraph S4 [階段 4: 前端展示 Presentation]
        App["app.py<br/>Streamlit 應用程式"]
        SelectUI["區域選擇下拉選單<br/>(st.selectbox)"]
        LineChart["一週最高/最低氣溫折線圖<br/>(MaxT vs MinT)"]
        DataTable["一週預報數據表格<br/>(Data Table)"]
        FoliumMap["進階加分項: 台灣氣溫分級地圖<br/>(Folium + Streamlit-Folium)"]
    end

    %% 資料流走向
    API -->|HTTP 200| F1
    F1 -->|儲存/傳遞| RawJSON
    RawJSON -->|讀取| P1
    P1 -->|萃取 MinT, MaxT, dataDate| CleanData
    CleanData -->|寫入| DB
    DB -->|建表與儲存| SQLite
    DB -.->|驗證| Verify
    
    %% 前端資料綁定 (強調：禁止直接連 API)
    SQLite ==>|SQL 讀取資料 (禁止前端直呼 API)| App
    App --> SelectUI
    SelectUI --> LineChart
    SelectUI --> DataTable
    App --> FoliumMap

    %% 樣式設定
    classDef highlight fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    class API,SQLite,App highlight;
```

---

## 2. 模組說明 (Modules)

| 檔案名稱 | 所屬階段 | 職責與功能說明 |
| :--- | :--- | :--- |
| [`fetch_weather.py`](fetch_weather.py) | 階段 1: 資料獲取 | 發送 HTTP GET 請求取得預報資料，存為 `weather_data.json`。具備無金鑰/離線時自動啟用模擬資料之容錯機制。 |
| [`parse_weather.py`](parse_weather.py) | 階段 2: 資料解析 | 解析巢狀 JSON，萃取全台 6 大區域（北部、中部、南部、東部、澎湖、金門馬祖）7 天預報（MinT, MaxT, dataDate）。 |
| [`database.py`](database.py) | 階段 3: 資料庫存儲 | 建立 SQLite `data.db` 與 `TemperatureForecasts` 表，具備防重複寫入機制 (`ON CONFLICT DO UPDATE`) 與 SQL 驗證查詢。 |
| [`main.py`](main.py) | 整合管線 | 一鍵式執行完整 ETL 流程 (`fetch` -> `parse` -> `database` -> `verify`)。 |
| [`app.py`](app.py) | 階段 4: 前端展示 | Streamlit 互動儀表板，**嚴格透過 SQL 自 SQLite 查詢**。提供區域切換、MaxT vs MinT 雙線折線圖、預報表格與 Folium 氣溫分級地圖。 |

---

## 3. 安裝與執行方式 (Quick Start)

### 3.1 安裝相依套件
```bash
pip install -r requirements.txt
```

### 3.2 執行 ETL 資料管線 (一鍵同步)
```bash
# 預設執行 (無 API Key 時自動以離線標準資料建庫)
python main.py

# 若具備中央氣象署 API 授權碼
python main.py --api-key YOUR_CWA_API_KEY
```

### 3.3 執行獨立資料庫驗證
```bash
python database.py --verify
```

### 3.4 啟動 Streamlit 視覺化儀表板
```bash
python -m streamlit run app.py
```
啟動後於瀏覽器開啟 `http://localhost:8501` 即可操作。
