import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

MYSQL_URL = os.getenv("MYSQL_URL", "").strip()
if not MYSQL_URL:
    raise RuntimeError("MYSQL_URL non impostata nelle variabili d'ambiente.")

engine = create_engine(
    MYSQL_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_session():
    return SessionLocal()
