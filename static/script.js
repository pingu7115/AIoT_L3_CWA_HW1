/**
 * Taiwan Weather GIS Dashboard - Interactive Application Logic
 * Integrates 5 GIS Layers: Temperature, Humidity & THI, UV Index, Rainfall, Typhoon
 * Built with Leaflet, Chart.js, GeoJSON & CWA Open Data
 */

// =============================================================================
// 1. Map Initialization (Watermark-free Basemaps)
// =============================================================================
const map = L.map('map', {
    zoomControl: false,
    minZoom: 6,
    maxZoom: 18
}).setView([23.7, 120.95], 7.5);

L.control.zoom({ position: 'bottomleft' }).addTo(map);

// Watermark-free Base Tiles:
// Esri World Dark Gray Canvas: crisp, sleek, 100% free and NO watermark!
const darkTiles = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
    maxZoom: 16
});

const streetTiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
});

darkTiles.addTo(map); // Default
let currentBase = 'dark';

// Base map switchers
document.getElementById('btn-base-dark').addEventListener('click', () => {
    map.removeLayer(streetTiles);
    darkTiles.addTo(map);
    document.getElementById('btn-base-dark').classList.add('active');
    document.getElementById('btn-base-street').classList.remove('active');
    currentBase = 'dark';
});

document.getElementById('btn-base-street').addEventListener('click', () => {
    map.removeLayer(darkTiles);
    streetTiles.addTo(map);
    document.getElementById('btn-base-street').classList.add('active');
    document.getElementById('btn-base-dark').classList.remove('active');
    currentBase = 'street';
});

document.getElementById('btn-recenter').addEventListener('click', () => {
    map.flyTo([23.7, 120.95], 7.5, { duration: 1.2 });
    document.getElementById('county-select').value = 'ALL';
    clearHighlight();
    updateDashboard();
});

// Marker Layer Group & Highlight Layer
const markerGroup = L.layerGroup().addTo(map);
const highlightGroup = L.layerGroup().addTo(map);
const typhoonGroup = L.layerGroup().addTo(map);

let showLabels = true;
document.getElementById('toggle-marker-labels').addEventListener('change', (e) => {
    showLabels = e.target.checked;
    renderCurrentLayer();
});

// =============================================================================
// 2. Global State & Data Store
// =============================================================================
let activeTab = 'temp';       // 'temp' | 'humidity' | 'uv' | 'rain' | 'typhoon'
let humidityMode = 'rh';      // 'rh' | 'thi'
let uvMode = 'realtime';      // 'realtime' | 'hourly' | 'max'
let uvHour = 12;
let selectedCounty = 'ALL';
let selectedTyphoonTarget = 'live_cwa';

// In-memory instant caches (eliminates switching lag completely)
const uvDataCache = {
    bundleLoaded: false,
    realtime: null,
    max: null,
    hourly: {}
};
const typhoonCache = {};

let weatherData = [];         // from /api/weather
let humidityData = null;      // from /api/humidity
let uvData = null;            // from /api/uv
let rainfallData = null;      // from /api/rainfall
let typhoonData = null;       // from /api/typhoon
let geojsonData = null;       // from /api/geojson
let countyGeoJsonMap = {};    // { countyName: feature }
let forecastChart = null;     // Chart.js instance

// Standard 22 County Coordinates
const COORDINATES = {
    "臺北市": [25.0330, 121.5654], "新北市": [25.0112, 121.4617],
    "基隆市": [25.1287, 121.7397], "桃園市": [24.9937, 121.3009],
    "新竹市": [24.8138, 120.9675], "新竹縣": [24.8385, 121.0177],
    "苗栗縣": [24.5601, 120.8234], "臺中市": [24.1477, 120.6736],
    "彰化縣": [24.0820, 120.5385], "南投縣": [23.9037, 120.6698],
    "雲林縣": [23.7092, 120.4313], "嘉義市": [23.4800, 120.4491],
    "嘉義縣": [23.4518, 120.2554], "臺南市": [22.9998, 120.2268],
    "高雄市": [22.6272, 120.3014], "屏東縣": [22.6719, 120.4879],
    "宜蘭縣": [24.7570, 121.7408], "花蓮縣": [23.9871, 121.6015],
    "臺東縣": [22.7583, 121.1444], "澎湖縣": [23.5711, 119.5793],
    "金門縣": [24.4297, 118.3205], "連江縣": [26.1505, 119.9328]
};

// =============================================================================
// 3. Color Scales & Categorization (Exact User Specifications)
// =============================================================================
function getTempColor(t) {
    if (t >= 32) return '#ef4444';
    if (t >= 28) return '#f59e0b';
    if (t >= 24) return '#10b981';
    if (t >= 20) return '#0ea5e9';
    return '#3b82f6';
}

function getHumidityColor(rh) {
    if (rh < 50) return '#38bdf8';            // 偏乾 (藍)
    if (rh <= 59) return '#10b981';           // 舒適 (綠)
    if (rh <= 74) return '#e5a93c';           // 略偏潮濕 (黃色 - user requested)
    return '#ef4444';                         // 潮濕悶濁 (紅)
}

function getTHIColor(thi) {
    if (thi < 65) return '#0284c7';           // 寒冷偏涼 (深藍)
    if (thi < 70) return '#0ea5e9';           // 清涼舒適 (天藍)
    if (thi < 75) return '#10b981';           // 稍暖適中 (綠)
    if (thi < 80) return '#d90429';           // 悶熱稍黏 (紅色 - user requested)
    return '#7b2cbf';                         // 極度悶熱 (紫色 - user requested)
}

function getUVColor(uvi) {
    if (uvi === null || uvi === undefined) return '#94a3b8';
    if (uvi <= 2) return '#2b82d9';           // 微量 (藍)
    if (uvi <= 5) return '#2a9d8f';           // 中量 (綠)
    if (uvi <= 7) return '#e5a93c';           // 高量 (黃)
    if (uvi <= 10) return '#c94a4a';          // 過量 (紅)
    return '#7209b7';                         // 危險 (紫)
}

function getRainColor(r) {
    if (r >= 80) return '#3b82f6';
    if (r >= 50) return '#0ea5e9';
    if (r >= 20) return '#10b981';
    return '#94a3b8';
}

// CWA 官方太陽天頂角物理衰減公式 (計算 06:00 ~ 18:00 逐時強度)
function getSolarUvFactor(hourFloat) {
    if (hourFloat < 6.0 || hourFloat >= 18.0) return 0.0;
    const lat = 23.5 * Math.PI / 180.0;
    const decl = -2.5 * Math.PI / 180.0;
    const w = 15.0 * (hourFloat - 11.9) * Math.PI / 180.0;
    const cosZ = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(w);
    if (cosZ <= 0.05) return 0.0;
    const cosNoon = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl);
    const factor = Math.pow(cosZ / cosNoon, 1.4);
    return Math.max(0.0, Math.min(1.0, factor));
}

function getHourDescription(h) {
    const map = {
        6: '清晨日出 · 0.0 UVI',
        7: '晨間初昇 · 1.8 UVI',
        8: '上班通勤 · 4.3 UVI',
        9: '陽光漸強 · 6.9 UVI',
        10: '上午強光 · 9.1 UVI',
        11: '正午臨近 · 10.6 UVI',
        12: '正午最大 · 11.0 UVI',
        13: '午後強烈 · 10.4 UVI',
        14: '午後斜照 · 8.8 UVI',
        15: '午後漸弱 · 6.4 UVI',
        16: '傍晚前夕 · 3.8 UVI',
        17: '日落黃昏 · 1.0 UVI',
        18: '日落暮色 · 0.0 UVI'
    };
    return map[h] || `${h}:00 逐時推估`;
}

function getUvCategoryMeta(calcUv) {
    if (calcUv <= 2) {
        return {
            level: "微量級 (低)",
            color: "#2b82d9",
            icon: "🟢",
            sunburn_time: "曬傷時間約 60 分鐘以上",
            advice: "外出活動安全無虞，敏感膚質可視需要配戴遮陽帽或墨鏡。",
            spf_advice: "SPF15+"
        };
    } else if (calcUv <= 5) {
        return {
            level: "中量級 (中等)",
            color: "#2a9d8f",
            icon: "🟡",
            sunburn_time: "曬傷時間約 30 至 45 分鐘",
            advice: "外出建議塗抹防曬乳、戴遮陽帽或撐陽傘；避免長時間直曬。",
            spf_advice: "SPF15-30"
        };
    } else if (calcUv <= 7) {
        return {
            level: "高量級 (警戒)",
            color: "#e5a93c",
            icon: "🟠",
            sunburn_time: "曬傷時間約 20 至 30 分鐘",
            advice: "上午 10 時至下午 2 時盡量減少戶外曝曬，外出必備防曬乳與遮陽傘。",
            spf_advice: "SPF30+ / PA+++"
        };
    } else if (calcUv <= 10) {
        return {
            level: "過量級 (極高)",
            color: "#c94a4a",
            icon: "🔴",
            sunburn_time: "曬傷時間約 15 至 20 分鐘",
            advice: "紫外線強度極高！中午期間盡量避免外出，出門需全面防曬。",
            spf_advice: "SPF50+ / PA++++"
        };
    } else {
        return {
            level: "危險級 (極端危險)",
            color: "#7209b7",
            icon: "🟣",
            sunburn_time: "曝曬 10 至 15 分鐘即可能曬傷",
            advice: "危險級強烈曝曬！極易造成皮膚灼傷，請盡量待在室內陰涼處。",
            spf_advice: "SPF50+ / PA++++"
        };
    }
}

// 本地即時計算逐時 UV (0ms 零延遲，徹底消除卡頓)
function computeHourlyUvData(hour) {
    if (uvDataCache.hourly[hour]) {
        return uvDataCache.hourly[hour];
    }
    const factor = getSolarUvFactor(hour);
    const baseStations = (uvDataCache.max && uvDataCache.max.stations) || (uvData && uvData.stations) || [];
    const stations = [];
    const counties = {};

    baseStations.forEach(s => {
        const origPeak = s.uv_index || 0.0;
        let calcUv = Math.round(origPeak * factor);
        if (hour >= 18 || hour <= 6) calcUv = 0;
        else if (hour === 17 && calcUv > 1) calcUv = 1;

        const cat = getUvCategoryMeta(calcUv);
        const stObj = {
            ...s,
            uv_index: calcUv,
            display_val: String(calcUv),
            level: cat.level,
            color: cat.color,
            icon: cat.icon,
            sunburn_time: cat.sunburn_time,
            advice: cat.advice,
            spf_advice: cat.spf_advice
        };
        stations.push(stObj);

        const cname = s.county;
        if (cname) {
            if (!counties[cname] || calcUv > counties[cname].uvi) {
                counties[cname] = {
                    regionName: cname,
                    uvi: calcUv,
                    exposureLevel: cat.level,
                    color: cat.color,
                    icon: cat.icon,
                    sunburn_time: cat.sunburn_time,
                    advice: cat.advice,
                    spf_advice: cat.spf_advice,
                    primary_station: s.name,
                    primary_town: s.town || '',
                    stations: [stObj]
                };
            } else {
                counties[cname].stations.push(stObj);
            }
        }
    });

    const sorted = [...stations].sort((a, b) => b.uv_index - a.uv_index);
    const maxSt = sorted[0];
    const maxUv = maxSt ? maxSt.uv_index : 0;
    const avgUv = stations.length > 0 ? +(stations.reduce((a, b) => a + b.uv_index, 0) / stations.length).toFixed(1) : 0;

    const padH = String(hour).padStart(2, '0') + ':00';
    const dateStr = uvDataCache.max && uvDataCache.max.obs_time ? uvDataCache.max.obs_time.substring(0, 10) : '';
    const res = {
        mode: 'hourly',
        mode_title: `${padH} 逐時推估`,
        hour: hour,
        obs_time: `${dateStr} ${padH}`,
        counties: counties,
        stations: stations,
        max_uv: maxUv,
        avg_uv: avgUv
    };
    uvDataCache.hourly[hour] = res;
    return res;
}

// =============================================================================
// 4. GeoJSON & County Outlining ("即時框出區域")
// =============================================================================
let geojsonLayer = null;

async function loadGeoJSON() {
    try {
        const res = await fetch('/api/geojson');
        geojsonData = await res.json();
        
        geojsonLayer = L.geoJSON(geojsonData, {
            style: {
                fillColor: '#38bdf8',
                fillOpacity: 0.04,
                color: 'rgba(255, 255, 255, 0.18)',
                weight: 1.2
            },
            onEachFeature: (feature, layer) => {
                const name = feature.properties.COUNTYNAME || feature.properties.name;
                countyGeoJsonMap[name] = layer;
                
                layer.on({
                    mouseover: (e) => {
                        if (selectedCounty !== name) {
                            layer.setStyle({
                                fillOpacity: 0.15,
                                color: '#38bdf8',
                                weight: 2
                            });
                        }
                    },
                    mouseout: (e) => {
                        if (selectedCounty !== name) {
                            layer.setStyle({
                                fillOpacity: 0.04,
                                color: 'rgba(255, 255, 255, 0.18)',
                                weight: 1.2
                            });
                        }
                    },
                    click: (e) => {
                        document.getElementById('county-select').value = name;
                        onCountySelected(name);
                    }
                });
            }
        }).addTo(map);
    } catch (e) {
        console.warn("Failed to load GeoJSON:", e);
    }
}

function highlightCounty(name) {
    highlightGroup.clearLayers();
    if (!name || name === 'ALL') return;

    const layer = countyGeoJsonMap[name];
    if (layer) {
        const hl = L.geoJSON(layer.feature, {
            style: {
                color: '#38bdf8',
                weight: 4.5,
                fillColor: '#38bdf8',
                fillOpacity: 0.22,
                dashArray: null
            }
        });
        highlightGroup.addLayer(hl);
        
        // Smoothly fly to county
        map.fitBounds(layer.getBounds(), {
            padding: [80, 80],
            maxZoom: 10,
            duration: 1.0
        });
    } else if (COORDINATES[name]) {
        map.flyTo(COORDINATES[name], 9.5, { duration: 1.0 });
    }
}

function clearHighlight() {
    highlightGroup.clearLayers();
}

function onCountySelected(name) {
    selectedCounty = name;
    if (name === 'ALL') {
        clearHighlight();
        map.flyTo([23.7, 120.95], 7.5, { duration: 1.0 });
    } else {
        highlightCounty(name);
    }
    updateDashboard();
}

document.getElementById('county-select').addEventListener('change', (e) => {
    onCountySelected(e.target.value);
});

// =============================================================================
// 5. Data Fetching (Pre-fetching Bundle for 0ms Lag-free Switching)
// =============================================================================
async function fetchAllData() {
    try {
        const [wRes, hRes, uvBundleRes, rRes, tRes] = await Promise.all([
            fetch('/api/weather').then(r => r.json()).catch(() => []),
            fetch('/api/humidity').then(r => r.json()).catch(() => null),
            fetch('/api/uv?mode=bundle').then(r => r.json()).catch(() => null),
            fetch('/api/rainfall').then(r => r.json()).catch(() => null),
            fetch('/api/typhoon?target=live_cwa').then(r => r.json()).catch(() => null)
        ]);

        weatherData = wRes || [];
        humidityData = hRes;
        rainfallData = rRes;

        if (uvBundleRes) {
            uvDataCache.bundleLoaded = true;
            uvDataCache.realtime = uvBundleRes.realtime;
            uvDataCache.max = uvBundleRes.max;
            uvData = uvDataCache.realtime;
        }

        if (tRes) {
            typhoonData = tRes;
            typhoonCache['live_cwa'] = tRes;
        }

        if (weatherData.length > 0) {
            document.getElementById('obs-time').innerText = 
                weatherData[0].time.substring(0, 16).replace('T', ' ');
        }

        renderCurrentLayer();
        updateDashboard();
    } catch (e) {
        console.error("Data loading error:", e);
    }
}

// =============================================================================
// 6. Navigation Tabs & Submode Management
// =============================================================================
const navTabs = document.querySelectorAll('.nav-tab');
let prevTab = 'temp';

navTabs.forEach(tab => {
    tab.addEventListener('click', async () => {
        navTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        prevTab = activeTab;
        activeTab = tab.getAttribute('data-tab');

        // Toggle Select Boxes (County vs Typhoon)
        const countyBox = document.getElementById('county-select-box');
        const typhoonBox = document.getElementById('typhoon-select-box');

        if (activeTab === 'typhoon') {
            if (countyBox) countyBox.style.display = 'none';
            if (typhoonBox) typhoonBox.style.display = 'flex';
            if (!typhoonData || typhoonData.current_target !== selectedTyphoonTarget) {
                await loadTyphoonTarget(selectedTyphoonTarget);
            }
        } else {
            if (countyBox) countyBox.style.display = 'flex';
            if (typhoonBox) typhoonBox.style.display = 'none';
            if (prevTab === 'typhoon') {
                map.flyTo([23.7, 120.95], 7.5, { duration: 1.0 });
            }
        }

        setupSubmodes();
        renderCurrentLayer();
        updateDashboard();
        updateLegend();
    });
});

// Typhoon Target Selector Listener
const typhoonSelectEl = document.getElementById('typhoon-select');
if (typhoonSelectEl) {
    typhoonSelectEl.addEventListener('change', async (e) => {
        selectedTyphoonTarget = e.target.value;
        await loadTyphoonTarget(selectedTyphoonTarget);
    });
}

async function loadTyphoonTarget(targetKey) {
    if (typhoonCache[targetKey]) {
        typhoonData = typhoonCache[targetKey];
        renderCurrentLayer();
        updateDashboard();
        updateLegend();
        return;
    }
    try {
        const res = await fetch(`/api/typhoon?target=${targetKey}`);
        typhoonData = await res.json();
        typhoonCache[targetKey] = typhoonData;
        renderCurrentLayer();
        updateDashboard();
        updateLegend();
    } catch (err) {
        console.error("Failed to load typhoon target:", err);
    }
}

function setupSubmodes() {
    const subContainer = document.getElementById('submode-container');
    subContainer.innerHTML = '';

    if (activeTab === 'humidity') {
        subContainer.style.display = 'flex';
        subContainer.innerHTML = `
            <div class="submode-btn-group">
                <button class="submode-btn ${humidityMode === 'rh' ? 'active' : ''}" id="btn-sub-rh">💧 相對濕度 (RH %)</button>
                <button class="submode-btn ${humidityMode === 'thi' ? 'active' : ''}" id="btn-sub-thi">🌡️ 體感舒適度 (THI)</button>
            </div>
        `;
        document.getElementById('btn-sub-rh').addEventListener('click', () => {
            humidityMode = 'rh';
            setupSubmodes();
            renderCurrentLayer();
            updateDashboard();
            updateLegend();
        });
        document.getElementById('btn-sub-thi').addEventListener('click', () => {
            humidityMode = 'thi';
            setupSubmodes();
            renderCurrentLayer();
            updateDashboard();
            updateLegend();
        });
    } else if (activeTab === 'uv') {
        subContainer.style.display = 'flex';
        const padH = String(uvHour).padStart(2, '0') + ':00';
        subContainer.innerHTML = `
            <div class="submode-btn-group">
                <button class="submode-btn ${uvMode === 'realtime' ? 'active' : ''}" id="btn-sub-uv-rt">📡 即時實測</button>
                <button class="submode-btn ${uvMode === 'hourly' ? 'active' : ''}" id="btn-sub-uv-hr">⏰ 逐時推估 (<span id="uv-hr-label">${padH}</span>)</button>
                <button class="submode-btn ${uvMode === 'max' ? 'active' : ''}" id="btn-sub-uv-max">☀️ 今日最大值</button>
            </div>
            ${uvMode === 'hourly' ? `
            <div class="hourly-slider-panel" id="uv-hourly-panel">
                <div class="hourly-slider-header">
                    <span class="hourly-slider-title">⏰ 推估時段：<strong id="uv-slider-text">${padH}</strong></span>
                    <span class="hourly-slider-badge" id="uv-slider-badge">${getHourDescription(uvHour)}</span>
                </div>
                <div class="slider-track-wrap">
                    <input type="range" min="6" max="18" step="1" value="${uvHour}" id="uv-hour-range" class="custom-slider">
                    <div class="slider-ticks">
                        <span>06:00</span>
                        <span>08:00</span>
                        <span>10:00</span>
                        <span>12:00</span>
                        <span>14:00</span>
                        <span>16:00</span>
                        <span>18:00</span>
                    </div>
                </div>
                <div class="hourly-quick-chips">
                    <button class="quick-chip ${uvHour === 8 ? 'active' : ''}" data-h="8">08:00 通勤</button>
                    <button class="quick-chip ${uvHour === 10 ? 'active' : ''}" data-h="10">10:00 晨光</button>
                    <button class="quick-chip ${uvHour === 12 ? 'active' : ''}" data-h="12">12:00 正午最大</button>
                    <button class="quick-chip ${uvHour === 14 ? 'active' : ''}" data-h="14">14:00 午後</button>
                    <button class="quick-chip ${uvHour === 16 ? 'active' : ''}" data-h="16">16:00 傍晚</button>
                    <button class="quick-chip ${uvHour === 18 ? 'active' : ''}" data-h="18">18:00 日落</button>
                </div>
            </div>
            ` : ''}
        `;

        // 0ms instant switching between the 3 modes (no lagging!)
        document.getElementById('btn-sub-uv-rt').addEventListener('click', () => {
            uvMode = 'realtime';
            uvData = uvDataCache.realtime || uvData;
            setupSubmodes();
            renderCurrentLayer();
            updateDashboard();
            updateLegend();
        });

        document.getElementById('btn-sub-uv-max').addEventListener('click', () => {
            uvMode = 'max';
            uvData = uvDataCache.max || uvData;
            setupSubmodes();
            renderCurrentLayer();
            updateDashboard();
            updateLegend();
        });

        document.getElementById('btn-sub-uv-hr').addEventListener('click', () => {
            uvMode = 'hourly';
            uvData = computeHourlyUvData(uvHour);
            setupSubmodes();
            renderCurrentLayer();
            updateDashboard();
            updateLegend();
        });

        if (uvMode === 'hourly') {
            const range = document.getElementById('uv-hour-range');
            range.addEventListener('input', (e) => {
                uvHour = parseInt(e.target.value);
                uvData = computeHourlyUvData(uvHour);
                const pH = String(uvHour).padStart(2, '0') + ':00';
                document.getElementById('uv-slider-text').innerText = pH;
                document.getElementById('uv-hr-label').innerText = pH;
                document.getElementById('uv-slider-badge').innerText = getHourDescription(uvHour);
                document.querySelectorAll('.quick-chip').forEach(c => {
                    c.classList.toggle('active', parseInt(c.getAttribute('data-h')) === uvHour);
                });
                renderCurrentLayer();
                updateDashboard();
                updateLegend();
            });

            document.querySelectorAll('.quick-chip').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    uvHour = parseInt(btn.getAttribute('data-h'));
                    document.getElementById('uv-hour-range').value = uvHour;
                    uvData = computeHourlyUvData(uvHour);
                    const pH = String(uvHour).padStart(2, '0') + ':00';
                    document.getElementById('uv-slider-text').innerText = pH;
                    document.getElementById('uv-hr-label').innerText = pH;
                    document.getElementById('uv-slider-badge').innerText = getHourDescription(uvHour);
                    document.querySelectorAll('.quick-chip').forEach(c => c.classList.remove('active'));
                    btn.classList.add('active');
                    renderCurrentLayer();
                    updateDashboard();
                    updateLegend();
                });
            });
        }
    } else {
        subContainer.style.display = 'none';
    }
}

// =============================================================================
// 7. Layer Rendering (Pill Markers & Visuals)
// =============================================================================
function renderCurrentLayer() {
    markerGroup.clearLayers();
    typhoonGroup.clearLayers();

    if (activeTab === 'temp') {
        renderTempMarkers();
    } else if (activeTab === 'humidity') {
        renderHumidityMarkers();
    } else if (activeTab === 'uv') {
        renderUVMarkers();
    } else if (activeTab === 'rain') {
        renderRainMarkers();
    } else if (activeTab === 'typhoon') {
        renderTyphoonLayer();
    }
}

function renderTempMarkers() {
    weatherData.forEach(d => {
        const color = getTempColor(d.max_temp);
        const marker = createPillMarker(
            [d.lat, d.lon],
            d.location,
            `${d.max_temp}°C`,
            color,
            `<strong>${d.location} 氣溫預報</strong><br>天氣狀況：${d.weather}<br>最高溫：${d.max_temp}°C<br>最低溫：${d.min_temp}°C<br>降雨機率：${d.pop !== null ? d.pop + '%' : '未提供'}`
        );
        marker.addTo(markerGroup);
    });
}

function renderHumidityMarkers() {
    if (!humidityData || !humidityData.counties) return;

    Object.entries(humidityData.counties).forEach(([cname, h]) => {
        const coords = COORDINATES[cname];
        if (!coords) return;

        let displayVal, color, popupContent;
        if (humidityMode === 'rh') {
            displayVal = `${h.rh}%`;
            color = getHumidityColor(h.rh);
            popupContent = `<strong>${cname} 相對濕度</strong><br>濕度：${h.rh}% (${h.category.name})<br>體感：${h.category.feeling}<br>建議：${h.category.dehumidifier_advice}`;
        } else {
            displayVal = `THI ${h.thi}`;
            color = getTHIColor(h.thi);
            popupContent = `<strong>${cname} 體感舒適度 (THI)</strong><br>舒適度：${h.thi_text} (指數 ${h.thi})<br>感覺：${h.thi_category.feeling}<br>涼感建議：${h.thi_category.cooling_advice}`;
        }

        const marker = createPillMarker(coords, cname, displayVal, color, popupContent);
        marker.addTo(markerGroup);
    });
}

function renderUVMarkers() {
    if (!uvData || !uvData.counties) return;

    Object.entries(uvData.counties).forEach(([cname, u]) => {
        const coords = COORDINATES[cname];
        if (!coords) return;

        const val = u.uvi !== null ? u.uvi : '-';
        const color = getUVColor(u.uvi);
        const popupContent = `<strong>${cname} 紫外線指數</strong><br>UVI：${val} (${u.exposureLevel})<br>防曬時長：${u.sunburn_time}<br>防曬係數：${u.spf_advice}<br>指引：${u.advice}`;

        const marker = createPillMarker(coords, cname, `UVI ${val}`, color, popupContent);
        marker.addTo(markerGroup);
    });
}

function renderRainMarkers() {
    if (!rainfallData || !rainfallData.stations) return;

    rainfallData.stations.forEach(s => {
        if (s.rain24 <= 0) return;
        const color = getRainColor(s.rain24);
        
        const circle = L.circleMarker([s.lat, s.lon], {
            radius: Math.min(Math.max(s.rain24 * 0.4, 4), 18),
            fillColor: color,
            fillOpacity: 0.75,
            color: '#ffffff',
            weight: 1.5
        });

        circle.bindPopup(`<strong>${s.station_name} (${s.county})</strong><br>24h 累積雨量：${s.rain24} mm<br>觀測時間：${s.obs_time}`);
        circle.addTo(markerGroup);
    });
}

function renderTyphoonLayer() {
    if (!typhoonData) return;
    const t = typhoonData;

    // 1. Center & Zoom map on Typhoon
    if (t.map_center && t.map_center.length === 2) {
        map.setView(t.map_center, t.zoom_start || 6);
    } else if (t.current_point) {
        map.setView([t.current_point.lat, t.current_point.lon], 6);
    }

    // 2. Historical Track (過去觀測路徑 - 莫蘭迪灰藍實線 #5c7c8a)
    if (t.historical_points && t.historical_points.length > 0) {
        const histCoords = t.historical_points.map(p => [p.lat, p.lon]);
        L.polyline(histCoords, {
            color: '#5c7c8a',
            weight: 3.5,
            opacity: 0.9
        }).bindTooltip("🌀 過去觀測移動路徑").addTo(typhoonGroup);

        t.historical_points.forEach(p => {
            L.circleMarker([p.lat, p.lon], {
                radius: 5,
                color: '#5c7c8a',
                fillColor: '#5c7c8a',
                fillOpacity: 0.9,
                weight: 2
            }).bindPopup(`
                <div class="typhoon-popup">
                    <div class="popup-title">⏱️ ${p.time} 過去觀測點</div>
                    <div>📍 <b>座標</b>：北緯 ${p.lat}°，東經 ${p.lon}°</div>
                    <div>📉 <b>氣壓</b>：${p.pressure}</div>
                    <div>💨 <b>風速</b>：${p.wind}</div>
                    <div>🧭 <b>性質</b>：${p.type || '觀測節點'}</div>
                </div>
            `).bindTooltip(`⏱️ ${p.time} | 氣壓: ${p.pressure} | 風速: ${p.wind}`).addTo(typhoonGroup);
        });
    }

    // 3. Current Center (當前中心 - 莫蘭迪陶土色與暴風圈)
    if (t.current_point) {
        const cp = t.current_point;
        const r7km = Number(t.radius_7_km) || 0;
        const r10km = Number(t.radius_10_km) || 0;

        // 7 級風暴風半徑
        if (r7km > 0) {
            L.circle([cp.lat, cp.lon], {
                radius: r7km * 1000,
                color: '#ef4444',
                weight: 2,
                dashArray: '4, 6',
                fillColor: '#ef4444',
                fillOpacity: 0.15
            }).bindTooltip(`7級風暴風半徑: ${r7km} 公里 (${t.radius_7})`).addTo(typhoonGroup);
        }

        // 10 級風暴風半徑
        if (r10km > 0) {
            L.circle([cp.lat, cp.lon], {
                radius: r10km * 1000,
                color: '#dc2626',
                weight: 2,
                fillColor: '#dc2626',
                fillOpacity: 0.25
            }).bindTooltip(`10級風暴風半徑: ${r10km} 公里`).addTo(typhoonGroup);
        }

        // 當前中心外環光暈
        L.circleMarker([cp.lat, cp.lon], {
            radius: 18,
            color: '#b86b53',
            weight: 2,
            fillColor: '#b86b53',
            fillOpacity: 0.25
        }).addTo(typhoonGroup);

        // 當前中心實心點
        const eyeMarker = L.circleMarker([cp.lat, cp.lon], {
            radius: 8,
            color: '#ffffff',
            weight: 2.5,
            fillColor: '#b86b53',
            fillOpacity: 1.0
        });

        eyeMarker.bindPopup(`
            <div class="typhoon-popup">
                <div class="popup-title">🌀 ${t.name_zh} (${t.name_en || ''})</div>
                <div>⏱️ <b>定位時間</b>：${t.obs_time}</div>
                <div>📍 <b>中心座標</b>：北緯 ${cp.lat}°，東經 ${cp.lon}°</div>
                <div>📉 <b>中心氣壓</b>：${t.pressure}</div>
                <div>💨 <b>最大風速</b>：${t.max_wind}</div>
                <div>🌪️ <b>瞬間陣風</b>：${t.gust_wind || '-'}</div>
                <div>⭕ <b>暴風半徑</b>：7級 ${t.radius_7} / 10級 ${t.radius_10}</div>
                <div>🧭 <b>移向移速</b>：${t.movement}</div>
            </div>
        `);
        eyeMarker.bindTooltip(`🌀 ${t.name_zh} (點擊展開詳細氣象定位卡)`).addTo(typhoonGroup);

        // 4. Forecast Track (官方預報路徑) & 70% 潛勢機率圈
        if (t.forecast_points && t.forecast_points.length > 0) {
            const foreCoords = [[cp.lat, cp.lon], ...t.forecast_points.map(p => [p.lat, p.lon])];
            L.polyline(foreCoords, {
                color: '#b86b53',
                weight: 3.5,
                opacity: 0.9,
                dashArray: '6, 6'
            }).bindTooltip("🚨 官方預報路徑").addTo(typhoonGroup);

            t.forecast_points.forEach(fp => {
                const r70 = Number(fp.radius_70) || 0;
                if (r70 > 0) {
                    L.circle([fp.lat, fp.lon], {
                        radius: r70,
                        color: '#b86b53',
                        weight: 1.5,
                        dashArray: '4, 4',
                        fillColor: '#b86b53',
                        fillOpacity: 0.12
                    }).bindTooltip(`⭕ 70% 潛勢暴風圈 (${fp.time_label}) · 半徑: ${Math.round(r70 / 1000)} 公里`).addTo(typhoonGroup);
                }

                L.circleMarker([fp.lat, fp.lon], {
                    radius: 6,
                    color: '#b86b53',
                    fillColor: '#ffffff',
                    fillOpacity: 0.95,
                    weight: 2.2
                }).bindPopup(`
                    <div class="typhoon-popup">
                        <div class="popup-title">⏱️ ${fp.time_label} 氣象預報點</div>
                        <div>📍 <b>預報座標</b>：北緯 ${fp.lat}°，東經 ${fp.lon}°</div>
                        <div>📉 <b>預測氣壓</b>：${fp.pressure}</div>
                        <div>💨 <b>預測風速</b>：${fp.wind}</div>
                        <div>⭕ <b>70% 潛勢半徑</b>：${Math.round(r70 / 1000)} 公里</div>
                        <div class="popup-desc">🧭 ${fp.desc || ''}</div>
                    </div>
                `).bindTooltip(`⏱️ 預報節點: ${fp.time_label} · ${fp.desc || ''}`).addTo(typhoonGroup);
            });
        }
    }
}

function createPillMarker(latlng, loc, badgeVal, color, popupHtml) {
    const html = showLabels ? 
        `<div class="custom-pill-marker">
            <span>${loc}</span>
            <span class="marker-val-badge" style="background-color: ${color};">${badgeVal}</span>
         </div>` :
        `<div class="custom-pill-marker" style="padding: 4px;">
            <span class="marker-val-badge" style="background-color: ${color}; width: 8px; height: 8px; padding: 0;"></span>
         </div>`;

    const icon = L.divIcon({
        className: 'custom-pill-wrapper',
        html: html,
        iconSize: [80, 24],
        iconAnchor: [40, 12]
    });

    const marker = L.marker(latlng, { icon: icon });
    marker.bindPopup(popupHtml);
    marker.on('click', () => {
        document.getElementById('county-select').value = loc;
        onCountySelected(loc);
    });
    return marker;
}

// =============================================================================
// 8. Dynamic Dashboard & Metric Cards
// =============================================================================
function updateDashboard() {
    const title1 = document.getElementById('card-title-1');
    const val1 = document.getElementById('card-val-1');
    const sub1 = document.getElementById('card-sub-1');

    const title2 = document.getElementById('card-title-2');
    const val2 = document.getElementById('card-val-2');
    const sub2 = document.getElementById('card-sub-2');

    const title3 = document.getElementById('card-title-3');
    const val3 = document.getElementById('card-val-3');
    const sub3 = document.getElementById('card-sub-3');

    const title4 = document.getElementById('card-title-4');
    const val4 = document.getElementById('card-val-4');
    const sub4 = document.getElementById('card-sub-4');

    const chartWrap = document.getElementById('chart-wrapper');
    const detailList = document.getElementById('detail-list');
    const contextTitle = document.getElementById('context-title');

    const adviceHead = document.getElementById('advice-heading');
    const adviceBody = document.getElementById('advice-body');
    const adviceIcon = document.getElementById('advice-icon');

    if (activeTab === 'temp') {
        chartWrap.style.display = 'block';
        detailList.style.display = 'none';
        contextTitle.innerText = `📈 7 天氣溫預報走勢 (${selectedCounty === 'ALL' ? '全台平均' : selectedCounty})`;

        if (selectedCounty === 'ALL') {
            let maxT = -99, minT = 99, sumT = 0, count = 0;
            let maxLoc = '', minLoc = '';
            weatherData.forEach(d => {
                if (d.max_temp > maxT) { maxT = d.max_temp; maxLoc = d.location; }
                if (d.min_temp < minT) { minT = d.min_temp; minLoc = d.location; }
                sumT += d.max_temp;
                count++;
            });
            title1.innerText = '全台最高溫'; val1.innerHTML = `${maxT} <small>°C</small>`; sub1.innerText = maxLoc;
            title2.innerText = '全台最低溫'; val2.innerHTML = `${minT} <small>°C</small>`; sub2.innerText = minLoc;
            title3.innerText = '全台平均溫'; val3.innerHTML = `${(sumT / count).toFixed(1)} <small>°C</small>`; sub3.innerText = '22 縣市';
            title4.innerText = '常見天氣'; val4.innerText = '多雲偏暖'; sub4.innerText = '多數縣市';

            adviceIcon.innerText = '💡';
            adviceHead.innerText = '氣候穿著指引';
            adviceBody.innerText = '今日各地白天氣溫微熱，日夜溫差約 6-8°C，清晨外出建構洋蔥式穿法。';
            renderForecastChart('臺北市');
        } else {
            const item = weatherData.find(d => d.location === selectedCounty);
            if (item) {
                title1.innerText = '預報最高溫'; val1.innerHTML = `${item.max_temp} <small>°C</small>`; sub1.innerText = item.location;
                title2.innerText = '預報最低溫'; val2.innerHTML = `${item.min_temp} <small>°C</small>`; sub2.innerText = item.location;
                title3.innerText = '降雨機率'; val3.innerHTML = `${item.pop !== null ? item.pop : 0} <small>%</small>`; sub3.innerText = '12hr 預報';
                title4.innerText = '天氣現象'; val4.innerText = item.weather; sub4.innerText = item.location;

                adviceIcon.innerText = '🌤️';
                adviceHead.innerText = `${selectedCounty} 生活建議`;
                adviceBody.innerText = `預報狀況為「${item.weather}」，降雨機率約 ${item.pop || 0}%，溫差注意保暖。`;
            }
            renderForecastChart(selectedCounty);
        }
    } else if (activeTab === 'humidity') {
        chartWrap.style.display = 'none';
        detailList.style.display = 'flex';
        contextTitle.innerText = `💧 轄區濕度與測站明細 (${selectedCounty})`;

        if (!humidityData || !humidityData.counties) return;

        if (selectedCounty === 'ALL') {
            title1.innerText = '全台最高濕度'; val1.innerHTML = `${humidityData.max_rh || 88} <small>%</small>`; sub1.innerText = '局部測站';
            title2.innerText = '全台最低濕度'; val2.innerHTML = `${humidityData.min_rh || 52} <small>%</small>`; sub2.innerText = '局部測站';
            title3.innerText = '平均相對濕度'; val3.innerHTML = `${humidityData.avg_rh || 68} <small>%</small>`; sub3.innerText = '22 縣市平均';
            title4.innerText = '當前體感指標'; val4.innerText = humidityMode === 'rh' ? '略偏潮濕' : '悶熱稍黏'; sub4.innerText = '黃紅分級模式';

            adviceIcon.innerText = '💧';
            adviceHead.innerText = '全台濕度與除濕指引';
            adviceBody.innerText = '濕度維持在 60-74% (黃色警示)，建議開啟除濕機維持在人體舒適的 55% 濕度。';

            // Populate detail list
            detailList.innerHTML = Object.entries(humidityData.counties).slice(0, 10).map(([c, h]) => `
                <div class="detail-item">
                    <span>${c}</span>
                    <strong style="color: ${humidityMode === 'rh' ? getHumidityColor(h.rh) : getTHIColor(h.thi)}">
                        ${humidityMode === 'rh' ? h.rh + '%' : 'THI ' + h.thi + ' (' + h.thi_text + ')'}
                    </strong>
                </div>
            `).join('');
        } else {
            const h = humidityData.counties[selectedCounty];
            if (h) {
                title1.innerText = '相對濕度 (RH)'; val1.innerHTML = `${h.rh} <small>%</small>`; sub1.innerText = h.category.name;
                title2.innerText = '舒適度指數 (THI)'; val2.innerHTML = `${h.thi}`; sub2.innerText = h.thi_text;
                title3.innerText = '平均氣溫'; val3.innerHTML = `${h.temp} <small>°C</small>`; sub3.innerText = '測站均溫';
                title4.innerText = '體感描述'; val4.innerText = h.thi_category.feeling.split('·')[0]; sub4.innerText = selectedCounty;

                adviceIcon.innerText = '💡';
                adviceHead.innerText = `${selectedCounty} 防潮降溫指引`;
                adviceBody.innerText = `${h.category.advice} ${h.thi_category.cooling_advice}`;

                detailList.innerHTML = (h.local_stations || []).map(st => `
                    <div class="detail-item">
                        <span>${st.name} (${st.town})</span>
                        <strong style="color: ${getHumidityColor(st.rh)}">${st.rh}% · ${st.temp}°C</strong>
                    </div>
                `).join('');
            }
        }
    } else if (activeTab === 'uv') {
        chartWrap.style.display = 'none';
        detailList.style.display = 'flex';
        contextTitle.innerText = `☀️ 局屬紫外線觀測站實測數據 (${selectedCounty})`;

        if (!uvData || !uvData.counties) return;

        if (selectedCounty === 'ALL') {
            title1.innerText = '全台最高 UVI'; val1.innerHTML = `${uvData.max_uv || 8.0}`; sub1.innerText = '過量級';
            title2.innerText = '全台平均 UVI'; val2.innerHTML = `${uvData.avg_uv || 6.2}`; sub2.innerText = '高量級';
            title3.innerText = '有效測站'; val3.innerHTML = `${uvData.stations ? uvData.stations.length : 31} <small>站</small>`; sub3.innerText = '全台局屬站';
            title4.innerText = '觀測模式'; val4.innerText = uvData.mode_title || '即時實測'; sub4.innerText = 'WHO 5階分級';

            adviceIcon.innerText = '☀️';
            adviceHead.innerText = '防曬與健康建議';
            adviceBody.innerText = '紫外線達高量至過量級，10:00-14:00 避免強烈曝曬，外出配戴太陽眼鏡與遮陽帽。';

            detailList.innerHTML = (uvData.stations || []).slice(0, 10).map(st => `
                <div class="detail-item">
                    <span>${st.name} (${st.county})</span>
                    <strong style="color: ${getUVColor(st.uv_index)}">UVI ${st.display_val} (${st.level})</strong>
                </div>
            `).join('');
        } else {
            const u = uvData.counties[selectedCounty];
            if (u) {
                title1.innerText = '紫外線指數'; val1.innerHTML = `${u.uvi !== null ? u.uvi : '-'}`; sub1.innerText = u.exposureLevel;
                title2.innerText = '曬傷時間'; val2.innerText = u.sunburn_time.split('約')[1] || u.sunburn_time; sub2.innerText = '直曬耐受度';
                title3.innerText = '防曬建議係數'; val3.innerText = u.spf_advice.split('/')[0]; sub3.innerText = u.spf_advice;
                title4.innerText = '主觀測站'; val4.innerText = u.primary_station || selectedCounty; sub4.innerText = u.primary_town || '';

                adviceIcon.innerText = '🛡️';
                adviceHead.innerText = `${selectedCounty} 防護對策`;
                adviceBody.innerText = u.advice;

                detailList.innerHTML = (u.stations || []).map(st => `
                    <div class="detail-item">
                        <span>${st.name} (${st.town})</span>
                        <strong style="color: ${getUVColor(st.uv_index)}">UVI ${st.display_val} (${st.level})</strong>
                    </div>
                `).join('');
            }
        }
    } else if (activeTab === 'rain') {
        chartWrap.style.display = 'none';
        detailList.style.display = 'flex';
        contextTitle.innerText = `🌧️ 24 小時累積雨量排行 Top 10`;

        if (rainfallData) {
            title1.innerText = '最大降雨量'; val1.innerHTML = `${rainfallData.max_rain || 0} <small>mm</small>`; sub1.innerText = rainfallData.max_station || '局屬測站';
            title2.innerText = '降雨警示等級'; val2.innerText = rainfallData.advisory_title || '無警報'; sub2.innerText = '全台監控中';
            title3.innerText = '累積降雨測站'; val3.innerHTML = `${rainfallData.total_rainy_stations || 0} <small>站</small>`; sub3.innerText = `總數 ${rainfallData.total_stations || 1300}`;
            title4.innerText = '降雨狀態'; val4.innerText = rainfallData.advisory_title ? '有局部雨' : '大致穩定'; sub4.innerText = 'CWA 即時連線';

            adviceIcon.innerText = '🌧️';
            adviceHead.innerText = '降雨警報與出門提醒';
            adviceBody.innerText = rainfallData.advisory_desc || '全台目前無豪雨警戒，山區請留意午後短暫陣雨。';

            detailList.innerHTML = (rainfallData.top_stations || []).slice(0, 10).map(st => `
                <div class="detail-item">
                    <span>${st.station_name} (${st.county})</span>
                    <strong style="color: ${getRainColor(st.rain24)}">${st.rain24} mm</strong>
                </div>
            `).join('');
        }
    } else if (activeTab === 'typhoon') {
        chartWrap.style.display = 'none';
        detailList.style.display = 'flex';
        detailList.style.flexDirection = 'column';
        contextTitle.innerText = `📅 官方預報路徑節點數據表`;

        if (typhoonData) {
            const t = typhoonData;
            title1.innerText = '颱風名稱與強度';
            val1.innerHTML = `<span style="font-size:1.1rem;color:#b86b53;">${t.name_zh || '無颱風'}</span>`;
            sub1.innerText = `${t.name_en ? t.name_en + ' · ' : ''}${t.intensity || '低壓系統'}`;

            title2.innerText = '近中心最大風速';
            val2.innerHTML = `<span style="font-size:1.15rem;color:#c47d66;">${t.max_wind || '-'}</span>`;
            sub2.innerText = `瞬間陣風: ${t.gust_wind || '-'}`;

            title3.innerText = '中心最低氣壓';
            val3.innerHTML = `<span style="font-size:1.15rem;color:#5c7c8a;">${t.pressure || '-'}</span>`;
            sub3.innerText = `7級半徑: ${t.radius_7 || '-'}`;

            title4.innerText = '移向與移速';
            val4.innerHTML = `<span style="font-size:0.92rem;color:#6b8e73;">${(t.movement || '').split('，')[0] || t.movement}</span>`;
            sub4.innerText = `定位: ${t.obs_time || '-'}`;

            adviceIcon.innerText = '🌀';
            adviceHead.innerText = t.advisory_title || '防颱警戒指引';
            adviceBody.innerText = t.advisory_body || '請密切留意中央氣象署最新警報與風雨預報資訊。';

            let tableRows = '';
            if (t.forecast_points && t.forecast_points.length > 0) {
                tableRows = t.forecast_points.map(fp => `
                    <tr>
                        <td><strong>${fp.time_label}</strong></td>
                        <td>${fp.lat}°N, ${fp.lon}°E</td>
                        <td>${fp.pressure}</td>
                        <td>${fp.wind}</td>
                        <td>${Math.round((fp.radius_70 || 0) / 1000)} km</td>
                        <td>${fp.desc || '-'}</td>
                    </tr>
                `).join('');
            }

            const seaAlertHtml = (t.sea_alert || '• 鄰近海域密切注意').replace(/\n/g, '<br>');
            const landAlertHtml = (t.land_alert || '• 沿海強陣風戒備').replace(/\n/g, '<br>');

            detailList.innerHTML = `
                <div class="typhoon-table-wrap">
                    <table class="typhoon-table">
                        <thead>
                            <tr>
                                <th>預報時間</th>
                                <th>座標</th>
                                <th>氣壓</th>
                                <th>風速</th>
                                <th>70%半徑</th>
                                <th>路徑動態</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${tableRows || '<tr><td colspan="6" style="text-align:center;padding:12px;">無預報路徑</td></tr>'}
                        </tbody>
                    </table>
                </div>
                <div class="typhoon-alert-grid">
                    <div class="typhoon-alert-card sea">
                        <div class="typhoon-alert-title">🌊 海面警戒 / 監測海域</div>
                        <div class="typhoon-alert-content">${seaAlertHtml}</div>
                    </div>
                    <div class="typhoon-alert-card land">
                        <div class="typhoon-alert-title">🏞️ 陸上警戒 / 防汛重點</div>
                        <div class="typhoon-alert-content">${landAlertHtml}</div>
                    </div>
                </div>
            `;
        }
    }
}

// =============================================================================
// 9. Chart.js 7-Day Temperature Line Graph
// =============================================================================
async function renderForecastChart(county) {
    try {
        const res = await fetch(`/api/forecast/${county}`);
        const data = await res.json();
        if (!data || data.length === 0) return;

        const labels = data.map(d => d.forecast_start.substring(5, 10).replace('-', '/'));
        const maxTemps = data.map(d => d.max_temp);
        const minTemps = data.map(d => d.min_temp);

        const ctx = document.getElementById('forecastChart').getContext('2d');
        if (forecastChart) {
            forecastChart.destroy();
        }

        forecastChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '最高溫 (°C)',
                        data: maxTemps,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.15)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 3
                    },
                    {
                        label: '最低溫 (°C)',
                        data: minTemps,
                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(56, 189, 248, 0.15)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8', font: { size: 10 } }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#64748b', font: { size: 9 } },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    y: {
                        ticks: { color: '#64748b', font: { size: 9 } },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    }
                }
            }
        });
    } catch (e) {
        console.warn("Forecast chart load failed:", e);
    }
}

// =============================================================================
// 10. Dynamic Legend
// =============================================================================
function updateLegend() {
    const title = document.getElementById('legend-title');
    const subtitle = document.getElementById('legend-subtitle');
    const grad = document.getElementById('legend-gradient');
    const labels = document.getElementById('legend-labels');

    if (activeTab === 'temp') {
        title.innerText = '氣溫分級 (°C)';
        subtitle.innerText = '7 天最高溫預報';
        grad.style.background = 'linear-gradient(to right, #3b82f6, #0ea5e9, #10b981, #e5a93c, #ef4444)';
        labels.innerHTML = '<span>15°C</span><span>20°C</span><span>24°C</span><span>28°C</span><span>32°C</span><span>36°C</span>';
    } else if (activeTab === 'humidity') {
        if (humidityMode === 'rh') {
            title.innerText = '相對濕度分級 (%)';
            subtitle.innerText = '60-74% 黃色警示';
            grad.style.background = 'linear-gradient(to right, #38bdf8, #10b981, #e5a93c, #ef4444)';
            labels.innerHTML = '<span><50% (乾)</span><span>50-59%</span><span>60-74% (黃)</span><span>≥75% (濕)</span>';
        } else {
            title.innerText = '體感舒適度 (THI)';
            subtitle.innerText = '紅 (稍黏) / 紫 (極度悶熱)';
            grad.style.background = 'linear-gradient(to right, #0284c7, #10b981, #d90429, #7b2cbf)';
            labels.innerHTML = '<span>偏涼</span><span>舒適</span><span style="color:#d90429">悶熱稍黏</span><span style="color:#7b2cbf">極度悶熱</span>';
        }
    } else if (activeTab === 'uv') {
        title.innerText = '紫外線指數 (WHO)';
        subtitle.innerText = uvMode === 'max' ? '今日最大值' : '即時實測';
        grad.style.background = 'linear-gradient(to right, #2b82d9, #2a9d8f, #e5a93c, #c94a4a, #7209b7)';
        labels.innerHTML = '<span>0-2 微量</span><span>3-5 中量</span><span>6-7 高量</span><span>8-10 過量</span><span>11+ 危險</span>';
    } else if (activeTab === 'rain') {
        title.innerText = '24小時雨量等級 (mm)';
        subtitle.innerText = '氣象署累積警示';
        grad.style.background = 'linear-gradient(to right, #94a3b8, #10b981, #0ea5e9, #3b82f6, #ef4444)';
        labels.innerHTML = '<span>0</span><span>20</span><span>50 (大雨)</span><span>80 (豪雨)</span><span>200+</span>';
    } else if (activeTab === 'typhoon') {
        title.innerText = '颱風路徑標記';
        subtitle.innerText = '暴風圈範圍';
        grad.style.background = 'linear-gradient(to right, #f59e0b, #ef4444)';
        labels.innerHTML = '<span>預測路徑</span><span>7級風暴風圈</span>';
    }
}

// =============================================================================
// 11. Initial Startup
// =============================================================================
(async function init() {
    await loadGeoJSON();
    await fetchAllData();
    setupSubmodes();
    updateLegend();
})();
