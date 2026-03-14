# database/db.py
# ─────────────────────────────────────────────────────────────
# SQLite database — stores every prediction + incident reports
# No extra server needed. File: database/safespace.db
# ─────────────────────────────────────────────────────────────

import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "safespace.db")

def get_conn():
    """Return a new DB connection. Use in a with-block."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # Rows behave like dicts
    return conn


def init_db():
    """Create tables if they don't exist yet."""
    with get_conn() as conn:
        conn.executescript("""

        -- Every message that gets analyzed
        CREATE TABLE IF NOT EXISTS predictions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            text        TEXT    NOT NULL,
            platform    TEXT    DEFAULT 'Unknown',
            label       TEXT    NOT NULL,           -- SAFE | WARNING | DANGER
            confidence  REAL    NOT NULL,
            categories  TEXT    NOT NULL,           -- JSON array as string
            action      TEXT    NOT NULL,
            source      TEXT    DEFAULT 'model',    -- model | demo
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        -- High-severity cases that need moderator attention
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pred_id     INTEGER REFERENCES predictions(id),
            label       TEXT    NOT NULL,
            platform    TEXT    NOT NULL,
            summary     TEXT    NOT NULL,
            status      TEXT    DEFAULT 'new',      -- new | reviewing | resolved
            created_at  TEXT    DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        -- Anonymous reports submitted by students
        CREATE TABLE IF NOT EXISTS reports (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type  TEXT NOT NULL,
            platform     TEXT NOT NULL,
            description  TEXT NOT NULL,
            status       TEXT DEFAULT 'pending',    -- pending | reviewed | escalated
            created_at   TEXT DEFAULT (datetime('now'))
        );

        """)
    print("✅ Database ready →", DB_PATH)


# ── Small helper used across routes ──────────────────────────────

def save_prediction(text, platform, label, confidence, categories, action, source):
    """Insert one prediction row; return its new id."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO predictions
               (text, platform, label, confidence, categories, action, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (text, platform, label, round(confidence, 4),
             str(categories), action, source)
        )
        return cur.lastrowid


def save_alert(pred_id, label, platform, summary):
    """Create a moderator alert for WARNING/DANGER predictions."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO alerts (pred_id, label, platform, summary)
               VALUES (?, ?, ?, ?)""",
            (pred_id, label, platform, summary)
        )
