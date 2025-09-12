from sqlalchemy import text
from .db import get_session

def kv_get(key: str):
    with get_session() as s:
        row = s.execute(text("SELECT val FROM config_kv WHERE k=:k"), {"k": key}).fetchone()
        return row[0] if row else None

def kv_set(key: str, val: str):
    with get_session() as s:
        s.execute(text("INSERT INTO config_kv (k, val) VALUES (:k, :v) ON DUPLICATE KEY UPDATE val=:v"), {"k": key, "v": val})
        s.commit()

def log_error(source: str, message: str):
    with get_session() as s:
        s.execute(text("INSERT INTO error_log (source, message, created_at) VALUES (:s, :m, NOW())"), {"s": source, "m": message})
        s.commit()

def create_betslip(code: str, total_odds: float, legs_count: int, short_id: str):
    with get_session() as s:
        s.execute(text("""
            INSERT INTO betslips (code, short_id, total_odds, legs_count, status, created_at)
            VALUES (:c, :sid, :o, :l, 'OPEN', NOW())
        """), {"c": code, "sid": short_id, "o": total_odds, "l": legs_count})
        s.commit()
        row = s.execute(text("SELECT LAST_INSERT_ID()")).fetchone()
        return int(row[0])

def add_selection(betslip_id: int, fixture_id: int, league_id: int, start_iso: str,
                  home: str, away: str, market: str, pick: str, odds: float):
    with get_session() as s:
        s.execute(text("""
            INSERT INTO selections (betslip_id, fixture_id, league_id, start_time, home, away, market, pick, odds, result)
            VALUES (:bid, :fid, :lid, :st, :h, :a, :m, :p, :o, 'PENDING')
        """), {
            "bid": betslip_id, "fid": fixture_id, "lid": league_id, "st": start_iso,
            "h": home, "a": away, "m": market, "p": pick, "o": odds
        })
        s.commit()

def get_open_betslips():
    with get_session() as s:
        return s.execute(text("SELECT * FROM betslips WHERE status IN ('OPEN','PENDING') ORDER BY id DESC")).mappings().all()

def get_selections_for_betslip(betslip_id: int):
    with get_session() as s:
        return s.execute(text("SELECT * FROM selections WHERE betslip_id = :b ORDER BY id ASC"), {"b": betslip_id}).mappings().all()

def mark_selection_result(selection_id: int, result: str):
    with get_session() as s:
        s.execute(text("UPDATE selections SET result=:r WHERE id=:i"), {"r": result, "i": selection_id})
        s.commit()

def update_betslip_progress(betslip_id: int):
    with get_session() as s:
        row = s.execute(text("""
            SELECT
              SUM(CASE WHEN result='WON'  THEN 1 ELSE 0 END) AS won,
              SUM(CASE WHEN result='LOST' THEN 1 ELSE 0 END) AS lost,
              COUNT(*) AS total
            FROM selections WHERE betslip_id=:b
        """), {"b": betslip_id}).fetchone()
        won  = int(row[0] or 0); lost = int(row[1] or 0); total= int(row[2] or 0)
        if lost > 0:
            s.execute(text("UPDATE betslips SET status='LOST', settled_at=NOW() WHERE id=:b"), {"b": betslip_id})
        elif total > 0 and won == total:
            s.execute(text("UPDATE betslips SET status='WON', settled_at=NOW() WHERE id=:b"), {"b": betslip_id})
        else:
            s.execute(text("UPDATE betslips SET status='OPEN' WHERE id=:b"), {"b": betslip_id})
        s.commit(); return won, total

def close_betslip_if_done(betslip_id: int):
    with get_session() as s:
        row = s.execute(text("SELECT status FROM betslips WHERE id=:b"), {"b": betslip_id}).fetchone()
        return row[0] if row else None

def mark_betslip_cancelled_by_code(code: str) -> bool:
    with get_session() as s:
        res = s.execute(text("UPDATE betslips SET status='CANCELLED', settled_at=NOW() WHERE code=:c"), {"c": code})
        s.commit(); return res.rowcount > 0

def cache_get_fixture(fid: int):
    with get_session() as s:
        row = s.execute(text("SELECT fixture_id, odds_json FROM fixture_cache WHERE fixture_id=:f"), {"f": fid}).mappings().first()
        return row or {}

def cache_put_fixture(fid: int, odds_json: str):
    with get_session() as s:
        s.execute(text("""
            INSERT INTO fixture_cache (fixture_id, odds_json, updated_at)
            VALUES (:f, :j, NOW())
            ON DUPLICATE KEY UPDATE odds_json=:j, updated_at=NOW()
        """), {"f": fid, "j": odds_json})
        s.commit()

def schedule_enqueue(short_id: str, kind: str, payload: str, send_at_iso: str):
    with get_session() as s:
        s.execute(text("""
            INSERT INTO scheduled_messages (short_id, kind, payload, send_at, status)
            VALUES (:sid, :k, :p, :sa, 'QUEUED')
        """), {"sid": short_id, "k": kind, "p": payload, "sa": send_at_iso})
        s.commit()

def schedule_due_now(limit: int = 10):
    with get_session() as s:
        return s.execute(text("""
            SELECT * FROM scheduled_messages
            WHERE status='QUEUED' AND send_at <= UTC_TIMESTAMP()
            ORDER BY send_at ASC
            LIMIT :lim
        """), {"lim": limit}).mappings().all()

def schedule_mark_sent(rec_id: int):
    with get_session() as s:
        s.execute(text("UPDATE scheduled_messages SET status='SENT', sent_at=NOW() WHERE id=:i"), {"i": rec_id})
        s.commit()

def schedule_cancel_by_short_id(short_id: str) -> int:
    with get_session() as s:
        res = s.execute(text("UPDATE scheduled_messages SET status='CANCELLED' WHERE short_id=:sid AND status='QUEUED'"), {"sid": short_id})
        s.commit(); return res.rowcount

def schedule_cancel_all_today() -> int:
    with get_session() as s:
        res = s.execute(text("UPDATE scheduled_messages SET status='CANCELLED' WHERE status='QUEUED' AND DATE(send_at)=CURDATE()"))
        s.commit(); return res.rowcount

def schedule_get_today():
    with get_session() as s:
        return s.execute(text("SELECT * FROM scheduled_messages WHERE DATE(send_at)=CURDATE() ORDER BY send_at ASC")).mappings().all()

def schedule_get_by_short_id(short_id: str):
    with get_session() as s:
        return s.execute(text("SELECT * FROM scheduled_messages WHERE short_id=:sid ORDER BY id DESC LIMIT 1"), {"sid": short_id}).mappings().first()

def emit_count(kind: str, day):
    with get_session() as s:
        row = s.execute(text("SELECT COUNT(*) FROM emit_log WHERE kind=:k AND DATE(created_at)=:d"), {"k": kind, "d": day}).fetchone()
        return int(row[0] or 0)

def emit_mark(kind: str):
    with get_session() as s:
        s.execute(text("INSERT INTO emit_log (kind, created_at) VALUES (:k, NOW())"), {"k": kind}); s.commit()
