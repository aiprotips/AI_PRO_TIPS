# Esecuzione file SQL usando MYSQL_URL o sqlite fallback.
import sys, os
from sqlalchemy import text, create_engine

def run_sql_file(path: str):
    MYSQL_URL = os.getenv("MYSQL_URL", "").strip()
    engine = create_engine(MYSQL_URL or "sqlite:///aipro_tips.sqlite3", future=True)
    with engine.begin() as conn, open(path, "r", encoding="utf-8") as f:
        sql = f.read()
        for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
            conn.execute(text(stmt))

def main():
    if len(sys.argv) < 2:
        print("Uso: python -m sql_exec <path_sql>")
        sys.exit(1)
    run_sql_file(sys.argv[1])
    print("Migrazione eseguita.")

if __name__ == "__main__":
    main()
