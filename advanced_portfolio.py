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

# Smart-Money-Daten (Insider-Transaktionen, institutionelle Beteiligung) kosten
# zusätzliche yfinance-Requests pro Aktie. Bei 800+ Tickern wäre das für JEDE
# Aktie zu langsam und würde Yahoo schnell ins Rate-Limit laufen lassen.
# Deshalb: Phase 1 screent technisch GÜNSTIG (1 Request/Aktie), Phase 3 holt
# Smart-Money-Daten NUR für die Shortlist der technisch interessanten Kandidaten.
ENABLE_SMART_MONEY      = True
SMART_MONEY_MIN_SCORE   = 4     # Technischer Score
SMART_MONEY_MIN_EARLY   = 3     # ODER Early-Signal-Score
SMART_MONEY_MAX_CANDIDATES = 250  # Hard Cap, damit ein Lauf nicht ausartet

BENCHMARK_TICKER = "SPY"  # Für Markt-relative Stärke


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
# 🏛️ SMART-MONEY-SIGNAL  (Insider-Käufe + institutionelle Beteiligung)
# ============================================================

def fetch_smart_money_signal(stock, info):
    """
    Holt Insider-Transaktionen und institutionelle Beteiligung über yfinance.
    Beides kostet zusätzliche Requests, deshalb wird das nur für die
    Shortlist-Kandidaten aufgerufen (siehe SMART_MONEY_* Konfiguration oben).

    Insider-Käufe sind oft eines der aussagekräftigsten Frühindikatoren:
    Wer im Unternehmen sitzt und kauft, hat selten Zufallsgründe.
    """
    result = {
        "Smart Money Score":   0,
        "Smart Money Signal":  "⚪ Keine Daten",
        "Smart Money Details": "-",
        "Insider Buys 6M":     0,
        "Insider Sells 6M":    0,
        "Insider Net Value":   None,
        "Institutional %":     None,
        "Short % Float":       None,
        "Short Ratio":         None,
    }

    score = 0
    notes = []

    # ---- Insider-Transaktionen (Form 4 über Yahoo) -----------
    try:
        try:
            insider_df = stock.get_insider_transactions()
        except AttributeError:
            insider_df = stock.insider_transactions

        if insider_df is not None and not insider_df.empty:
            # Datumsspalte robust finden (Name variiert je yfinance-Version)
            date_col = None
            for col in insider_df.columns:
                if "date" in str(col).lower():
                    date_col = col
                    break

            if date_col is not None:
                insider_df = insider_df.copy()
                insider_df["_parsed_date"] = pd.to_datetime(insider_df[date_col], errors="coerce")
                cutoff = pd.Timestamp.today() - pd.Timedelta(days=182)
                recent = insider_df[insider_df["_parsed_date"] >= cutoff]
            else:
                # Kein Datum auffindbar -> alle verfügbaren Zeilen als "letzte bekannte" nehmen
                recent = insider_df.head(15)

            transaction_col = None
            for col in recent.columns:
                if str(col).lower() == "transaction":
                    transaction_col = col
                    break
            if transaction_col is None:
                for col in recent.columns:
                    if "transaction" in str(col).lower() or "text" in str(col).lower():
                        transaction_col = col
                        break

            value_col = None
            for col in recent.columns:
                if "value" in str(col).lower():
                    value_col = col
                    break

            buys, sells = 0, 0
            buy_value, sell_value = 0.0, 0.0

            if transaction_col is not None:
                for _, r in recent.iterrows():
                    text = str(r.get(transaction_col, "")).lower()
                    val = safe_number(r.get(value_col)) if value_col else None
                    val = abs(val) if val is not None else 0

                    if "purchase" in text or "buy" in text:
                        buys += 1
                        buy_value += val
                    elif "sale" in text or "sell" in text:
                        sells += 1
                        sell_value += val

            result["Insider Buys 6M"]  = buys
            result["Insider Sells 6M"] = sells
            net_value = buy_value - sell_value
            result["Insider Net Value"] = round(net_value, 2) if (buys or sells) else None

            if buys > 0 and sells == 0:
                score += 3
                notes.append(f"{buys}x Insider-Kauf, keine Verkäufe (6M)")
            elif buys > sells and buys >= 2:
                score += 2
                notes.append(f"Mehr Insider-Käufe ({buys}) als Verkäufe ({sells})")
            elif buys > 0 and net_value > 0:
                score += 1
                notes.append(f"Insider-Käufe vorhanden ({buys}x)")
            elif sells > buys and sells >= 3:
                score -= 1
                notes.append(f"Auffällig viele Insider-Verkäufe ({sells}x)")

    except Exception:
        pass

    # ---- Institutionelle Beteiligung --------------------------
    try:
        inst_pct = info.get("heldPercentInstitutions")
        if inst_pct is not None:
            inst_pct = float(inst_pct) * 100
            result["Institutional %"] = round(inst_pct, 2)

            if inst_pct >= 70:
                score += 1
                notes.append("hohe institutionelle Beteiligung")
            elif inst_pct <= 10:
                notes.append("geringe institutionelle Beteiligung (mehr Retail-getrieben)")
    except Exception:
        pass

    # ---- Short-Interest / Squeeze-Potenzial -------------------
    # Hohe Shortquote + sich verbessernde Technik ist eines der klassischen
    # Setups für überproportionale Bewegungen nach oben (Short Squeeze).
    try:
        short_pct   = info.get("shortPercentOfFloat") or info.get("sharesPercentSharesOut")
        short_ratio = info.get("shortRatio")

        if short_pct is not None:
            short_pct_val = float(short_pct) * 100
            result["Short % Float"] = round(short_pct_val, 2)
            if short_pct_val >= 20:
                notes.append(f"hohe Shortquote ({short_pct_val:.1f}% Float) -> Squeeze-Potenzial, aber auch Warnsignal")
            elif short_pct_val >= 10:
                notes.append(f"erhöhte Shortquote ({short_pct_val:.1f}% Float) -> Squeeze-Kontext")

        if short_ratio is not None:
            short_ratio_val = float(short_ratio)
            result["Short Ratio"] = round(short_ratio_val, 2)
            if short_ratio_val >= 6:
                notes.append(f"hohe Days-to-Cover ({short_ratio_val:.1f}) -> bei Rally schwer eindeckbar")
    except Exception:
        pass

    result["Smart Money Score"] = score

    if not notes:
        result["Smart Money Signal"] = "⚪ Keine Daten"
    elif score >= 3:
        result["Smart Money Signal"] = "🟢 Starkes Insider-Signal"
    elif score >= 1:
        result["Smart Money Signal"] = "🔵 Leicht positiv"
    elif score <= -1:
        result["Smart Money Signal"] = "🟠 Insider verkaufen"
    else:
        result["Smart Money Signal"] = "⚪ Neutral"

    result["Smart Money Details"] = " | ".join(notes) if notes else "-"

    return result


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
    ema200_series = close.ewm(span=200).mean()

    ema20  = ema20_series.iloc[-1]
    ema50  = ema50_series.iloc[-1]
    ema100 = ema100_series.iloc[-1]
    ema200 = ema200_series.iloc[-1]

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
    # Earnings-Datum ohne Zusatzrequest: soweit Yahoo es bereits in info liefert.
    earnings_ts = (
        info.get("earningsTimestampStart")
        or info.get("earningsTimestamp")
        or info.get("earningsTimestampEnd")
    )
    next_earnings_date = convert_timestamp(earnings_ts)

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
    if current_price > ema200:  score += 1
    if ema20 > ema50:           score += 1
    if ema50 > ema200:          score += 1
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
    if current_price > ema200:  reason.append("über EMA200")
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
        "EMA200":  format_price(ema200, currency),

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
        "Next Earnings Date": next_earnings_date,

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
# ANALYSE STARTEN  (Phase 1: technischer Schnell-Scan, alle Ticker)
# ============================================================

results     = []
total_count = len(PORTFOLIO)

for index, ticker in enumerate(PORTFOLIO, start=1):
    try:
        result = analyze_stock(ticker, index, total_count)
        results.append(result)
    except Exception as error:
        print(f"  ⚠ Fehler bei {ticker}: {error}")

df = pd.DataFrame(results)

if df.empty:
    print("Keine gültigen Daten gefunden.")
else:

    # Sector/Industry kommen aus watchlist_cleaner.py (clean_watchlist.csv),
    # nicht aus analyze_stock() selbst -> hier zusammenführen.
    sector_lookup = watchlist[[c for c in ["Ticker", "Sector", "Industry", "Liquidity", "Exchange", "Avg Dollar Volume"] if c in watchlist.columns]].drop_duplicates(subset="Ticker")
    df = df.merge(sector_lookup, on="Ticker", how="left")
    df["Sector"] = df["Sector"].fillna("OTHER")
    df["Industry"] = df["Industry"].fillna("-")

    # ============================================================
    # PHASE 2: 📡 RELATIVE STÄRKE  (Sektor-Peer-Group + Markt)
    # ============================================================
    # Idee: Ein technischer Score allein sagt nichts darüber aus, ob eine
    # Aktie STÄRKER ist als ihr eigenes Themenfeld. Eine Quantum-Aktie mit
    # +8% in 1M ist nichts Besonderes, wenn der ganze Quantum-Sektor +15%
    # gemacht hat — und sehr wohl etwas Besonderes, wenn der Sektor -5% steht.
    # Das ist reine Pandas-Mathematik auf bereits geladenen Daten, kostet
    # also KEINE zusätzlichen Netzwerk-Requests.

    print("\n📡 Berechne relative Stärke vs. Sektor...")

    sector_avg = df.groupby("Sector").agg(
        **{
            "_sector_avg_1m": ("1M %", "mean"),
            "_sector_avg_3m": ("3M %", "mean"),
            "_sector_avg_6m": ("6M %", "mean"),
            "_sector_count":  ("1M %", "count"),
        }
    ).reset_index()

    df = df.merge(sector_avg, on="Sector", how="left")

    df["Relative Strength 1M"] = (df["1M %"] - df["_sector_avg_1m"]).round(2)
    df["Relative Strength 3M"] = (df["3M %"] - df["_sector_avg_3m"]).round(2)

    # Perzentil innerhalb des eigenen Sektors (0-100, höher = stärker als Peers)
    df["RS Percentile"] = (
        df.groupby("Sector")["1M %"].rank(pct=True) * 100
    ).round(1)

    def label_rs(row):
        if row["_sector_count"] < 3:
            return "❓ Zu wenig Peers"
        if row["RS Percentile"] >= 80:
            return "🟢 Top-Performer im Sektor"
        if row["RS Percentile"] >= 60:
            return "🔵 Überdurchschnittlich"
        if row["RS Percentile"] <= 20:
            return "🔴 Schwächster im Sektor"
        return "🟡 Durchschnittlich"

    df["RS Rating"] = df.apply(label_rs, axis=1)
    df["Sector Avg 1M %"] = df["_sector_avg_1m"].round(2)
    df = df.drop(columns=["_sector_avg_1m", "_sector_avg_3m", "_sector_avg_6m", "_sector_count"])

    # ---- Markt-relative Stärke (vs. SPY) ----------------------
    try:
        spy_hist = yf.Ticker(BENCHMARK_TICKER).history(period=HISTORY_PERIOD)
        spy_close = spy_hist["Close"]
        spy_1m = percent_change(spy_close, 22)
        spy_3m = percent_change(spy_close, 66)
        print(f"   Markt-Benchmark {BENCHMARK_TICKER}: 1M {round(spy_1m,2)}% | 3M {round(spy_3m,2)}%")
    except Exception:
        spy_1m, spy_3m = 0.0, 0.0
        print(f"   ⚠ Konnte Benchmark {BENCHMARK_TICKER} nicht laden, nutze 0% als Fallback")

    df["Market RS 1M"] = (df["1M %"] - spy_1m).round(2)
    df["Market RS 3M"] = (df["3M %"] - spy_3m).round(2)

    # ============================================================
    # PHASE 3: 🏛️ SMART MONEY  (nur für die Shortlist)
    # ============================================================

    if ENABLE_SMART_MONEY:
        shortlist_mask = (
            (df["Score"] >= SMART_MONEY_MIN_SCORE)
            | (df["Early Signal Score"] >= SMART_MONEY_MIN_EARLY)
        )
        shortlist = df[shortlist_mask].sort_values(
            by=["Early Signal Score", "Score"], ascending=[False, False]
        ).head(SMART_MONEY_MAX_CANDIDATES)

        print(f"\n🏛️ Smart-Money-Check für {len(shortlist)} Shortlist-Kandidaten "
              f"(von {len(df)} gescreenten Aktien)...")

        smart_money_results = {}

        for i, (_, row) in enumerate(shortlist.iterrows(), start=1):
            ticker = row["Ticker"]
            print(f"   [{i}/{len(shortlist)}] Insider-Check {ticker}...")
            try:
                stock_obj = yf.Ticker(ticker)
                info_obj  = stock_obj.info
                smart_money_results[ticker] = fetch_smart_money_signal(stock_obj, info_obj)
            except Exception as err:
                print(f"      ⚠ Fehler: {err}")

        sm_defaults = {
            "Smart Money Score": 0, "Smart Money Signal": "⚪ Nicht geprüft",
            "Smart Money Details": "-", "Insider Buys 6M": 0, "Insider Sells 6M": 0,
            "Insider Net Value": None, "Institutional %": None,
            "Short % Float": None, "Short Ratio": None,
        }
        for col, default in sm_defaults.items():
            df[col] = df["Ticker"].map(lambda t, c=col: smart_money_results.get(t, {}).get(c, default))

    else:
        df["Smart Money Score"]   = 0
        df["Smart Money Signal"]  = "⚪ Deaktiviert"
        df["Smart Money Details"] = "-"
        df["Insider Buys 6M"]     = 0
        df["Insider Sells 6M"]    = 0
        df["Insider Net Value"]   = None
        df["Institutional %"]     = None
        df["Short % Float"]       = None
        df["Short Ratio"]         = None

    # ============================================================
    # PHASE 4: 🎯 SWING SCORE  (vereinheitlichter Ranking-Score, 0-100)
    # ============================================================
    # Kombiniert alles, was für einen Swingtrader zählt:
    #   - Technischer Trend (Score)          → 20 Punkte
    #   - Early-Signal (Aufbauphase)         → 30 Punkte  (Kernstück: FRÜH erkennen)
    #   - Relative Stärke im Sektor          → 30 Punkte  (stärker als die Peers?)
    #   - Insider-/Smart-Money-Hinweise      → 10 Punkte  (nur Zusatzfilter, kein Hauptsignal)
    #   - Risiko-Malus                       → bis -15 Punkte

    def build_swing_score(row):
        tech      = max(0, min(row.get("Score", 0), 8)) / 8 * 20
        early     = max(0, min(row.get("Early Signal Score", 0), 10)) / 10 * 30
        rs_pct    = row.get("RS Percentile", 50)
        rs_pct    = 50 if pd.isna(rs_pct) else rs_pct
        rs_points = max(0, min(rs_pct, 100)) / 100 * 30
        smart     = row.get("Smart Money Score", 0)
        smart_points = max(0, min((smart + 1) / 5, 1)) * 10  # -1..+4 auf 0..10 gemappt; nur Zusatzfilter

        risk_malus = 0
        if row.get("Risk Level") == "HIGH RISK":
            risk_malus = 15
        elif row.get("Risk Level") == "MEDIUM RISK":
            risk_malus = 5

        total = tech + early + rs_points + smart_points - risk_malus
        return round(max(0, min(total, 100)), 1)

    df["Swing Score"] = df.apply(build_swing_score, axis=1)

    def swing_tier(score):
        if score >= 80: return "🎯 TOP SWING SETUP"
        if score >= 65: return "🟢 Starkes Setup"
        if score >= 50: return "🔵 Solide"
        if score >= 35: return "🟡 Beobachten"
        return "⚪ Schwach"

    df["Swing Tier"] = df["Swing Score"].apply(swing_tier)

    # ============================================================
    # SPEICHERN
    # ============================================================

    df = df.sort_values(by=["Swing Score"], ascending=False)

    df.to_csv(OUTPUT_CSV, sep=";", index=False, encoding="utf-8-sig")

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now().isoformat(), "files": {OUTPUT_CSV: {"updated_at": datetime.now().isoformat()}}}, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print("ANALYSE FERTIG")
    print("=" * 50)
    print(f"Analysierte Aktien: {len(results)}")
    print(f"Output: {OUTPUT_CSV}")

    top_swing = df[df["Swing Score"] >= 65]
    if not top_swing.empty:
        print(f"\n🎯 Top-Swing-Setups ({len(top_swing)}):")
        for _, row in top_swing.head(15).iterrows():
            print(f"   {row['Ticker']:8s} | Swing {row['Swing Score']:5.1f} | "
                  f"{row['Swing Tier']:20s} | RS: {row['RS Rating']:25s} | {row['Smart Money Signal']}")
