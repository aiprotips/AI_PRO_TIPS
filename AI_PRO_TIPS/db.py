import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

MYSQL_URL = os.getenv("MYSQL_URL", "").strip()
if not MYSQL_URL:
    print("[WARN] MYSQL_URL is empty. Set it in .env or Replit Secrets. Using sqlite fallback aipro_tips.sqlite3")

engine = create_engine(MYSQL_URL or "sqlite:///aipro_tips.sqlite3", pool_pre_ping=True, pool_recycle=3600, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_session():
    return SessionLocal()

def exec_sql(sql: str):
    with engine.begin() as conn:
        conn.execute(text(sql))
