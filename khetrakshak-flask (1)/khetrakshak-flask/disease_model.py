"""
disease_model.py
-----------------
Crop Disease Photo Detection module.

IMPORTANT — READ THIS BEFORE THE HACKATHON:
This module runs in TWO modes:

  1. DEMO MODE (default, works with zero setup, zero internet)
     Returns a realistic-looking simulated diagnosis so your app is fully
     demoable right now. Clearly disclose this to judges if asked — it's
     completely normal for a hackathon MVP.

  2. REAL MODEL MODE (optional — do this on your own laptop before the
     final demo if you want a genuinely working AI model)
     Uses a pretrained PyTorch model fine-tuned on the PlantVillage
     dataset. This requires internet access to download model weights,
     so it can't be set up in this sandboxed environment — but the code
     below is ready to run as-is once you have torch/torchvision
     installed and internet access.

HOW TO ENABLE REAL MODEL MODE:
  1. pip install torch torchvision
  2. Download a PlantVillage-trained checkpoint. Two easy options:
       a) Use a ready HuggingFace model, e.g.:
          https://huggingface.co/linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification
          (search "plant disease" on huggingface.co/models for alternatives)
       b) Train your own quickly using the PlantVillage dataset:
          https://www.kaggle.com/datasets/emmarex/plantdisease
  3. Set REAL_MODEL = True below and fill in MODEL_PATH / class labels.
  4. Restart the Flask app — it will now run real inference.

For your hackathon submission, it's completely fine to say:
"Demo currently uses simulated classification; a production version
would integrate a PlantVillage-trained CNN, for which we've already
written the integration code" — judges respect that honesty and it
shows you understand the full path to production.
"""

REAL_MODEL = False  # flip to True once you've set up torch + a checkpoint locally

# ---------------------------------------------------------------------
# DEMO MODE — real color-pattern analysis, no torch required
# ---------------------------------------------------------------------
# This is NOT a trained CNN. It looks at the actual pixel colors of the
# uploaded photo (how much yellowing, browning, or dark-spotting is
# present) and maps that to the closest matching category. This means
# different photos genuinely produce different results, unlike a random
# guess — but it's still a heuristic, not real disease classification.
# Be upfront about this with judges; it's a legitimate "MVP now, CNN
# later" story.

DISEASE_INFO = {
    "Healthy Leaf": {
        "healthy": True,
        "en": {"name": "Healthy Leaf",
               "remedy": "No signs of disease detected. Continue regular watering and monitoring — check again if new spots appear."},
        "hi": {"name": "स्वस्थ पत्ती",
               "remedy": "कोई रोग नहीं दिख रहा। नियमित पानी और निगरानी जारी रखें — नए धब्बे दिखने पर फिर से जांचें।"},
        "gu": {"name": "તંદુરસ્ત પાન",
               "remedy": "કોઈ રોગના ચિહ્નો દેખાતા નથી. નિયમિત પાણી અને દેખરેખ ચાલુ રાખો — નવા ડાઘ દેખાય તો ફરી ચકાસો."},
    },
    "Leaf Blight": {
        "healthy": False,
        "en": {"name": "Leaf Blight",
               "remedy": "Remove and destroy affected leaves. Spray a copper-based fungicide every 7-10 days. Avoid overhead watering to reduce leaf wetness."},
        "hi": {"name": "पत्ती झुलसा रोग",
               "remedy": "प्रभावित पत्तियों को हटाकर नष्ट करें। हर 7-10 दिन में कॉपर-आधारित फफूंदनाशक छिड़कें। ऊपर से पानी देने से बचें।"},
        "gu": {"name": "પાન સુકારો રોગ",
               "remedy": "અસરગ્રસ્ત પાન દૂર કરી નાશ કરો. દર 7-10 દિવસે કોપર આધારિત ફૂગનાશક છાંટો. ઉપરથી પાણી આપવાનું ટાળો."},
    },
    "Powdery Mildew": {
        "healthy": False,
        "en": {"name": "Powdery Mildew / Nutrient Stress (yellowing)",
               "remedy": "Improve air circulation between plants. Apply a sulfur-based fungicide or a neem oil spray. Avoid excess nitrogen fertilizer."},
        "hi": {"name": "पाउडरी मिल्ड्यू / पोषक तत्व की कमी (पीलापन)",
               "remedy": "पौधों के बीच हवा का आवागमन बढ़ाएं। सल्फर-आधारित फफूंदनाशक या नीम तेल का छिड़काव करें। अधिक नाइट्रोजन खाद से बचें।"},
        "gu": {"name": "પાવડરી માઇલ્ડ્યુ / પોષક તત્વની ખામી (પીળાશ)",
               "remedy": "છોડ વચ્ચે હવાની અવરજવર વધારો. સલ્ફર આધારિત ફૂગનાશક અથવા લીમડાનું તેલ છાંટો. વધુ નાઇટ્રોજન ખાતર ટાળો."},
    },
    "Bacterial Leaf Spot": {
        "healthy": False,
        "en": {"name": "Bacterial Leaf Spot",
               "remedy": "Remove infected leaves immediately. Avoid working in the field when leaves are wet. Use a copper-based bactericide as a preventive spray."},
        "hi": {"name": "बैक्टीरियल लीफ स्पॉट",
               "remedy": "संक्रमित पत्तियों को तुरंत हटा दें। पत्तियां गीली होने पर खेत में काम न करें। कॉपर-आधारित बैक्टीरियानाशक का छिड़काव करें।"},
        "gu": {"name": "બેક્ટેરિયલ લીફ સ્પોટ",
               "remedy": "ચેપગ્રસ્ત પાન તરત દૂર કરો. પાન ભીના હોય ત્યારે ખેતરમાં કામ ન કરો. કોપર આધારિત બેક્ટેરિયાનાશક છાંટો."},
    },
}


def _analyze_colors(image_path: str) -> dict:
    """Real pixel-level analysis of the uploaded photo — computes the
    proportion of yellow, brown/dark, and healthy-green tones."""
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    img = img.resize((120, 120))  # downsample for speed
    pixels = list(img.getdata())

    total = len(pixels)
    yellow = brown = green = dark_spot = 0

    for r, g, b in pixels:
        # Yellowing: high red+green, low blue
        if r > 140 and g > 120 and b < 110:
            yellow += 1
        # Brown/blight: moderate red, low green, low blue
        elif r > 90 and r < 180 and g < 100 and b < 90:
            brown += 1
        # Dark spot (bacterial-style lesions): all channels low but not pure black background
        elif r < 70 and g < 70 and b < 70 and (r + g + b) > 30:
            dark_spot += 1
        # Healthy green: green clearly dominant
        elif g > r and g > b and g > 90:
            green += 1

    return {
        "yellow_ratio": yellow / total,
        "brown_ratio": brown / total,
        "dark_spot_ratio": dark_spot / total,
        "green_ratio": green / total,
    }


def predict_demo(image_path: str, lang: str = "en") -> dict:
    """Analyzes actual image colors to choose the closest-matching
    category, then returns the diagnosis in the requested language."""
    ratios = _analyze_colors(image_path)

    # Decide category based on strongest signal
    scores = {
        "Leaf Blight": ratios["brown_ratio"],
        "Powdery Mildew": ratios["yellow_ratio"],
        "Bacterial Leaf Spot": ratios["dark_spot_ratio"],
        "Healthy Leaf": ratios["green_ratio"],
    }
    category = max(scores, key=scores.get)
    top_score = scores[category]

    # Confidence scales with how dominant the winning signal is
    confidence = min(95, 55 + round(top_score * 150))
    if ratios["green_ratio"] > 0.55 and category != "Healthy Leaf":
        # Mostly green photo but a disease signal won — trust green more
        category = "Healthy Leaf"
        confidence = min(95, 55 + round(ratios["green_ratio"] * 60))

    info = DISEASE_INFO[category]
    lang = lang if lang in ("en", "hi", "gu") else "en"
    localized = info[lang]

    return {
        "name": localized["name"],
        "healthy": info["healthy"],
        "confidence": confidence,
        "remedy": localized["remedy"],
        "lang": lang,
    }


# ---------------------------------------------------------------------
# REAL MODEL MODE — requires torch + torchvision + internet to set up
# ---------------------------------------------------------------------
def predict_real(image_path: str) -> dict:
    """
    Real inference using a PyTorch image classification model.
    Fill in MODEL_PATH and CLASS_NAMES to match your downloaded checkpoint.
    """
    import torch
    from torchvision import transforms
    from PIL import Image

    MODEL_PATH = "models/plant_disease_model.pt"  # your downloaded/trained checkpoint

    # Example class list for a typical PlantVillage-trained model.
    # Replace this with the exact class order your checkpoint was trained on.
    CLASS_NAMES = [
        "Healthy Leaf",
        "Leaf Blight",
        "Powdery Mildew",
        "Bacterial Leaf Spot",
        "Early Blight",
        "Late Blight",
        "Mosaic Virus",
    ]

    REMEDY_MAP = {
        "Healthy Leaf": "No signs of disease detected. Continue regular watering and monitoring.",
        "Leaf Blight": "Remove and destroy affected leaves. Spray a copper-based fungicide every 7-10 days.",
        "Powdery Mildew": "Improve air circulation. Apply a sulfur-based fungicide or neem oil spray.",
        "Bacterial Leaf Spot": "Remove infected leaves. Avoid working in wet conditions. Use a copper-based bactericide.",
        "Early Blight": "Rotate crops yearly. Apply chlorothalonil or copper fungicide at first sign of spots.",
        "Late Blight": "Remove infected plants immediately to prevent spread. Apply a systemic fungicide.",
        "Mosaic Virus": "No cure available — remove and destroy infected plants. Control aphids, which spread the virus.",
    }

    model = torch.load(MODEL_PATH, map_location="cpu")
    model.eval()

    preprocess = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    img = Image.open(image_path).convert("RGB")
    input_tensor = preprocess(img).unsqueeze(0)

    with torch.no_grad():
        output = model(input_tensor)
        probs = torch.nn.functional.softmax(output[0], dim=0)
        confidence, predicted_idx = torch.max(probs, 0)

    predicted_class = CLASS_NAMES[predicted_idx.item()]

    return {
        "name": predicted_class,
        "healthy": predicted_class == "Healthy Leaf",
        "confidence": round(confidence.item() * 100),
        "remedy": REMEDY_MAP.get(predicted_class, "Consult a local agricultural expert for treatment options."),
    }


# ---------------------------------------------------------------------
def predict(image_path: str, lang: str = "en") -> dict:
    """Single entry point the Flask route calls — switches based on REAL_MODEL flag."""
    if REAL_MODEL:
        return predict_real(image_path)  # NOTE: hook up lang translation here too once real model is wired in
    return predict_demo(image_path, lang)
