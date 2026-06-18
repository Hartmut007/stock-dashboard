import pandas as pd
import yfinance as yf
import json
from datetime import datetime


# ============================================================
# KONFIGURATION
# ============================================================

WATCHLIST_CSV    = "clean_watchlist.csv"
OUTPUT_CSV       = "portfolio_analysis.csv"
META_FILE        = "data_update_meta.json"
HISTORY_PERIOD   = "1y"


# ============================================================
# WATCHLIST LADEN
# ============================================================

watchlist = pd.read_csv(WATCHLIST_CSV, sep=";")
PORTFOLIO = watchlist["Ticker"].tolist()
print(f"\nGeladene Aktien: {len(PORTFOLIO)}")


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def convert_timestamp(ts):
    if ts is None:
        return "-"
    try:
        return datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
    except Exception:
        return "-"


def safe_number(value):
    if value is None:
        return None
    try:
        v = float(value)
        return None if pd.isna(v) else v
    except Exception:
        return None


def format_price(value, currency):
    try:
        if value is None or pd.isna(value):
            return "-"
        currency = currency or ""
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


def format_number(value):
    v = safe_number(value)
    return round(v, 2) if v is not None else "-"


def format_big_number(value):
    v = safe_number(value)
    if v is None:
        return "-"
    a = abs(v)
    if a >= 1_000_000_000:
        return f"{round(v / 1_000_000_000, 2)} Mrd."
    if a >= 1_000_000:
        return f"{round(v / 1_000_000, 2)} Mio."
    return f"{round(v, 2)}"


def format_growth(value):
    v = safe_number(value)
    return f"{round(v * 100, 2)}%" if v is not None else "-"


def percent_change(close, days):
    if len(close) <= days:
        return 0.0
    return ((close.iloc[-1] - close.iloc[-days]) / close.iloc[-days]) * 100


# ============================================================
# RSI – Wilder's Smoothing (korrekte Methode)
# ============================================================

def calculate_rsi(close, period=14):
    """
    Berechnet den RSI nach Wilder's Smoothing Method (EWM mit adjust=False).
    Das ist die korrekte, von den meisten Charting-Tools verwendete Methode.
    Der einfache Rolling-Mean überschätzt kurzfristige Ausschläge.
    """
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]


def calculate_rsi_series(close, period=14):
    """Gibt die komplette RSI-Serie zurück (für Early-Signal-Vergleiche)."""
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs  = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


# ============================================================
# KLASSIFIKATOREN
# ============================================================

def classify_market_cap(market_cap):
    if market_cap is None:
        return "UNKNOWN"
    if market_cap >= 200_000_000_000:
        return "Mega Cap"
    if market_cap >= 10_000_000_000:
        return "Large Cap"
    if market_cap >= 2_000_000_000:
        return "Mid Cap"
    if market_cap >= 300_000_000:
        return "Small Cap"
    return "Micro Cap"


def calculate_risk_level(rsi, distance_ema20, volatility_30d, beta):
    score = 0
    if rsi > 75:       score += 2
    elif rsi > 70:     score += 1
    if distance_ema20 > 15:  score += 2
    elif distance_ema20 > 8: score += 1
    if volatility_30d > 5:   score += 2
    elif volatility_30d > 3: score += 1
    if beta is not None:
        if beta > 1.8:       score += 2
        elif beta > 1.3:     score += 1
    if score >= 5:  return "HIGH RISK"
    if score >= 3:  return "MEDIUM RISK"
    return "LOW RISK"


# ============================================================
# FUNDAMENTAL-SCORE
# ============================================================

def calculate_fundamental_score(
    forward_pe, trailing_pe, peg_ratio,
    revenue_growth, earnings_growth, profit_margin,
    debt_to_equity, free_cashflow, dividend_yield
):
    score = 0
    pros  = []
    cons  = []

    values = [forward_pe, trailing_pe, peg_ratio, revenue_growth,
              earnings_growth, profit_margin, debt_to_equity, free_cashflow]
    available_count = sum(v is not None for v in values)

    if forward_pe is not None:
        if 0 < forward_pe <= 25:
            score += 1; pros.append("Forward KGV im gesunden Bereich")
        elif forward_pe > 40:
            cons.append("Forward KGV sehr hoch")

    if trailing_pe is not None:
        if 0 < trailing_pe <= 30:
            score += 1; pros.append("KGV nicht übertrieben")
        elif trailing_pe > 45:
            cons.append("KGV sehr hoch")

    if peg_ratio is not None:
        if 0 < peg_ratio <= 2:
            score += 1; pros.append("PEG Ratio attraktiv")
        elif peg_ratio > 3:
            cons.append("PEG Ratio hoch")

    if revenue_growth is not None:
        if revenue_growth > 0:
            score += 1; pros.append("Umsatzwachstum positiv")
        else:
            cons.append("Umsatzwachstum negativ")

    if earnings_growth is not None:
        if earnings_growth > 0:
            score += 1; pros.append("Gewinnwachstum positiv")
        else:
            cons.append("Gewinnwachstum negativ")

    if profit_margin is not None:
        if profit_margin > 0.10:
            score += 1; pros.append("Solide Gewinnmarge")
        elif profit_margin > 0:
            pros.append("Gewinnmarge positiv")
        else:
            cons.append("Negative Gewinnmarge")

    if free_cashflow is not None:
        if free_cashflow > 0:
            score += 1; pros.append("Free Cashflow positiv")
        else:
            cons.append("Free Cashflow negativ")

    if debt_to_equity is not None:
        if debt_to_equity <= 100:
            score += 1; pros.append("Verschuldung moderat")
        elif debt_to_equity > 200:
            cons.append("Verschuldung hoch")

    if dividend_yield is not None and dividend_yield > 0:
        pros.append("Dividende vorhanden")

    if available_count < 3:
        rating       = "UNKNOWN"
        data_quality = "LOW"
        cons.append("Fundamentaldaten unvollständig")
    elif score >= 7:
        rating = "VERY SOLID"; data_quality = "GOOD"
    elif score >= 5:
        rating = "SOLID";      data_quality = "GOOD"
    elif score >= 3:
        rating = "MIXED";      data_quality = "OK"
    else:
        rating = "WEAK";       data_quality = "OK"

    pros = list(dict.fromkeys(pros))
    cons = list(dict.fromkeys(cons))
    return score, rating, pros, cons, available_count, data_quality


# ============================================================
# 🚀 EARLY-SIGNAL-SCORE  (Kernstück des neuen Systems)
# ============================================================

def calculate_early_signal(close, volume, rsi_series, ema20_series, ema50_series):
    """
    Erkennt Aktien in der Aufbau-/Akkumulationsphase BEVOR sie ausbrechen.

    Gibt zurück:
        score   – 0 bis 10
        signals – Liste erkannter Muster (Erklärtext)
        label   – Kurzbezeichnung des stärksten Musters
    """
    score   = 0
    signals = []

    if len(close) < 50:
        return 0, [], "KEINE DATEN"

    current_price = close.iloc[-1]

    # ---- Volumen-Akkumulation --------------------------------
    # Steigendes Volumen bei seitwärts laufendem Kurs = institutionelle
    # Akkumulation. Das klassische Frühwarnzeichen vor einem Breakout.
    vol_20   = volume.tail(20).mean()
    vol_5    = volume.tail(5).mean()
    price_hi = close.tail(20).max()
    price_lo = close.tail(20).min()
    range_20 = (price_hi - price_lo) / price_lo * 100 if price_lo > 0 else 999

    if vol_5 > vol_20 * 1.35 and range_20 < 8:
        score += 3
        signals.append("Volumen-Akkumulation (steigendes Vol. bei engem Kurs)")
    elif vol_5 > vol_20 * 1.15 and range_20 < 12:
        score += 1
        signals.append("Leichte Vol.-Erhöhung in Seitwärtsphase")

    # ---- Relatives Volumen (RVOL) ----------------------------
    rvol = vol_5 / vol_20 if vol_20 > 0 else 1.0

    # ---- EMA-Squeeze / Annäherung ----------------------------
    # Kurs bewegt sich von unten auf EMA20 zu und bricht gerade durch.
    ema20_current = ema20_series.iloc[-1]
    ema20_prev5   = ema20_series.iloc[-6] if len(ema20_series) >= 6 else ema20_current
    prev_price5   = close.iloc[-6] if len(close) >= 6 else close.iloc[-1]

    if prev_price5 < ema20_prev5 and current_price >= ema20_current * 0.98:
        score += 2
        signals.append("EMA20-Squeeze / Kurs nähert sich von unten")

    # ---- EMA50 dreht aufwärts --------------------------------
    ema50_current = ema50_series.iloc[-1]
    ema50_prev5   = ema50_series.iloc[-6] if len(ema50_series) >= 6 else ema50_current
    if ema50_current > ema50_prev5:
        score += 1
        signals.append("EMA50 dreht nach oben")

    # ---- RSI-Erholung aus überverkaufter Zone ----------------
    rsi_now   = rsi_series.iloc[-1]
    rsi_prev5 = rsi_series.iloc[-6] if len(rsi_series) >= 6 else rsi_now

    if 30 < rsi_now < 55 and rsi_now > rsi_prev5 + 5:
        score += 2
        signals.append("RSI erholt sich aus überverkaufter Zone")
    elif 30 < rsi_now < 50 and rsi_now > rsi_prev5 + 2:
        score += 1
        signals.append("RSI leichte Erholung")

    # ---- Bodenbildung: Kurs nahe 52W-Tief, aber dreht -------
    low_52w       = close.tail(252).min()
    dist_from_low = (current_price - low_52w) / low_52w * 100 if low_52w > 0 else 999

    change_5d  = percent_change(close, 5)
    change_10d = percent_change(close, 10)

    if 3 < dist_from_low < 25 and change_5d > 0 and change_10d > 0:
        score += 2
        signals.append("Bodenbildung: nahe 52W-Tief mit positiver Kursdrehung")
    elif 3 < dist_from_low < 35 and change_5d > 0:
        score += 1
        signals.append("Mögliche Bodenbildung nahe 52W-Tief")

    # ---- Momentum-Divergenz: 1M besser als 3M ---------------
    # Wenn der Kurs nach einer langen Schwächephase gerade dreht,
    # ist der 1M-Wert meist viel besser als der 3M-Wert.
    change_1m = percent_change(close, 22)
    change_3m = percent_change(close, 66)

    if change_1m > 0 and change_3m < -5 and change_1m > change_3m + 8:
        score += 1
        signals.append("Momentum-Divergenz: 1M dreht positiv nach langem Abschwung")

    # ---- Label bestimmen ------------------------------------
    if score >= 7:
        label = "STARKES EARLY SIGNAL"
    elif score >= 5:
        label = "EARLY SIGNAL"
    elif score >= 3:
        label = "MÖGLICHES SIGNAL"
    else:
        label = "-"

    return min(score, 10), signals, label


# ============================================================
# AKTIEN ANALYSIEREN
# ============================================================

def analyze_stock(ticker, current_index, total_count):
    print(f"[{current_index}/{total_count}] Analysiere {ticker}...")

    stock = yf.Ticker(ticker)
    hist  = stock.history(period=HISTORY_PERIOD)

    if hist.empty:
        raise ValueError("Keine Kursdaten gefunden")

    close  = hist["Close"]
    volume = hist["Volume"]
    info   = stock.info

    company_name = info.get("shortName", ticker)
    currency     = info.get("currency", "")
    market_cap   = info.get("marketCap")
    beta         = info.get("beta")

    # Fundamentaldaten
    forward_pe       = safe_number(info.get("forwardPE"))
    trailing_pe      = safe_number(info.get("trailingPE"))
    peg_ratio        = safe_number(info.get("pegRatio"))
    revenue_growth   = safe_number(info.get("revenueGrowth"))
    earnings_growth  = safe_number(info.get("earningsGrowth"))
    profit_margin    = safe_number(info.get("profitMargins"))
    debt_to_equity   = safe_number(info.get("debtToEquity"))
    free_cashflow    = safe_number(info.get("freeCashflow"))
    operating_cf     = safe_number(info.get("operatingCashflow"))

    # ---- Technische Berechnungen ----------------------------
    current_price = close.iloc[-1]

    ema20_series = close.ewm(span=20).mean()
    ema50_series = close.ewm(span=50).mean()
    ema100_series = close.ewm(span=100).mean()

    ema20  = ema20_series.iloc[-1]
    ema50  = ema50_series.iloc[-1]
    ema100 = ema100_series.iloc[-1]

    change_1d = percent_change(close, 2)
    change_1w = percent_change(close, 6)
    change_1m = percent_change(close, 22)
    change_3m = percent_change(close, 66)
    change_6m = percent_change(close, 132)

    rsi_series = calculate_rsi_series(close)
    rsi        = rsi_series.iloc[-1]

    # Explizit auf 252 Handelstage (≈1 Jahr) begrenzen
    high_52w       = close.tail(252).max()
    low_52w        = close.tail(252).min()
    dist_52w_high  = ((current_price - high_52w) / high_52w) * 100
    dist_52w_low   = ((current_price - low_52w)  / low_52w)  * 100

    distance_ema20 = ((current_price - ema20) / ema20) * 100
    distance_ema50 = ((current_price - ema50) / ema50) * 100

    daily_returns  = close.pct_change() * 100
    volatility_30d = daily_returns.tail(30).std()

    avg_vol_20     = volume.tail(20).mean()
    current_volume = volume.iloc[-1]
    rvol           = round(current_volume / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

    # Volumen-Trend (10 Tage, mittlere prozentuale Veränderung)
    vol_slope = round(volume.tail(10).pct_change().mean() * 100, 2)

    volume_signal = "NORMAL"
    if current_volume > avg_vol_20 * 1.5:
        volume_signal = "HIGH"
    elif current_volume < avg_vol_20 * 0.7:
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
        forward_pe, trailing_pe, peg_ratio,
        revenue_growth, earnings_growth, profit_margin,
        debt_to_equity, free_cashflow, dividend_yield
    )

    ex_dividend_date   = convert_timestamp(info.get("exDividendDate"))
    last_dividend_date = convert_timestamp(info.get("lastDividendDate"))

    stop_loss_ema50  = ema50 * 0.98
    market_cap_class = classify_market_cap(market_cap)

    risk_level = calculate_risk_level(rsi, distance_ema20, volatility_30d, beta)

    # ---- Early-Signal-Score ---------------------------------
    early_score, early_signals, early_label = calculate_early_signal(
        close, volume, rsi_series, ema20_series, ema50_series
    )

    # ---- Technischer Score (Trend-Stärke) -------------------
    score = 0
    if current_price > ema20:   score += 1
    if current_price > ema50:   score += 1
    if current_price > ema100:  score += 1
    if ema20 > ema50:           score += 1
    if ema50 > ema100:          score += 1
    if change_1w > 0:           score += 1
    if change_1m > 0:           score += 1
    if 45 <= rsi <= 70:         score += 1

    # ---- Rating bestimmen -----------------------------------
    turnaround = (
        change_6m < -15
        and change_1m > 5
        and current_price > ema20
        and rsi > 40
    )
    overbought = (rsi > 75 or distance_ema20 > 15)

    if early_score >= 5 and score <= 5 and not overbought:
        rating = "PRE-BREAKOUT"
    elif turnaround:
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

    # ---- Begründung -----------------------------------------
    reason = []
    if current_price > ema20:   reason.append("über EMA20")
    if current_price > ema50:   reason.append("über EMA50")
    if current_price > ema100:  reason.append("über EMA100")
    if change_1m > 0:           reason.append("1M positiv")
    if turnaround:              reason.append("mögliche Trendwende")
    if overbought:              reason.append("kurzfristig heiß gelaufen")
    if rsi < 35:                reason.append("überverkauft")
    if volume_signal == "HIGH": reason.append("hohes Volumen")
    if risk_level == "HIGH RISK": reason.append("hohes Risiko")
    if early_label != "-":      reason.append(f"Early: {early_label}")

    if fundamental_rating in ["VERY SOLID", "SOLID"]:
        reason.append("fundamental solide")
    if fundamental_rating == "UNKNOWN":
        reason.append("Fundamentaldaten unvollständig")
    if fundamental_rating == "WEAK":
        reason.append("Fundamentaldaten schwach")

    return {
        "Ticker":    ticker,
        "Company":   company_name,
        "Currency":  currency,

        "Price":     format_price(current_price, currency),
        "Raw Price": round(current_price, 2),

        "EMA20":   format_price(ema20,  currency),
        "EMA50":   format_price(ema50,  currency),
        "EMA100":  format_price(ema100, currency),

        "Distance EMA20 %": round(distance_ema20, 2),
        "Distance EMA50 %": round(distance_ema50, 2),

        "1D %": round(change_1d, 2),
        "1W %": round(change_1w, 2),
        "1M %": round(change_1m, 2),
        "3M %": round(change_3m, 2),
        "6M %": round(change_6m, 2),

        "RSI": round(rsi, 2),

        "52W High":             format_price(high_52w, currency),
        "52W High Raw":         round(high_52w, 2),
        "52W Low Raw":          round(low_52w, 2),
        "Distance 52W High %":  round(dist_52w_high, 2),
        "Distance 52W Low %":   round(dist_52w_low, 2),

        "Volatility 30D %": round(volatility_30d, 2),
        "Beta":              beta,

        "Volume Signal":    volume_signal,
        "RVOL":             rvol,
        "Volume Trend 10D": vol_slope,

        "Dividend Yield %":  format_percent(dividend_yield),
        "Dividend Rate":     format_price(dividend_rate, currency),
        "Ex Dividend Date":  ex_dividend_date,
        "Last Dividend Date": last_dividend_date,

        "Stop Loss Idea": format_price(stop_loss_ema50, currency),

        "Market Cap":       market_cap,
        "Market Cap Class": market_cap_class,

        "Forward PE":           format_number(forward_pe),
        "Trailing PE":          format_number(trailing_pe),
        "PEG Ratio":            format_number(peg_ratio),
        "Revenue Growth":       format_growth(revenue_growth),
        "Revenue Growth Raw":   format_number(revenue_growth),
        "Earnings Growth":      format_growth(earnings_growth),
        "Earnings Growth Raw":  format_number(earnings_growth),
        "Profit Margin":        format_growth(profit_margin),
        "Profit Margin Raw":    format_number(profit_margin),
        "Debt To Equity":       format_number(debt_to_equity),
        "Free Cashflow":        format_big_number(free_cashflow),
        "Free Cashflow Raw":    format_number(free_cashflow),
        "Operating Cashflow":   format_big_number(operating_cf),
        "Operating Cashflow Raw": format_number(operating_cf),

        "Fundamental Score":        fundamental_score,
        "Fundamental Rating":       fundamental_rating,
        "Fundamental Data Points":  fundamental_data_points,
        "Fundamental Data Quality": fundamental_data_quality,
        "Fundamental Pros":  " | ".join(fundamental_pros) if fundamental_pros else "-",
        "Fundamental Cons":  " | ".join(fundamental_cons) if fundamental_cons else "-",

        "Risk Level": risk_level,

        "Turnaround Candidate": "YES" if turnaround else "NO",

        # Early-Signal-Felder
        "Early Signal Score":   early_score,
        "Early Signal Label":   early_label,
        "Early Signal Details": " | ".join(early_signals) if early_signals else "-",

        "Score":  score,
        "Rating": rating,
        "Reason": ", ".join(reason),
    }


# ============================================================
# ANALYSE STARTEN
# ============================================================

results     = []
total_count = len(PORTFOLIO)

for index, ticker in enumerate(PORTFOLIO, start=1):
    try:
        result = analyze_stock(ticker, index, total_count)
        results.append(result)
    except Exception as error:
        print(f"  ⚠ Fehler bei {ticker}: {error}")


# ============================================================
# DATAFRAME & SPEICHERN
# ============================================================

df = pd.DataFrame(results)

if not df.empty:
    df = df.sort_values(
        by=["Early Signal Score", "Score", "1M %"],
        ascending=[False, False, False]
    )

    df.to_csv(OUTPUT_CSV, sep=";", index=False, encoding="utf-8-sig")

    # Zeitstempel schreiben (wird vom Dashboard gelesen)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now().isoformat()}, f)

    print("\n" + "=" * 50)
    print("ANALYSE FERTIG")
    print("=" * 50)
    print(f"Analysierte Aktien: {len(results)}")
    print(f"Output: {OUTPUT_CSV}")

    # Kurze Übersicht der Top-Early-Signals
    early_candidates = df[df["Early Signal Label"].str.contains("SIGNAL", na=False)]
    if not early_candidates.empty:
        print(f"\n🚀 Early-Signal-Kandidaten ({len(early_candidates)}):")
        for _, row in early_candidates.head(10).iterrows():
            print(f"   {row['Ticker']:8s} | {row['Early Signal Label']:22s} | Score: {row['Early Signal Score']} | {row['Early Signal Details'][:60]}")

else:
    print("Keine gültigen Daten gefunden.")
