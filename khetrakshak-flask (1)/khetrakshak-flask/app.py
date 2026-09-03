"""
app.py
------
KhetRakshak — Flask backend.

Routes:
  GET  /                     -> main single-page app
  GET  /api/schemes          -> list government schemes (supports ?q= & ?category=)
  POST /api/scan             -> upload a leaf image, get a diagnosis
  GET  /api/weather          -> live forecast and crop-protection advice
  GET  /api/markets          -> live AGMARKNET mandi prices
"""

import json
import os
import uuid
from datetime import datetime

import requests

from flask import Flask, jsonify, render_template, request

import disease_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
SCHEMES_PATH = os.path.join(BASE_DIR, "data", "schemes.json")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB upload limit

with open(SCHEMES_PATH, encoding="utf-8") as f:
    SCHEMES = json.load(f)

SCHEME_URLS = {
    "PM-KISAN": "https://pmkisan.gov.in/", "PMFBY (Crop Insurance)": "https://pmfby.gov.in/",
    "Kisan Credit Card (KCC)": "https://www.india.gov.in/spotlight/kisan-credit-card-kcc",
    "Soil Health Card Scheme": "https://soilhealth.dac.gov.in/", "PM Krishi Sinchayee Yojana": "https://pmksy.gov.in/",
    "e-NAM (National Agriculture Market)": "https://www.enam.gov.in/",
}
for scheme in SCHEMES:
    scheme["apply_url"] = SCHEME_URLS.get(scheme["name"], "https://www.india.gov.in/")

# Public Government of India resource: Daily Prices of Commodities.
# Set DATAGOV_API_KEY in production. DEMO_KEY is useful for local evaluation,
# but a personal key should be used before deployment to avoid rate limits.
AGMARKNET_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
DATAGOV_API_KEY = os.getenv("DATAGOV_API_KEY", "DEMO_KEY")
# Keep this False while developing or presenting offline. Change to True when
# a real Data.gov.in key is ready and live AGMARKNET prices are required.
USE_LIVE_MARKET_DATA = False

SAMPLE_MARKET_RECORDS = [
    {"market": "Ahmedabad APMC", "commodity": "Tomato", "date": "03-09-2026", "min_price": "1,200", "modal_price": "1,650", "max_price": "2,100"},
    {"market": "Rajkot APMC", "commodity": "Tomato", "date": "03-09-2026", "min_price": "1,100", "modal_price": "1,550", "max_price": "2,000"},
    {"market": "Surat APMC", "commodity": "Tomato", "date": "02-09-2026", "min_price": "1,300", "modal_price": "1,700", "max_price": "2,200"},
    {"market": "Gondal APMC", "commodity": "Groundnut", "date": "03-09-2026", "min_price": "5,400", "modal_price": "6,100", "max_price": "6,650"},
    {"market": "Unjha APMC", "commodity": "Cumin", "date": "03-09-2026", "min_price": "18,000", "modal_price": "20,250", "max_price": "22,000"},
    {"market": "Deesa APMC", "commodity": "Potato", "date": "03-09-2026", "min_price": "900", "modal_price": "1,150", "max_price": "1,400"},
    {"market": "Vadodara APMC", "commodity": "Onion", "date": "02-09-2026", "min_price": "1,300", "modal_price": "1,600", "max_price": "1,950"},
    {"market": "Jamnagar APMC", "commodity": "Cotton", "date": "03-09-2026", "min_price": "6,200", "modal_price": "6,650", "max_price": "7,050"},
    {"market": "Palanpur APMC", "commodity": "Wheat", "date": "03-09-2026", "min_price": "2,350", "modal_price": "2,550", "max_price": "2,700"},
    {"market": "Mehsana APMC", "commodity": "Castor", "date": "03-09-2026", "min_price": "5,650", "modal_price": "5,950", "max_price": "6,300"},
]


# ---------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------
@app.route("/")
def index():
    categories = sorted({s["category"] for s in SCHEMES})
    return render_template("index.html", categories=categories)


# ---------------------------------------------------------------------
# Sarkari Yojana Guide API
# ---------------------------------------------------------------------
@app.route("/api/schemes")
def api_schemes():
    query = request.args.get("q", "").lower().strip()
    category = request.args.get("category", "All")

    results = SCHEMES
    if category and category != "All":
        results = [s for s in results if s["category"] == category]
    if query:
        results = [
            s for s in results
            if query in s["name"].lower() or query in s["desc"].lower()
        ]
    return jsonify(results)


# ---------------------------------------------------------------------
# Live weather — Open-Meteo uses geocoding plus forecast endpoints and
# does not need a key. The endpoint returns forecast data and farmer advice.
# ---------------------------------------------------------------------
WEATHER_TEXT = {
    "en": {
        "rain": ("Rain expected", "Avoid spraying fertiliser or pesticide before rain. Improve drainage and harvest mature produce if possible."),
        "heat": ("High heat", "Irrigate in the early morning, use mulch where possible and avoid transplanting during the hottest hours."),
        "wind": ("Strong wind", "Support young plants, postpone pesticide spraying and secure shade nets or covers."),
        "normal": ("Routine field check", "Check soil moisture and inspect leaves early in the morning for pests or disease symptoms."),
    },
    "hi": {
        "rain": ("बारिश की संभावना", "बारिश से पहले कीटनाशक या उर्वरक का छिड़काव न करें। जल निकासी साफ रखें और पकी उपज हो तो काट लें।"),
        "heat": ("अधिक गर्मी", "सुबह जल्दी सिंचाई करें, मल्च का उपयोग करें और तेज धूप में रोपाई से बचें।"),
        "wind": ("तेज हवा", "छोटे पौधों को सहारा दें, छिड़काव टालें और जाल या ढकने की चीज़ें सुरक्षित करें।"),
        "normal": ("नियमित खेत जाँच", "मिट्टी की नमी जाँचें और सुबह पत्तियों पर कीट या रोग के लक्षण देखें।"),
    },
    "gu": {
        "rain": ("વરસાદની શક્યતા", "વરસાદ પહેલાં ખાતર કે જંતુનાશક ન છાંટો. પાણીનો નિકાલ સાફ રાખો અને પાકી ઉપજ હોય તો લણણી કરો."),
        "heat": ("વધુ ગરમી", "વહેલી સવારે સિંચાઈ કરો, શક્ય હોય ત્યાં મલ્ચ વાપરો અને ભારે ગરમીમાં રોપણી ટાળો."),
        "wind": ("તીવ્ર પવન", "નાના છોડને ટેકો આપો, છંટકાવ ટાળો અને શેડ નેટ અથવા આવરણ સુરક્ષિત કરો."),
        "normal": ("નિયમિત ખેતર તપાસ", "જમીનની ભેજ તપાસો અને સવારે પાન પર જીવાત કે રોગના લક્ષણો જુઓ."),
    },
}


@app.route("/api/weather")
def api_weather():
    location = request.args.get("location", "Ahmedabad, Gujarat").strip()
    lang = request.args.get("lang", "en")
    lang = lang if lang in WEATHER_TEXT else "en"
    if not location:
        return jsonify({"error": "Please enter a location"}), 400
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "language": "en", "format": "json"}, timeout=10,
        ).json()
        if not geo.get("results"):
            return jsonify({"error": "Location not found. Try village, town and state."}), 404
        place = geo["results"][0]
        forecast = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": place["latitude"], "longitude": place["longitude"], "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max", "timezone": "auto", "forecast_days": 5}, timeout=10,
        ).json()["daily"]
    except (requests.RequestException, KeyError, ValueError):
        return jsonify({"error": "Live weather is unavailable right now. Please try again shortly."}), 503

    summaries = {0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle", 61: "Rain", 63: "Rain", 65: "Heavy rain", 80: "Rain showers", 81: "Rain showers", 82: "Heavy showers", 95: "Thunderstorm"}
    days = []
    for i, date in enumerate(forecast["time"]):
        days.append({"day": datetime.strptime(date, "%Y-%m-%d").strftime("%a, %d %b"), "code": forecast["weather_code"][i], "max": round(forecast["temperature_2m_max"][i]), "min": round(forecast["temperature_2m_min"][i]), "rain": forecast["precipitation_sum"][i], "wind": round(forecast["wind_speed_10m_max"][i]), "summary": summaries.get(forecast["weather_code"][i], "Variable weather")})
    first = days[:2]
    alert_keys = []
    if any(d["rain"] >= 5 or d["code"] >= 61 for d in first): alert_keys.append("rain")
    if any(d["max"] >= 35 for d in first): alert_keys.append("heat")
    if any(d["wind"] >= 35 for d in first): alert_keys.append("wind")
    if not alert_keys: alert_keys.append("normal")
    return jsonify({"location": f"{place['name']}, {place.get('admin1') or place.get('country', '')}", "days": days, "advice": [{"title": WEATHER_TEXT[lang][key][0], "message": WEATHER_TEXT[lang][key][1]} for key in alert_keys]})


# ---------------------------------------------------------------------
# Live mandi prices — AGMARKNET / data.gov.in
# ---------------------------------------------------------------------
@app.route("/api/markets")
def api_markets():
    state = request.args.get("state", "").strip()
    district = request.args.get("district", "").strip()
    commodity = request.args.get("commodity", "").strip()
    if not USE_LIVE_MARKET_DATA:
        return jsonify({"records": SAMPLE_MARKET_RECORDS, "updated": "Sample records — not live market prices", "source": "Demo data · 10 sample mandi records"})
    if DATAGOV_API_KEY == "DEMO_KEY":
        return jsonify({"error": "Mandi prices need your free Data.gov.in API key. Set DATAGOV_API_KEY, restart the app, then try again."}), 503
    params = {"api-key": DATAGOV_API_KEY, "format": "json", "limit": 30}
    if state: params["filters[state]"] = state
    if district: params["filters[district]"] = district
    if commodity: params["filters[commodity]"] = commodity
    try:
        response = requests.get(f"https://api.data.gov.in/resource/{AGMARKNET_RESOURCE}", params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return jsonify({"error": "Official mandi data is unavailable right now. Please try again shortly."}), 503
    records = payload.get("records", [])
    # Do not provide static or invented fallback values: every row is source data.
    clean = [{"market": row.get("market", "—"), "commodity": row.get("commodity", "—"), "date": row.get("arrival_date", "—"), "min_price": row.get("min_price", "—"), "modal_price": row.get("modal_price", "—"), "max_price": row.get("max_price", "—")} for row in records]
    return jsonify({"records": clean, "updated": "AGMARKNET live query", "source": "Live Government of India AGMARKNET data"})


# ---------------------------------------------------------------------
# Crop Disease Scan API
# ---------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/api/scan", methods=["POST"])
def api_scan():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Please upload a JPG, PNG, or WEBP image"}), 400

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[1].lower()
    saved_name = f"{uuid.uuid4().hex}.{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_name)
    file.save(saved_path)

    lang = request.form.get("lang", "en")

    try:
        result = disease_model.predict(saved_path, lang)
    except Exception as e:
        return jsonify({"error": f"Model error: {e}"}), 500

    result["image_url"] = f"/static/uploads/{saved_name}"
    return jsonify(result)


if __name__ == "__main__":
    # Enable only for your own computer while developing. Public deployments
    # should never expose Flask's interactive debugger.
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", port=5000)
