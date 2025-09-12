# Telegram Odds Bot — Bet365 (API-Football)

Bot Telegram (DM admin) che mostra le **quote reali** SOLO Bet365 (bookmaker=8) per OGGI e DOMANI
dei campionati whitelisted, raggruppate per LEGA e ordinate per ORA.

## Comandi
- `/quote` → oggi + domani
- `/quote today` → solo oggi
- `/quote tomorrow` → solo domani

## Variabili d'ambiente (Railway → Variables)
- TELEGRAM_TOKEN
- ADMIN_ID
- APIFOOTBALL_KEY
- TZ (es. Europe/Rome)

## Deploy
- `requirements.txt` in root
- `Procfile` con `worker: python -m app.main`
- push su GitHub → deploy su Railway
