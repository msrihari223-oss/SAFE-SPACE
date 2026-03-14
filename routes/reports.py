# routes/reports.py
# ─────────────────────────────────────────────────────────────
# POST /api/reports/submit   → student submits anonymous report
# GET  /api/reports          → moderator reads all reports
# PUT  /api/reports/<id>     → moderator updates report status
# ─────────────────────────────────────────────────────────────

from flask import Blueprint, request, jsonify
from database.db import get_conn
import logging

logger     = logging.getLogger(__name__)
reports_bp = Blueprint("reports", __name__)

VALID_TYPES = {
    "Harassment / Bullying",
    "Threats & Intimidation",
    "Identity-based Abuse",
    "Sexual Harassment",
    "Doxxing / Privacy Violation",
    "Other",
}
VALID_PLATFORMS = {"Instagram","Twitter/X","WhatsApp","Discord","Snapchat","Other"}
VALID_STATUSES  = {"pending","reviewed","escalated","closed"}


# ════════════════════════════════════════════════════════════════
# POST /api/reports/submit
# ════════════════════════════════════════════════════════════════
@reports_bp.route("/api/reports/submit", methods=["POST"])
def submit_report():
    """
    Student submits an anonymous bullying report.

    Request → {
        "report_type": "Harassment / Bullying",
        "platform":    "Instagram",
        "description": "A classmate keeps sending me..."
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    report_type = data.get("report_type", "").strip()
    platform    = data.get("platform",    "").strip()
    description = data.get("description", "").strip()

    # ── Validate ──────────────────────────────────────────────────
    errors = {}
    if not report_type:
        errors["report_type"] = "required"
    if not platform:
        errors["platform"] = "required"
    if not description:
        errors["description"] = "required"
    elif len(description) < 10:
        errors["description"] = "too short (min 10 characters)"
    elif len(description) > 3000:
        errors["description"] = "too long (max 3000 characters)"

    if errors:
        return jsonify({"error": "Validation failed", "fields": errors}), 422

    # ── Save ──────────────────────────────────────────────────────
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO reports (report_type, platform, description)
               VALUES (?, ?, ?)""",
            (report_type, platform, description)
        )
        report_id = cur.lastrowid

    logger.info("Report submitted | id=%d | type=%s | platform=%s",
                report_id, report_type, platform)

    return jsonify({
        "message":   "Report submitted successfully. A moderator will review it shortly.",
        "report_id": report_id,
    }), 201


# ════════════════════════════════════════════════════════════════
# GET /api/reports
# ════════════════════════════════════════════════════════════════
@reports_bp.route("/api/reports", methods=["GET"])
def list_reports():
    """
    Moderator reads all submitted reports.

    Query params (optional):
        status   = pending | reviewed | escalated | closed
        platform = Instagram | ...
        limit    = int (default 50)
        page     = int (default 1)
    """
    status   = request.args.get("status")
    platform = request.args.get("platform")
    limit    = min(int(request.args.get("limit", 50)), 100)
    page     = max(int(request.args.get("page",  1)),  1)
    offset   = (page - 1) * limit

    conditions, params = [], []
    if status:
        conditions.append("status = ?");   params.append(status)
    if platform:
        conditions.append("platform = ?"); params.append(platform)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM reports {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()

        total = conn.execute(
            f"SELECT COUNT(*) FROM reports {where}", params
        ).fetchone()[0]

    return jsonify({
        "reports": [dict(r) for r in rows],
        "total":   total,
        "page":    page,
        "limit":   limit,
    }), 200


# ════════════════════════════════════════════════════════════════
# PUT /api/reports/<id>
# ════════════════════════════════════════════════════════════════
@reports_bp.route("/api/reports/<int:report_id>", methods=["PUT"])
def update_report(report_id):
    """
    Moderator updates a report's status.

    Request → { "status": "reviewed" }
    """
    data = request.get_json(silent=True)
    if not data or "status" not in data:
        return jsonify({"error": "'status' field required"}), 400

    new_status = data["status"].lower()
    if new_status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of: {sorted(VALID_STATUSES)}"}), 400

    with get_conn() as conn:
        result = conn.execute(
            "UPDATE reports SET status = ? WHERE id = ?",
            (new_status, report_id)
        )
        if result.rowcount == 0:
            return jsonify({"error": f"Report {report_id} not found"}), 404

    logger.info("Report %d → '%s'", report_id, new_status)
    return jsonify({
        "message":   f"Report {report_id} marked as '{new_status}'",
        "report_id": report_id,
        "status":    new_status,
    }), 200
