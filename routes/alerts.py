# routes/alerts.py
# ─────────────────────────────────────────────────────────────
# GET /api/alerts              → list all alerts (moderator feed)
# GET /api/alerts/<id>         → single alert details
# PUT /api/alerts/<id>         → update status (reviewing/resolved)
# GET /api/alerts/stats        → summary counts
# ─────────────────────────────────────────────────────────────

from flask import Blueprint, request, jsonify
from database.db import get_conn
import logging

logger    = logging.getLogger(__name__)
alerts_bp = Blueprint("alerts", __name__)

VALID_STATUSES = {"new", "reviewing", "resolved"}


# ════════════════════════════════════════════════════════════════
# GET /api/alerts
# ════════════════════════════════════════════════════════════════
@alerts_bp.route("/api/alerts", methods=["GET"])
def list_alerts():
    """
    Returns moderator alert feed.

    Query params (all optional):
        status   = new | reviewing | resolved   (filter by status)
        label    = WARNING | DANGER             (filter by severity)
        platform = Instagram | ...              (filter by platform)
        limit    = int (default 50)
        page     = int (default 1)
    """
    status   = request.args.get("status")
    label    = request.args.get("label")
    platform = request.args.get("platform")
    limit    = min(int(request.args.get("limit", 50)), 100)
    page     = max(int(request.args.get("page",  1)),  1)
    offset   = (page - 1) * limit

    # Build dynamic WHERE clause
    conditions, params = [], []
    if status:
        conditions.append("a.status = ?");   params.append(status)
    if label:
        conditions.append("a.label = ?");    params.append(label)
    if platform:
        conditions.append("a.platform = ?"); params.append(platform)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT a.id, a.label, a.platform, a.summary, a.status,
                   a.created_at, a.resolved_at,
                   p.text, p.confidence, p.categories
            FROM   alerts a
            JOIN   predictions p ON p.id = a.pred_id
            {where}
            ORDER  BY a.created_at DESC
            LIMIT  ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        total = conn.execute(
            f"SELECT COUNT(*) FROM alerts a {where}", params
        ).fetchone()[0]

    return jsonify({
        "alerts": [dict(r) for r in rows],
        "total":  total,
        "page":   page,
        "limit":  limit,
    }), 200


# ════════════════════════════════════════════════════════════════
# GET /api/alerts/stats  (must be before /<id> route)
# ════════════════════════════════════════════════════════════════
@alerts_bp.route("/api/alerts/stats", methods=["GET"])
def alert_stats():
    """Dashboard summary counts."""
    with get_conn() as conn:
        total      = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        new        = conn.execute("SELECT COUNT(*) FROM alerts WHERE status='new'").fetchone()[0]
        reviewing  = conn.execute("SELECT COUNT(*) FROM alerts WHERE status='reviewing'").fetchone()[0]
        resolved   = conn.execute("SELECT COUNT(*) FROM alerts WHERE status='resolved'").fetchone()[0]
        danger_cnt = conn.execute("SELECT COUNT(*) FROM alerts WHERE label='DANGER'").fetchone()[0]
        warn_cnt   = conn.execute("SELECT COUNT(*) FROM alerts WHERE label='WARNING'").fetchone()[0]

        # Total predictions
        total_pred = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        safe_pred  = conn.execute("SELECT COUNT(*) FROM predictions WHERE label='SAFE'").fetchone()[0]

    return jsonify({
        "alerts": {
            "total":     total,
            "new":       new,
            "reviewing": reviewing,
            "resolved":  resolved,
        },
        "severity": {
            "danger":  danger_cnt,
            "warning": warn_cnt,
        },
        "predictions": {
            "total":   total_pred,
            "safe":    safe_pred,
            "flagged": total_pred - safe_pred,
        }
    }), 200


# ════════════════════════════════════════════════════════════════
# GET /api/alerts/<id>
# ════════════════════════════════════════════════════════════════
@alerts_bp.route("/api/alerts/<int:alert_id>", methods=["GET"])
def get_alert(alert_id):
    """Full details for one alert."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT a.*, p.text, p.confidence, p.categories, p.source
            FROM   alerts a
            JOIN   predictions p ON p.id = a.pred_id
            WHERE  a.id = ?
        """, (alert_id,)).fetchone()

    if not row:
        return jsonify({"error": f"Alert {alert_id} not found"}), 404
    return jsonify(dict(row)), 200


# ════════════════════════════════════════════════════════════════
# PUT /api/alerts/<id>
# ════════════════════════════════════════════════════════════════
@alerts_bp.route("/api/alerts/<int:alert_id>", methods=["PUT"])
def update_alert(alert_id):
    """
    Moderator updates alert status.

    Request → { "status": "reviewing" | "resolved" }
    """
    data = request.get_json(silent=True)
    if not data or "status" not in data:
        return jsonify({"error": "Request body must contain 'status'"}), 400

    new_status = data["status"].lower()
    if new_status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of: {VALID_STATUSES}"}), 400

    resolved_at = "datetime('now')" if new_status == "resolved" else "NULL"

    with get_conn() as conn:
        result = conn.execute(
            f"""UPDATE alerts
                SET status = ?, resolved_at = {resolved_at}
                WHERE id = ?""",
            (new_status, alert_id)
        )
        if result.rowcount == 0:
            return jsonify({"error": f"Alert {alert_id} not found"}), 404

    logger.info("Alert %d → status updated to '%s'", alert_id, new_status)
    return jsonify({
        "message":  f"Alert {alert_id} updated to '{new_status}'",
        "alert_id": alert_id,
        "status":   new_status,
    }), 200
