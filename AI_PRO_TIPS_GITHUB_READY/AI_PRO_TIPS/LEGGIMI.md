# AI Pro Tips — Telegram Hype Bot (MySQL + API-Football)

**Scopo**: Bot one-way che invia giocate *safe* (quote basse 1.20–1.35), progress bar, live alert intelligenti
(incluso *favorita sotto entro 20’*), storytelling/ironia, statistiche lampo, value scanner 1/die, celebrazioni/quasi‑vincente/cuori spezzati.

## Deploy (GitHub → Railway)
1. Carica questo progetto su GitHub **così com'è**.
2. In Railway: *New Project → Deploy from GitHub repo*.
3. Aggiungi in **Variables** (Railway) i seguenti valori:
   - `APIFOOTBALL_KEY`
   - `TELEGRAM_TOKEN`
   - `CHANNEL_ID`
   - `ADMIN_ID`
   - `TZ=Europe/Rome`
   - `MYSQL_URL` = `mysql+pymysql://USER:PASS@HOST:PORT/DB?charset=utf8mb4`
4. **Non devi eseguire migrazioni a mano**: all’avvio `principale.py` applica automaticamente `migrazioni/001_init.sql`.
5. Assicurati che il bot sia **admin** del canale `CHANNEL_ID`.

## Struttura
- `principale.py` — entry-point, avvia Autopilot + Live e applica migrazioni auto.
- `config.py` — config via env.
- `db.py` — connessione SQLAlchemy (MySQL) con fallback a SQLite se `MYSQL_URL` vuota.
- `sql_exec.py` — esecuzione SQL generica (usato dal bootstrap).
- `repo.py` — operazioni DB.
- `api_football.py` — client API-Football v3.
- `telegram_client.py` — invio messaggi al canale.
- `costruttori.py` — builder delle combo 'safe' (1X/Over0.5/Under3.5/DNB...).
- `autopilot.py` — palinsesto push (stat/value/story/combo/banter).
- `live_engine.py` — live alerts + progress + chiusure schedine.
- `templates.py` — messaggi (story/banter/stat/progress/value/celebrations).
- `migrazioni/001_init.sql` — schema MySQL.
