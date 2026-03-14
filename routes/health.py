# routes/health.py
# GET /api/health  →  server status + model info

from flask import jsonify
from model.loader import model, vectorizer
from database.db  import get_conn
import platform, sys

health_bp = __import__('flask', fromlist=['Blueprint']).Blueprint("health", __name__)

@health_bp.route("/api/health", methods=["GET"])
def health():
    # Quick DB ping
    try:
        with get_conn() as conn:
            pred_count  = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
            alert_count = conn.execute("SELECT COUNT(*) FROM alerts WHERE status='new'").fetchone()[0]
        db_status = "connected"
    except Exception as e:
        pred_count = alert_count = 0
        db_status = f"error: {e}"

    return jsonify({
        "status":       "online",
        "model":        "loaded" if (model and vectorizer) else "demo_mode",
        "database":     db_status,
        "predictions":  pred_count,
        "open_alerts":  alert_count,
        "python":       sys.version.split()[0],
        "platform":     platform.system(),
        "endpoints": {
            "predict": "POST /api/predict",
            "batch":   "POST /api/batch",
            "alerts":  "GET  /api/alerts",
            "reports": "GET  /api/reports",
            "stats":   "GET  /api/alerts/stats",
        }
    }), 200
