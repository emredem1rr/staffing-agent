"""
Gelişmiş SQLite veritabanı katmanı — v2

Yeni tablolar:
- staff_scores: Performans puanlama
- schedule: Takvim ve müsaitlik
- agent_memory: Uzun süreli hafıza
- agent_activity: Canlı aktivite logu
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Any

DB_PATH = os.getenv("DB_PATH", "staffing_agent.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    """Tüm tabloları oluştur."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            email TEXT,
            roles TEXT NOT NULL,
            location TEXT,
            hourly_rate REAL DEFAULT 0,
            status TEXT DEFAULT 'available',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS staff_scores (
            staff_id INTEGER PRIMARY KEY,
            reliability_score REAL DEFAULT 5.0,
            quality_score REAL DEFAULT 5.0,
            response_speed REAL DEFAULT 5.0,
            total_jobs INTEGER DEFAULT 0,
            completed_jobs INTEGER DEFAULT 0,
            cancelled_jobs INTEGER DEFAULT 0,
            no_show_count INTEGER DEFAULT 0,
            avg_response_minutes REAL DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        );

        CREATE TABLE IF NOT EXISTS client_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            original_message TEXT NOT NULL,
            contact_email TEXT,
            contact_phone TEXT,
            priority TEXT DEFAULT 'normal',
            parsed_needs TEXT,
            status TEXT DEFAULT 'pending',
            agent_log TEXT DEFAULT '[]',
            crew_result TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            status TEXT DEFAULT 'invited',
            message_sent TEXT,
            invited_at TEXT DEFAULT (datetime('now','localtime')),
            responded_at TEXT,
            FOREIGN KEY (request_id) REFERENCES client_requests(id),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        );

        CREATE TABLE IF NOT EXISTS messages_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER,
            staff_id INTEGER NOT NULL,
            request_id INTEGER NOT NULL,
            message_type TEXT NOT NULL,
            message_text TEXT NOT NULL,
            channel TEXT DEFAULT 'sms',
            sent_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            request_id INTEGER,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT,
            client_name TEXT,
            role TEXT,
            status TEXT DEFAULT 'confirmed',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        );

        CREATE TABLE IF NOT EXISTS agent_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            relevance_score REAL DEFAULT 1.0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            last_accessed TEXT DEFAULT (datetime('now','localtime')),
            access_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS agent_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            agent_role TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT NOT NULL,
            thought_data TEXT,
            timestamp TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_staff_phone ON staff(phone);
    """)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════
# STAFF CRUD
# ═══════════════════════════════════════════════════════

def create_staff(name, phone, roles, email=None, location=None, hourly_rate=0):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO staff (name,phone,email,roles,location,hourly_rate) VALUES (?,?,?,?,?,?)",
        (name, phone, email, json.dumps(roles, ensure_ascii=False), location, hourly_rate)
    )
    staff_id = cur.lastrowid
    conn.execute(
        "INSERT OR IGNORE INTO staff_scores (staff_id) VALUES (?)", (staff_id,)
    )
    conn.commit()
    conn.close()
    return staff_id


def get_all_staff():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, sc.total_jobs, sc.completed_jobs, sc.cancelled_jobs,
               sc.no_show_count
        FROM staff s
        LEFT JOIN staff_scores sc ON s.id = sc.staff_id
        ORDER BY s.name
    """).fetchall()
    conn.close()
    return [_staff_row(r) for r in rows]


def get_staff_by_id(staff_id):
    conn = get_db()
    row = conn.execute("""
        SELECT s.*, sc.total_jobs, sc.completed_jobs, sc.cancelled_jobs,
               sc.no_show_count
        FROM staff s LEFT JOIN staff_scores sc ON s.id = sc.staff_id
        WHERE s.id=?
    """, (staff_id,)).fetchone()
    conn.close()
    return _staff_row(row) if row else None


def get_available_staff_by_role(role):
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, sc.total_jobs, sc.completed_jobs, sc.cancelled_jobs,
               sc.no_show_count
        FROM staff s LEFT JOIN staff_scores sc ON s.id = sc.staff_id
        WHERE s.status='available'
        ORDER BY s.name
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        roles = json.loads(r["roles"])
        if role.lower() in [rl.lower() for rl in roles]:
            result.append(_staff_row(r))
    return result


def get_staff_by_phone(phone: str) -> Optional[dict]:
    """Telefon numarasına göre personel bul (son 10 hane eşleşmesi)."""
    conn = get_db()
    phone_suffix = phone.replace("+", "").replace(" ", "")[-10:]
    row = conn.execute("""
        SELECT s.*, sc.total_jobs, sc.completed_jobs, sc.cancelled_jobs, sc.no_show_count
        FROM staff s LEFT JOIN staff_scores sc ON s.id = sc.staff_id
        WHERE REPLACE(REPLACE(s.phone, '+', ''), ' ', '') LIKE ?
    """, (f"%{phone_suffix}",)).fetchone()
    conn.close()
    return _staff_row(row) if row else None


def update_staff_status(staff_id: int, status: str) -> None:
    conn = get_db()
    conn.execute("UPDATE staff SET status=? WHERE id=?", (status, staff_id))
    conn.commit()
    conn.close()


def _staff_row(row):
    return {
        "id": row["id"], "name": row["name"], "phone": row["phone"],
        "email": row["email"], "roles": json.loads(row["roles"]),
        "location": row["location"], "hourly_rate": row["hourly_rate"] or 0,
        "status": row["status"], "created_at": row["created_at"],
        "total_jobs": row["total_jobs"] or 0,
        "completed_jobs": row["completed_jobs"] or 0,
        "cancelled_jobs": row["cancelled_jobs"] or 0,
        "no_show_count": row["no_show_count"] or 0,
    }


# ═══════════════════════════════════════════════════════
# STAFF SCORING
# ═══════════════════════════════════════════════════════

_ALLOWED_SCORE_COLS = {
    "reliability_score", "quality_score", "response_speed",
    "avg_response_minutes", "total_jobs", "completed_jobs",
    "cancelled_jobs", "no_show_count",
}


def update_staff_score(staff_id, **kwargs):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO staff_scores (staff_id) VALUES (?)", (staff_id,))
    valid = {k: v for k, v in kwargs.items() if k in _ALLOWED_SCORE_COLS}
    if valid:
        sets = ", ".join(f"{k}=?" for k in valid)
        values = list(valid.values()) + [datetime.now().isoformat(), staff_id]
        conn.execute(f"UPDATE staff_scores SET {sets}, updated_at=? WHERE staff_id=?", values)
    conn.commit()
    conn.close()


def record_job_accepted(staff_id):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO staff_scores (staff_id) VALUES (?)", (staff_id,))
    conn.execute("""
        UPDATE staff_scores SET
            total_jobs = total_jobs + 1,
            updated_at = ?
        WHERE staff_id = ?
    """, (datetime.now().isoformat(), staff_id))
    conn.commit()
    conn.close()


def record_job_completed(staff_id):
    conn = get_db()
    conn.execute("""
        UPDATE staff_scores SET
            completed_jobs = completed_jobs + 1,
            reliability_score = MIN(10, reliability_score + 0.1),
            updated_at = ?
        WHERE staff_id = ?
    """, (datetime.now().isoformat(), staff_id))
    conn.commit()
    conn.close()


def record_job_cancelled(staff_id):
    conn = get_db()
    conn.execute("""
        UPDATE staff_scores SET
            cancelled_jobs = cancelled_jobs + 1,
            reliability_score = MAX(0, reliability_score - 0.5),
            updated_at = ?
        WHERE staff_id = ?
    """, (datetime.now().isoformat(), staff_id))
    conn.commit()
    conn.close()


def record_no_show(staff_id):
    conn = get_db()
    conn.execute("""
        UPDATE staff_scores SET
            no_show_count = no_show_count + 1,
            reliability_score = MAX(0, reliability_score - 1.0),
            updated_at = ?
        WHERE staff_id = ?
    """, (datetime.now().isoformat(), staff_id))
    conn.commit()
    conn.close()


def record_response_time(staff_id, minutes):
    conn = get_db()
    row = conn.execute(
        "SELECT avg_response_minutes, total_jobs FROM staff_scores WHERE staff_id=?",
        (staff_id,)
    ).fetchone()
    if row:
        old_avg = row["avg_response_minutes"] or 0
        count = row["total_jobs"] or 1
        new_avg = (old_avg * (count - 1) + minutes) / count
        speed_score = max(0, min(10, 10 - (new_avg / 10)))  # 0 dk = 10 puan, 100 dk = 0 puan
        conn.execute("""
            UPDATE staff_scores SET avg_response_minutes=?, response_speed=?, updated_at=?
            WHERE staff_id=?
        """, (round(new_avg, 1), round(speed_score, 2), datetime.now().isoformat(), staff_id))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════
# SCHEDULE (TAKVİM)
# ═══════════════════════════════════════════════════════

def add_schedule_entry(staff_id, request_id, date, start_time, end_time,
                       location=None, client_name=None, role=None):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO schedule (staff_id, request_id, date, start_time, end_time,
                              location, client_name, role)
        VALUES (?,?,?,?,?,?,?,?)
    """, (staff_id, request_id, date, start_time, end_time, location, client_name, role))
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()
    return entry_id


def check_schedule_conflict(staff_id, date, start_time, end_time):
    """Çakışma kontrolü: aynı personel aynı zaman diliminde başka iş var mı?"""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM schedule
        WHERE staff_id=? AND date=? AND status='confirmed'
        AND NOT (end_time <= ? OR start_time >= ?)
    """, (staff_id, date, start_time, end_time)).fetchall()
    conn.close()
    if rows:
        conflict = dict(rows[0])
        return {
            "has_conflict": True,
            "conflicting_entry": conflict,
            "message": f"{date} tarihinde {conflict['start_time']}-{conflict['end_time']} arası {conflict.get('client_name','başka iş')} için meşgul"
        }
    return {"has_conflict": False, "conflicting_entry": None, "message": ""}


def get_staff_schedule(staff_id, date_from=None, date_to=None):
    conn = get_db()
    q = "SELECT * FROM schedule WHERE staff_id=? AND status='confirmed'"
    params = [staff_id]
    if date_from:
        q += " AND date >= ?"
        params.append(date_from)
    if date_to:
        q += " AND date <= ?"
        params.append(date_to)
    q += " ORDER BY date, start_time"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cancel_schedule_entry(schedule_id):
    conn = get_db()
    conn.execute("UPDATE schedule SET status='cancelled' WHERE id=?", (schedule_id,))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════
# AGENT MEMORY (HAFIZA)
# ═══════════════════════════════════════════════════════

def store_memory(key, category, content, relevance=1.0):
    conn = get_db()
    conn.execute("""
        INSERT INTO agent_memory (key, category, content, relevance_score)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            content=excluded.content,
            relevance_score=excluded.relevance_score,
            last_accessed=datetime('now','localtime'),
            access_count=access_count+1
    """, (key, category, content, relevance))
    conn.commit()
    conn.close()


def recall_memory(category=None, keyword=None, limit=10):
    conn = get_db()
    q = "SELECT * FROM agent_memory WHERE 1=1"
    params = []
    if category:
        q += " AND category=?"
        params.append(category)
    if keyword:
        q += " AND (content LIKE ? OR key LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    q += " ORDER BY relevance_score DESC, last_accessed DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    # Her erişimde last_accessed güncelle
    for r in rows:
        conn.execute("""
            UPDATE agent_memory SET last_accessed=datetime('now','localtime'),
            access_count=access_count+1 WHERE id=?
        """, (r["id"],))
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]


def decay_memories(factor=0.98):
    """Hafıza relevanslığını zamanla azalt (unutma)."""
    conn = get_db()
    conn.execute("UPDATE agent_memory SET relevance_score = relevance_score * ?", (factor,))
    conn.execute("DELETE FROM agent_memory WHERE relevance_score < 0.1")
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════
# AGENT ACTIVITY LOG
# ═══════════════════════════════════════════════════════

def log_activity(request_id, agent_role, action, detail, thought_data=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO agent_activity (request_id, agent_role, action, detail, thought_data)
        VALUES (?,?,?,?,?)
    """, (request_id, agent_role, action, detail,
          json.dumps(thought_data, ensure_ascii=False) if thought_data else None))
    conn.commit()
    conn.close()


def get_recent_activity(limit=50):
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM agent_activity ORDER BY timestamp DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_activity_for_request(request_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM agent_activity WHERE request_id=? ORDER BY timestamp
    """, (request_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
# CLIENT REQUESTS
# ═══════════════════════════════════════════════════════

def create_request(client_name, message, contact_email=None,
                   contact_phone=None, priority="normal"):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO client_requests (client_name, original_message,
            contact_email, contact_phone, priority)
        VALUES (?,?,?,?,?)
    """, (client_name, message, contact_email, contact_phone, priority))
    conn.commit()
    req_id = cur.lastrowid
    conn.close()
    return req_id


def get_request(request_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM client_requests WHERE id=?", (request_id,)).fetchone()
    conn.close()
    return _req_row(row) if row else None


def get_all_requests():
    conn = get_db()
    rows = conn.execute("SELECT * FROM client_requests ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_req_row(r) for r in rows]


def update_request_status(request_id, status):
    conn = get_db()
    conn.execute("UPDATE client_requests SET status=?, updated_at=? WHERE id=?",
                 (status, datetime.now().isoformat(), request_id))
    conn.commit()
    conn.close()


def update_request_parsed(request_id, parsed_needs):
    conn = get_db()
    conn.execute("UPDATE client_requests SET parsed_needs=?, updated_at=? WHERE id=?",
                 (json.dumps(parsed_needs, ensure_ascii=False),
                  datetime.now().isoformat(), request_id))
    conn.commit()
    conn.close()


def update_request_crew_result(request_id, crew_result):
    conn = get_db()
    conn.execute("UPDATE client_requests SET crew_result=?, updated_at=? WHERE id=?",
                 (json.dumps(crew_result, ensure_ascii=False),
                  datetime.now().isoformat(), request_id))
    conn.commit()
    conn.close()


def append_agent_log(request_id, action):
    conn = get_db()
    row = conn.execute("SELECT agent_log FROM client_requests WHERE id=?", (request_id,)).fetchone()
    if row:
        log = json.loads(row["agent_log"] or "[]")
        log.append(action)
        conn.execute("UPDATE client_requests SET agent_log=?, updated_at=? WHERE id=?",
                     (json.dumps(log, ensure_ascii=False),
                      datetime.now().isoformat(), request_id))
    conn.commit()
    conn.close()


def _req_row(row):
    return {
        "id": row["id"], "client_name": row["client_name"],
        "original_message": row["original_message"],
        "contact_email": row["contact_email"], "contact_phone": row["contact_phone"],
        "priority": row["priority"],
        "parsed_needs": json.loads(row["parsed_needs"]) if row["parsed_needs"] else None,
        "status": row["status"],
        "agent_log": json.loads(row["agent_log"] or "[]"),
        "crew_result": json.loads(row["crew_result"]) if row["crew_result"] else None,
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


# ═══════════════════════════════════════════════════════
# ASSIGNMENTS
# ═══════════════════════════════════════════════════════

def create_assignment(request_id, staff_id, role, message_sent=None):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO assignments (request_id, staff_id, role, message_sent)
        VALUES (?,?,?,?)
    """, (request_id, staff_id, role, message_sent))
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid


def get_assignments_for_request(request_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, s.name as staff_name, s.phone as staff_phone,
               sc.reliability_score, sc.quality_score, sc.response_speed
        FROM assignments a
        JOIN staff s ON a.staff_id = s.id
        LEFT JOIN staff_scores sc ON s.id = sc.staff_id
        WHERE a.request_id=? ORDER BY a.invited_at
    """, (request_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_invited_assignments_by_staff(staff_id, request_id):
    conn = get_db()
    row = conn.execute("""
        SELECT a.*, s.name as staff_name
        FROM assignments a JOIN staff s ON a.staff_id = s.id
        WHERE a.staff_id=? AND a.request_id=? AND a.status='invited'
    """, (staff_id, request_id)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_assignment_status(assignment_id, status):
    conn = get_db()
    conn.execute("UPDATE assignments SET status=?, responded_at=? WHERE id=?",
                 (status, datetime.now().isoformat(), assignment_id))
    conn.commit()
    conn.close()


def get_accepted_count(request_id, role):
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM assignments WHERE request_id=? AND role=? AND status='accepted'",
        (request_id, role)).fetchone()
    conn.close()
    return row["cnt"]


def get_pending_invitations_for_role(request_id, role):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, s.name as staff_name, s.phone as staff_phone
        FROM assignments a JOIN staff s ON a.staff_id = s.id
        WHERE a.request_id=? AND a.role=? AND a.status='invited'
    """, (request_id, role)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
# MESSAGES LOG
# ═══════════════════════════════════════════════════════

def log_message(staff_id, request_id, message_type, message_text,
                assignment_id=None, channel="sms"):
    conn = get_db()
    conn.execute("""
        INSERT INTO messages_log (assignment_id, staff_id, request_id,
            message_type, message_text, channel)
        VALUES (?,?,?,?,?,?)
    """, (assignment_id, staff_id, request_id, message_type, message_text, channel))
    conn.commit()
    conn.close()


def get_messages_for_request(request_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT ml.*, s.name as staff_name
        FROM messages_log ml JOIN staff s ON ml.staff_id = s.id
        WHERE ml.request_id=? ORDER BY ml.sent_at
    """, (request_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
# DASHBOARD STATS
# ═══════════════════════════════════════════════════════

def get_dashboard_stats():
    conn = get_db()
    total_req = conn.execute("SELECT COUNT(*) as c FROM client_requests").fetchone()["c"]
    active = conn.execute(
        "SELECT COUNT(*) as c FROM client_requests WHERE status IN ('pending','analyzing','matching','messaging','partially_filled')"
    ).fetchone()["c"]
    fulfilled = conn.execute("SELECT COUNT(*) as c FROM client_requests WHERE status='fulfilled'").fetchone()["c"]
    failed = conn.execute("SELECT COUNT(*) as c FROM client_requests WHERE status='failed'").fetchone()["c"]
    total_staff = conn.execute("SELECT COUNT(*) as c FROM staff").fetchone()["c"]
    avail_staff = conn.execute("SELECT COUNT(*) as c FROM staff WHERE status='available'").fetchone()["c"]

    # En çok talep edilen roller
    role_stats = conn.execute("""
        SELECT role, COUNT(*) as cnt FROM assignments GROUP BY role ORDER BY cnt DESC LIMIT 5
    """).fetchall()

    # Son 7 gün talep grafiği
    daily = conn.execute("""
        SELECT DATE(created_at) as day, COUNT(*) as cnt
        FROM client_requests
        WHERE created_at >= datetime('now', '-7 days', 'localtime')
        GROUP BY DATE(created_at) ORDER BY day
    """).fetchall()

    # Personel performans sıralaması (top 10)
    perf = conn.execute("""
        SELECT s.id, s.name, s.roles, sc.reliability_score, sc.quality_score,
               sc.response_speed, sc.total_jobs, sc.completed_jobs, sc.cancelled_jobs,
               (sc.reliability_score*0.4 + sc.quality_score*0.35 + sc.response_speed*0.25) as overall
        FROM staff s JOIN staff_scores sc ON s.id = sc.staff_id
        WHERE sc.total_jobs > 0
        ORDER BY overall DESC LIMIT 10
    """).fetchall()

    # Son talepler
    recent_req = conn.execute(
        "SELECT * FROM client_requests ORDER BY created_at DESC LIMIT 10"
    ).fetchall()

    # Son atamalar
    recent_assign = conn.execute("""
        SELECT a.*, s.name as staff_name, cr.client_name
        FROM assignments a
        JOIN staff s ON a.staff_id = s.id
        JOIN client_requests cr ON a.request_id = cr.id
        ORDER BY a.invited_at DESC LIMIT 20
    """).fetchall()

    conn.close()

    return {
        "total_requests": total_req,
        "active_requests": active,
        "fulfilled_requests": fulfilled,
        "failed_requests": failed,
        "total_staff": total_staff,
        "available_staff": avail_staff,
        "top_roles": [{"role": r["role"], "count": r["cnt"]} for r in role_stats],
        "daily_requests": [{"day": d["day"], "count": d["cnt"]} for d in daily],
        "staff_performance": [dict(p) for p in perf],
        "recent_requests": [_req_row(r) for r in recent_req],
        "recent_assignments": [dict(r) for r in recent_assign],
    }