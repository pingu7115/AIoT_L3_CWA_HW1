// Initialize Map
const map = L.map('map', {
    zoomControl: false // Hide default zoom control to not overlap with panels
}).setView([23.7, 121.0], 7);

L.control.zoom({
    position: 'bottomleft'
}).addTo(map);

// Tile Layers
const darkTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
});

const streetTiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
});

darkTiles.addTo(map); // Default

let currentLayer = 'temp'; // 'temp' or 'rain'
let showLabels = true;
let weatherData = [];
let markerGroup = L.layerGroup().addTo(map);

// Color scales
function getTempColor(t) {
    if (t >= 32) return '#ef4444'; // Red
    if (t >= 28) return '#f59e0b'; // Amber
    if (t >= 24) return '#10b981'; // Emerald
    if (t >= 20) return '#0ea5e9'; // Sky
    return '#3b82f6'; // Blue
}

function getRainColor(r) {
    if (r >= 80) return '#3b82f6';
    if (r >= 50) return '#0ea5e9';
    if (r >= 20) return '#10b981';
    return '#94a3b8'; // Slate
}

// Fetch data from API
async function loadData() {
    try {
        const res = await fetch('/api/weather');
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`HTTP error! status: ${res.status}, body: ${errText}`);
        }
        weatherData = await res.json();

        if (weatherData.length > 0) {
            document.getElementById('obs-time').innerText = weatherData[0].time.substring(0, 16).replace('T', ' ');
            updateDashboard();
            renderMarkers();
        }
    } catch (e) {
        console.error("Failed to load weather data:", e);
    }
}

// Update dashboard stats
function updateDashboard() {
    let maxTemp = -999, minTemp = 999, maxRain = -1;
    let maxTempLoc = '', minTempLoc = '', maxRainLoc = '';

    // Find most common weather
    let weatherCounts = {};

    weatherData.forEach(d => {
        if (d.max_temp > maxTemp) { maxTemp = d.max_temp; maxTempLoc = d.location; }
        if (d.min_temp < minTemp) { minTemp = d.min_temp; minTempLoc = d.location; }
        if (d.pop > maxRain) { maxRain = d.pop; maxRainLoc = d.location; }

        weatherCounts[d.weather] = (weatherCounts[d.weather] || 0) + 1;
    });

    document.getElementById('max-temp').innerText = maxTemp !== -999 ? maxTemp : '-';
    document.getElementById('max-temp-loc').innerText = maxTempLoc;

    document.getElementById('min-temp').innerText = minTemp !== 999 ? minTemp : '-';
    document.getElementById('min-temp-loc').innerText = minTempLoc;

    document.getElementById('max-rain').innerText = maxRain !== -1 ? maxRain : '-';
    document.getElementById('max-rain-loc').innerText = maxRainLoc;

    let commonWeather = Object.keys(weatherCounts).reduce((a, b) => weatherCounts[a] > weatherCounts[b] ? a : b, '-');
    document.getElementById('common-weather').innerText = commonWeather;
}

// Render Makers
function renderMarkers() {
    markerGroup.clearLayers();

    weatherData.forEach(d => {
        let val = currentLayer === 'temp' ? d.max_temp : d.pop;
        let suffix = currentLayer === 'temp' ? '°C' : '%';
        let color = currentLayer === 'temp' ? getTempColor(d.max_temp) : getRainColor(d.pop);

        let labelHtml = showLabels
            ? `<div class="custom-pill-label" style="border-left: 4px solid ${color};">${d.location} ${val}${suffix}</div>`
            : `<div class="custom-pill-label" style="width:16px;height:16px;border-radius:50%;padding:0;background:${color};border:2px solid white;"></div>`;

        let icon = L.divIcon({
            html: labelHtml,
            className: '',
            iconSize: showLabels ? [100, 30] : [16, 16],
            iconAnchor: showLabels ? [50, 15] : [8, 8]
        });

        let popupContent = `
            <div class="popup-custom">
                <h3>${d.location}</h3>
                <p>天氣：${d.weather}</p>
                <p>氣溫：${d.min_temp}°C ~ ${d.max_temp}°C</p>
                <p>降雨機率：${d.pop !== null ? d.pop + '%' : '-'}</p>
            </div>
        `;

        L.marker([d.lat, d.lon], { icon: icon })
            .bindPopup(popupContent)
            .addTo(markerGroup);
    });
}

// Events
document.getElementById('btn-temp').addEventListener('click', (e) => {
    currentLayer = 'temp';
    e.target.classList.add('active');
    document.getElementById('btn-rain').classList.remove('active');

    document.getElementById('legend-title').innerText = '°C';
    document.getElementById('legend-gradient').style.background = 'linear-gradient(to right, #3b82f6, #0ea5e9, #10b981, #f59e0b, #ef4444)';
    document.getElementById('legend-labels').innerHTML = '<span>5</span><span>10</span><span>15</span><span>20</span><span>24</span><span>28</span><span>32</span><span>36</span>';

    renderMarkers();
});

document.getElementById('btn-rain').addEventListener('click', (e) => {
    currentLayer = 'rain';
    e.target.classList.add('active');
    document.getElementById('btn-temp').classList.remove('active');

    document.getElementById('legend-title').innerText = '% 降雨機率';
    document.getElementById('legend-gradient').style.background = 'linear-gradient(to right, #94a3b8, #10b981, #0ea5e9, #3b82f6)';
    document.getElementById('legend-labels').innerHTML = '<span>0</span><span>20</span><span>50</span><span>80</span><span>100</span>';

    renderMarkers();
});

document.getElementById('toggle-marker').addEventListener('change', (e) => {
    showLabels = e.target.checked;
    renderMarkers();
});

document.getElementById('base-dark').addEventListener('click', (e) => {
    e.target.classList.add('active');
    document.getElementById('base-street').classList.remove('active');
    map.removeLayer(streetTiles);
    darkTiles.addTo(map);
});

document.getElementById('base-street').addEventListener('click', (e) => {
    e.target.classList.add('active');
    document.getElementById('base-dark').classList.remove('active');
    map.removeLayer(darkTiles);
    streetTiles.addTo(map);
});

document.getElementById('btn-locate').addEventListener('click', () => {
    map.setView([23.7, 121.0], 7);
});

// Boot
loadData();
