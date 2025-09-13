# app/repo_sched.py
import os
import pymysql
from urllib.parse import urlparse
from contextlib import contextmanager

# Tabella di scheduling indipendente dalle tabelle delle schedine/eventi che hai già
# scheduled_messages:
#   id BIGINT PK
#   short_id VARCHAR(8)  -- ID umano (5 cifre)
#   kind VARCHAR(20)     -- 'single','double','triple','quint','long'
#   payload MEDIUMTEXT   -- messaggio Telegram già pronto
#   send_at_utc DATETIME -- quando inviare (UTC)
#   status ENUM('QUEUED','SENT','CANCELLED')
#   created_at DATETIME
#   sent_at DATETIME NULL

def _parse_mysql_url(url: str):
    # mysql://user:pass@host:port/dbname
    u = urlparse(url)
    return {
        "host": u.hostname,
        "port": int(u.port or 3306),
        "user": u.username,
        "password": u.password or "",
        "db": (u.path or "/")[1:] or "railway",
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True,
    }

def _conn():
    url = os.getenv("MYSQL_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("MYSQL_URL non configurato")
    return pymysql.connect(**_parse_mysql_url(url))

@contextmanager
def get_conn():
    c = _conn()
    try:
        yield c
    finally:
        c.close()

def ensure_table():
    ddl = """
    CREATE TABLE IF NOT EXISTS scheduled_messages (
      id BIGINT AUTO_INCREMENT PRIMARY KEY,
      short_id VARCHAR(8) NOT NULL,
      kind VARCHAR(20) NOT NULL,
      payload MEDIUMTEXT NOT NULL,
      send_at_utc DATETIME NOT NULL,
      status ENUM('QUEUED','SENT','CANCELLED') NOT NULL DEFAULT 'QUEUED',
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      sent_at DATETIME NULL,
      INDEX idx_sched_due (status, send_at_utc),
      UNIQUE KEY uniq_short (short_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute(ddl)

def enqueue(short_id: str, kind: str, payload: str, send_at_utc: str):
    sql = """
    INSERT INTO scheduled_messages (short_id, kind, payload, send_at_utc, status)
    VALUES (%s,%s,%s,%s,'QUEUED')
    """
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, (short_id, kind, payload, send_at_utc))

def due_now(limit: int = 10):
    sql = """
    SELECT * FROM scheduled_messages
    WHERE status='QUEUED' AND send_at_utc <= UTC_TIMESTAMP()
    ORDER BY send_at_utc ASC
    LIMIT %s
    """
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, (limit,))
            return cur.fetchall()

def mark_sent(rec_id: int):
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE scheduled_messages SET status='SENT', sent_at=UTC_TIMESTAMP() WHERE id=%s", (rec_id,))

def cancel_by_short_id(short_id: str) -> int:
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE scheduled_messages SET status='CANCELLED' WHERE short_id=%s AND status='QUEUED'", (short_id,))
            return cur.rowcount

def cancel_all_today() -> int:
    sql = """
    UPDATE scheduled_messages 
    SET status='CANCELLED'
    WHERE status='QUEUED' 
      AND DATE(CONVERT_TZ(send_at_utc,'+00:00',@@session.time_zone)) = CURRENT_DATE()
    """
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute("SET time_zone = '+00:00'")
            cur.execute(sql)
            return cur.rowcount

def list_today():
    sql = """
    SELECT * FROM scheduled_messages 
    WHERE DATE(CONVERT_TZ(send_at_utc,'+00:00',@@session.time_zone)) = CURRENT_DATE()
    ORDER BY send_at_utc ASC
    """
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute("SET time_zone = '+00:00'")
            cur.execute(sql)
            return cur.fetchall()

def get_by_short(short_id: str):
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM scheduled_messages WHERE short_id=%s", (short_id,))
            return cur.fetchone()
