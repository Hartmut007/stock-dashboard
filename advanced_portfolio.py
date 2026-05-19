import pandas as pd
import yfinance as yf
from datetime import datetime


# ============================================================
# WATCHLIST LADEN
# ============================================================

watchlist = pd.read_csv(
    "clean_watchlist.csv",
    sep=";"
)

PORTFOLIO = watchlist["Ticker"].tolist()

print(f"\nGeladene Aktien: {len(PORTFOLIO)}")


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def convert_timestamp(timestamp):
    if timestamp is None:
        return "-"

    try:
        return datetime.fromtimestamp(timestamp).strftime("%d.%m.%Y")
    except:
        return "-"


def calculate_rsi(close, period=14):
    delta = close.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.iloc[-1]


def percent_change(close, days):
    if len(close) <= days:
        return 0

    return ((close.iloc[-1] - close.iloc[-days]) / close.iloc[-days]) * 100


def format_price(value, currency):
    try:
        return f"{round(value, 2)} {currency}"
    except:
        return "-"


def format_percent(value):
    try:
        return f"{round(value, 2)}%"
    except:
        return "-"


def classify_market_cap(market_cap):
    if market_cap is None:
        return "UNKNOWN"

    if market_cap >= 200_000_000_000:
        return "Mega Cap"

    elif market_cap >= 10_000_000_000:
        return "Large Cap"

    elif market_cap >= 2_000_000_000:
        return "Mid Cap"

    elif market_cap >= 300_000_000:
        return "Small Cap"

    else:
        return "Micro Cap"


def calculate_risk_level(rsi, distance_ema20, volatility_30d, beta):
    risk_score = 0

    if rsi > 75:
        risk_score += 2
    elif rsi > 70:
        risk_score += 1

    if distance_ema20 > 15:
        risk_score += 2
    elif distance_ema20 > 8:
        risk_score += 1

    if volatility_30d > 5:
        risk_score += 2
    elif volatility_30d > 3:
        risk_score += 1

    if beta is not None:
        if beta > 1.8:
            risk_score += 2
        elif beta > 1.3:
            risk_score += 1

    if risk_score >= 5:
        return "HIGH RISK"

    elif risk_score >= 3:
        return "MEDIUM RISK"

    else:
        return "LOW RISK"


# ============================================================
# AKTIEN ANALYSIEREN
# ============================================================

def analyze_stock(ticker, current_index, total_count):
    print(f"[{current_index}/{total_count}] Analysiere {ticker}...")

    stock = yf.Ticker(ticker)
    hist = stock.history(period="1y")

    if hist.empty:
        raise ValueError("Keine Kursdaten gefunden")

    close = hist["Close"]
    volume = hist["Volume"]

    info = stock.info

    company_name = info.get("shortName", ticker)
    currency = info.get("currency", "")
    market_cap = info.get("marketCap")
    beta = info.get("beta")

    current_price = close.iloc[-1]

    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]
    ema100 = close.ewm(span=100).mean().iloc[-1]

    change_1d = percent_change(close, 2)
    change_1w = percent_change(close, 6)
    change_1m = percent_change(close, 22)
    change_3m = percent_change(close, 66)
    change_6m = percent_change(close, 132)

    rsi = calculate_rsi(close)

    high_52w = close.max()
    distance_52w_high = ((current_price - high_52w) / high_52w) * 100

    distance_ema20 = ((current_price - ema20) / ema20) * 100
    distance_ema50 = ((current_price - ema50) / ema50) * 100

    daily_returns = close.pct_change() * 100
    volatility_30d = daily_returns.tail(30).std()

    avg_volume_20 = volume.tail(20).mean()
    current_volume = volume.iloc[-1]

    volume_signal = "NORMAL"

    if current_volume > avg_volume_20 * 1.5:
        volume_signal = "HIGH"
    elif current_volume < avg_volume_20 * 0.7:
        volume_signal = "LOW"

    dividend_rate = info.get("dividendRate")

    if dividend_rate is not None and current_price > 0:
        dividend_yield = (dividend_rate / current_price) * 100
    else:
        dividend_yield = 0

    ex_dividend_date = convert_timestamp(info.get("exDividendDate"))
    last_dividend_date = convert_timestamp(info.get("lastDividendDate"))

    stop_loss_ema50 = ema50 * 0.98

    market_cap_class = classify_market_cap(market_cap)

    risk_level = calculate_risk_level(
        rsi,
        distance_ema20,
        volatility_30d,
        beta
    )

    score = 0

    if current_price > ema20:
        score += 1

    if current_price > ema50:
        score += 1

    if current_price > ema100:
        score += 1

    if ema20 > ema50:
        score += 1

    if ema50 > ema100:
        score += 1

    if change_1w > 0:
        score += 1

    if change_1m > 0:
        score += 1

    if 45 <= rsi <= 70:
        score += 1

    turnaround = False

    if (
        change_6m < -15
        and change_1m > 5
        and current_price > ema20
        and rsi > 40
    ):
        turnaround = True

    overbought = False

    if rsi > 75 or distance_ema20 > 15:
        overbought = True

    if turnaround:
        rating = "TURNAROUND"

    elif overbought and score >= 6:
        rating = "WATCH - OVERBOUGHT"

    elif score >= 7:
        rating = "STRONG BUY"

    elif score >= 5:
        rating = "BUY"

    elif score >= 3:
        rating = "HOLD"

    else:
        rating = "AVOID"

    reason = []

    if current_price > ema20:
        reason.append("über EMA20")

    if current_price > ema50:
        reason.append("über EMA50")

    if current_price > ema100:
        reason.append("über EMA100")

    if change_1m > 0:
        reason.append("1M positiv")

    if turnaround:
        reason.append("mögliche Trendwende")

    if overbought:
        reason.append("kurzfristig heiß gelaufen")

    if rsi < 35:
        reason.append("überverkauft")

    if volume_signal == "HIGH":
        reason.append("hohes Volumen")

    if risk_level == "HIGH RISK":
        reason.append("hohes Risiko")

    reason_text = ", ".join(reason)

    return {
        "Ticker": ticker,
        "Company": company_name,
        "Currency": currency,

        "Price": format_price(current_price, currency),
        "Raw Price": round(current_price, 2),

        "EMA20": format_price(ema20, currency),
        "EMA50": format_price(ema50, currency),
        "EMA100": format_price(ema100, currency),

        "Distance EMA20 %": round(distance_ema20, 2),
        "Distance EMA50 %": round(distance_ema50, 2),

        "1D %": round(change_1d, 2),
        "1W %": round(change_1w, 2),
        "1M %": round(change_1m, 2),
        "3M %": round(change_3m, 2),
        "6M %": round(change_6m, 2),

        "RSI": round(rsi, 2),

        "52W High": format_price(high_52w, currency),
        "Distance 52W High %": round(distance_52w_high, 2),

        "Volatility 30D %": round(volatility_30d, 2),
        "Beta": beta,

        "Volume Signal": volume_signal,

        "Dividend Yield %": format_percent(dividend_yield),
        "Dividend Rate": format_price(dividend_rate, currency),

        "Ex Dividend Date": ex_dividend_date,
        "Last Dividend Date": last_dividend_date,

        "Stop Loss Idea": format_price(stop_loss_ema50, currency),

        "Market Cap": market_cap,
        "Market Cap Class": market_cap_class,

        "Risk Level": risk_level,

        "Turnaround Candidate": "YES" if turnaround else "NO",

        "Score": score,
        "Rating": rating,
        "Reason": reason_text,
    }


# ============================================================
# ANALYSE STARTEN
# ============================================================

results = []

total_count = len(PORTFOLIO)

for index, ticker in enumerate(PORTFOLIO, start=1):
    try:
        result = analyze_stock(
            ticker,
            index,
            total_count
        )

        results.append(result)

    except Exception as error:
        print(f"Fehler bei {ticker}: {error}")


# ============================================================
# DATAFRAME
# ============================================================

df = pd.DataFrame(results)

if not df.empty:
    df = df.sort_values(
        by=["Score", "1M %"],
        ascending=False
    )

    print("\nAnalyse-Ergebnis:")
    print(df)

    df.to_csv(
        "portfolio_analysis.csv",
        sep=";",
        index=False,
        encoding="utf-8-sig"
    )

    print("\n====================================")
    print("FERTIG")
    print("====================================")
    print("Datei gespeichert:")
    print("portfolio_analysis.csv")

else:
    print("Keine gültigen Daten gefunden.")