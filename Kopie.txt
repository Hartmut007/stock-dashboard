import pandas as pd
import streamlit as st
import os
import subprocess
import hmac

# ============================================================
# 🔐 LOGIN-BEREICH
# ============================================================

def check_password():
    """Einfacher Login mit Benutzern aus Streamlit Secrets."""

    def password_entered():
        username = st.session_state.get("username", "").strip()
        password = st.session_state.get("password", "")

        users = st.secrets.get("users", {})

        if username in users and hmac.compare_digest(password, users[username]):
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = username
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.title("🔐 Login")
    st.write("Bitte melde dich an, um das Hartmut-Portfolio zu sehen.")

    st.text_input("Benutzername", key="username")
    st.text_input("Passwort", type="password", key="password")

    st.button("Einloggen", on_click=password_entered)

    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("Benutzername oder Passwort falsch.")

    return False


if not check_password():
    st.stop()


# Optional: eingeloggten Nutzer anzeigen
st.sidebar.success(f"Angemeldet als: {st.session_state.get('current_user', '')}")

if st.sidebar.button("Ausloggen"):
    for key in ["password_correct", "current_user", "username"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Portfolio Dashboard",
    layout="wide"
)


# ============================================================
# CSV LADEN
# ============================================================

if not os.path.exists("portfolio_analysis.csv"):

    st.warning(
        "Portfolio-Datei nicht gefunden. "
        "Analyse wird erstellt..."
    )

    subprocess.run(
        ["python", "advanced_portfolio.py"]
    )

df = pd.read_csv(
    "portfolio_analysis.csv",
    sep=";"
)


# ============================================================
# DATUM FÜR DIVIDENDENKALENDER VORBEREITEN
# ============================================================

df["Ex Dividend Parsed"] = pd.to_datetime(
    df["Ex Dividend Date"],
    format="%d.%m.%Y",
    errors="coerce"
)

df["Dividend Year"] = df["Ex Dividend Parsed"].dt.year
df["Dividend Month"] = df["Ex Dividend Parsed"].dt.month


# ============================================================
# FUNDAMENTAL-SPALTEN ABSICHERN
# ============================================================

fundamental_defaults = {
    "Forward PE": "-",
    "Trailing PE": "-",
    "PEG Ratio": "-",
    "Revenue Growth": "-",
    "Earnings Growth": "-",
    "Profit Margin": "-",
    "Debt To Equity": "-",
    "Free Cashflow": "-",
    "Operating Cashflow": "-",
    "Fundamental Score": 0,
    "Fundamental Rating": "WEAK / UNKNOWN",
    "Fundamental Pros": "-",
    "Fundamental Cons": "-"
}

for column, default_value in fundamental_defaults.items():

    if column not in df.columns:
        df[column] = default_value

# Numeric-Spalten absichern, damit Mittelwerte, Sortierung und Regeln stabil bleiben.
for numeric_column in [
    "Score",
    "1D %",
    "1W %",
    "1M %",
    "3M %",
    "6M %",
    "RSI",
    "Fundamental Score"
]:

    if numeric_column in df.columns:
        df[numeric_column] = pd.to_numeric(
            df[numeric_column],
            errors="coerce"
        ).fillna(0)


# ============================================================
# STRATEGIE-HORIZONT
# ============================================================

strategy_mode = st.sidebar.selectbox(
    "Strategie-Horizont",
    [
        "Kurzfristig",
        "Mittelfristig",
        "Langfristig"
    ],
    index=1
)




# ============================================================
# ENTSCHEIDUNGSLOGIK: ACTION SIGNAL, CRV, PRO / CONTRA
# ============================================================

def safe_float(value):

    try:
        if pd.isna(value):
            return None

        value = str(value)

        for currency_text in [
            "€", "$", "%", "EUR", "USD", "GBP", "CHF",
            "JPY", "CAD", "AUD", "HKD", "CNY"
        ]:
            value = value.replace(currency_text, "")

        value = value.replace(",", ".")
        value = value.strip()

        if value in ["", "-", "nan", "None"]:
            return None

        return float(value)

    except Exception:
        return None


def format_number(value):

    if value is None:
        return "-"

    return f"{value:.2f}"


def clean_text_value(value):

    value = str(value).strip()

    if value in ["", "-", "nan", "None"]:
        return ""

    return value


def unique_items(items):

    result = []

    for item in items:
        item = clean_text_value(item)

        if item and item not in result:
            result.append(item)

    return result


def build_trade_levels(price, ema20, ema50, ema100, high_52w):

    if price is None:
        return None, None, None, None, None, None, "-"

    entry_low = price * 0.98
    entry_high = price * 1.02

    # Stop-Loss wird je nach Zeithorizont anders gewählt.
    # Kurzfristig: näher am EMA20; mittelfristig: EMA50; langfristig: EMA100.
    if strategy_mode == "Kurzfristig":

        if ema20 is not None:
            stop_loss = ema20 * 0.97
        elif ema50 is not None:
            stop_loss = ema50 * 0.98
        else:
            stop_loss = price * 0.94

        fallback_target_1 = price * 1.08
        fallback_target_2 = price * 1.14

    elif strategy_mode == "Langfristig":

        if ema100 is not None:
            stop_loss = ema100 * 0.95
        elif ema50 is not None:
            stop_loss = ema50 * 0.95
        else:
            stop_loss = price * 0.85

        fallback_target_1 = price * 1.20
        fallback_target_2 = price * 1.35

    else:

        if ema50 is not None:
            stop_loss = ema50 * 0.97
        elif ema100 is not None:
            stop_loss = ema100 * 0.98
        else:
            stop_loss = price * 0.92

        fallback_target_1 = price * 1.12
        fallback_target_2 = price * 1.22

    target_basis = "Fallback-Ziel"

    # Echtes Ziel bevorzugen: 52W-Hoch, sofern es noch oberhalb des aktuellen Preises liegt.
    if high_52w is not None and high_52w > price * 1.03:
        target_1 = high_52w
        target_2 = max(high_52w * 1.05, fallback_target_2)
        target_basis = "52W-Hoch"
    else:
        target_1 = fallback_target_1
        target_2 = fallback_target_2

    if stop_loss is not None and stop_loss < price and target_1 > price:
        risk = price - stop_loss
        reward = target_1 - price
        crv = reward / risk if risk > 0 else None
    else:
        crv = None

    return entry_low, entry_high, stop_loss, target_1, target_2, crv, target_basis


def build_decision_data(row):

    price = safe_float(row.get("Price"))
    ema20 = safe_float(row.get("EMA20"))
    ema50 = safe_float(row.get("EMA50"))
    ema100 = safe_float(row.get("EMA100"))
    high_52w = safe_float(row.get("52W High"))
    rsi = safe_float(row.get("RSI"))
    score = safe_float(row.get("Score"))
    perf_1m = safe_float(row.get("1M %"))
    perf_3m = safe_float(row.get("3M %"))
    perf_6m = safe_float(row.get("6M %"))

    fundamental_score = safe_float(row.get("Fundamental Score"))
    forward_pe = safe_float(row.get("Forward PE"))
    trailing_pe = safe_float(row.get("Trailing PE"))
    peg_ratio = safe_float(row.get("PEG Ratio"))
    revenue_growth = safe_float(row.get("Revenue Growth"))
    earnings_growth = safe_float(row.get("Earnings Growth"))
    profit_margin = safe_float(row.get("Profit Margin"))
    debt_to_equity = safe_float(row.get("Debt To Equity"))
    free_cashflow = safe_float(row.get("Free Cashflow"))

    rating = str(row.get("Rating", ""))
    risk_level = str(row.get("Risk Level", ""))
    turnaround = str(row.get("Turnaround Candidate", ""))
    fundamental_rating = str(row.get("Fundamental Rating", "WEAK / UNKNOWN"))
    fundamental_pros = clean_text_value(row.get("Fundamental Pros", "-"))
    fundamental_cons = clean_text_value(row.get("Fundamental Cons", "-"))

    pros = []
    cons = []

    # ----------------------------
    # ENTRY / STOP / TARGET / CRV
    # ----------------------------

    (
        entry_low,
        entry_high,
        stop_loss,
        target_1,
        target_2,
        crv,
        target_basis
    ) = build_trade_levels(
        price,
        ema20,
        ema50,
        ema100,
        high_52w
    )

    # ----------------------------
    # FUNDAMENTAL-DATENQUALITÄT
    # ----------------------------

    # Score 0 + WEAK / UNKNOWN wird als "Daten fehlen" behandelt, nicht automatisch als schlecht.
    has_fundamental_data = not (
        fundamental_score is None
        or (
            fundamental_score == 0
            and fundamental_rating in ["WEAK / UNKNOWN", "UNKNOWN", "-"]
        )
    )

    fundamental_ok = (
        not has_fundamental_data
        or (
            fundamental_score is not None
            and fundamental_score >= 5
        )
        or fundamental_rating in ["SOLID", "VERY SOLID"]
    )

    fundamental_weak = (
        has_fundamental_data
        and (
            (
                fundamental_score is not None
                and fundamental_score <= 2
            )
            or fundamental_rating == "WEAK"
        )
    )

    # ----------------------------
    # PRO ARGUMENTE
    # ----------------------------

    if score is not None and score >= 6:
        pros.append("starker technischer Score")

    if rating in ["BUY", "STRONG BUY"]:
        pros.append("positives Rating")

    if price is not None and ema20 is not None and price > ema20:
        pros.append("Kurs über EMA20")

    if price is not None and ema50 is not None and price > ema50:
        pros.append("Kurs über EMA50")

    if price is not None and ema100 is not None and price > ema100:
        pros.append("Kurs über EMA100")

    if ema20 is not None and ema50 is not None and ema20 > ema50:
        pros.append("EMA20 über EMA50")

    if ema50 is not None and ema100 is not None and ema50 > ema100:
        pros.append("EMA50 über EMA100")

    if rsi is not None and 40 <= rsi <= 70:
        pros.append("RSI im gesunden Bereich")

    if perf_1m is not None and perf_1m > 0:
        pros.append("positive 1M-Performance")

    if perf_3m is not None and perf_3m > 0:
        pros.append("positive 3M-Performance")

    if crv is not None and crv >= 1.6:
        pros.append("attraktives Chance-Risiko-Verhältnis")

    if target_basis == "52W-Hoch":
        pros.append("Ziel basiert auf 52W-Hoch")

    if turnaround == "YES":
        pros.append("Turnaround-Kandidat")

    if has_fundamental_data and fundamental_score is not None and fundamental_score >= 5:
        pros.append("solider Fundamental-Score")

    if fundamental_rating in ["SOLID", "VERY SOLID"]:
        pros.append("fundamental solide bewertet")

    if revenue_growth is not None and revenue_growth > 0:
        pros.append("positives Umsatzwachstum")

    if earnings_growth is not None and earnings_growth > 0:
        pros.append("positives Gewinnwachstum")

    if profit_margin is not None and profit_margin > 0:
        pros.append("positive Gewinnmarge")

    if free_cashflow is not None and free_cashflow > 0:
        pros.append("positiver Free Cashflow")

    if peg_ratio is not None and peg_ratio > 0 and peg_ratio <= 2:
        pros.append("PEG Ratio attraktiv")

    if fundamental_pros:
        pros.append(fundamental_pros)

    # ----------------------------
    # CONTRA ARGUMENTE
    # ----------------------------

    if score is not None and score <= 3:
        cons.append("schwacher technischer Score")

    if rating == "AVOID":
        cons.append("negatives Rating")

    if risk_level == "HIGH RISK":
        cons.append("hohes Risiko")

    if rsi is not None and rsi > 70:
        cons.append("RSI überkauft")

    if rsi is not None and rsi < 30:
        cons.append("RSI sehr schwach")

    if price is not None and ema50 is not None and price < ema50:
        cons.append("Kurs unter EMA50")

    if price is not None and ema100 is not None and price < ema100:
        cons.append("Kurs unter EMA100")

    if perf_1m is not None and perf_1m < 0:
        cons.append("negative 1M-Performance")

    if perf_3m is not None and perf_3m < 0:
        cons.append("negative 3M-Performance")

    if crv is not None and crv < 1.2:
        cons.append("CRV zu schwach")

    if price is not None and ema20 is not None and price > ema20 * 1.12:
        cons.append("Kurs weit über EMA20")

    if not has_fundamental_data:
        cons.append("Fundamentaldaten unvollständig")

    if fundamental_weak:
        cons.append("schwacher Fundamental-Score")

    if forward_pe is not None and forward_pe > 35:
        cons.append("Forward KGV hoch")

    if trailing_pe is not None and trailing_pe > 40:
        cons.append("KGV hoch")

    if peg_ratio is not None and peg_ratio > 2.5:
        cons.append("PEG Ratio hoch")

    if revenue_growth is not None and revenue_growth < 0:
        cons.append("negatives Umsatzwachstum")

    if earnings_growth is not None and earnings_growth < 0:
        cons.append("negatives Gewinnwachstum")

    if profit_margin is not None and profit_margin < 0:
        cons.append("negative Gewinnmarge")

    if debt_to_equity is not None and debt_to_equity > 200:
        cons.append("hohe Verschuldung")

    if free_cashflow is not None and free_cashflow < 0:
        cons.append("negativer Free Cashflow")

    if fundamental_cons:
        cons.append(fundamental_cons)

    # Duplikate entfernen, damit Pro/Contra nicht unnötig lang wird.
    pros = unique_items(pros)
    cons = unique_items(cons)

    # ----------------------------
    # ACTION SIGNAL
    # ----------------------------

    if strategy_mode == "Kurzfristig":

        if (
            score is not None
            and score >= 6
            and rating in ["BUY", "STRONG BUY"]
            and risk_level != "HIGH RISK"
            and rsi is not None
            and 42 <= rsi <= 68
            and perf_1m is not None
            and perf_1m > 0
            and price is not None
            and ema20 is not None
            and price > ema20
            and crv is not None
            and crv >= 1.4
        ):

            action_signal = "🟢 BUY ZONE"
            setup_quality = "Kurzfristig stark"
            action_sort = 1
            decision_summary = (
                "Kurzfristige Kaufzone möglich – Momentum, EMA20, RSI "
                "und ein realistisches CRV sprechen für ein aktives Setup."
            )

        elif (
            rsi is not None
            and rsi > 72
            and perf_1m is not None
            and perf_1m > 8
        ):

            action_signal = "🟠 TAKE PROFIT"
            setup_quality = "Kurzfristig überhitzt"
            action_sort = 4
            decision_summary = (
                "Kurzfristig heiß gelaufen. Gewinnmitnahme, engerer Stop "
                "oder Rücksetzer beobachten."
            )

        elif turnaround == "YES":

            action_signal = "🔵 TURNAROUND WATCH"
            setup_quality = "Kurzfristig spekulativ"
            action_sort = 3
            decision_summary = (
                "Kurzfristige Trendwende möglich, aber Bestätigung abwarten."
            )

        elif (
            rating == "AVOID"
            or (score is not None and score <= 3)
            or (
                risk_level == "HIGH RISK"
                and perf_1m is not None
                and perf_1m < 0
            )
            or (
                price is not None
                and ema50 is not None
                and price < ema50
                and perf_1m is not None
                and perf_1m < 0
            )
        ):

            action_signal = "🔴 SELL / AVOID"
            setup_quality = "Kurzfristig schwach"
            action_sort = 5
            decision_summary = (
                "Kurzfristig schwaches Setup oder erhöhtes Risiko. "
                "Aktuell eher meiden."
            )

        else:

            action_signal = "🟡 WATCH"
            setup_quality = "Kurzfristig neutral"
            action_sort = 2
            decision_summary = (
                "Kurzfristig interessant, aber noch kein sauberes Einstiegssignal."
            )

    elif strategy_mode == "Langfristig":

        long_fundamental_buy = (
            has_fundamental_data
            and fundamental_score is not None
            and fundamental_score >= 6
            and fundamental_rating in ["SOLID", "VERY SOLID"]
        )

        long_quality_ok = (
            (free_cashflow is None or free_cashflow > 0)
            and (profit_margin is None or profit_margin > 0)
            and (revenue_growth is None or revenue_growth >= 0)
            and (debt_to_equity is None or debt_to_equity <= 200)
        )

        long_trend_ok = (
            price is None
            or ema100 is None
            or price >= ema100
            or (score is not None and score >= 5)
        )

        if (
            long_fundamental_buy
            and long_quality_ok
            and long_trend_ok
            and risk_level != "HIGH RISK"
            and (rsi is None or rsi < 78)
        ):

            action_signal = "🟢 BUY ZONE"
            setup_quality = "Langfristig solide"
            action_sort = 1
            decision_summary = (
                "Langfristige Kaufzone möglich – Fundamentaldaten, Qualität "
                "und Langfristtrend wirken ausreichend solide."
            )

        elif (
            rsi is not None
            and rsi > 78
            and perf_1m is not None
            and perf_1m > 12
        ):

            action_signal = "🟠 OVERHEATED"
            setup_quality = "Langfristig heiß"
            action_sort = 4
            decision_summary = (
                "Langfristig nicht zwingend schlecht, aber kurzfristig stark "
                "überhitzt. Rücksetzer abwarten oder Position enger überwachen."
            )

        elif (
            turnaround == "YES"
            and (
                not has_fundamental_data
                or (
                    fundamental_score is not None
                    and fundamental_score >= 4
                )
            )
        ):

            action_signal = "🔵 TURNAROUND WATCH"
            setup_quality = "Langfristig spekulativ"
            action_sort = 3
            decision_summary = (
                "Trendwende möglich. Für langfristige Käufe erst weitere "
                "Bestätigung und stabile Fundamentaldaten abwarten."
            )

        elif (
            fundamental_weak
            or (
                rating == "AVOID"
                and score is not None
                and score <= 3
            )
            or (
                risk_level == "HIGH RISK"
                and perf_6m is not None
                and perf_6m < 0
            )
        ):

            action_signal = "🔴 SELL / AVOID"
            setup_quality = "Langfristig schwach"
            action_sort = 5
            decision_summary = (
                "Langfristig schwach oder zu unsicher – Fundamentaldaten, "
                "Trend oder Risiko sprechen aktuell dagegen."
            )

        else:

            action_signal = "🟡 WATCH"
            setup_quality = "Langfristig beobachten"
            action_sort = 2
            decision_summary = (
                "Langfristig interessant, aber Qualität, Bewertung oder "
                "Trend liefern noch kein klares Kaufsetup."
            )

    else:

        if (
            score is not None
            and score >= 6
            and rating in ["BUY", "STRONG BUY"]
            and risk_level != "HIGH RISK"
            and rsi is not None
            and 40 <= rsi <= 70
            and crv is not None
            and crv >= 1.5
            and fundamental_ok
        ):

            action_signal = "🟢 BUY ZONE"
            setup_quality = "Sehr gut"
            action_sort = 1
            decision_summary = (
                "Kaufzone möglich – starkes technisches Setup, "
                "Risiko vertretbar, CRV realistisch attraktiv und Fundamentaldaten ausreichend solide."
            )

        elif (
            rsi is not None
            and rsi > 72
            and perf_1m is not None
            and perf_1m > 8
        ):

            action_signal = "🟠 TAKE PROFIT"
            setup_quality = "Überhitzt"
            action_sort = 4
            decision_summary = (
                "Aktie ist stark gelaufen. Gewinnmitnahme oder "
                "Rücksetzer beobachten."
            )

        elif turnaround == "YES":

            action_signal = "🔵 TURNAROUND WATCH"
            setup_quality = "Spekulativ"
            action_sort = 3
            decision_summary = (
                "Mögliche Trendwende sichtbar, aber Bestätigung abwarten."
            )

        elif (
            rating == "AVOID"
            or (score is not None and score <= 3)
            or fundamental_weak
            or (
                risk_level == "HIGH RISK"
                and perf_1m is not None
                and perf_1m < 0
            )
        ):

            action_signal = "🔴 SELL / AVOID"
            setup_quality = "Schwach"
            action_sort = 5
            decision_summary = (
                "Schwaches Setup oder erhöhtes Risiko. Aktuell eher meiden."
            )

        else:

            action_signal = "🟡 WATCH"
            setup_quality = "Neutral"
            action_sort = 2
            decision_summary = (
                "Interessant, aber noch kein klares Kaufsetup."
            )

    # ----------------------------
    # FORMATIERUNG
    # ----------------------------

    if entry_low is not None and entry_high is not None:
        entry_zone = f"{entry_low:.2f} - {entry_high:.2f}"
    else:
        entry_zone = "-"

    return pd.Series({
        "Action Signal": action_signal,
        "Strategy Mode": strategy_mode,
        "Action Sort": action_sort,
        "Entry Zone": entry_zone,
        "Stop Loss New": format_number(stop_loss),
        "Target 1": format_number(target_1),
        "Target 2": format_number(target_2),
        "Target Basis": target_basis,
        "CRV": round(crv, 2) if crv is not None else "-",
        "Setup Quality": setup_quality,
        "Pros": " | ".join(pros) if pros else "-",
        "Cons": " | ".join(cons) if cons else "-",
        "Decision Summary": decision_summary
    })


decision_columns = df.apply(
    build_decision_data,
    axis=1
)

df = pd.concat(
    [df, decision_columns],
    axis=1
)

# ============================================================
# TITEL
# ============================================================

st.title("📊 Hartmuts Dashboard")

st.write(
    "Aktienanalyse mit Momentum, RSI, EMA, "
    "Turnaround-Erkennung, Risiko, Dividenden und Strategie-Horizont."
)


# ============================================================
# LEGENDE
# ============================================================

with st.expander("📖 Dashboard Legende"):

    st.markdown("""

    ## ⭐ Ratings

    - **STRONG BUY** → sehr starke technische Struktur
    - **BUY** → bullish
    - **HOLD** → neutral
    - **TURNAROUND** → mögliche Trendwende
    - **WATCH - OVERBOUGHT** → stark gelaufen, Rücksetzer möglich
    - **AVOID** → schwache technische Lage

    ---

    ## 🕒 Strategie-Horizont

    Über den Sidebar-Schalter **Strategie-Horizont** kannst du die Bewertung umstellen:

    - **Kurzfristig** → Fokus auf EMA20, RSI, 1M-Momentum, kurzfristigen Stop und CRV. Geeignet für aktive Einstiege oder Swing-Ideen.
    - **Mittelfristig** → Mischung aus technischem Score, Risiko, RSI, CRV und Fundamentaldaten. Das ist der Standardmodus.
    - **Langfristig** → Fokus auf Fundamental Score, Cashflow, Marge, Wachstum, Verschuldung und EMA100/Langfristtrend.

    Dadurch kann dieselbe Aktie je nach Zeithorizont ein anderes Signal bekommen.

    ---

    ## 🎯 Action Signale

    Die Action Signale sind eine regelbasierte Entscheidungshilfe. Sie ersetzen keine eigene Prüfung, zeigen aber klar, warum eine Aktie gerade interessant, riskant oder überhitzt wirkt.

    ### 🟢 BUY ZONE

    **Kurzfristig:**

    - Score mindestens **6 von 8**
    - Rating **BUY** oder **STRONG BUY**
    - Risk Level nicht **HIGH RISK**
    - RSI zwischen **42 und 68**
    - 1M Performance positiv
    - Kurs über EMA20
    - realistisches CRV mindestens **1,4**

    **Mittelfristig:**

    - Score mindestens **6 von 8**
    - Rating **BUY** oder **STRONG BUY**
    - Risk Level nicht **HIGH RISK**
    - RSI zwischen **40 und 70**
    - realistisches CRV mindestens **1,5**
    - Fundamental Score mindestens **5** oder Fundamentaldaten sind nicht vollständig verfügbar

    **Langfristig:**

    - Fundamental Score mindestens **6 von 8**
    - Fundamental Rating **SOLID** oder **VERY SOLID**
    - Free Cashflow, Marge und Umsatzwachstum nicht klar negativ
    - Debt/Equity nicht extrem hoch
    - Langfristtrend okay, z. B. Kurs über EMA100 oder Score mindestens 5
    - Risk Level nicht **HIGH RISK**
    - RSI nicht extrem überhitzt

    ---

    ### 🟡 WATCH

    **WATCH** bedeutet: Die Aktie ist interessant, aber mindestens ein wichtiger Punkt fehlt noch. Typische Gründe sind ein zu schwaches CRV, ein zu hoher RSI, gemischte Fundamentaldaten oder ein noch nicht bestätigter Trend.

    ---

    ### 🔵 TURNAROUND WATCH

    Eine Aktie bekommt **TURNAROUND WATCH**, wenn sie als Turnaround-Kandidat erkannt wurde:

    - 6M Performance unter **-15 %**
    - 1M Performance über **+5 %**
    - Kurs zurück über EMA20
    - RSI über 40

    Bedeutung: Erste Trendwende möglich, aber spekulativer als BUY ZONE.

    ---

    ### 🟠 TAKE PROFIT / OVERHEATED

    **TAKE PROFIT** erscheint im kurz- oder mittelfristigen Modus, wenn die Aktie kurzfristig heiß gelaufen ist:

    - RSI über **72**
    - 1M Performance über **+8 %**

    Im langfristigen Modus heißt das Signal **OVERHEATED**, weil eine starke Aktie langfristig nicht automatisch verkauft werden muss, nur weil sie kurzfristig überhitzt ist.

    ---

    ### 🔴 SELL / AVOID

    Eine Aktie bekommt **SELL / AVOID**, wenn klare Warnsignale vorliegen:

    - Rating **AVOID**
    - Score **3 oder niedriger**
    - wirklich schwacher Fundamental Score, nicht nur fehlende Daten
    - HIGH RISK plus negative Performance

    ---

    ## ⚖️ CRV / Chance-Risiko-Verhältnis

    Das CRV wird jetzt nicht mehr künstlich aus dem Stop-Loss erzeugt. Ziel 1 basiert bevorzugt auf dem **52-Wochen-Hoch**, sofern dieses sinnvoll über dem aktuellen Kurs liegt. Falls kein brauchbares 52W-Ziel vorhanden ist, nutzt das Dashboard einen vorsichtigen Fallback je nach Zeithorizont.

    - **Kurzfristig:** Stop näher am EMA20
    - **Mittelfristig:** Stop am EMA50
    - **Langfristig:** Stop stärker am EMA100 orientiert

    Dadurch ist das CRV realistischer als vorher.

    ---

    ## 📈 Score System

    Jede Aktie bekommt Punkte für:

    - Kurs über EMA20
    - Kurs über EMA50
    - Kurs über EMA100
    - EMA20 > EMA50
    - EMA50 > EMA100
    - positive Wochenperformance
    - positive Monatsperformance
    - gesunder RSI

    Maximaler Score: **8**

    ---

    ## 📉 RSI

    RSI = Relative Strength Index

    - unter 30 → überverkauft
    - 30–70 → gesund
    - über 70 → heiß gelaufen

    ---

    ## 🔄 Turnaround Kandidat

    Eine Aktie gilt als Turnaround-Kandidat, wenn sie zuvor stark gefallen ist, aber Momentum zurückkommt, der Kurs EMA20 zurückerobert und der RSI sich stabilisiert.

    ---

    ## ⚠ Risk Level

    Risiko basiert auf RSI, Volatilität, Abstand zum EMA20 und Beta.

    ---

    ## 🛑 Stop-Loss-Idee

    Vorschlag basierend auf den gleitenden Durchschnitten. Kein Finanzrat, nur technische Orientierung.

    ---

    ## 📅 Dividendenkalender

    Der Dividendenkalender filtert nach dem Ex-Dividenden-Datum. In der Übersicht und Gesamttabelle bleiben trotzdem alle Aktien sichtbar.

    """)


# ============================================================
# SIDEBAR FILTER
# ============================================================

st.sidebar.header("Filter")

search_text = st.sidebar.text_input(
    "🔎 Aktie suchen",
    ""
)

stock_options = (
    df["Ticker"].astype(str)
    + " - "
    + df["Company"].astype(str)
).sort_values().tolist()

selected_stocks = st.sidebar.multiselect(
    "Aktien auswählen",
    options=stock_options,
    default=[]
)

ratings = st.sidebar.multiselect(
    "Ratings",
    options=df["Rating"].unique(),
    default=df["Rating"].unique()
)

risk_levels = st.sidebar.multiselect(
    "Risk Level",
    options=df["Risk Level"].unique(),
    default=df["Risk Level"].unique()
)

action_signal_options = (
    df[["Action Signal", "Action Sort"]]
    .drop_duplicates()
    .sort_values("Action Sort")["Action Signal"]
    .tolist()
)

action_signals = st.sidebar.multiselect(
    "Action Signal",
    options=action_signal_options,
    default=action_signal_options
)

turnaround_only = st.sidebar.checkbox(
    "Nur Turnaround Kandidaten"
)

sort_option = st.sidebar.selectbox(
    "Sortieren nach",
    [
        "Action Signal",
        "Score",
        "Fundamental Score",
        "CRV",
        "1M %",
        "6M %",
        "RSI",
        "Dividend Yield %",
        "Risk Level"
    ]
)


# ============================================================
# DIVIDENDENKALENDER FILTER
# ============================================================

st.sidebar.subheader("📅 Dividendenkalender")

dividend_years = sorted(
    df.loc[df["Dividend Year"] >= 2026, "Dividend Year"]
    .dropna()
    .astype(int)
    .unique()
)

selected_year = st.sidebar.selectbox(
    "Jahr",
    options=["Alle"] + dividend_years
)

months = {
    "Alle": None,
    "Januar": 1,
    "Februar": 2,
    "März": 3,
    "April": 4,
    "Mai": 5,
    "Juni": 6,
    "Juli": 7,
    "August": 8,
    "September": 9,
    "Oktober": 10,
    "November": 11,
    "Dezember": 12,
}

selected_month_name = st.sidebar.selectbox(
    "Monat",
    options=list(months.keys())
)

selected_month = months[selected_month_name]


# ============================================================
# FILTER
# ============================================================

df_filtered = df[
    (df["Rating"].isin(ratings))
    &
    (df["Risk Level"].isin(risk_levels))
    &
    (df["Action Signal"].isin(action_signals))
].copy()

if search_text != "":

    df_filtered = df_filtered[
        df_filtered["Company"]
        .str.contains(
            search_text,
            case=False,
            na=False
        )
        |
        df_filtered["Ticker"]
        .str.contains(
            search_text,
            case=False,
            na=False
        )
    ]

if selected_stocks:

    selected_tickers = [
        item.split(" - ")[0]
        for item in selected_stocks
    ]

    df_filtered = df_filtered[
        df_filtered["Ticker"].isin(selected_tickers)
    ]

if turnaround_only:

    df_filtered = df_filtered[
        df_filtered["Turnaround Candidate"] == "YES"
    ]

# Hinweis:
# Jahr und Monat filtern bewusst NICHT df_filtered.
# Dadurch bleiben alle Aktien in Gesamttabelle und Aktienübersicht sichtbar.
# Die Kalenderfilter werden nur unten im Dividendenkalender angewendet.


# ============================================================
# SORTIERUNG
# ============================================================

if sort_option in df_filtered.columns:

    if sort_option == "Action Signal":

        df_filtered = df_filtered.sort_values(
            by="Action Sort",
            ascending=True
        )

    elif sort_option == "Risk Level":

        risk_order = {
            "LOW RISK": 1,
            "MEDIUM RISK": 2,
            "HIGH RISK": 3
        }

        df_filtered["Risk Sort"] = (
            df_filtered["Risk Level"]
            .map(risk_order)
            .fillna(99)
        )

        df_filtered = df_filtered.sort_values(
            by="Risk Sort",
            ascending=True
        )

    elif sort_option == "CRV":

        df_filtered["CRV Numeric"] = pd.to_numeric(
            df_filtered["CRV"],
            errors="coerce"
        ).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="CRV Numeric",
            ascending=False
        )

    elif sort_option == "Dividend Yield %":

        df_filtered["Dividend Yield Numeric"] = pd.to_numeric(
            df_filtered["Dividend Yield %"]
            .astype(str)
            .str.replace("%", "", regex=False)
            .replace("-", "0"),
            errors="coerce"
        ).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="Dividend Yield Numeric",
            ascending=False
        )

    else:

        df_filtered = df_filtered.sort_values(
            by=sort_option,
            ascending=False
        )


# ============================================================
# METRICS
# ============================================================

st.divider()

col1, col2, col3, col4, col5, col6 = st.columns(6)

col1.metric(
    "Aktien",
    len(df_filtered)
)

col2.metric(
    "Ø Score",
    round(df_filtered["Score"].mean(), 2)
    if len(df_filtered) > 0 else 0
)

col3.metric(
    "Beste 1M %",
    f"{round(df_filtered['1M %'].max(), 2)}%"
    if len(df_filtered) > 0 else "0%"
)

col4.metric(
    "Turnaround",
    (
        df_filtered["Turnaround Candidate"]
        == "YES"
    ).sum()
)

col5.metric(
    "Strong Buy",
    (
        df_filtered["Rating"]
        == "STRONG BUY"
    ).sum()
)

col6.metric(
    "Ø Fundamental",
    round(df_filtered["Fundamental Score"].mean(), 2)
    if len(df_filtered) > 0 else 0
)


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def get_border_color(rating):

    if rating == "STRONG BUY":
        return "#16a34a"

    if rating == "BUY":
        return "#22c55e"

    if rating == "TURNAROUND":
        return "#2563eb"

    if rating == "WATCH - OVERBOUGHT":
        return "#f59e0b"

    if rating == "HOLD":
        return "#9ca3af"

    if rating == "AVOID":
        return "#dc2626"

    return "#6b7280"


def get_rating_light(rating):

    if rating == "STRONG BUY":
        return "🟢"

    if rating == "BUY":
        return "🟢"

    if rating == "TURNAROUND":
        return "🔵"

    if rating == "WATCH - OVERBOUGHT":
        return "🟡"

    if rating == "HOLD":
        return "🟡"

    return "🔴"


def get_risk_light(risk):

    if risk == "LOW RISK":
        return "🟢"

    if risk == "MEDIUM RISK":
        return "🟡"

    if risk == "HIGH RISK":
        return "🔴"

    return "⚪"


# ============================================================
# DIVIDENDENKALENDER
# ============================================================

st.divider()

st.subheader("📅 Dividendenkalender")

dividend_calendar = df_filtered[
    (df_filtered["Ex Dividend Parsed"].notna())
    &
    (df_filtered["Dividend Year"] >= 2026)
]

if selected_year != "Alle":

    dividend_calendar = dividend_calendar[
        dividend_calendar["Dividend Year"] == selected_year
    ]

if selected_month is not None:

    dividend_calendar = dividend_calendar[
        dividend_calendar["Dividend Month"] == selected_month
    ]

dividend_calendar = dividend_calendar.sort_values(
    by="Ex Dividend Parsed",
    ascending=True
)[
    [
        "Ticker",
        "Company",
        "Dividend Yield %",
        "Dividend Rate",
        "Ex Dividend Date",
        "Price",
        "Rating",
        "Score",
        "Fundamental Score",
        "Fundamental Rating",
        "Action Signal",
        "Strategy Mode",
        "CRV",
        "Target Basis"
    ]
]

st.dataframe(
    dividend_calendar,
    width="stretch"
)


# ============================================================
# TABELLE
# ============================================================

st.divider()

st.subheader("📋 Gesamttabelle")

# Action Signal bewusst direkt nach Ticker und Company anzeigen,
# damit die Entscheidungseinschätzung in der Gesamtliste sofort sichtbar ist.
priority_columns = [
    "Ticker",
    "Company",
    "Action Signal",
    "Strategy Mode"
]

remaining_columns = [
    column for column in df_filtered.columns
    if column not in priority_columns
]

table_columns = [
    column for column in priority_columns
    if column in df_filtered.columns
] + remaining_columns

st.dataframe(
    df_filtered[table_columns],
    width="stretch"
)


# ============================================================
# AKTIENKARTEN
# ============================================================

st.divider()

st.subheader("🔥 Aktienübersicht")

for _, row in df_filtered.iterrows():

    color = get_border_color(row["Rating"])
    rating_light = get_rating_light(row["Rating"])
    risk_light = get_risk_light(row["Risk Level"])

    card_html = f"""
<div style="background-color:#ffffff; padding:24px 26px; border-radius:22px; margin-bottom:26px; border-left:13px solid {color}; box-shadow:0 4px 14px rgba(0,0,0,0.10); font-family:Arial, sans-serif; color:#111827; line-height:1.55; overflow-wrap:break-word; word-break:break-word;">
<h2 style="margin:0 0 16px 0; font-size:27px; font-weight:800;">{row['Ticker']} - {row['Company']}</h2>
<hr style="border:none; border-top:2px solid #9ca3af; margin:0 0 20px 0;">

<p style="font-size:18px; margin:0 0 18px 0;">💰 <b>Preis:</b> {row['Price']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">⭐ <b>Rating:</b> {rating_light} {row['Rating']} | 📈 <b>Score:</b> {row['Score']} | ⚠️ <b>Risiko:</b> {risk_light} {row['Risk Level']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">🎯 <b>Signal:</b> {row['Action Signal']} | 🧭 <b>Setup:</b> {row['Setup Quality']} | 🕒 <b>Horizont:</b> {row['Strategy Mode']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">📍 <b>Einstiegszone:</b> {row['Entry Zone']} | 🛑 <b>Stop:</b> {row['Stop Loss New']} | 🎯 <b>Ziel 1:</b> {row['Target 1']} | 🚀 <b>Ziel 2:</b> {row['Target 2']} | ⚖️ <b>CRV:</b> {row['CRV']} | 🧱 <b>Zielbasis:</b> {row['Target Basis']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">📊 <b>Performance:</b><br>1D: {row['1D %']}% | 1W: {row['1W %']}% | 1M: {row['1M %']}% | 3M: {row['3M %']}% | 6M: {row['6M %']}%</p>

<p style="font-size:18px; margin:0 0 18px 0;">📉 <b>EMA:</b><br>EMA20: {row['EMA20']} | EMA50: {row['EMA50']} | EMA100: {row['EMA100']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">💵 <b>Dividende:</b> {row['Dividend Yield %']} | 📅 <b>Ex-Dividende:</b> {row['Ex Dividend Date']} | 🪙 <b>Dividendensatz:</b> {row['Dividend Rate']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">🛑 <b>Stop-Loss-Idee:</b> {row['Stop Loss Idea']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">🏢 <b>Market Cap:</b> {row['Market Cap Class']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">🧾 <b>Fundamental:</b> {row['Fundamental Rating']} | 📊 <b>Fundamental Score:</b> {row['Fundamental Score']}/8</p>

<p style="font-size:18px; margin:0 0 18px 0;">🏦 <b>Bewertung:</b><br>Forward KGV: {row['Forward PE']} | KGV: {row['Trailing PE']} | PEG: {row['PEG Ratio']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">📈 <b>Fundamentales Wachstum:</b><br>Umsatzwachstum: {row['Revenue Growth']} | Gewinnwachstum: {row['Earnings Growth']} | Marge: {row['Profit Margin']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">💸 <b>Cashflow / Verschuldung:</b><br>Free Cashflow: {row['Free Cashflow']} | Operating Cashflow: {row['Operating Cashflow']} | Debt/Equity: {row['Debt To Equity']}</p>

<p style="font-size:18px; margin:0 0 18px 0;">🔄 <b>Turnaround:</b> {row['Turnaround Candidate']}</p>

<div style="font-size:17px; margin:8px 0 14px 0; background:#ecfdf5; padding:12px 14px; border-radius:12px;">✅ <b>Pro:</b> {row['Pros']}</div>

<div style="font-size:17px; margin:8px 0 14px 0; background:#fff7ed; padding:12px 14px; border-radius:12px;">⚠️ <b>Contra:</b> {row['Cons']}</div>

<div style="font-size:17px; margin:8px 0 14px 0; background:#eef2ff; padding:12px 14px; border-radius:12px;">🧭 <b>Entscheidung:</b> {row['Decision Summary']}</div>

<div style="font-size:17px; margin:8px 0 0 0; background:#f3f4f6; padding:12px 14px; border-radius:12px;">🧠 <b>Analyse:</b> {row['Reason']}</div>
</div>
"""

    st.markdown(card_html, unsafe_allow_html=True)
