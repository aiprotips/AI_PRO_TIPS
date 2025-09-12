# Esecuzione:
#   APIFOOTBALL_KEY=... python -m scripts.check_odds 1390858
# oppure:
#   python -m scripts.check_odds 1390858 --fresh

import os, sys, argparse
from AI_PRO_TIPS.api_football import APIFootball

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture_id", type=int)
    parser.add_argument("--fresh", action="store_true", help="richiedi blocchi Bet365 con lastUpdate recente")
    args = parser.parse_args()

    key = os.getenv("APIFOOTBALL_KEY")
    if not key:
        print("APIFOOTBALL_KEY non impostata")
        sys.exit(1)

    api = APIFootball(key, tz="Europe/Rome")
    resp = api.odds_by_fixture(args.fixture_id)
    mk = api.parse_markets_bet365(resp, fresh_only=args.fresh, max_staleness_min=15)

    if not mk:
        print("Nessuna quota Bet365 disponibile per questo fixture.")
        sys.exit(0)

    # stampa mercati ordinati
    keys_order = ("1","X","2","1X","12","X2","DNB Home","DNB Away",
                  "Under 3.5","Under 2.5","Over 0.5","Over 1.5","Over 2.5",
                  "Home to Score","Away to Score","Gol","No Gol")
    for k in keys_order:
        if k in mk:
            print(f"{k}: {mk[k]}")

if __name__ == "__main__":
    main()
