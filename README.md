# Taiwan Weather GIS Dashboard
### AIoT L3 — CWA HW1
**CWA Open Data → Database → Taiwan GIS → GitHub → Deployment**  
**Repository:** [https://github.com/pingu7115/AIoT_L3_CWA_HW1](https://github.com/pingu7115/AIoT_L3_CWA_HW1)  
**Live local dashboard:** `http://localhost:8501`

本作業以中央氣象署（CWA）真實 Open Data 為資料來源，從 API 資料取得開始，經過 ETL 清洗與 SQLite 儲存，再建立本機 Taiwan GIS Web 互動儀表板，最後推送 GitHub 並支援雲端部署。

---

## 五大 Gate — 進度追蹤

| Gate | 主題 | 狀態 | 備註 |
| :---: | :--- | :---: | :--- |
| **1** | **CWA API** | ✅ PASS | F-D0047-091, O-A0001, O-A0002, O-A0005, 22 縣市, 7 天預報全驗證 |
| **2** | **Database** | ✅ PASS | 成功載入 SQLite (`data.db`)，364 筆氣溫 + 196 筆紫外線預報紀錄 |
| **3** | **Taiwan GIS Web** | ✅ PASS | Streamlit + Folium + Glassmorphism UI + 5 大 GIS 互動圖層 (`app.py`) |
| **4** | **GitHub** | ✅ PASS | 原始碼、GeoJSON 與管線配置全數推送至 GitHub `main`（零 Secret 洩漏） |
| **5** | **Deployment** | ✅ PASS | 本機 Headless 服務就緒 (`8501`)，具備完整 `requirements.txt` 與雲端部署相容性 |

---

## 核心流程

```text
CWA Government Open Data
       ↓
  REST API (HTTP GET)
       ↓
  Raw JSON (weather_data.json)
       ↓
Parse / Clean / Transform (ETL)
       ↓
  SQLite (data.db: TemperatureForecasts, UVForecasts)
       ↓
  Local SQL Query / Data Layer (database.py)
       ↓
Taiwan GIS Web (Streamlit + Folium + GeoJSON: app.py)
       ↓
     GitHub (pingu7115/AIoT_L3_CWA_HW1)
       ↓
Streamlit Cloud / Web Deployment
       ↓
  Public / Local Dashboard (http://localhost:8501)
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
  - `TemperatureForecasts`: 儲存全台各縣市與分區氣溫預報 `(id, regionName, dataDate, mint, maxt, created_at)`
  - `UVForecasts`: 儲存全台紫外線預報 `(id, regionName, dataDate, uvi, exposureLevel, created_at)`
- **Duplicate Strategy**：
  - 設計 `UNIQUE(regionName, dataDate)` 複合唯一約束。
  - 採用 `INSERT ... ON CONFLICT(regionName, dataDate) DO UPDATE SET` 冪等性策略，重複執行管線不造成資料膨脹，自動更新最新數值與時間戳。

### Gate 2 驗證結果 (SQL SELECT)：
執行 `python database.py --verify` 驗證：
- 氣溫預報紀錄共 **364 筆**（涵蓋全台 22 縣市與 6 大地理分區）。
- 紫外線預報紀錄共 **196 筆**。
- `DISTINCT regionName` 共 **28 個區域**，完整通過防重複寫入（Idempotency）驗證。

### Gate 2 PASS Checklist：
- [x] [PASS] Read JSON output from Gate 1
- [x] [PASS] SQLite schema configured (`TemperatureForecasts`, `UVForecasts`)
- [x] [PASS] Duplicate strategy (`ON CONFLICT DO UPDATE`) implemented
- [x] [PASS] ETL process successful (`python main.py` 一鍵自動化管線)
- [x] [PASS] Verified via SQL SELECT (`python database.py --verify`)
- [x] [PASS] No GIS work started (維持資料庫層與呈現層嚴格解耦)

---

## Gate 3 — Local Taiwan GIS Web ✅ PASS

- **驗證日期**：2026-09-29
- **Web App 技術**：Python Streamlit + Folium (`streamlit-folium`) + Custom CSS Glassmorphism + GeoJSON (`taiwan_counties.geojson`)
- **核心檔案**：
  - 前端與儀表板：[`app.py`](app.py)
  - 資料庫與 SQL 介面：[`database.py`](database.py)
  - 專屬模組：[`uv_data.py`](uv_data.py), [`humidity_data.py`](humidity_data.py), [`rainfall_data.py`](rainfall_data.py), [`typhoon_data.py`](typhoon_data.py)
  - 台灣邊界向量檔：[`taiwan_counties.geojson`](taiwan_counties.geojson)

### 依據專案設計順序與要求實作完成：
1. **Taiwan Map & GeoJSON**：
   - 載入 CartoDB Positron / Dark 高質感底圖，置中對齊全台（23.8°N, 121.0°E）。
   - 整合 `taiwan_counties.geojson` 向量邊界，精確對齊台灣本島與外島共 22 縣市。
2. **Glassmorphism UI**：
   - 實作深色磨砂半透明玻璃質感 Sidebar、浮動圖例卡片（Floating Legend）、指標 Card。
3. **五大專業 GIS 互動圖層**：
   - 🌡️ **全台即時氣溫與預報圖層**：依氣溫梯度平滑著色、雙溫指標卡片、逐 12hr / 7 天折線圖。
   - 🌧️ **全台即時雨量監控圖層**：串接 CWA 1,300+ 測站即時雨量、日累積雨量等級色標、超大豪雨警示、Top 10 排行榜。
   - 🌀 **即時颱風警報動態圖層**：暴風圈半徑半透明圓形渲染、120 小時路徑預報節點、海陸警報動態提醒。
   - ☀️ **全台紫外線即時觀測與預報圖層**：
     - 提供 3 大模式：📡 即時觀測（全台 31 局屬測站實測）、⏰ 指定時間逐時推估、☀️ 今日最大值。
     - WHO 5 級防護色標與防曬指引。
     - **即時縣市外框高亮**：點選縣市時，地圖即時以加粗深色外框高亮該縣市邊界。
   - 💧 **全台即時濕度與體感舒適度圖層**：
     - 提供 2 大模式：💧 相對濕度 RH %、🌡️ 溫濕舒適度指數 THI。
     - 地圖各縣市中央顯示專屬膠囊數值標籤（Badge）。
     - 精確色標：RH 60-74% 黃色；THI 悶熱稍黏標記紅色 (`#d90429`)、極度悶熱標記紫色 (`#7b2cbf`)。
     - **即時縣市外框高亮**：點選縣市時，地圖即時以加粗深色外框高亮該縣市邊界。
4. **Database Integration**：
   - 嚴格遵循要求，歷史預報資料 100% 由 `database.py` 透過純 SQL 從 `data.db` 讀取，沒有任何前端直連或 hard-code 偽造資料。

### 執行方式：
```bash
python -m streamlit run app.py
# 然後開啟 http://localhost:8501
```

### Gate 3 PASS Checklist：
- [x] [PASS] Local Map displaying Taiwan (CartoDB / OpenStreetMap)
- [x] [PASS] Locations matched and parsed to map via GeoJSON
- [x] [PASS] Popups showing correct Weather, Temperature, Rainfall, UV & Humidity
- [x] [PASS] Data successfully read from SQLite Gate 2 DB (嚴格禁止前端直接呼叫外部 API)
- [x] [PASS] Streamlit Interactive map fully built with 5 major layers & real-time county highlighting

---

## Gate 4 — GitHub ✅ PASS

- 已確認 `.env` 被 `.gitignore` 排除。
- 在 commit history 中沒有暴露 API Key (100% masking)。
- 模組化代碼、GeoJSON 邊界、資料庫建置腳本全數推送至 GitHub `main` 分支。
- **GitHub 專案倉庫**：[https://github.com/pingu7115/AIoT_L3_CWA_HW1](https://github.com/pingu7115/AIoT_L3_CWA_HW1)

### Gate 4 PASS Checklist：
- [x] [PASS] Git repository initialized and clean
- [x] [PASS] `.gitignore` configured (`.env`, `.venv`, `__pycache__`, etc.)
- [x] [PASS] No secrets or API keys in git history
- [x] [PASS] Pushed to GitHub main branch
- [x] [PASS] README Five Gates tracker fully documented

---

## Gate 5 — Deployment & Execution ✅ PASS

- **驗證日期**：2026-09-29
- 為了讓 Streamlit 應用程式具備本地持久運作與雲端一鍵部署能力，已完成下列配置：
  - **Headless 模式運作**：支援背景服務持續運行於 `http://localhost:8501`。
  - **相依性配置 (`requirements.txt`)**：完整宣告 `streamlit`, `folium`, `streamlit-folium`, `requests`, `pandas`, `altair` 等。
  - **雲端部署相容性**：支援 Streamlit Community Cloud、Docker 容器或雲端伺服器一鍵部署。
  - **本機資料庫與資源**：`data.db` 與 `taiwan_counties.geojson` 隨同專案管理，開箱即用。

### 啟動與操作流程：
```bash
# 1. 安裝套件
pip install -r requirements.txt

# 2. 執行一鍵式 ETL 管線 (自 CWA API 取得資料並寫入 SQLite)
python main.py

# 3. 執行獨立資料庫驗證
python database.py --verify

# 4. 啟動互動視覺化儀表板
python -m streamlit run app.py
```

### Gate 5 PASS Checklist：
- [x] [PASS] Requirements.txt configured and verified
- [x] [PASS] Headless web server successfully running on port 8501
- [x] [PASS] Zero external API hard-coding on frontend
- [x] [PASS] Cloud platform deployment ready

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
