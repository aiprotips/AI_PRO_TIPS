# AI_PRO_TIPS — Telegram Betting Bot

## Funzioni principali
- Generazione schedine giornaliere alle 08:00 locali (2 singole, doppia, tripla, quintupla, super combo 8–12).
- Invio programmato **T-3h** rispetto al primo kickoff (mai prima delle 08:00 locali).
- Dedup tra schedine, degradazione intelligente se mancano match.
- Live Engine: alert favorita (pre Bet365 ≤1.25) sotto entro 20’ (senza rosso); Live Energy solo se schedina ancora viva.
- Chiusura schedine: 🎉 Cassa / 💔 Quasi / 💔 Cuori.
- Admin 360° in DM: /status, /preview, /publish, /resched, /cancel, /cancel_all, /gen, /check_today, /check_picks, /leagues, /dup, /where.

## Deploy (Railway)
1. Carica il repo su GitHub.
2. Railway → New Project → Deploy from GitHub.
3. Imposta le variabili d’ambiente (vedi `.env.example`).
4. Esegui lo schema SQL: `AI_PRO_TIPS/migrazioni/001_init.sql`.
5. Il worker parte con `Procfile` (python -m AI_PRO_TIPS.principale).

## Note
- Quote **solo Bet365** (filtrate in `api_football.py`).
- Match solo tra **08:00–24:00** locali (TZ configurabile).
- Template/frasi modulari in `AI_PRO_TIPS/data/templates.json` e `AI_PRO_TIPS/phrasi/`.
