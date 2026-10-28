from flask import Flask, jsonify, render_template, request
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "weather.db"

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
HTTP = requests.Session()

DESCRIPTIONS = {
    0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing Rime Fog", 51: "Light Drizzle",
    53: "Moderate Drizzle", 55: "Dense Drizzle", 56: "Light Freezing Drizzle",
    57: "Dense Freezing Drizzle", 61: "Light Rain", 63: "Moderate Rain",
    65: "Heavy Rain", 66: "Light Freezing Rain", 67: "Heavy Freezing Rain",
    71: "Light Snow", 73: "Moderate Snow", 75: "Heavy Snow", 77: "Snow Grains",
    80: "Rain Showers", 81: "Moderate Rain Showers", 82: "Heavy Rain Showers",
    85: "Snow Showers", 86: "Heavy Snow Showers", 95: "Thunderstorm",
    96: "Thunderstorm with Hail", 99: "Heavy Thunderstorm with Hail",
}


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the weather search history table if it does not exist."""
    with get_db_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS weather_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT NOT NULL,
                temperature REAL NOT NULL,
                feels_like REAL NOT NULL,
                humidity INTEGER NOT NULL,
                wind_speed REAL NOT NULL,
                description TEXT NOT NULL,
                weather_date TEXT NOT NULL,
                searched_at TEXT NOT NULL
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_weather_history_city "
            "ON weather_history(city)"
        )


def get_description(code):
    return DESCRIPTIONS.get(code, "Unknown Conditions")


def get_icon(code):
    if code == 0:
        return "☀️"
    if code in (1, 2):
        return "🌤️"
    if code == 3:
        return "☁️"
    if code in (45, 48):
        return "🌫️"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "🌧️"
    if code in (71, 73, 75, 77, 85, 86):
        return "❄️"
    if code in (95, 96, 99):
        return "⛈️"
    return "🌡️"


def fetch_weather(city):
    """Fetch live weather from Open-Meteo and return a normalized result."""
    geo_response = HTTP.get(
        GEOCODING_URL,
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=15,
    )
    geo_response.raise_for_status()
    locations = geo_response.json().get("results", [])
    if not locations:
        return None

    place = locations[0]
    weather_response = HTTP.get(
        WEATHER_URL,
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "timezone": "auto",
            "forecast_days": 7,
        },
        timeout=20,
    )
    weather_response.raise_for_status()
    data = weather_response.json()
    current = data["current"]
    code = current["weather_code"]

    name_parts = [place.get("name"), place.get("admin1"), place.get("country")]
    display_city = ", ".join(part for part in name_parts if part)

    current_weather = {
        "temperature": round(current["temperature_2m"]),
        "feels_like": round(current["apparent_temperature"]),
        "humidity": current["relative_humidity_2m"],
        "wind": current["wind_speed_10m"],
        "weather_code": code,
        "description": get_description(code),
        "icon": get_icon(code),
        "time": current["time"].replace("T", " "),
    }

    daily = data["daily"]
    rain_values = daily.get("precipitation_probability_max") or []
    forecast = []
    for index, date in enumerate(daily["time"]):
        daily_code = daily["weather_code"][index]
        rain = (
            rain_values[index]
            if index < len(rain_values) and rain_values[index] is not None
            else 0
        )
        forecast.append({
            "date": date,
            "icon": get_icon(daily_code),
            "description": get_description(daily_code),
            "max_temp": round(daily["temperature_2m_max"][index]),
            "min_temp": round(daily["temperature_2m_min"][index]),
            "rain": rain,
        })

    return {
        "city": display_city,
        "weather": current_weather,
        "forecast": forecast,
    }


def save_weather(result):
    """Save one current-weather snapshot to SQLite."""
    weather = result["weather"]
    with get_db_connection() as connection:
        connection.execute("""
            INSERT INTO weather_history
                (city, temperature, feels_like, humidity, wind_speed,
                 description, weather_date, searched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result["city"],
            weather["temperature"],
            weather["feels_like"],
            weather["humidity"],
            weather["wind"],
            weather["description"],
            weather["time"],
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ))


@app.get("/")
def home():
    return render_template("index.html", default_city="Hyderabad")


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "weather-forecasting-api",
        "database": "SQLite",
    })


@app.get("/api/weather")
def weather_api():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "Please enter a city name."}), 400
    if len(city) > 100:
        return jsonify({"error": "City name must be 100 characters or fewer."}), 400

    try:
        result = fetch_weather(city)
        if result is None:
            return jsonify({"error": "City not found. Please try another city."}), 404
        save_weather(result)
        return jsonify(result)
    except requests.Timeout:
        return jsonify({"error": "Weather service timed out. Please retry."}), 504
    except requests.RequestException:
        logger.exception("Weather provider request failed")
        return jsonify({
            "error": "Cannot connect to the weather service. Check your internet connection."
        }), 502
    except (KeyError, ValueError, IndexError, TypeError, sqlite3.Error):
        logger.exception("Could not process or save weather data")
        return jsonify({"error": "Weather data could not be processed or saved."}), 500


@app.get("/api/history")
def history_api():
    """Return the latest 50 saved weather searches."""
    try:
        with get_db_connection() as connection:
            rows = connection.execute("""
                SELECT id, city, temperature, feels_like, humidity, wind_speed,
                       description, weather_date, searched_at
                FROM weather_history
                ORDER BY id DESC
                LIMIT 50
            """).fetchall()
        return jsonify([dict(row) for row in rows])
    except sqlite3.Error:
        logger.exception("Could not read weather history")
        return jsonify({"error": "Could not read search history."}), 500


@app.delete("/api/history")
def clear_history():
    """Delete all saved search records."""
    try:
        with get_db_connection() as connection:
            connection.execute("DELETE FROM weather_history")
        return jsonify({"message": "Weather search history cleared."})
    except sqlite3.Error:
        logger.exception("Could not clear weather history")
        return jsonify({"error": "Could not clear search history."}), 500


init_db()

if __name__ == "__main__":
    # Development server; use a production WSGI server for deployment.
    app.run(host="127.0.0.1", port=5000, debug=True)
