# AIoT HW10: Taiwan Weather Forecast 系統實作成果與工作流程驗證 (Walkthrough)

本專案已使用**中央氣象署 (CWA) 官方 API 授權碼**，完整串接即時預報資料，經由 Python 進行 ETL 清洗、入庫 SQLite，最後於 Streamlit 與 Folium 建立互動式視覺化儀表板，並通過端到端測試與 GitHub 交付。

---

## 1. 系統整體架構與模組總覽 (Pipeline Architecture)

```mermaid
flowchart TD
    %% 階段定義
    subgraph S1 [階段 1: 資料獲取 Data Ingestion]
        API["中央氣象署 CWA Open Data API<br/>(資料集: F-D0047-091)"]
        F1["fetch_weather.py<br/>發送 HTTP GET 請求 (含 API Key)"]
        RawJSON[("weather_data.json<br/>(全台 22 縣市原始預報 JSON)")]
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
    F1 -->|儲存| RawJSON
    RawJSON -->|讀取| P1
    P1 -->|萃取 MinT, MaxT, dataDate| CleanData
    CleanData -->|寫入| DB
    DB -->|建表與儲存| SQLite
    DB -.->|驗證| Verify
    
    %% 前端資料綁定 (強調：禁止直接連 API)
    SQLite ==>|SQL 讀取資料 (嚴格禁止前端直接連 API)| App
    App --> SelectUI
    SelectUI --> LineChart
    SelectUI --> DataTable
    App --> FoliumMap

    %% 樣式設定
    classDef highlight fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    class API,SQLite,App highlight;
```

### 模組職責說明

| 階段 | 檔案名稱 | 核心功能與實作重點 |
| :--- | :--- | :--- |
| **階段 1** | [`fetch_weather.py`](fetch_weather.py) | 發送 HTTP GET 請求向 CWA API 抓取一週預報（支援 `--api-key` 或環境變數 `CWA_API_KEY`），存為 `weather_data.json`。 |
| **階段 2** | [`parse_weather.py`](parse_weather.py) | 解析巢狀 JSON，將全台 22 縣市氣溫資料依照地理分區彙整為 6 大區域（北部、中部、南部、東部、澎湖、金門馬祖）7 天之 `MinT`、`MaxT` 與 `dataDate`。 |
| **階段 3** | [`database.py`](database.py) | 建立 SQLite `data.db`（`TemperatureForecasts` 表），以 `UNIQUE(regionName, dataDate)` 實作 `ON CONFLICT DO UPDATE` 防重複寫入機制。 |
| **整合管線** | [`main.py`](main.py) | 一鍵式串聯 ETL 流程 (`Fetch -> Parse -> DB Upsert -> Verify`)。 |
| **階段 4** | [`app.py`](app.py) | **100% 透過 SQL 向 SQLite 查詢**。包含下拉區域選擇、指標卡片、Altair 雙線折線圖、7 天預報表格與 Folium 氣溫熱力分級地圖。 |

---

## 2. 真實 CWA API 串接紀錄 (Live CWA Ingestion)

- **API 授權金鑰**：已配置於安全環境變數（並存放於已加入 `.gitignore` 的 `.env`）。
- **CWA 端點處理**：
  - 檢測到歷史端點 `F-A0010-001` 已被官方下線（回傳 404）。
  - 管線自動平滑切換至現行全台縣市一週天氣預報資料集 **`F-D0047-091`**。
  - 成功向中央氣象署取得全台 22 縣市最新即時預報 JSON 資料。
- **資料庫入庫**：
  - 寫入 SQLite `data.db` 的 `TemperatureForecasts` 表。
  - 經 SQL 驗證：共 42 筆真實氣象預報紀錄，DISTINCT 涵蓋全台 6 大區域。

---

## 3. 北部地區真實氣溫預報數據範例

| 預報日期 | 最低溫 (MinT) | 最高溫 (MaxT) | 日溫差 | 氣候概況 |
| :---: | :---: | :---: | :---: | :---: |
| 2026-09-23 | 23.3 °C | 29.3 °C | 6.0 °C | 舒適偏暖 |
| 2026-09-24 | 23.7 °C | 29.4 °C | 5.7 °C | 舒適偏暖 |
| 2026-09-25 | 24.1 °C | 29.6 °C | 5.5 °C | 舒適偏暖 |
| 2026-09-26 | 24.3 °C | 29.4 °C | 5.1 °C | 舒適偏暖 |
| 2026-09-27 | 23.9 °C | 29.9 °C | 6.0 °C | 舒適偏暖 |
| 2026-09-28 | 24.3 °C | 29.4 °C | 5.1 °C | 舒適偏暖 |
| 2026-09-29 | 24.9 °C | 29.6 °C | 4.7 °C | 舒適偏暖 |

---

## 4. 驗證結果與防重複寫入測試 (Verification & Idempotency)

執行 `python main.py` 進行資料庫寫入與驗證結果如下：

```text
=================================================================
[START] 啟動 AIoT HW10 台灣氣象預報系統 ETL 流程
=================================================================

[階段 1: 資料獲取 Data Ingestion]
[INFO] 正在向中央氣象署 API 發送請求: F-A0010-001 ...
[WARN] 資料集 F-A0010-001 回傳 404 (官方已改版)。自動切換至現行縣市一週預報資料集 F-D0047-091 ...
[SUCCESS] 成功從 CWA API (F-D0047-091) 取得全台縣市最新一週即時氣象資料！已寫入 weather_data.json

[階段 2: 資料解析 Data Parsing]
[INFO] 偵測到全台 22 縣市詳細資料，依地理分區彙整為 6 大區域 7 天氣溫預報...
[SUCCESS] 解析完成！共提取 42 筆結構化氣溫預報資料。

[階段 3: 資料庫存儲 Data Storage]
[INFO] 資料庫初始化完成，已確認資料表 TemperatureForecasts 存在 (data.db)
[SUCCESS] 成功寫入/更新 42 筆氣溫預報資料至資料庫。

[階段 3.1: 資料庫驗證]
============================================================
[VERIFY] 開始執行 SQLite 資料庫 (data.db) 驗證流程
============================================================
[STATS] 總紀錄數: 42 筆 (6 區 × 7 天)
[STATS] DISTINCT 區域 (6 個): 中部地區, 北部地區, 南部地區, 東部地區, 澎湖地區, 金門馬祖地區
[SUCCESS] 資料庫存儲與防重複機制驗證通過！
============================================================

[FINISH] ETL 流程順利完成！資料已就緒，可啟動 Streamlit 前端 (app.py) 進行展示。
=================================================================
```

- **防重複寫入驗證**：多次重複執行 `main.py`，資料庫總筆數皆穩定維持 42 筆，證實 `ON CONFLICT` 防重複寫入機制正常運作。
- **前端獨立性檢驗**：Streamlit 應用程式完全透過 `database.py` 向本地 SQLite 查詢，未向外部 CWA API 發送任何 HTTP 請求。

---

## 5. GitHub 同步狀態

所有最新實作程式碼、真實預報 JSON 與資料庫皆已提交並推播至遠端 GitHub：
- **倉庫網址**：`https://github.com/pingu7115/AIoT_L3_CWA_HW1.git`
- **安全防護**：真實 API Key 存放於已加入 `.gitignore` 的 `.env`，不外流至公開代碼庫。

---

## 6. 儀表板啟動與檢視

目前 Streamlit 應用程式持續在背景運行中，可於瀏覽器開啟：
👉 **http://localhost:8501**
