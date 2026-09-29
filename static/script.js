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
// 5. Data Fetching
// =============================================================================
async function fetchAllData() {
    try {
        const [wRes, hRes, uvRes, rRes, tRes] = await Promise.all([
            fetch('/api/weather').then(r => r.json()),
            fetch('/api/humidity').then(r => r.json()).catch(() => null),
            fetch('/api/uv?mode=realtime').then(r => r.json()).catch(() => null),
            fetch('/api/rainfall').then(r => r.json()).catch(() => null),
            fetch('/api/typhoon').then(r => r.json()).catch(() => null)
        ]);

        weatherData = wRes || [];
        humidityData = hRes;
        uvData = uvRes;
        rainfallData = rRes;
        typhoonData = tRes;

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
navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        navTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeTab = tab.getAttribute('data-tab');
        
        setupSubmodes();
        renderCurrentLayer();
        updateDashboard();
        updateLegend();
    });
});

function setupSubmodes() {
    const subContainer = document.getElementById('submode-container');
    subContainer.innerHTML = '';

    if (activeTab === 'humidity') {
        subContainer.style.display = 'flex';
        subContainer.innerHTML = `
            <button class="submode-btn ${humidityMode === 'rh' ? 'active' : ''}" id="btn-sub-rh">💧 相對濕度 (RH %)</button>
            <button class="submode-btn ${humidityMode === 'thi' ? 'active' : ''}" id="btn-sub-thi">🌡️ 體感舒適度 (THI)</button>
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
        subContainer.innerHTML = `
            <button class="submode-btn ${uvMode === 'realtime' ? 'active' : ''}" id="btn-sub-uv-rt">📡 即時實測</button>
            <button class="submode-btn ${uvMode === 'hourly' ? 'active' : ''}" id="btn-sub-uv-hr">⏰ 逐時推估 (${uvHour}:00)</button>
            <button class="submode-btn ${uvMode === 'max' ? 'active' : ''}" id="btn-sub-uv-max">☀️ 今日最大值</button>
        `;
        document.getElementById('btn-sub-uv-rt').addEventListener('click', async () => {
            uvMode = 'realtime';
            uvData = await fetch('/api/uv?mode=realtime').then(r => r.json());
            setupSubmodes();
            renderCurrentLayer();
            updateDashboard();
            updateLegend();
        });
        document.getElementById('btn-sub-uv-hr').addEventListener('click', async () => {
            uvMode = 'hourly';
            uvHour = (new Date()).getHours();
            if (uvHour < 6) uvHour = 6;
            if (uvHour > 18) uvHour = 18;
            uvData = await fetch(`/api/uv?mode=hourly&hour=${uvHour}`).then(r => r.json());
            setupSubmodes();
            renderCurrentLayer();
            updateDashboard();
            updateLegend();
        });
        document.getElementById('btn-sub-uv-max').addEventListener('click', async () => {
            uvMode = 'max';
            uvData = await fetch('/api/uv?mode=max').then(r => r.json());
            setupSubmodes();
            renderCurrentLayer();
            updateDashboard();
            updateLegend();
        });
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
    if (t.current_point) {
        const cp = t.current_point;
        
        // Storm Radius Circle
        if (t.radius_7 > 0) {
            L.circle([cp.lat, cp.lon], {
                radius: t.radius_7 * 1000,
                color: '#ef4444',
                weight: 2,
                fillColor: '#ef4444',
                fillOpacity: 0.18,
                dashArray: '4, 6'
            }).addTo(typhoonGroup);
        }

        // Center Eye Marker
        const eyeMarker = L.circleMarker([cp.lat, cp.lon], {
            radius: 8,
            fillColor: '#ef4444',
            color: '#ffffff',
            weight: 2.5,
            fillOpacity: 0.95
        });
        eyeMarker.bindPopup(`<strong>颱風中心: ${t.name_zh} (${t.name_en})</strong><br>強度：${t.intensity}<br>最大風速：${t.max_wind} m/s<br>中心氣壓：${t.pressure} hPa<br>7級風暴風半徑：${t.radius_7} km`);
        eyeMarker.addTo(typhoonGroup);

        // Forecast path line
        if (t.forecast_points && t.forecast_points.length > 0) {
            const latlngs = [[cp.lat, cp.lon], ...t.forecast_points.map(p => [p.lat, p.lon])];
            L.polyline(latlngs, {
                color: '#f59e0b',
                weight: 3,
                dashArray: '6, 6'
            }).addTo(typhoonGroup);

            t.forecast_points.forEach(fp => {
                const node = L.circleMarker([fp.lat, fp.lon], {
                    radius: 5,
                    fillColor: '#f59e0b',
                    color: '#ffffff',
                    weight: 1.5
                });
                node.bindPopup(`<strong>${fp.time} 預估路徑</strong><br>風速：${fp.max_wind} m/s<br>暴風半徑：${fp.radius_7} km`);
                node.addTo(typhoonGroup);
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
        contextTitle.innerText = `🌀 颱風路徑與觀測數據`;

        if (typhoonData) {
            title1.innerText = '熱帶系統'; val1.innerText = typhoonData.name_zh || '無颱風'; sub1.innerText = typhoonData.name_en || '西北太平洋';
            title2.innerText = '系統強度'; val2.innerText = typhoonData.intensity || '一般低壓'; sub2.innerText = 'CWA 即時監控';
            title3.innerText = '中心氣壓'; val3.innerHTML = `${typhoonData.pressure || 1008} <small>hPa</small>`; sub3.innerText = `最大風速 ${typhoonData.max_wind || 15} m/s`;
            title4.innerText = '暴風半徑'; val4.innerHTML = `${typhoonData.radius_7 || 0} <small>km</small>`; sub4.innerText = '7 級風暴風圈';

            adviceIcon.innerText = '🌀';
            adviceHead.innerText = typhoonData.advisory_title || '海上陸上警報概況';
            adviceBody.innerText = typhoonData.advisory_body || '目前台灣近海無颱風直接威脅，氣象署持續嚴密監控中。';

            if (typhoonData.forecast_points) {
                detailList.innerHTML = typhoonData.forecast_points.map(fp => `
                    <div class="detail-item">
                        <span>${fp.time}</span>
                        <strong style="color: #f59e0b">${fp.max_wind} m/s · 半徑 ${fp.radius_7} km</strong>
                    </div>
                `).join('');
            }
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
