import pandas as pd
import yfinance as yf
import time


# ============================================================
# DATEI EINLESEN
# ============================================================

with open("raw_watchlist.txt", "r") as file:

    raw_tickers = file.readlines()


# ============================================================
# CLEANING
# ============================================================

tickers = []

for ticker in raw_tickers:

    ticker = ticker.strip().upper()

    if ticker != "":
        tickers.append(ticker)


# ============================================================
# DUPLIKATE ENTFERNEN
# ============================================================

tickers = list(set(tickers))

tickers.sort()

print(f"\nGefundene Ticker: {len(tickers)}")


# ============================================================
# KATEGORIEN
# ============================================================

def detect_sector(name):

    name = name.lower()

    if "quantum" in name:
        return "QUANTUM"

    elif "ai" in name:
        return "AI"

    elif "defense" in name:
        return "DEFENSE"

    elif "lithium" in name:
        return "LITHIUM"

    elif "energy" in name:
        return "ENERGY"

    elif "semiconductor" in name:
        return "SEMICONDUCTOR"

    elif "mining" in name:
        return "MINING"

    elif "software" in name:
        return "SOFTWARE"

    else:
        return "OTHER"


# ============================================================
# YFINANCE TEST
# ============================================================

valid_stocks = []

invalid_tickers = []

for ticker in tickers:

    try:

        print(f"Prüfe {ticker}...")

        stock = yf.Ticker(ticker)

        info = stock.info

        company_name = info.get("shortName")

        market_cap = info.get("marketCap")

        current_price = info.get("currentPrice")

        if company_name is None:
            raise ValueError("Kein Firmenname gefunden")

        sector = detect_sector(company_name)

        valid_stocks.append({
            "Ticker": ticker,
            "Company": company_name,
            "Sector": sector,
            "Price": current_price,
            "Market Cap": market_cap
        })

        print(f"OK -> {company_name}")

        time.sleep(0.3)

    except Exception as error:

        print(f"FEHLER -> {ticker}")

        invalid_tickers.append(ticker)


# ============================================================
# DATAFRAME
# ============================================================

df = pd.DataFrame(valid_stocks)

if not df.empty:

    df = df.sort_values(
        by="Market Cap",
        ascending=False
    )

else:

    print("Keine gültigen Aktien gefunden.")

# ============================================================
# SPEICHERN
# ============================================================

df.to_csv(
    "clean_watchlist.csv",
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

# ============================================================
# FEHLER SPEICHERN
# ============================================================

with open("invalid_tickers.txt", "w") as file:

    for ticker in invalid_tickers:

        file.write(ticker + "\n")


# ============================================================
# ENDE
# ============================================================

print("\n====================================")
print("FERTIG")
print("====================================")

print(f"Gültige Aktien: {len(valid_stocks)}")
print(f"Ungültige Ticker: {len(invalid_tickers)}")

print("\nDateien erstellt:")
print("clean_watchlist.csv")
print("invalid_tickers.txt")