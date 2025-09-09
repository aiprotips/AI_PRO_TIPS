# Helper to execute an SQL file (migrations) using MYSQL_URL env or sqlite fallback.
import sys, os
from sqlalchemy import text, create_engine

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m sql_exec <path_to_sql_file>")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}")
        sys.exit(1)

    MYSQL_URL = os.getenv("MYSQL_URL", "").strip()
    engine = create_engine(MYSQL_URL or "sqlite:///aipro_tips.sqlite3", future=True)
    with engine.begin() as conn, open(path, "r", encoding="utf-8") as f:
        sql = f.read()
        # Allow running multiple statements
        for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
            conn.execute(text(stmt))
    print("Migration executed successfully.")

if __name__ == "__main__":
    main()
