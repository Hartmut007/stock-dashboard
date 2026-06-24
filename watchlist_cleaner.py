import pandas as pd
import yfinance as yf
import time
import json
from datetime import datetime


# ============================================================
# KONFIGURATION
# ============================================================

INPUT_FILE         = "raw_watchlist.txt"
OUTPUT_CSV         = "clean_watchlist.csv"
INVALID_FILE       = "invalid_tickers.txt"
META_FILE          = "data_update_meta.json"

REQUEST_DELAY      = 0.6   # Sekunden zwischen einzelnen Abfragen
BATCH_SIZE         = 10    # Ticker pro Batch-Download-Versuch
MIN_DOLLAR_VOLUME  = 1_000_000   # Tagesumsatz in Geldeinheiten, unter dem eine Aktie als "schwer handelbar" markiert wird


# ============================================================
# DATEI EINLESEN & CLEANING
# ============================================================

with open(INPUT_FILE, "r") as f:
    raw_lines = f.readlines()

tickers = sorted(set(
    line.strip().upper()
    for line in raw_lines
    if line.strip()
))

print(f"\nGefundene Ticker (bereinigt, keine Duplikate): {len(tickers)}")


# ============================================================
# SEKTOR-MAPPING AUS YFINANCE (kein Name-Guessing mehr)
# ============================================================

SECTOR_TRANSLATION = {
    "Technology":                 "TECHNOLOGY",
    "Healthcare":                 "HEALTHCARE",
    "Financial Services":         "FINANCIALS",
    "Industrials":                "INDUSTRIALS",
    "Consumer Cyclical":          "CONSUMER CYCLICAL",
    "Consumer Defensive":         "CONSUMER DEFENSIVE",
    "Energy":                     "ENERGY",
    "Basic Materials":            "MATERIALS",
    "Communication Services":     "COMMUNICATION",
    "Real Estate":                "REAL ESTATE",
    "Utilities":                  "UTILITIES",
}

INDUSTRY_OVERRIDES = {
    "Semiconductor":              "SEMICONDUCTOR",
    "Software":                   "SOFTWARE",
    "Biotechnology":              "BIOTECH",
    "Drug Manufacturers":         "PHARMA",
    "Gold":                       "MINING",
    "Silver":                     "MINING",
    "Copper":                     "MINING",
    "Uranium":                    "URANIUM",
    "Lithium":                    "LITHIUM",
    "Defense":                    "DEFENSE",
    "Aerospace":                  "DEFENSE",
    "Quantum":                    "QUANTUM",
    "Artificial Intelligence":    "AI",
}


def map_sector(yf_sector: str | None, yf_industry: str | None) -> str:
    if yf_industry:
        for keyword, label in INDUSTRY_OVERRIDES.items():
            if keyword.lower() in yf_industry.lower():
                return label
    if yf_sector:
        return SECTOR_TRANSLATION.get(yf_sector, yf_sector.upper())
    return "OTHER"


# ============================================================
# YFINANCE VALIDIERUNG (einzeln, mit Fallback)
# ============================================================

valid_stocks   = []
invalid_tickers = []

for i, ticker in enumerate(tickers, start=1):
    print(f"[{i}/{len(tickers)}] Prüfe {ticker}...", end=" ")

    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        company_name = info.get("shortName") or info.get("longName")
        if not company_name:
            raise ValueError("Kein Firmenname")

        market_cap    = info.get("marketCap")
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        yf_sector     = info.get("sector")
        yf_industry   = info.get("industry")
        exchange      = info.get("exchange", "")
        currency      = info.get("currency", "")

        avg_volume   = info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0
        dollar_volume = (avg_volume or 0) * (current_price or 0)

        if dollar_volume == 0:
            liquidity_flag = "UNBEKANNT"
        elif dollar_volume < MIN_DOLLAR_VOLUME:
            liquidity_flag = "NIEDRIG"
        elif dollar_volume < MIN_DOLLAR_VOLUME * 5:
            liquidity_flag = "MITTEL"
        else:
            liquidity_flag = "HOCH"

        sector = map_sector(yf_sector, yf_industry)

        valid_stocks.append({
            "Ticker":          ticker,
            "Company":         company_name,
            "Sector":          sector,
            "Industry":        yf_industry or "-",
            "Price":           round(float(current_price), 4) if current_price else None,
            "Market Cap":      market_cap,
            "Currency":        currency,
            "Exchange":        exchange,
            "Avg Volume":      int(avg_volume) if avg_volume else None,
            "Avg Dollar Volume": round(dollar_volume, 0) if dollar_volume else None,
            "Liquidity":       liquidity_flag,
        })

        print(f"OK → {company_name} | {sector}")

    except Exception as err:
        print(f"FEHLER → {err}")
        invalid_tickers.append(ticker)

    time.sleep(REQUEST_DELAY)


# ============================================================
# DATAFRAME & SORTIERUNG
# ============================================================

df = pd.DataFrame(valid_stocks)

if not df.empty:
    df = df.sort_values(by="Market Cap", ascending=False, na_position="last")
else:
    print("\nKeine gültigen Aktien gefunden.")


# ============================================================
# SPEICHERN
# ============================================================

df.to_csv(OUTPUT_CSV, sep=";", index=False, encoding="utf-8-sig")

with open(INVALID_FILE, "w") as f:
    for t in invalid_tickers:
        f.write(t + "\n")

# Zeitstempel für Dashboard-Datenstand
with open(META_FILE, "w", encoding="utf-8") as f:
    json.dump({"updated_at": datetime.now().isoformat()}, f)


# ============================================================
# ZUSAMMENFASSUNG
# ============================================================

print("\n" + "=" * 50)
print("WATCHLIST CLEANER – FERTIG")
print("=" * 50)
print(f"Gültige Aktien:    {len(valid_stocks)}")
print(f"Ungültige Ticker:  {len(invalid_tickers)}")
if invalid_tickers:
    print(f"Fehlgeschlagen:    {', '.join(invalid_tickers)}")
print(f"\nOutput: {OUTPUT_CSV}, {INVALID_FILE}, {META_FILE}")

if not df.empty:
    print("\nSektor-Verteilung:")
    print(df["Sector"].value_counts().to_string())
    print("\nLiquiditäts-Verteilung:")
    print(df["Liquidity"].value_counts().to_string())
    low_liquidity = df[df["Liquidity"] == "NIEDRIG"]["Ticker"].tolist()
    if low_liquidity:
        print(f"\n⚠ Niedrige Liquidität (>{MIN_DOLLAR_VOLUME:,.0f}$/Tag Schwellenwert) bei {len(low_liquidity)} Titeln:")
        print(", ".join(low_liquidity))
        print("Diese Titel bleiben in der Liste, werden im Dashboard aber als Liquiditätsrisiko markiert.")
