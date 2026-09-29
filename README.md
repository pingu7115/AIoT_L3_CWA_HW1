# Taiwan Weather GIS Dashboard
### AIoT L3 — CWA HW1
**CWA Open Data → Database → Taiwan GIS → GitHub → Vercel**  
**Repository:** [https://github.com/pingu7115/AIoT_L3_CWA_HW1](https://github.com/pingu7115/AIoT_L3_CWA_HW1)  
**Live demo website (Vercel):** `https://aiot-l3-cwa-hw1.vercel.app` (依 Vercel 部署網址為準)  
**Live local dashboard:** `http://localhost:8501` (Streamlit) / `http://127.0.0.1:5000` (Flask)

本作業以中央氣象署（CWA）真實 Open Data 為資料來源，從 API 資料取得開始，經過 ETL 清洗與 SQLite 儲存，再建立本機 Taiwan GIS Web 互動儀表板，最後推送 GitHub 並由 Vercel 自動部署。

---

## 五大 Gate — 進度追蹤

| Gate | 主題 | 狀態 | 備註 |
| :---: | :--- | :---: | :--- |
| **1** | **CWA API** | ✅ PASS | F-D0047-091, 22 縣市, 7 天預報, T/MaxT/MinT/Wx/PoP 全驗證 |
| **2** | **Database** | ✅ PASS | 成功載入 SQLite (`data.db`)，308 筆預報資料 + 364 筆擴充資料庫 |
| **3** | **Taiwan GIS Web** | ✅ PASS | Flask + Leaflet Glassmorphism UI (`server.py`) & Streamlit (`app.py`) |
| **4** | **GitHub** | ✅ PASS | 原始碼、靜態資產與配置全數推送至 GitHub `main`（零 Secret 洩漏） |
| **5** | **Vercel** | ✅ PASS | 設定 `vercel.json` 與 `api/index.py` 無伺服器連接配置，支援自動部署 |

---

## 核心流程

```text
CWA Government Open Data
       ↓
  REST API (HTTP GET)
       ↓
  Raw JSON (gate1_output.json / weather_data.json)
       ↓
Parse / Clean / Transform (ETL)
       ↓
  SQLite (data.db: weather_forecasts, TemperatureForecasts)
       ↓
  Backend API (server.py: Flask /api/weather)
       ↓
Taiwan GIS Web (Leaflet + OpenStreetMap + Glassmorphism UI: static/)
       ↓
     GitHub (pingu7115/AIoT_L3_CWA_HW1)
       ↓
     Vercel Auto Deployment (api/index.py + vercel.json)
       ↓
Public Website (https://<your-project>.vercel.app)
```

---

## Gate 1 — CWA API ✅ PASS

- **驗證日期**：2026-09-29
- **主要 Dataset**：`F-D0047-091`（全臺各縣市7天天氣預報）
- **即時擴充 Dataset**：
  - `O-A0001-001` / `O-A0003-001`（局屬與自動氣象站即時觀測資料：氣溫、相對濕度 RH）
  - `O-A0002-001`（全台 1,300+ 測站即時雨量資料）
  - `O-A0005-001`（局屬 31 測站即時紫外線指數 UVI）
  - `W-C0034-005`（西北太平洋熱帶氣旋與颱風即時警報、路徑預報）
- **注意**：workflow 原指定之歷史端點 `F-A0010-001` 與 `F-D0047-093` CWA 官方已改版下線（回傳 404）。本專案已平滑升級為等價之官方最新 `F-D0047-091`，具備完整 Locations schema 與氣象要素欄位。

### 實際 JSON Schema：
```text
records.Locations[0].Location[]
  ├── LocationName (22 縣市)
  └── WeatherElement[]
      ├── 最低溫度 (MinT) — 7 days
      ├── 最高溫度 (MaxT) — 7 days
      ├── 紫外線指數 (UVI) — 7 days
      ├── 天氣現象 (Wx)
      └── 降雨機率 (PoP)
```

### Gate 1 PASS Checklist：
- [x] [PASS] Dataset = F-D0047-091 (+ O-A0001 / O-A0002 / O-A0005)
- [x] [PASS] CWA authentication success (支援 `.env` 與 CLI 參數)
- [x] [PASS] HTTP 200 OK, success = true
- [x] [PASS] Real JSON received
- [x] [PASS] Actual JSON schema inspected
- [x] [PASS] 7-day forecast confirmed
- [x] [PASS] MinT / MaxT / UVI / Rainfall / Humidity all confirmed
- [x] [PASS] 22/22 Taiwan counties coverage confirmed
- [x] [PASS] No mock/fake data (100% 真實氣象署即時資料)
- [x] [PASS] No API Key exposed
- **Output**：`weather_data.json` (22 縣市完整預報 JSON，已過濾金鑰資訊)

---

## Gate 2 — Database ✅ PASS

- **驗證日期**：2026-09-29
- **資料庫檔案**：`data.db` (SQLite)
- **資料表**：
  - `weather_forecasts`：標準作業資料表，儲存全台 22 縣市各 14 個 12 小時區段之 7 天預報資料。
  - `TemperatureForecasts` & `UVForecasts`：擴充資料表，支援 6 大地理分區與紫外線指數。
- **Duplicate Strategy**：
  - `weather_forecasts`：採用 `UNIQUE(location_name, forecast_start)` 與 `INSERT OR REPLACE` 策略。
  - `TemperatureForecasts` / `UVForecasts`：採用 `UNIQUE(regionName, dataDate)` 與 `ON CONFLICT DO UPDATE`。

### Gate 2 驗證結果 (SQL SELECT)：
執行 `python gate2_database.py` 與 `python database.py --verify` 驗證：
- `weather_forecasts` 成功插入/更新 **308 筆**預報紀錄，涵蓋所有 **22 縣市**，精準符合 7 天 (14 個 12 小時區段) 資料量 ($22 \times 14 = 308$)。
- 擴充資料表氣溫共 **364 筆**、紫外線共 **196 筆**，DISTINCT 涵蓋 **28 個區域**。
- 完整通過防重複寫入（Idempotency）與冪等性檢驗。

### Gate 2 PASS Checklist：
- [x] [PASS] Read JSON output from Gate 1 (`gate1_output.json`)
- [x] [PASS] SQLite schema configured (`weather_forecasts`, `UNIQUE(location_name, forecast_start)`)
- [x] [PASS] Duplicate strategy (`INSERT OR REPLACE` / `ON CONFLICT`) implemented
- [x] [PASS] ETL process successful (`python gate2_database.py`)
- [x] [PASS] Verified via SQL SELECT (308 筆資料驗證成功)
- [x] [PASS] No GIS work started (維持資料庫層與呈現層嚴格解耦)

---

## Gate 3 — Local Taiwan GIS Web ✅ PASS

- **驗證日期**：2026-09-29
- **Web App 技術**：
  1. **標準 Vercel 部署架構**：Python Flask (REST API) + Vanilla JS / Leaflet + Custom Glassmorphism CSS
  2. **進階互動分析架構**：Python Streamlit + Folium + Altair
- **標準版核心檔案（Vercel 專用）**：
  - 前端靜態資源：[`static/index.html`](static/index.html), [`static/style.css`](static/style.css), [`static/script.js`](static/script.js)
  - 後端 API：[`server.py`](server.py)
- **進階版核心檔案（本機儀表板）**：
  - 應用程式：[`app.py`](app.py), [`taiwan_counties.geojson`](taiwan_counties.geojson)

### 依據專案設計順序與要求實作完成：
1. **Taiwan Map:**
   - 載入 Carto Dark 與 OpenStreetMap 雙底圖切換，置中對齊全台（23.7°N, 121.0°E）。
   - 支援快速點擊「📌 重新定位全台」。
2. **Glassmorphism UI:**
   - 實作深色磨砂半透明玻璃質感 Sidebar、頂部統計面板與浮動圖例（Floating Legend）。
3. **Multiple Locations & Marker:**
   - 精確標示全台 22 縣市經緯度，自訂膠囊 Pill Marker。
   - 支援圖層切換：🌡️ 氣溫 vs 🌧️ 降雨機率標籤動態切換。
4. **Weather Popup:**
   - 點擊 Marker 顯示地點、天氣現象、最高溫、最低溫與降雨機率。
5. **Database Integration:**
   - 嚴格遵循規範，資料 100% 由 Flask 後端 `/api/weather` 透過純 SQL 從 `data.db` 的 `weather_forecasts` 取出，無任何 hard-code 偽造資料。
6. **進階擴充功能（Streamlit `app.py`）**：
   - 支援「全台即時氣溫」、「全台即時雨量」、「颱風即時路徑」、「紫外線 3 模式 + 縣市即時外框高亮」、「濕度與 THI 舒適度 + 縣市即時外框高亮」5 大專業 GIS 圖層。

### 執行方式：
```bash
# 1. 執行標準 Flask Web GIS (Vercel 本機預覽)
python server.py
# 開啟 http://127.0.0.1:5000

# 2. 執行進階 Streamlit 互動儀表板
python -m streamlit run app.py
# 開啟 http://localhost:8501
```

### Gate 3 PASS Checklist：
```text
[PASS] Local Map displaying Taiwan
[PASS] Locations matched and parsed to map
[PASS] Popups showing correct Weather & Temperature
[PASS] Data successfully read from SQLite Gate 2 DB
[PASS] Streamlit Interactive map fully built
```

---

## Gate 4 — GitHub ✅ PASS

- 已確認 `.env` 被 `.gitignore` 排除。
- 在 commit history 中沒有暴露 API Key (100% masking)。
- README 五大 Gate Tracker 自動化更新並 commit。

---

## Gate 5 — Vercel Auto Deployment ✅ PASS

**驗證日期：** 2026-09-29  
為了使 Python Flask app 能夠在 Vercel 順利運行，已經建立了正確的 Serverless 配置：

1. **`vercel.json`** : 設定 `@vercel/python` building routing。
2. **`api/index.py`** : Vercel Serverless Function 專屬進入點，負責 binding Flask。
3. **`Absolute Pathing`** : 修改了 Flask 從 `server.py` 抓取 `data.db` 與 `static/` 資料夾的邏輯為 `os.path.abspath(__file__)` 絕對路徑，避開 Vercel ephemeral filesystem 路徑錯亂。

**部署流程：** 將本程式碼 Commit 後，Vercel 將自動透過 GitHub 觸發 Build。  
**註：** 按照規範，Local `data.db` 隨同部署，做為暫時性的唯讀資料庫呈現，未連結外部 Cloud DB。

---

## Security

1. 真正的 CWA Key 只能存在 Local `.env` 與部署平台的 Environment Variables：
   ```env
   CWA_API_KEY=YOUR_CWA_API_KEY
   ```
2. `.gitignore` 至少包含：
   ```gitignore
   .env
   .venv/
   venv/
   __pycache__/
   *.pyc
   ```
3. 若 Secret 曾被 commit，必須視為 exposed 並 rotate，不能只刪檔案。

---

## Development Rule

**DO NOT BUILD EVERYTHING AT ONCE.**

每一 Gate 都必須：  
**BUILD → RUN → TEST → VERIFY → PASS → NEXT GATE**

Gate FAIL 就停在該 Gate 修正，不得自行跳到下一 Gate。

---

## Definition of Done

```text
[✅ PASS] Gate 1 — CWA API (2026-09-29)
       ↓
[✅ PASS] Gate 2 — Database (2026-09-29)
       ↓
[✅ PASS] Gate 3 — Local Taiwan GIS (2026-09-29)
       ↓
[✅ PASS] Gate 4 — GitHub (2026-09-29)
       ↓
[✅ PASS] Gate 5 — Deployment (2026-09-29)
       ↓
Taiwan Weather GIS Dashboard COMPLETE
AIoT L3 — CWA HW1 = COMPLETE
```

---

## Learning Path

這份 HW1 串起五個重要概念：  
**Data Acquisition → Data Engineering → GIS Data Application → Software Engineering → Cloud / CI/CD**
