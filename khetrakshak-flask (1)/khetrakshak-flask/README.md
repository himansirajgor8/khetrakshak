# KhetRakshak — Flask Version

## Current features

English, Hindi and Gujarati UI; crop-photo diagnosis; government scheme application links; live Open-Meteo forecasts with crop-protection alerts; and ten clearly labelled sample mandi-price rows. Real Government of India AGMARKNET data can be enabled later with `DATAGOV_API_KEY`.

## Project structure
```
khetrakshak-flask/
├── app.py                  # Flask routes (backend entry point)
├── security.py             # Anomaly detection + hash-chain logic (Module 1)
├── disease_model.py        # Crop disease detection (Module 3) — demo + real model code
├── data/schemes.json       # Government scheme data (Module 2)
├── requirements.txt
├── templates/index.html    # Single-page frontend (Jinja template)
└── static/
    ├── css/style.css
    ├── js/app.js            # Frontend logic — calls the Flask API
    └── uploads/             # Uploaded leaf photos land here
```

## How to run it

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser.

## What's real vs simulated

| Module | Status |
|---|---|
| Security Ledger (anomaly detection, trust scores, SHA-256 hash chain) | **Fully real** — actual peer-comparison math and real SHA-256 hashing in `security.py` |
| Sarkari Yojana Guide (search, filter, scheme details) | **Fully real** — real Flask search/filter logic over `data/schemes.json` |
| Crop Disease Detection | **Simulated by default.** See below to make it real. |

## Making crop disease detection real

`disease_model.py` has two functions: `predict_demo()` (default, works with zero setup) and `predict_real()` (a complete, ready-to-run PyTorch inference pipeline).

To switch it on, **on your own laptop with internet access**:
1. `pip install torch torchvision`
2. Download a PlantVillage-trained checkpoint (search "plant disease" on huggingface.co/models, or train your own on the [PlantVillage dataset](https://www.kaggle.com/datasets/emmarex/plantdisease))
3. Update `MODEL_PATH` and `CLASS_NAMES` in `disease_model.py` to match your checkpoint
4. Set `REAL_MODEL = True` at the top of `disease_model.py`
5. Restart the app

This sandboxed environment has no internet access, so this step has to happen on your machine — but all the integration code is already written and ready to go.

## Extending it further
- Add teammate's price-predictor or voice-assistant modules as new files (`pricing.py`, etc.) and wire up new routes in `app.py` the same way `security.py` and `disease_model.py` are wired in.
- For a persistent database instead of in-memory state, swap `SensorNetwork`'s in-memory lists for SQLite (Flask has built-in support via `sqlite3` or `flask-sqlalchemy`).
