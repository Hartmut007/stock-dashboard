import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import json
import os
import time
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime

try:
    import feedparser
except Exception:
    feedparser = None


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
        if value is None or pd.isna(value):
            return "-"

        if currency is None or pd.isna(currency):
            currency = ""

        return f"{round(float(value), 2)} {currency}".strip()

    except Exception:
        return "-"


def format_percent(value):
    try:
        if value is None or pd.isna(value):
            return "-"

        return f"{round(float(value), 2)}%"

    except Exception:
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


def safe_number(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None

        return float(value)

    except Exception:
        return None


def format_number(value):
    value = safe_number(value)

    if value is None:
        return "-"

    return round(value, 2)


def format_big_number(value):
    value = safe_number(value)

    if value is None:
        return "-"

    abs_value = abs(value)

    if abs_value >= 1_000_000_000:
        return f"{round(value / 1_000_000_000, 2)} Mrd."

    if abs_value >= 1_000_000:
        return f"{round(value / 1_000_000, 2)} Mio."

    return f"{round(value, 2)}"


def format_growth(value):
    value = safe_number(value)

    if value is None:
        return "-"

    return f"{round(value * 100, 2)}%"


# ============================================================
# EQS / GOOGLE NEWS RSS RADAR
# ============================================================

NEWS_CACHE_FILE = "eqs_news_cache.json"
NEWS_CACHE_TTL_HOURS = 12
NEWS_DAYS = 14
NEWS_MAX_ITEMS = 5
NEWS_REQUEST_TIMEOUT = 8
NEWS_SLEEP_SECONDS = 0.15

POSITIVE_EQS_KEYWORDS = {
    "auftrag": 3,
    "großauftrag": 4,
    "grossauftrag": 4,
    "rahmenvertrag": 3,
    "vertrag": 2,
    "partnerschaft": 2,
    "kooperation": 2,
    "finanzierung": 2,
    "finanzierungsvereinbarung": 3,
    "anleihe": 1,
    "umsatzwachstum": 2,
    "umsatz steigt": 2,
    "prognose erhöht": 4,
    "prognose angehoben": 4,
    "ebitda verbessert": 2,
    "gewinn steigt": 3,
    "zulassung": 4,
    "genehmigung": 3,
    "auslieferung": 3,
    "serienproduktion": 3,
    "defence": 2,
    "verteidigung": 2,
    "übernahmeangebot": 3,
    "uebernahmeangebot": 3,
    "strategische investition": 3,
    "launch": 2,
    "contract": 2,
    "partnership": 2,
    "approval": 3,
    "order": 2,
    "milestone": 2,
}

NEGATIVE_EQS_KEYWORDS = {
    "kapitalerhöhung": -2,
    "kapitalerhoehung": -2,
    "verwässerung": -3,
    "verwaesserung": -3,
    "prognose gesenkt": -4,
    "prognose reduziert": -4,
    "verlustwarnung": -5,
    "umsatzrückgang": -3,
    "umsatzrueckgang": -3,
    "ebitda sinkt": -3,
    "insolvenz": -6,
    "sanierung": -5,
    "liquidität": -3,
    "liquiditaet": -3,
    "delisting": -5,
    "klage": -2,
    "untersuchung": -2,
    "investigation": -3,
    "downgrade": -2,
}


def load_news_cache():
    try:
        if os.path.exists(NEWS_CACHE_FILE):
            with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def save_news_cache(cache):
    try:
        with open(NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


NEWS_CACHE = load_news_cache()


def _cache_is_fresh(cache_entry):
    try:
        checked_at = datetime.fromisoformat(cache_entry.get("checked_at", ""))
        return datetime.now() - checked_at < timedelta(hours=NEWS_CACHE_TTL_HOURS)
    except Exception:
        return False


def clean_company_for_news(company_name, ticker):
    """Baut einen brauchbaren Suchnamen für EQS/Google News."""
    company = str(company_name or ticker or "").strip()
    ticker_text = str(ticker or "").strip()

    # Yahoo hängt teils Handelsplatz-/ADR-Zusätze in den Namen; für News ist der Firmenname wichtiger.
    replace_terms = [
        " Aktiengesellschaft", " AG", " SE", " N.V.", " NV", " S.A.", " SA",
        " Inc.", " Inc", " Corporation", " Corp.", " Corp", " plc", " PLC",
        " Ltd.", " Ltd", " Limited", " Holding", " Holdings",
        " Registered Shares", " Common Stock", " ADR", " Sponsored ADR"
    ]
    search_name = company
    for term in replace_terms:
        if len(search_name) > 10:
            search_name = search_name.replace(term, "")

    search_name = " ".join(search_name.split()).strip()

    if not search_name or search_name == "-":
        search_name = ticker_text.split(".")[0]

    return search_name[:80]


def parse_google_news_date(value):
    try:
        dt = parsedate_to_datetime(value)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(value or "-")


def fetch_google_news_rss(query, max_items=NEWS_MAX_ITEMS):
    if feedparser is None:
        return []

    encoded_query = urllib.parse.quote(query)
    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded_query}&hl=de&gl=DE&ceid=DE:de"
    )

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 NewsMomentumRadar/1.0"}
        )
        with urllib.request.urlopen(request, timeout=NEWS_REQUEST_TIMEOUT) as response:
            raw = response.read()

        feed = feedparser.parse(raw)
        items = []
        for entry in feed.entries[:max_items]:
            source = ""
            try:
                source = entry.source.get("title", "")
            except Exception:
                source = ""

            items.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": parse_google_news_date(entry.get("published", "")),
                "source": source,
            })

        return items

    except Exception:
        return []


def get_eqs_news(company_name, ticker, days=NEWS_DAYS, max_items=NEWS_MAX_ITEMS):
    search_name = clean_company_for_news(company_name, ticker)
    ticker_base = str(ticker or "").split(".")[0]
    query = f'site:eqs-news.com "{search_name}" OR "{ticker_base}" when:{days}d'
    cache_key = f"{ticker}|{search_name}|{days}|{max_items}"

    cached = NEWS_CACHE.get(cache_key)
    if isinstance(cached, dict) and _cache_is_fresh(cached):
        return cached.get("items", []), query

    items = fetch_google_news_rss(query, max_items=max_items)

    NEWS_CACHE[cache_key] = {
        "checked_at": datetime.now().isoformat(),
        "query": query,
        "items": items,
    }

    time.sleep(NEWS_SLEEP_SECONDS)
    return items, query


def score_eqs_news(news_items):
    score = 0
    hits = []

    for item in news_items:
        title = str(item.get("title", "")).lower()

        for keyword, points in POSITIVE_EQS_KEYWORDS.items():
            if keyword in title:
                score += points
                hits.append(keyword)

        for keyword, points in NEGATIVE_EQS_KEYWORDS.items():
            if keyword in title:
                score += points
                hits.append(keyword)

    hits = sorted(set(hits))
    return score, ", ".join(hits) if hits else "-"


def build_eqs_signal(score, count):
    if count == 0:
        return "⚪ Keine EQS-News"
    if score >= 7:
        return "🔥 Starker Katalysator"
    if score >= 4:
        return "🟠 Positive EQS-News"
    if score >= 1:
        return "🟡 Leicht positiv"
    if score <= -5:
        return "🔴 Kritische EQS-News"
    if score < 0:
        return "🟠 Negative EQS-News"
    return "⚪ Neutral"


def build_news_momentum_signal(perf_1d, perf_1w, volume_ratio, rsi, price, ema20, eqs_score, eqs_count):
    score = 0

    perf_1d = safe_number(perf_1d) or 0
    perf_1w = safe_number(perf_1w) or 0
    volume_ratio = safe_number(volume_ratio) or 0
    rsi = safe_number(rsi)
    price = safe_number(price)
    ema20 = safe_number(ema20)
    eqs_score = safe_number(eqs_score) or 0
    eqs_count = int(eqs_count or 0)

    if perf_1d > 5:
        score += 2
    elif perf_1d > 2:
        score += 1

    if perf_1w > 10:
        score += 2
    elif perf_1w > 4:
        score += 1

    if volume_ratio > 2:
        score += 2
    elif volume_ratio > 1.5:
        score += 1

    if price is not None and ema20 is not None and price > ema20:
        score += 1

    if rsi is not None and 40 <= rsi <= 65:
        score += 1

    if eqs_score >= 4:
        score += 3
    elif eqs_score >= 1:
        score += 1
    elif eqs_score <= -4:
        score -= 3

    if eqs_count > 0 and eqs_score == 0:
        score += 1

    if score >= 8:
        return "🔥 News-Momentum", score
    if score >= 6:
        return "🟠 Bewegung möglich", score
    if score >= 3:
        return "🟡 Beobachten", score
    if score <= 0:
        return "🔴 Schwach / Risiko", score
    return "⚪ Neutral", score


def calculate_fundamental_score(
    forward_pe,
    trailing_pe,
    peg_ratio,
    revenue_growth,
    earnings_growth,
    profit_margin,
    debt_to_equity,
    free_cashflow,
    dividend_yield
):
    score = 0
    pros = []
    cons = []

    fundamental_values = [
        forward_pe,
        trailing_pe,
        peg_ratio,
        revenue_growth,
        earnings_growth,
        profit_margin,
        debt_to_equity,
        free_cashflow
    ]

    available_count = sum(value is not None for value in fundamental_values)

    # Wichtig:
    # UNKNOWN bedeutet: Es fehlen zu viele Daten.
    # WEAK bedeutet: Es gibt ausreichend Daten, aber sie sind schwach.
    # Dadurch wird eine Aktie mit fehlenden Yahoo-Daten nicht automatisch
    # wie ein fundamental schlechtes Unternehmen behandelt.

    if forward_pe is not None:
        if 0 < forward_pe <= 25:
            score += 1
            pros.append("Forward KGV im gesunden Bereich")
        elif forward_pe > 40:
            cons.append("Forward KGV sehr hoch")

    if trailing_pe is not None:
        if 0 < trailing_pe <= 30:
            score += 1
            pros.append("KGV nicht übertrieben")
        elif trailing_pe > 45:
            cons.append("KGV sehr hoch")

    if peg_ratio is not None:
        if 0 < peg_ratio <= 2:
            score += 1
            pros.append("PEG Ratio attraktiv")
        elif peg_ratio > 3:
            cons.append("PEG Ratio hoch")

    if revenue_growth is not None:
        if revenue_growth > 0:
            score += 1
            pros.append("Umsatzwachstum positiv")
        else:
            cons.append("Umsatzwachstum negativ")

    if earnings_growth is not None:
        if earnings_growth > 0:
            score += 1
            pros.append("Gewinnwachstum positiv")
        else:
            cons.append("Gewinnwachstum negativ")

    if profit_margin is not None:
        if profit_margin > 0.10:
            score += 1
            pros.append("solide Gewinnmarge")
        elif profit_margin > 0:
            pros.append("Gewinnmarge positiv")
        else:
            cons.append("negative Gewinnmarge")

    if free_cashflow is not None:
        if free_cashflow > 0:
            score += 1
            pros.append("Free Cashflow positiv")
        else:
            cons.append("Free Cashflow negativ")

    if debt_to_equity is not None:
        if debt_to_equity <= 100:
            score += 1
            pros.append("Verschuldung wirkt moderat")
        elif debt_to_equity > 200:
            cons.append("Verschuldung hoch")

    if dividend_yield is not None and dividend_yield > 0:
        pros.append("Dividende vorhanden")

    if available_count < 3:
        rating = "UNKNOWN"
        data_quality = "LOW"
        cons.append("Fundamentaldaten unvollständig")

    elif score >= 7:
        rating = "VERY SOLID"
        data_quality = "GOOD"

    elif score >= 5:
        rating = "SOLID"
        data_quality = "GOOD"

    elif score >= 3:
        rating = "MIXED"
        data_quality = "OK"

    else:
        rating = "WEAK"
        data_quality = "OK"

    pros = list(dict.fromkeys(pros))
    cons = list(dict.fromkeys(cons))

    return score, rating, pros, cons, available_count, data_quality


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

    # Fundamentaldaten aus yfinance
    forward_pe = safe_number(info.get("forwardPE"))
    trailing_pe = safe_number(info.get("trailingPE"))
    peg_ratio = safe_number(info.get("pegRatio"))
    revenue_growth = safe_number(info.get("revenueGrowth"))
    earnings_growth = safe_number(info.get("earningsGrowth"))
    profit_margin = safe_number(info.get("profitMargins"))
    debt_to_equity = safe_number(info.get("debtToEquity"))
    free_cashflow = safe_number(info.get("freeCashflow"))
    operating_cashflow = safe_number(info.get("operatingCashflow"))

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
    volume_ratio = current_volume / avg_volume_20 if avg_volume_20 and avg_volume_20 > 0 else 0

    volume_signal = "NORMAL"

    if current_volume > avg_volume_20 * 1.5:
        volume_signal = "HIGH"
    elif current_volume < avg_volume_20 * 0.7:
        volume_signal = "LOW"

    dividend_rate = safe_number(info.get("dividendRate"))

    if dividend_rate is not None and current_price > 0:
        dividend_yield = (dividend_rate / current_price) * 100
    else:
        dividend_yield = 0

    (
        fundamental_score,
        fundamental_rating,
        fundamental_pros,
        fundamental_cons,
        fundamental_data_points,
        fundamental_data_quality
    ) = calculate_fundamental_score(
        forward_pe,
        trailing_pe,
        peg_ratio,
        revenue_growth,
        earnings_growth,
        profit_margin,
        debt_to_equity,
        free_cashflow,
        dividend_yield
    )

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

    if fundamental_rating in ["VERY SOLID", "SOLID"]:
        reason.append("fundamental solide")

    if fundamental_rating == "UNKNOWN":
        reason.append("Fundamentaldaten unvollständig")

    if fundamental_rating == "WEAK":
        reason.append("Fundamentaldaten schwach")

    reason_text = ", ".join(reason)

    eqs_news_items, eqs_query = get_eqs_news(company_name, ticker)
    eqs_news_count = len(eqs_news_items)
    eqs_news_score, eqs_keywords = score_eqs_news(eqs_news_items)
    eqs_signal = build_eqs_signal(eqs_news_score, eqs_news_count)

    latest_eqs_news = eqs_news_items[0] if eqs_news_items else {}
    news_momentum_signal, news_momentum_score = build_news_momentum_signal(
        change_1d,
        change_1w,
        volume_ratio,
        rsi,
        current_price,
        ema20,
        eqs_news_score,
        eqs_news_count
    )

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
        "52W High Raw": round(high_52w, 2),
        "Distance 52W High %": round(distance_52w_high, 2),

        "Volatility 30D %": round(volatility_30d, 2),
        "Beta": beta,

        "Volume Signal": volume_signal,
        "Volume Ratio": round(volume_ratio, 2),

        "EQS News Count 14D": eqs_news_count,
        "EQS Latest Title": latest_eqs_news.get("title", "-"),
        "EQS Latest Date": latest_eqs_news.get("published", "-"),
        "EQS Latest Source": latest_eqs_news.get("source", "-"),
        "EQS Link": latest_eqs_news.get("link", "-"),
        "EQS Search Query": eqs_query,
        "EQS News Score": eqs_news_score,
        "EQS Keywords": eqs_keywords,
        "EQS Signal": eqs_signal,
        "News Momentum Score": news_momentum_score,
        "News Momentum Signal": news_momentum_signal,

        "Dividend Yield %": format_percent(dividend_yield),
        "Dividend Rate": format_price(dividend_rate, currency),

        "Ex Dividend Date": ex_dividend_date,
        "Last Dividend Date": last_dividend_date,

        "Stop Loss Idea": format_price(stop_loss_ema50, currency),

        "Market Cap": market_cap,
        "Market Cap Class": market_cap_class,

        "Forward PE": format_number(forward_pe),
        "Trailing PE": format_number(trailing_pe),
        "PEG Ratio": format_number(peg_ratio),
        "Revenue Growth": format_growth(revenue_growth),
        "Revenue Growth Raw": format_number(revenue_growth),
        "Earnings Growth": format_growth(earnings_growth),
        "Earnings Growth Raw": format_number(earnings_growth),
        "Profit Margin": format_growth(profit_margin),
        "Profit Margin Raw": format_number(profit_margin),
        "Debt To Equity": format_number(debt_to_equity),
        "Free Cashflow": format_big_number(free_cashflow),
        "Free Cashflow Raw": format_number(free_cashflow),
        "Operating Cashflow": format_big_number(operating_cashflow),
        "Operating Cashflow Raw": format_number(operating_cashflow),
        "Fundamental Score": fundamental_score,
        "Fundamental Rating": fundamental_rating,
        "Fundamental Data Points": fundamental_data_points,
        "Fundamental Data Quality": fundamental_data_quality,
        "Fundamental Pros": " | ".join(fundamental_pros) if fundamental_pros else "-",
        "Fundamental Cons": " | ".join(fundamental_cons) if fundamental_cons else "-",

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

        if index % 25 == 0:
            save_news_cache(NEWS_CACHE)

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

    save_news_cache(NEWS_CACHE)

    with open("data_update_meta.json", "w", encoding="utf-8") as meta_file:
        json.dump(
            {
                "portfolio_analysis.csv": datetime.now().isoformat(),
                "eqs_news_cache.json": datetime.now().isoformat(),
            },
            meta_file,
            ensure_ascii=False,
            indent=2
        )

    print("\n====================================")
    print("FERTIG")
    print("====================================")
    print("Datei gespeichert:")
    print("portfolio_analysis.csv")

else:
    print("Keine gültigen Daten gefunden.")