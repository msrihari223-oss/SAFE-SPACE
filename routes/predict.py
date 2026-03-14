# routes/predict.py
# ─────────────────────────────────────────────────────────────
# POST /api/predict   → analyze one message
# POST /api/batch     → analyze up to 50 messages
# ─────────────────────────────────────────────────────────────

from flask import Blueprint, request, jsonify
from model.loader import predict
from database.db  import save_prediction, save_alert
from utils        import build_response
import logging

logger     = logging.getLogger(__name__)
predict_bp = Blueprint("predict", __name__)


# ════════════════════════════════════════════════════════════════
# POST /api/predict
# ════════════════════════════════════════════════════════════════
@predict_bp.route("/api/predict", methods=["POST"])
def analyze_single():
    """
    Analyze one message for cyberbullying.

    Request  → { "text": "...", "platform": "Instagram" }
    Response → { label, confidence, confidence_pct, severity_score,
                 categories, action, platform, source, prediction_id }
    """
    data = request.get_json(silent=True)

    # ── Validate ──────────────────────────────────────────────────
    if not data or "text" not in data:
        return jsonify({"error": "Request body must contain 'text'"}), 400

    raw_text = data["text"].strip()
    platform = data.get("platform", "Unknown").strip()

    if not raw_text:
        return jsonify({"error": "text cannot be empty"}), 400
    if len(raw_text) > 2000:
        return jsonify({"error": "text exceeds 2000 character limit"}), 400

    # ── Predict ───────────────────────────────────────────────────
    pred   = predict(raw_text)
    result = build_response(raw_text, platform, pred)

    # ── Save to DB ────────────────────────────────────────────────
    pred_id = save_prediction(
        text       = raw_text,
        platform   = platform,
        label      = result["label"],
        confidence = result["confidence"],
        categories = result["categories"],
        action     = result["action"],
        source     = result["source"],
    )

    # ── Auto-create alert for WARNING / DANGER ────────────────────
    if result["label"] in ("WARNING", "DANGER"):
        save_alert(
            pred_id  = pred_id,
            label    = result["label"],
            platform = platform,
            summary  = f"{result['label']} detected ({result['confidence_pct']}). "
                       f"Categories: {', '.join(result['categories'])}. "
                       f"Text snippet: \"{raw_text[:80]}\"",
        )
        logger.warning("ALERT created | label=%s | platform=%s | id=%s",
                       result["label"], platform, pred_id)

    result["prediction_id"] = pred_id
    logger.info("Predict | label=%s | conf=%s | platform=%s",
                result["label"], result["confidence_pct"], platform)
    return jsonify(result), 200


# ════════════════════════════════════════════════════════════════
# POST /api/batch
# ════════════════════════════════════════════════════════════════
@predict_bp.route("/api/batch", methods=["POST"])
def analyze_batch():
    """
    Analyze up to 50 messages at once.

    Request  → { "messages": ["msg1", "msg2", ...] }
    Response → { results: [...], total, flagged }
    """
    data = request.get_json(silent=True)

    if not data or "messages" not in data:
        return jsonify({"error": "Request body must contain 'messages' list"}), 400

    messages = data["messages"]

    if not isinstance(messages, list):
        return jsonify({"error": "'messages' must be a JSON array"}), 400
    if len(messages) == 0:
        return jsonify({"error": "messages list is empty"}), 400
    if len(messages) > 50:
        return jsonify({"error": "Maximum 50 messages per batch request"}), 400

    results = []
    flagged = 0

    for msg in messages:
        raw  = str(msg).strip()
        if not raw:
            continue

        pred   = predict(raw)
        result = build_response(raw, "Batch", pred)

        # Save each prediction
        pred_id = save_prediction(
            text       = raw,
            platform   = "Batch",
            label      = result["label"],
            confidence = result["confidence"],
            categories = result["categories"],
            action     = result["action"],
            source     = result["source"],
        )

        if result["label"] in ("WARNING", "DANGER"):
            flagged += 1
            save_alert(pred_id, result["label"], "Batch",
                       f"Batch | {result['label']} | \"{raw[:80]}\"")

        results.append({
            "text":           raw[:100] + ("..." if len(raw) > 100 else ""),
            "label":          result["label"],
            "confidence_pct": result["confidence_pct"],
            "categories":     result["categories"],
            "prediction_id":  pred_id,
        })

    logger.info("Batch | total=%d | flagged=%d", len(results), flagged)
    return jsonify({
        "results": results,
        "total":   len(results),
        "flagged": flagged,
        "safe":    len(results) - flagged,
    }), 200
