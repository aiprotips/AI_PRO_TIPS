# app/repo_bets.py
from __future__ import annotations
import os
import pymysql
from urllib.parse import urlparse, unquote  # <-- unquote aggiunto
from contextlib import contextmanager
from typing import Dict, Any, List, Tuple

def _parse_mysql_url(url: str):
    u = urlparse(url)
    return {
        "host": u.hostname,
        "port": int(u.port or 3306),
        "user": unquote(u.username) if u.username else "",      # <-- decode username
        "password": unquote(u.password) if u.password else "",  # <-- decode password
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

def ensure_tables():
    """Crea le tabelle se mancano (betslips, selections)."""
    ddl_bets = """
    CREATE TABLE IF NOT EXISTS betslips (
      id BIGINT AUTO_INCREMENT PRIMARY KEY,
      code VARCHAR(32) NOT NULL,
      pack_type ENUM('single','double','triple','quint','long') NOT NULL,
      plan_date DATE NOT NULL,
      total_odds DECIMAL(10,2) NOT NULL,
      legs_count INT NOT NULL,
      status ENUM('OPEN','SENT','WON','LOST','CANCELLED') NOT NULL DEFAULT 'OPEN',
      sent_at DATETIME NULL,
      settled_at DATETIME NULL,
      UNIQUE KEY uniq_code (code),
      INDEX idx_plan (plan_date),
      INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    ddl_sel = """
    CREATE TABLE IF NOT EXISTS selections (
      id BIGINT AUTO_INCREMENT PRIMARY KEY,
      betslip_id BIGINT NOT NULL,
      fixture_id BIGINT NOT NULL,
      league_country VARCHAR(40) NOT NULL,
      league_name VARCHAR(80) NOT NULL,
      home VARCHAR(80) NOT NULL,
      away VARCHAR(80) NOT NULL,
      market VARCHAR(32) NOT NULL,
      odd DECIMAL(8,2) NOT NULL,
      kickoff_at DATETIME NOT NULL,
      result ENUM('PENDING','WON','LOST','VOID') NOT NULL DEFAULT 'PENDING',
      settled_at DATETIME NULL,
      score_home INT NULL,
      score_away INT NULL,
      CONSTRAINT fk_sel_betslip FOREIGN KEY (betslip_id) REFERENCES betslips(id) ON DELETE CASCADE,
      INDEX idx_betslip (betslip_id),
      INDEX idx_fixture (fixture_id),
      INDEX idx_result (result),
      INDEX idx_kickoff (kickoff_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with get_conn() as c, c.cursor() as cur:
        cur.execute(ddl_bets)
        cur.execute(ddl_sel)

def create_betslip(code: str, pack_type: str, plan_date: str, total_odds: float, legs_count: int) -> int:
    sql = """INSERT INTO betslips (code, pack_type, plan_date, total_odds, legs_count, status)
             VALUES (%s,%s,%s,%s,%s,'OPEN')"""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(sql, (code, pack_type, plan_date, float(total_odds), int(legs_count)))
        return cur.lastrowid

def add_selection(betslip_id: int, leg: Dict[str, Any], tz: str):
    iso = leg.get("kickoff_iso") or ""
    # kickoff_at salvato come UTC (ISO con Z -> +00:00)
    from datetime import datetime
    try:
        kickoff_at = datetime.fromisoformat(iso.replace("Z","+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        kickoff_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    sql = """INSERT INTO selections
             (betslip_id, fixture_id, league_country, league_name, home, away, market, odd, kickoff_at)
             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(sql, (
            + (betslip_id, int(leg["fixture_id"]),
+  leg.get("league_country", "N/D"), leg.get("league_name", "N/D"),
+  leg["home"], leg["away"], leg["market"], float(leg["odd"]), kickoff_at)
        ))

def mark_betslip_sent(betslip_id: int):
    with get_conn() as c, c.cursor() as cur:
        cur.execute("UPDATE betslips SET status='SENT', sent_at=UTC_TIMESTAMP() WHERE id=%s", (betslip_id,))

def get_open_betslips() -> List[Dict[str, Any]]:
    sql = "SELECT * FROM betslips WHERE status IN ('OPEN','SENT') ORDER BY id DESC"
    with get_conn() as c, c.cursor() as cur:
        cur.execute(sql); return cur.fetchall()

def get_selections(betslip_id: int) -> List[Dict[str, Any]]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT * FROM selections WHERE betslip_id=%s ORDER BY id ASC", (betslip_id,))
        return cur.fetchall()

def update_selection_result(selection_id: int, result: str, score_home: int = None, score_away: int = None):
    sql = "UPDATE selections SET result=%s, settled_at=UTC_TIMESTAMP(), score_home=%s, score_away=%s WHERE id=%s"
    with get_conn() as c, c.cursor() as cur:
        cur.execute(sql, (result, score_home, score_away, selection_id))

def recalc_betslip_status(betslip_id: int) -> str:
    sql = """
    SELECT
      SUM(result='WON') AS won,
      SUM(result='LOST') AS lost,
      SUM(result='PENDING') AS pending,
      COUNT(*) AS legs
    FROM selections WHERE betslip_id=%s
    """
    with get_conn() as c, c.cursor() as cur:
        cur.execute(sql, (betslip_id,)); row = cur.fetchone()
        won = int(row["won"] or 0); lost = int(row["lost"] or 0); pending = int(row["pending"] or 0)
        if lost > 0:
            cur.execute("UPDATE betslips SET status='LOST', settled_at=UTC_TIMESTAMP() WHERE id=%s", (betslip_id,))
            return "LOST"
        if pending == 0:
            cur.execute("UPDATE betslips SET status='WON', settled_at=UTC_TIMESTAMP() WHERE id=%s", (betslip_id,))
            return "WON"
        cur.execute("UPDATE betslips SET status='OPEN' WHERE id=%s", (betslip_id,))
        return "OPEN"
