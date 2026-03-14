# model/loader.py
# ─────────────────────────────────────────────────────────────
# Loads your ML teammate's saved model (Pickle / Joblib).
# Falls back to rule-based demo if model files are missing.
# ─────────────────────────────────────────────────────────────

import joblib, pickle, os, re, logging

logger = logging.getLogger(__name__)

MODEL_PATH      = os.path.join(os.path.dirname(__file__), "cyberbullying_model.pkl")
VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), "vectorizer.pkl")

model      = None
vectorizer = None


def load():
    """Called once at app startup."""
    global model, vectorizer
    try:
        if os.path.exists(MODEL_PATH):
            model = joblib.load(MODEL_PATH)
            logger.info("✅ ML model loaded: %s", MODEL_PATH)
        else:
            logger.warning("⚠️  Model file not found → running in DEMO mode")

        if os.path.exists(VECTORIZER_PATH):
            vectorizer = joblib.load(VECTORIZER_PATH)
            logger.info("✅ Vectorizer loaded: %s", VECTORIZER_PATH)
        else:
            logger.warning("⚠️  Vectorizer file not found → running in DEMO mode")

    except Exception as e:
        logger.error("Model load failed: %s", e)


# ── Text cleaning ─────────────────────────────────────────────────
def preprocess(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'http\S+|www\S+', '', text)   # strip URLs
    text = re.sub(r'@\w+', '', text)              # strip @mentions
    text = re.sub(r'#\w+', '', text)              # strip #hashtags
    text = re.sub(r'[^a-z\s]', ' ', text)         # letters only
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ── Label mapping ─────────────────────────────────────────────────
# ⚠️  EDIT THIS if your ML teammate uses different numbers
LABEL_MAP = {0: "SAFE", 1: "WARNING", 2: "DANGER"}


# ── Real model prediction ─────────────────────────────────────────
def ml_predict(clean_text: str) -> dict:
    features   = vectorizer.transform([clean_text])
    pred       = model.predict(features)[0]
    proba      = model.predict_proba(features)[0]
    confidence = float(max(proba))
    label      = LABEL_MAP.get(int(pred), str(pred))
    return {"label": label, "confidence": confidence, "source": "model"}


# ── Rule-based fallback (demo mode) ──────────────────────────────
_HIGH = [
    "kill", "die", "hate you", "worthless", "nobody likes",
    "find you", "hurt you", "end yourself", "threaten", "stupid idiot",
    "loser", "pathetic", "address", "where you live", "come for you"
]
_MED  = [
    "cringe", "dumb", "boring", "annoying", "nobody cares",
    "get out", "leave", "freak", "weirdo", "ugly",
    "shut up", "go away", "fat", "disgust"
]

def demo_predict(raw_text: str) -> dict:
    t = raw_text.lower()
    if any(w in t for w in _HIGH):
        return {"label": "DANGER",  "confidence": 0.91, "source": "demo"}
    if any(w in t for w in _MED):
        return {"label": "WARNING", "confidence": 0.72, "source": "demo"}
    return {"label": "SAFE", "confidence": 0.95, "source": "demo"}


# ── Public entry point ────────────────────────────────────────────
def predict(raw_text: str) -> dict:
    """Returns {"label", "confidence", "source"}"""
    clean = preprocess(raw_text)
    if model and vectorizer:
        try:
            return ml_predict(clean)
        except Exception as e:
            logger.error("ML predict error: %s — falling back to demo", e)
    return demo_predict(raw_text)


# Load on import
load()
