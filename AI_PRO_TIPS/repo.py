from sqlalchemy import text
from db import get_session
from typing import List, Optional, Dict, Any
from datetime import datetime

def create_betslip(code: str, total_odds: float, legs_count: int) -> int:
    sql = text("""
        INSERT INTO betslips (code, total_odds, legs_count)
        VALUES (:code, :total_odds, :legs_count)
    """)
    with get_session() as s:
        s.execute(sql, {"code": code, "total_odds": total_odds, "legs_count": legs_count})
        s.commit()
        res = s.execute(text("SELECT id FROM betslips WHERE code=:c"), {"c": code}).first()
        return int(res[0])

def add_selection(betslip_id: int, fixture_id: int, league_id: int, start_time: datetime,
                  home: str, away: str, market: str, pick: str, odds: float) -> int:
    sql = text("""
        INSERT INTO selections (betslip_id, fixture_id, league_id, start_time, home, away, market, pick, odds)
        VALUES (:betslip_id, :fixture_id, :league_id, :start_time, :home, :away, :market, :pick, :odds)
    """)
    with get_session() as s:
        s.execute(sql, {
            "betslip_id": betslip_id, "fixture_id": fixture_id, "league_id": league_id,
            "start_time": start_time, "home": home, "away": away, "market": market,
            "pick": pick, "odds": odds
        })
        s.commit()
        res = s.execute(text("SELECT LAST_INSERT_ID()")).first()
        return int(res[0])

def get_open_betslips():
    with get_session() as s:
        return s.execute(text("SELECT * FROM betslips WHERE status='PENDING' ORDER BY created_at DESC")).mappings().all()

def get_selections_for_betslip(betslip_id: int):
    with get_session() as s:
        return s.execute(text("SELECT * FROM selections WHERE betslip_id=:bid ORDER BY id ASC"), {"bid": betslip_id}).mappings().all()

def mark_selection_result(selection_id: int, result: str):
    with get_session() as s:
        s.execute(text("UPDATE selections SET result=:r, resolved_at=NOW() WHERE id=:id"),
                  {"r": result, "id": selection_id})
        s.commit()

def update_betslip_progress(betslip_id: int):
    with get_session() as s:
        won = s.execute(text("SELECT COUNT(*) FROM selections WHERE betslip_id=:bid AND result='WON'"),
                        {"bid": betslip_id}).scalar()
        total = s.execute(text("SELECT legs_count FROM betslips WHERE id=:bid"), {"bid": betslip_id}).scalar()
        s.execute(text("UPDATE betslips SET legs_won=:w WHERE id=:bid"), {"w": won, "bid": betslip_id})
        s.commit()
        return won, total

def close_betslip_if_done(betslip_id: int):
    with get_session() as s:
        row = s.execute(text("SELECT legs_count, legs_won, code, total_odds FROM betslips WHERE id=:bid"), {"bid": betslip_id}).first()
        if not row: return None
        legs_count, legs_won, code, total_odds = int(row[0]), int(row[1]), row[2], float(row[3])
        pending = s.execute(text("SELECT COUNT(*) FROM selections WHERE betslip_id=:bid AND result='PENDING'"),
                            {"bid": betslip_id}).scalar()
        if pending > 0:
            return None
        lost = s.execute(text("SELECT COUNT(*) FROM selections WHERE betslip_id=:bid AND result='LOST'"),
                         {"bid": betslip_id}).scalar()
        status = "WON" if lost == 0 else ("LOST_1" if lost == 1 else "LOST")
        final_status = "WON" if status=="WON" else "LOST"
        s.execute(text("UPDATE betslips SET status=:st, settled_at=NOW() WHERE id=:bid"),
                  {"st": final_status, "bid": betslip_id})
        s.commit()
        return status

def emit_count(kind: str, day: datetime.date):
    with get_session() as s:
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())
        return s.execute(text("SELECT COUNT(*) FROM emit_log WHERE kind=:k AND at BETWEEN :a AND :b"),
                         {"k": kind, "a": start, "b": end}).scalar()

def emit_mark(kind: str, at: datetime):
    with get_session() as s:
        s.execute(text("INSERT INTO emit_log (kind, at) VALUES (:k, :at)"), {"k": kind, "at": at})
        s.commit()

def emit_last_time():
    with get_session() as s:
        row = s.execute(text("SELECT at FROM emit_log ORDER BY at DESC LIMIT 1")).first()
        return row[0] if row else None

def cache_upsert_fixture(fixture_id: int, league_id: int, start_time, status: str, home: str, away: str, odds_json: str = None):
    with get_session() as se:
        se.execute(text("""
            INSERT INTO fixture_cache (fixture_id, league_id, start_time, status, home, away, odds_json)
            VALUES (:id, :lg, :st, :stat, :h, :a, :odj)
            ON DUPLICATE KEY UPDATE league_id=:lg, start_time=:st, status=:stat, home=:h, away=:a, odds_json=:odj
        """), {"id": fixture_id, "lg": league_id, "st": start_time, "stat": status, "h": home, "a": away, "odj": odds_json})
        se.commit()

def cache_get_fixture(fixture_id: int):
    with get_session() as s:
        row = s.execute(text("SELECT * FROM fixture_cache WHERE fixture_id=:id"), {"id": fixture_id}).mappings().first()
        return row

def log_error(src: str, message: str, payload: str = None):
    with get_session() as s:
        s.execute(text("INSERT INTO error_log (src, message, payload) VALUES (:s, :m, :p)"),
                  {"s": src, "m": message, "p": payload})
        s.commit()
# --- KV helpers ---
def kv_get(key: str):
    with get_session() as s:
        row = s.execute(text("SELECT v FROM config_kv WHERE k=:k"), {"k": key}).first()
        return row[0] if row else None

def kv_set(key: str, value: str):
    with get_session() as s:
        s.execute(text("""
            INSERT INTO config_kv (k, v) VALUES (:k, :v)
            ON DUPLICATE KEY UPDATE v=:v
        """), {"k": key, "v": value})
        s.commit()
