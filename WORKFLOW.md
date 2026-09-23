專案結構建議 (Project Structure)PlaintextHW10_weather/
├── fetch_weather.py      # [階段 1] 呼叫中央氣象署 API，取得一週天氣預報 JSON 資料
├── parse_weather.py      # [階段 2] 解析巢狀 JSON，萃取 6 大分區 7 天的氣溫數據
├── database.py           # [階段 3] 建立 SQLite 資料庫與表格，寫入資料並執行驗證查詢
├── app.py                # [階段 4] 透過 Streamlit 讀取 SQLite，建立互動預報介面與地圖
├── data.db               # SQLite 本地資料庫檔案 (由 database.py 產生)
├── requirements.txt      # 專案相依套件清單
└── README.md             # 專案說明與執行指南
(參考作業建議之模組化分工結構)   核心工作流程圖 (End-to-End Workflow)[階段 0: 環境準備]
       │
       ▼
[階段 1: 取得資料 (fetch_weather.py)] ──(CWA API: F-A0010-001)──> 原始預報 JSON
       │
       ▼
[階段 2: 解析清洗 (parse_weather.py)] ──(Pandas/Dict 解析)───────> 清理後的氣溫資料 (6區 × 7天)
       │
       ▼
[階段 3: 資料庫存儲 (database.py)]    ──(SQLite 寫入與驗證)──────> data.db (TemperatureForecasts 表)
       │
       ▼
[階段 4: 前端互動 (app.py)]          ──(Streamlit + Folium)───> 下拉選單 / 氣溫折線圖 / 表格 / 地圖視覺化
       │
       ▼
[階段 5: 專案發佈與交付]              ──(Git & GitHub)─────────> 版本控管與作業繳交
分階段實作步驟階段 0：環境準備與套件安裝建立與啟用虛擬環境：   Bashpython -m venv venv
# Windows 啟動:
venv\Scripts\activate
# macOS/Linux 啟動:
source venv/bin/activate
安裝必要套件：   Bashpip install requests pandas streamlit folium streamlit-folium
階段 1：API 資料取得 (fetch_weather.py，佔比 20%)核心目標：透過個人的 CWA API Key 下載台灣六大區域一週天氣預報資料。   實作要點：使用開放資料 API 代號 F-A0010-001。   使用 requests.get() 攜帶 API Key 發出 GET 請求，取得 JSON 格式回傳值。   驗證 HTTP 狀態碼與資料完整性，加入 try-except 例外處理機制。   階段 2：JSON 解析與資料清理 (parse_weather.py，佔比 20%)核心目標：從多層巢狀結構中提取六大分區每日的最高溫（MaxT）與最低溫（MinT）。   實作要點：走訪路徑：records -> locations -> location[]，篩選包含北部地區、中部地區、南部地區、東北部地區、東部地區、東南部地區。   提取 weatherElement 中的 MinT（最低溫）與 MaxT（最高溫）及其對應日期（dataDate）。   將資料清理為結構化的列表或字典，並可透過 pandas 檢視轉換成果。   階段 3：SQLite 資料庫儲存與驗證 (database.py，佔比 20%)核心目標：將整理後的數據寫入本地 data.db，並設計避免重複寫入的防呆機制。   實作要點：建立資料表 TemperatureForecasts（包含 id、regionName、dataDate、minT、maxT）。   建立防重複插入機制（如寫入前清空舊資料，或設定唯一鍵）[cite: 1]。執行 SQL 查詢驗證成果：   SELECT DISTINCT regionName FROM TemperatureForecasts;   SELECT * FROM TemperatureForecasts WHERE regionName = '中部地區';   階段 4：Streamlit 互動介面開發 (app.py，佔比 40% + 加分項)核心目標：製作互動式 Web 儀表板（注意：規範嚴禁前端直接發送 API 請求，必須查詢 SQLite 資料庫）。   實作要點：資料查詢：前端透過 sqlite3 連接 data.db，並用 pandas.read_sql_query() 讀取所需資料。   下拉選單：實作 st.selectbox 供使用者切換六大區域。   折線圖與表格：使用圖表元件動態展示該區 7 天的最高溫/最低溫曲線與對應數據表格[cite: 1, 2]。進階地圖視覺化（Optional 加分項）：整合 folium 繪製台灣地圖，依各區日平均氣溫設定色塊或標記（<20°C 藍色、20-25°C 綠色、25-30°C 黃色、>30°C 紅色）。   階段 5：專案驗證、優化與交付[cite: 1, 2]   執行測試流程[cite: 2]：Bash# 1. 執行一次性後端管線處理
python fetch_weather.py
python parse_weather.py
python database.py

# 2. 啟動 Streamlit 儀表板
streamlit run app.py
版本控管：撰寫 README.md 說明與 requirements.txt，並將程式碼提交推播至 GitHub 遠端倉庫[cite: 1, 2]。
