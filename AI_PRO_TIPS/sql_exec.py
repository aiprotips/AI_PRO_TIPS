# Esegue uno script SQL (DDL/DML) contenuto in un file .sql
# Uso: run_sql_file("/path/to/001_init.sql")

from sqlalchemy import text
from .db import get_session

def _split_sql(sql: str):
    """
    Split molto semplice per file di migrazione "normali":
    separa sui ';' a fine riga. Ignora righe vuote/commenti.
    Non gestisce casi patologici con ';' dentro stringhe.
    """
    stmts = []
    buff = []
    for line in sql.splitlines():
        # ignora commenti MySQL
        l = line.strip()
        if not l or l.startswith("--") or l.startswith("#"):
            continue
        buff.append(line)
        if l.endswith(";"):
            stmts.append("\n".join(buff))
            buff = []
    if buff:
        stmts.append("\n".join(buff))
    return stmts

def run_sql_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()

    statements = _split_sql(sql)

    # Esecuzione transazionale "best effort":
    # se una CREATE IF NOT EXISTS fallisce, logica di migrazione precedente
    with get_session() as s:
        for stmt in statements:
            st = stmt.strip().rstrip(";")
            if not st:
                continue
            s.execute(text(st))
        s.commit()
