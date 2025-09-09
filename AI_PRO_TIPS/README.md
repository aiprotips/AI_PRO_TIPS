# AI Pro Tips — Telegram Hype Bot (MySQL + API-Football)

**Scopo**: Bot one-way per show continuo: giocate safe (quote basse), progress bar, live alert intelligenti
(incluso *favorita sotto entro 20’*), storytelling/ironia, statistiche lampo, value scanner giornaliero,
celebrazioni/quasi-vincente/cuori spezzati, streak. Obiettivo: hype e audience, non ROI.

## Avvio rapido su Replit
1. Apri Replit e carica questo progetto.
2. Imposta i Secrets (o modifica `.env`):
   - `APIFOOTBALL_KEY`
   - `TELEGRAM_TOKEN`
   - `CHANNEL_ID`
   - `ADMIN_ID`
   - `TZ` (es. Europe/Rome)
   - `MYSQL_URL` (es. `mysql+pymysql://user:pass@host:3306/aiptips?charset=utf8mb4`)
3. Crea le tabelle su MySQL eseguendo `migrations/001_init.sql` (comandi in fondo).
4. Installa i pacchetti: `pip install -r requirements.txt`
5. Avvia: `python main.py`

> Il bot usa polling semplice (no webhook), due loop: Autopilot (ogni 5') e Live monitor (60–90s).

## Configurazione
Vedi `config.py`. Puoi regolare:
- Quiet hours, slot orari, jitter, antiflood.
- Target quote per leg (1.20–1.35).
- Frequenza dei contenuti (stat, banter, value, story, combo).

## Struttura
- `main.py` — Entry-point. Avvia loop Autopilot + Live monitor.
- `config.py` — Config & costanti.
- `db.py` — Connessione DB + helpers basi.
- `sql_exec.py` — Utility per eseguire SQL file (migrazioni).
- `repo.py` — Operazioni DB (betslip, selections, logs).
- `api_football.py` — Client API-Football (fixtures/odds/live/cache).
- `telegram_client.py` — Client Telegram.
- `builders.py` — Costruttori combo “safe” + selezione mercati.
- `autopilot.py` — Orchestrazione contenuti programmati (senza input utenti).
- `live_engine.py` — Monitor live: favorita sotto 20’, progress, chiusure.
- `templates.py` — Messaggi (story/banter/stat/progress/value/celebrazioni ecc.).
- `util.py` — Utilità (tempo, hashing, ecc.).
- `migrations/001_init.sql` — Schema MySQL completo.

## Creazione tabelle MySQL (copiaincolla)
Vedi file `migrations/001_init.sql`. Puoi lanciare anche via:
```bash
python -m sql_exec migrations/001_init.sql
```

## Note
- Il bot invia su `CHANNEL_ID`; accertati che il bot sia **amministratore** del canale.
- API-Football: servono crediti adeguati per live/odds. Il codice cache riduce le chiamate.
- Template messaggi: se hai un file dal progetto precedente, mettilo in `data/templates_custom.json`
  (stessa struttura) per override automatico all’avvio.

© 2025 AI Pro Tips. Tutti i diritti riservati.
