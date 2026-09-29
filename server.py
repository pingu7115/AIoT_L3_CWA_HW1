from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, 'static'))
CORS(app)

def get_db_connection():
    db_path = os.path.join(BASE_DIR, 'data.db')
    # Vercel filesystem is Read-Only. Must connect to SQLite in read-only mode.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/weather')
def get_weather():
    conn = get_db_connection()
    # Get the latest forecast for each location
    df = pd.read_sql_query('''
        SELECT location_name, min_temp, max_temp, weather, rain_probability, forecast_start
        FROM weather_forecasts
        WHERE forecast_start = (SELECT MIN(forecast_start) FROM weather_forecasts)
    ''', conn)
    conn.close()
    
    COORDINATES = {
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
    }
    
    data = []
    for _, row in df.iterrows():
        loc = row['location_name']
        data.append({
            "location": loc,
            "min_temp": row['min_temp'],
            "max_temp": row['max_temp'],
            "weather": row['weather'],
            "pop": row['rain_probability'],
            "lat": COORDINATES.get(loc, [23.5, 121.0])[0],
            "lon": COORDINATES.get(loc, [23.5, 121.0])[1],
            "time": row['forecast_start']
        })
        
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
