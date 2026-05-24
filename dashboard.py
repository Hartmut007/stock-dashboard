import pandas as pd
import streamlit as st
import os
import subprocess
import hmac
from datetime import datetime
from supabase import create_client, Client
import streamlit.components.v1 as components

# Optional: PyVis bleibt kompatibel, das neue Netzwerk nutzt aber ein eigenes statisches HTML/SVG.
try:
    from pyvis.network import Network
    import tempfile
    PYVIS_AVAILABLE = True
except Exception:
    PYVIS_AVAILABLE = False

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Portfolio Dashboard",
    layout="wide"
)

# ============================================================
# 🎨 PROFI-DESIGN / TERMINAL LOOK
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2.5rem;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(15,23,42,0.98), rgba(30,41,59,0.94));
        border: 1px solid rgba(148,163,184,0.28);
        border-radius: 18px;
        padding: 14px 16px;
        box-shadow: 0 12px 28px rgba(15,23,42,0.14);
    }
    div[data-testid="stMetric"] label {
        color: #cbd5e1 !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-weight: 800;
    }
    .terminal-panel {
        background: radial-gradient(circle at top left, rgba(59,130,246,0.28), transparent 28%),
                    linear-gradient(135deg, #020617 0%, #0f172a 52%, #111827 100%);
        border: 1px solid rgba(56,189,248,0.32);
        border-radius: 24px;
        padding: 22px 24px;
        margin: 12px 0 18px 0;
        box-shadow: 0 20px 50px rgba(2,6,23,0.36);
        color: #e5e7eb;
    }
    .terminal-panel h3 {
        margin: 0 0 8px 0;
        color: #f8fafc;
        font-size: 1.35rem;
    }
    .terminal-panel p {
        margin: 0;
        color: #cbd5e1;
    }
    .terminal-chip {
        display: inline-block;
        padding: 6px 10px;
        margin: 8px 6px 0 0;
        border-radius: 999px;
        background: rgba(15,23,42,0.72);
        border: 1px solid rgba(148,163,184,0.28);
        color: #e5e7eb;
        font-size: 0.82rem;
        font-weight: 700;
    }
    .legend-dot {
        display:inline-block;
        width:10px;
        height:10px;
        border-radius:50%;
        margin-right:6px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


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
# 💾 PERSÖNLICHE WATCHLIST / KAUFLIST IN SUPABASE SPEICHERN
# ============================================================

USER_LIST_COLUMNS = [
    "username",
    "list_type",
    "ticker",
    "name",
    "created_at"
]

SUPABASE_TABLE = "user_stock_lists"


@st.cache_resource
def get_supabase_client() -> Client:
    """Erstellt eine Supabase-Verbindung aus Streamlit Secrets."""

    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]

    return create_client(
        supabase_url,
        supabase_key
    )


def load_user_lists():
    """Lädt gespeicherte Watchlist- und Kauflisten aus Supabase."""

    try:
        supabase = get_supabase_client()

        response = (
            supabase
            .table(SUPABASE_TABLE)
            .select("username,list_type,ticker,name,created_at")
            .execute()
        )

        data = pd.DataFrame(response.data)

        if data.empty:
            data = pd.DataFrame(columns=USER_LIST_COLUMNS)

    except Exception as error:
        st.error(f"Supabase-Daten konnten nicht geladen werden: {error}")
        data = pd.DataFrame(columns=USER_LIST_COLUMNS)

    for column in USER_LIST_COLUMNS:
        if column not in data.columns:
            data[column] = ""

    return data[USER_LIST_COLUMNS]


def get_saved_tickers(username, list_type):
    """Gibt gespeicherte Ticker eines Nutzers für eine Liste zurück."""

    data = load_user_lists()

    user_data = data[
        (data["username"].astype(str) == str(username))
        &
        (data["list_type"].astype(str) == str(list_type))
    ]

    return user_data["ticker"].dropna().astype(str).tolist()


def update_user_list(username, list_type, selected_tickers, stock_df):
    """Aktualisiert eine Liste für einen Nutzer in Supabase."""

    try:
        supabase = get_supabase_client()

        # Alte Einträge dieses Nutzers für diese Liste löschen.
        # Danach wird die aktuelle Auswahl neu eingefügt.
        (
            supabase
            .table(SUPABASE_TABLE)
            .delete()
            .eq("username", username)
            .eq("list_type", list_type)
            .execute()
        )

        new_rows = []

        for ticker in selected_tickers:
            ticker = str(ticker).strip()

            stock_row = stock_df[
                stock_df["Ticker"].astype(str).str.strip() == ticker
            ]

            if not stock_row.empty:
                name = stock_row.iloc[0].get("Company", ticker)
            else:
                name = ticker

            new_rows.append({
                "username": username,
                "list_type": list_type,
                "ticker": ticker,
                "name": str(name),
                "created_at": datetime.now().isoformat()
            })

        if new_rows:
            (
                supabase
                .table(SUPABASE_TABLE)
                .insert(new_rows)
                .execute()
            )

    except Exception as error:
        st.error(f"Supabase-Daten konnten nicht gespeichert werden: {error}")

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
# STREAMLIT-TABELLENKOMPATIBILITÄT
# ============================================================

# Streamlit/PyArrow kann bei st.dataframe Probleme bekommen,
# wenn eine Spalte gemischt aus Zahlen und Text wie "-" besteht.
# Deshalb werden reine Anzeige-Spalten hier bewusst als Text behandelt.
display_text_columns = [
    "CRV",
    "Entry Zone",
    "Stop Loss New",
    "Target 1",
    "Target 2",
    "Price",
    "Dividend Yield %",
    "Dividend Rate",
    "Forward PE",
    "Trailing PE",
    "PEG Ratio",
    "Revenue Growth",
    "Earnings Growth",
    "Profit Margin",
    "Debt To Equity",
    "Free Cashflow",
    "Operating Cashflow"
]

for column in display_text_columns:
    if column in df.columns:
        df[column] = df[column].astype(str)

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
# 🍕 PIZZINT / GEOPOLITISCHER STRESS-INDIKATOR
# ============================================================

with st.expander("🍕 PizzINT / Geopolitischer Stress-Indikator", expanded=False):
    st.divider()

    st.subheader("🍕 PizzINT / Geopolitischer Stress-Indikator")

    st.caption(
        "Experimenteller OSINT-Indikator. Die Daten dienen nur als zusätzlicher "
        "Stimmungs- und Risiko-Hinweis und ersetzen keine Marktanalyse."
    )

    # Manuelle Einschätzung, kann später automatisiert werden.
    doughcon_level = st.selectbox(
        "DOUGHCON-Level einschätzen",
        options=[
            "1 - Ruhig",
            "2 - Beobachten",
            "3 - Erhöhte Aufmerksamkeit",
            "4 - Hoher Stress",
            "5 - Krisenmodus"
        ],
        index=2
    )

    if doughcon_level.startswith("1"):
        stress_label = "🟢 Niedrig"
        market_view = (
            "Normales Marktumfeld. Fokus bleibt auf technischen Signalen, "
            "Bewertungen und Trendstruktur."
        )
        focus_assets = "Qualitätsaktien, Tech, Dividendenwerte, breite Indizes"
    elif doughcon_level.startswith("2"):
        stress_label = "🟡 Leicht erhöht"
        market_view = (
            "Etwas mehr Vorsicht. Watchlist enger beobachten, "
            "aber keine Paniksignale."
        )
        focus_assets = "Qualitätsaktien, Cash-Reserve, defensive Werte"
    elif doughcon_level.startswith("3"):
        stress_label = "🟠 Erhöht"
        market_view = (
            "Geopolitische Risiken könnten stärker eingepreist werden. "
            "Turnaround- und High-Risk-Aktien vorsichtiger behandeln."
        )
        focus_assets = "Energie, Gold, Rüstung, Cybersecurity, defensive Aktien"
    elif doughcon_level.startswith("4"):
        stress_label = "🔴 Hoch"
        market_view = (
            "Risiko-Modus. Neue Käufe strenger prüfen, Stops enger beobachten, "
            "volatile Titel reduzieren."
        )
        focus_assets = "Gold, Energie, Rüstung, Cash, defensive Dividendenwerte"
    else:
        stress_label = "🚨 Extrem"
        market_view = (
            "Krisenmodus. Kapitalerhalt priorisieren, keine impulsiven Käufe, "
            "Marktreaktionen abwarten."
        )
        focus_assets = "Cash, Gold, kurzfristige Absicherung, defensive Sektoren"

    col_geo1, col_geo2, col_geo3 = st.columns(3)

    with col_geo1:
        st.metric("Geopolitischer Stress", stress_label)

    with col_geo2:
        st.metric("DOUGHCON", doughcon_level.split(" - ")[0])

    with col_geo3:
        st.metric("Marktmodus", "Risk Check")

    st.info(market_view)
    st.caption(f"Aktuell besonders beobachten: {focus_assets}")

    geo_focus_df = pd.DataFrame([
        {
            "Bereich": "Energie",
            "Warum relevant?": "Öl, Gas und Energiepreise reagieren oft sensibel auf geopolitische Spannungen.",
            "Beispiele": "XOM, CVX, SHEL, BP, ENPH"
        },
        {
            "Bereich": "Rüstung / Verteidigung",
            "Warum relevant?": "Verteidigungswerte können bei erhöhter Sicherheitslage stärker beobachtet werden.",
            "Beispiele": "LMT, RTX, NOC, HAG.DE, RHM.DE"
        },
        {
            "Bereich": "Cybersecurity",
            "Warum relevant?": "Cyberrisiken steigen häufig bei geopolitischen Konflikten.",
            "Beispiele": "CRWD, PANW, FTNT, ZS"
        },
        {
            "Bereich": "Gold / Sicherheit",
            "Warum relevant?": "Gold wird oft als sicherer Hafen betrachtet.",
            "Beispiele": "GOLD, NEM, AEM, GLD"
        },
        {
            "Bereich": "High-Risk / Turnaround",
            "Warum relevant?": "Spekulative Aktien können in Stressphasen stärker fallen.",
            "Beispiele": "enger prüfen, Positionsgröße reduzieren"
        }
    ])

    st.markdown("### 🧭 Mögliche Markt-Fokusbereiche")

    st.dataframe(
        geo_focus_df,
        width="stretch",
        hide_index=True
    )

    st.markdown("### 🍕 PizzINT Watch")

    pizza_watch_df = pd.DataFrame([
        {
            "Signal": "Pizza-Aktivität",
            "Interpretation": "Kann als humorvoller OSINT-Stimmungsindikator beobachtet werden.",
            "Relevanz fürs Portfolio": "Nur Zusatzsignal, niemals alleinige Entscheidungsbasis."
        },
        {
            "Signal": "DOUGHCON steigt",
            "Interpretation": "Mehr geopolitische Aufmerksamkeit.",
            "Relevanz fürs Portfolio": "Risk-Management prüfen, defensive Sektoren beobachten."
        },
        {
            "Signal": "DOUGHCON fällt",
            "Interpretation": "Lage wirkt entspannter.",
            "Relevanz fürs Portfolio": "Normale technische und fundamentale Signale stärker gewichten."
        }
    ])

    st.dataframe(
        pizza_watch_df,
        width="stretch",
        hide_index=True
    )

    st.link_button(
        "🍕 PizzINT extern öffnen",
        "https://www.pizzint.watch/"
    )



# ============================================================
# 🕸️ AKTIEN-NETZWERK / THEMEN-MAPPING
# ============================================================

with st.expander("🕸️ Aktien-Netzwerk / Themen-Mapping", expanded=True):
    st.divider()

    st.subheader("🕸️ Aktien-Netzwerk / Themen-Mapping")

    st.markdown(
        """
        <div class="terminal-panel">
            <h3>Market Relationship Terminal</h3>
            <p>Wähle eine Hauptaktie und analysiere Lieferketten, Kunden, Konkurrenz, Energiebedarf, Speicher, Cloud und Risiken als Netzwerk.</p>
            <span class="terminal-chip">Supply Chain</span>
            <span class="terminal-chip">AI / Cloud</span>
            <span class="terminal-chip">Energy / Datacenter</span>
            <span class="terminal-chip">Competition</span>
            <span class="terminal-chip">Risk Radar</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    RELATIONSHIPS_FILE = "stock_relationships.csv"

    def infer_supply_chain_stage(category, relationship):
        """Leitet eine Lieferketten-/Wertschöpfungsstufe aus Kategorie und Beschreibung ab."""

        text_value = f"{category} {relationship}".lower()

        stage_rules = [
            ("1 - Rohstoffe / Energie", ["uran", "öl", "gas", "gold", "lithium", "kupfer", "rohstoff", "energie /", "stromerzeugung", "atomstrom"]),
            ("2 - Energie- & Strominfrastruktur", ["strom", "netz", "elektrifizierung", "energieausrüstung", "strominfrastruktur", "rechenzentrum", "kühlung", "vertiv", "eaton"]),
            ("3 - Produktionsausrüstung", ["lithografie", "chipausrüstung", "equipment", "prozesskontrolle", "maschinen", "fertigungsanlagen"]),
            ("4 - Fertigung / Foundry", ["foundry", "fertigung", "chipfertigung", "tsmc", "samsung foundry"]),
            ("5 - Komponenten / Speicher / Chips", ["speicher", "hbm", "dram", "nand", "gpu", "cpu", "custom chips", "chips", "beschleuniger", "netzwerk / custom"]),
            ("6 - Server / Netzwerk / Infrastruktur", ["server", "netzwerk", "interconnect", "datacenter", "dateninfrastruktur", "ki-infrastruktur"]),
            ("7 - Plattform / Cloud / Software", ["cloud", "hyperscaler", "azure", "aws", "google cloud", "oracle", "software", "cybersecurity", "identity"]),
            ("8 - Endmarkt / Nachfrage", ["modelle", "nachfrage", "enterprise", "werbung", "automotive", "ev", "pharma", "kunden"]),
            ("9 - Konkurrenz / Substitution", ["konkurrenz", "competition", "substitution", "eigene chips", "tpu", "trainium"]),
            ("10 - Risiko / Geopolitik / Defense", ["verteidigung", "defense", "geopolitik", "drohnen", "sensorik", "sicherheit"]),
        ]

        for stage, keywords in stage_rules:
            if any(keyword in text_value for keyword in keywords):
                return stage

        return "99 - Sonstige Verbindung"

    def infer_connection_type(category, relationship, risk_note):
        """Leitet die Art der Verbindung ab: Lieferant, Kunde, Konkurrenz, Infrastruktur usw."""

        text_value = f"{category} {relationship} {risk_note}".lower()

        if any(word in text_value for word in ["konkurrenz", "konkurriert", "competition", "substitution", "eigene chips", "tpu", "trainium"]):
            return "Konkurrenz / Substitution"
        if any(word in text_value for word in ["liefert", "anbieter", "zuliefer", "fertigt", "maschinen", "anlagen", "speicher", "hbm"]):
            return "Lieferant / Zulieferer"
        if any(word in text_value for word in ["nutzt", "kauft", "nachfrage", "kunde", "cloud", "hyperscaler", "enterprise"]):
            return "Kunde / Nachfrage"
        if any(word in text_value for word in ["strom", "energie", "kühlung", "netz", "rechenzentrum", "infrastruktur"]):
            return "Infrastruktur / Ermöglicher"
        if any(word in text_value for word in ["risiko", "taiwan", "regulierung", "export", "geopolitik", "defense", "verteidigung"]):
            return "Risiko / Makro"

        return "Strategische Verbindung"

    if not os.path.exists(RELATIONSHIPS_FILE):

        st.warning(
            "Die Datei stock_relationships.csv wurde nicht gefunden. "
            "Bitte lege sie in den gleichen Ordner wie dashboard.py."
        )

    else:

        try:
            relationships_df = pd.read_csv(
                RELATIONSHIPS_FILE,
                encoding="utf-8",
                sep=None,
                engine="python"
            )
        except UnicodeDecodeError:
            try:
                relationships_df = pd.read_csv(
                    RELATIONSHIPS_FILE,
                    encoding="latin1",
                    sep=None,
                    engine="python"
                )
            except Exception as error:
                st.error(f"stock_relationships.csv konnte nicht geladen werden: {error}")
                relationships_df = pd.DataFrame()
        except Exception as error:
            st.error(f"stock_relationships.csv konnte nicht geladen werden: {error}")
            relationships_df = pd.DataFrame()

        needed_relationship_columns = [
            "source_ticker",
            "target_ticker",
            "target_name",
            "category",
            "relationship",
            "importance",
            "risk_note"
        ]

        missing_relationship_columns = [
            column for column in needed_relationship_columns
            if column not in relationships_df.columns
        ]

        if relationships_df.empty:

            st.info("Die Datei stock_relationships.csv ist noch leer.")

        elif missing_relationship_columns:

            st.error(
                "In stock_relationships.csv fehlen diese Spalten: "
                + ", ".join(missing_relationship_columns)
            )

        else:

            relationships_df = relationships_df.copy()

            for text_column in [
                "source_ticker",
                "target_ticker",
                "target_name",
                "category",
                "relationship",
                "importance",
                "risk_note"
            ]:
                relationships_df[text_column] = (
                    relationships_df[text_column]
                    .astype(str)
                    .str.strip()
                )

            # Neue Mapping-Logik: Auch wenn die CSV diese Spalten noch nicht hat,
            # werden Lieferkettenstufe und Verbindungsart automatisch abgeleitet.
            if "supply_chain_stage" not in relationships_df.columns:
                relationships_df["supply_chain_stage"] = relationships_df.apply(
                    lambda row: infer_supply_chain_stage(
                        row.get("category", ""),
                        row.get("relationship", "")
                    ),
                    axis=1
                )
            else:
                relationships_df["supply_chain_stage"] = (
                    relationships_df["supply_chain_stage"]
                    .astype(str)
                    .str.strip()
                )

            if "connection_type" not in relationships_df.columns:
                relationships_df["connection_type"] = relationships_df.apply(
                    lambda row: infer_connection_type(
                        row.get("category", ""),
                        row.get("relationship", ""),
                        row.get("risk_note", "")
                    ),
                    axis=1
                )
            else:
                relationships_df["connection_type"] = (
                    relationships_df["connection_type"]
                    .astype(str)
                    .str.strip()
                )

            available_network_tickers = sorted(
                relationships_df["source_ticker"]
                .dropna()
                .unique()
                .tolist()
            )

            query_network_ticker = st.query_params.get("network_ticker", None)
            query_network_reset = st.query_params.get("network_reset", None)

            if isinstance(query_network_ticker, list):
                query_network_ticker = query_network_ticker[0] if query_network_ticker else None

            if isinstance(query_network_reset, list):
                query_network_reset = query_network_reset[0] if query_network_reset else None

            if query_network_ticker is not None:
                query_network_ticker = str(query_network_ticker).strip().upper()

            # Wenn das Netzwerk über einen Link/Button gewechselt wird,
            # setzen wir die Hauptaktie UND die Filter vor dem Erzeugen der Widgets zurück.
            # Der Reset wird nur einmal pro Query-Wechsel angewendet, damit spätere Filteränderungen
            # nicht sofort wieder überschrieben werden.
            if query_network_ticker in available_network_tickers:
                old_network_ticker = st.session_state.get("network_selected_ticker")
                current_query_key = f"{query_network_ticker}:{query_network_reset}"
                last_query_key = st.session_state.get("_network_last_query_key")

                if old_network_ticker != query_network_ticker or (str(query_network_reset) == "1" and last_query_key != current_query_key):
                    st.session_state["network_selected_ticker"] = query_network_ticker
                    st.session_state["network_selected_category"] = "Alle"
                    st.session_state["network_selected_supply_chain_stage"] = "Alle"
                    st.session_state["network_selected_connection_type"] = "Alle"
                    st.session_state["_network_last_query_key"] = current_query_key

            selected_network_ticker = st.selectbox(
                "Aktie für Netzwerk auswählen",
                options=available_network_tickers,
                index=0,
                key="network_selected_ticker"
            )

            selected_relationships_base = relationships_df[
                relationships_df["source_ticker"] == selected_network_ticker
            ].copy()

            col_net_1, col_net_2, col_net_3, col_net_4 = st.columns(4)

            with col_net_1:
                st.metric(
                    "Verbindungen",
                    len(selected_relationships_base)
                )

            with col_net_2:
                st.metric(
                    "Kategorien",
                    selected_relationships_base["category"].nunique()
                    if not selected_relationships_base.empty else 0
                )

            with col_net_3:
                st.metric(
                    "Lieferkettenstufen",
                    selected_relationships_base["supply_chain_stage"].nunique()
                    if not selected_relationships_base.empty else 0
                )

            with col_net_4:
                high_count = (
                    selected_relationships_base["importance"]
                    .astype(str)
                    .str.lower()
                    .isin(["hoch", "high"])
                    .sum()
                    if not selected_relationships_base.empty else 0
                )
                st.metric(
                    "Hohe Relevanz",
                    int(high_count)
                )

            if selected_relationships_base.empty:

                st.info("Für diese Aktie sind noch keine Beziehungen hinterlegt.")

            else:

                filter_col_1, filter_col_2, filter_col_3 = st.columns(3)

                with filter_col_1:
                    category_options = ["Alle"] + sorted(
                        selected_relationships_base["category"]
                        .dropna()
                        .astype(str)
                        .unique()
                        .tolist()
                    )

                    selected_network_category = st.selectbox(
                        "Kategorie filtern",
                        options=category_options,
                        index=0,
                        key="network_selected_category"
                    )

                with filter_col_2:
                    stage_options = ["Alle"] + sorted(
                        selected_relationships_base["supply_chain_stage"]
                        .dropna()
                        .astype(str)
                        .unique()
                        .tolist()
                    )

                    selected_supply_chain_stage = st.selectbox(
                        "Lieferkettenstufe filtern",
                        options=stage_options,
                        index=0,
                        key="network_selected_supply_chain_stage"
                    )

                with filter_col_3:
                    connection_type_options = ["Alle"] + sorted(
                        selected_relationships_base["connection_type"]
                        .dropna()
                        .astype(str)
                        .unique()
                        .tolist()
                    )

                    selected_connection_type = st.selectbox(
                        "Verbindungsart filtern",
                        options=connection_type_options,
                        index=0,
                        key="network_selected_connection_type"
                    )

                selected_relationships = selected_relationships_base.copy()

                if selected_network_category != "Alle":
                    selected_relationships = selected_relationships[
                        selected_relationships["category"] == selected_network_category
                    ]

                if selected_supply_chain_stage != "Alle":
                    selected_relationships = selected_relationships[
                        selected_relationships["supply_chain_stage"] == selected_supply_chain_stage
                    ]

                if selected_connection_type != "Alle":
                    selected_relationships = selected_relationships[
                        selected_relationships["connection_type"] == selected_connection_type
                    ]

                dashboard_signal_columns = [
                    "Ticker",
                    "Company",
                    "Action Signal",
                    "Rating",
                    "Score",
                    "Risk Level",
                    "Price",
                    "CRV"
                ]

                available_signal_columns = [
                    column for column in dashboard_signal_columns
                    if column in df.columns
                ]

                signal_df = df[available_signal_columns].copy()
                signal_df["Ticker"] = signal_df["Ticker"].astype(str).str.strip()

                network_view = selected_relationships.merge(
                    signal_df,
                    left_on="target_ticker",
                    right_on="Ticker",
                    how="left"
                )

                network_view["Ticker"] = network_view["target_ticker"]

                if "Company" in network_view.columns:
                    network_view["Company"] = network_view["Company"].fillna(
                        network_view["target_name"]
                    )
                else:
                    network_view["Company"] = network_view["target_name"]

                importance_order = {
                    "hoch": 1,
                    "high": 1,
                    "mittel": 2,
                    "medium": 2,
                    "niedrig": 3,
                    "low": 3
                }

                network_view["Importance Sort"] = (
                    network_view["importance"]
                    .astype(str)
                    .str.lower()
                    .map(importance_order)
                    .fillna(9)
                )

                network_view = network_view.sort_values(
                    by=["supply_chain_stage", "category", "Importance Sort", "Ticker"],
                    ascending=True
                )

                signal_summary = network_view["Action Signal"].fillna("Nicht in Hauptliste").value_counts()

                with st.expander("📊 Netzwerk-Signal anzeigen", expanded=False):
                    st.caption(
                        "Zählt die aktuellen Dashboard-Signale der verbundenen Aktien, "
                        "sofern sie in deiner Hauptliste vorhanden sind."
                    )

                    signal_summary_df = signal_summary.reset_index()
                    signal_summary_df.columns = ["Action Signal", "Anzahl"]

                    st.dataframe(
                        signal_summary_df,
                        width="stretch",
                        hide_index=True
                    )

                    bullish_count = network_view["Action Signal"].astype(str).str.contains(
                        "BUY", case=False, na=False
                    ).sum()
                    avoid_count = network_view["Action Signal"].astype(str).str.contains(
                        "AVOID|SELL", case=False, na=False
                    ).sum()
                    watch_count = network_view["Action Signal"].astype(str).str.contains(
                        "WATCH", case=False, na=False
                    ).sum()

                    col_signal_1, col_signal_2, col_signal_3 = st.columns(3)
                    col_signal_1.metric("Bullish im Netzwerk", int(bullish_count))
                    col_signal_2.metric("Watch / Beobachten", int(watch_count))
                    col_signal_3.metric("Schwach / Avoid", int(avoid_count))

                display_columns = [
                    "supply_chain_stage",
                    "connection_type",
                    "category",
                    "Ticker",
                    "Company",
                    "importance",
                    "relationship",
                    "risk_note",
                    "Action Signal",
                    "Rating",
                    "Score",
                    "Risk Level",
                    "Price",
                    "CRV"
                ]

                display_columns = [
                    column for column in display_columns
                    if column in network_view.columns
                ]

                network_display = network_view[display_columns].rename(columns={
                    "supply_chain_stage": "Lieferkettenstufe",
                    "connection_type": "Verbindungsart",
                    "category": "Kategorie",
                    "importance": "Wichtigkeit",
                    "relationship": "Warum verbunden?",
                    "risk_note": "Risiko-Hinweis"
                })

                # ============================================================
                # ============================================================
                # 🕸️ PROFI-SPINNENNETZ / WERTSCHÖPFUNGSKETTE
                # ============================================================

                # ============================================================
                # 🕸️ PROFI-NETZWERK / FOKUS-WERTSCHÖPFUNGSKETTE
                # ============================================================

                with st.expander("🕸️ Netzwerk / Wertschöpfungskette anzeigen", expanded=True):
                    st.caption(
                        "Ruhige Profi-Ansicht: keine Physik, kein Wackeln. "
                        "Ein Klick zeigt Details rechts. Den Mittelpunkt wechselst du zuverlässig über die Buttons unter dem Netzwerk."
                    )

                    import json
                    import math
                    import html

                    def get_connection_color(connection_type, action_signal=""):
                        text_value = f"{connection_type} {action_signal}".lower()
                        if "avoid" in text_value or "sell" in text_value or "schwach" in text_value:
                            return "#ef4444"
                        if "konkurrenz" in text_value or "substitution" in text_value:
                            return "#f97316"
                        if "lieferant" in text_value or "zulieferer" in text_value:
                            return "#22c55e"
                        if "kunde" in text_value or "nachfrage" in text_value:
                            return "#8b5cf6"
                        if "infrastruktur" in text_value or "energie" in text_value or "strom" in text_value:
                            return "#f59e0b"
                        if "risk" in text_value or "risiko" in text_value:
                            return "#f43f5e"
                        return "#38bdf8"

                    def get_signal_badge(action_signal):
                        text_value = str(action_signal)
                        low_value = text_value.lower()
                        if "buy" in low_value:
                            return "BUY", "#22c55e"
                        if "watch" in low_value:
                            return "WATCH", "#eab308"
                        if "avoid" in low_value or "sell" in low_value:
                            return "RISK", "#ef4444"
                        if text_value.strip() in ["", "nan", "None"]:
                            return "N/A", "#64748b"
                        return text_value[:10], "#38bdf8"

                    spider_records = network_view.fillna("").to_dict(orient="records")

                    if not spider_records:
                        st.info("Für die aktuelle Auswahl gibt es keine Netzwerkdaten.")
                    else:
                        max_visible_nodes = st.slider(
                            "Maximale Aktien im Netzwerk",
                            min_value=10,
                            max_value=90,
                            value=min(42, max(10, len(spider_records))),
                            step=5,
                            key=f"spider_max_nodes_static_{selected_network_ticker}"
                        )

                        spider_records_sorted = sorted(
                            spider_records,
                            key=lambda row: (
                                str(row.get("supply_chain_stage", "99")),
                                str(row.get("category", "")),
                                str(row.get("Importance Sort", "9")),
                                str(row.get("Ticker", ""))
                            )
                        )[:max_visible_nodes]

                        stage_names = []
                        for row in spider_records_sorted:
                            stage_name = str(row.get("supply_chain_stage", "99 - Sonstige Verbindung"))
                            if stage_name not in stage_names:
                                stage_names.append(stage_name)

                        width = 1320
                        height = 760
                        center_x = 470
                        center_y = 380
                        stage_radius = 190
                        stock_radius_inner = 335
                        stock_radius_outer = 435

                        available_source_tickers = set(available_network_tickers)
                        nodes = []
                        edges = []

                        center_company = selected_network_ticker
                        if "Ticker" in df.columns and "Company" in df.columns:
                            center_match = df[df["Ticker"].astype(str).str.strip() == selected_network_ticker]
                            if not center_match.empty:
                                center_company = str(center_match.iloc[0].get("Company", selected_network_ticker))

                        nodes.append({
                            "id": selected_network_ticker,
                            "label": selected_network_ticker,
                            "name": center_company,
                            "type": "center",
                            "x": center_x,
                            "y": center_y,
                            "w": 150,
                            "h": 64,
                            "color": "#38bdf8",
                            "stage": "Hauptaktie",
                            "category": "Fokuswert",
                            "connection": "Zentrum",
                            "relationship": "Ausgangspunkt der Wertschöpfungskette und aller angezeigten Beziehungen.",
                            "risk": "-",
                            "importance": "Fokus",
                            "signal": "Fokus",
                            "rating": "-",
                            "score": "-",
                            "risk_level": "-",
                            "price": "-",
                            "crv": "-",
                            "can_drill": False
                        })

                        stage_positions = {}
                        total_stages = max(len(stage_names), 1)

                        for stage_index, stage_name in enumerate(stage_names):
                            angle = -math.pi / 2 + (2 * math.pi * stage_index / total_stages)
                            stage_x = center_x + stage_radius * math.cos(angle)
                            stage_y = center_y + stage_radius * math.sin(angle)
                            stage_id = f"stage::{stage_name}"
                            stage_label = stage_name.split(" - ", 1)[-1]
                            if len(stage_label) > 23:
                                stage_label = stage_label[:21] + "…"
                            stage_positions[stage_name] = (stage_x, stage_y, angle, stage_id)

                            nodes.append({
                                "id": stage_id,
                                "label": stage_label,
                                "name": stage_name,
                                "type": "stage",
                                "x": stage_x,
                                "y": stage_y,
                                "w": 158,
                                "h": 42,
                                "color": "#0f172a",
                                "stage": stage_name,
                                "category": "Lieferkettenstufe",
                                "connection": "Zwischenstufe",
                                "relationship": f"Diese Stufe bündelt Beziehungen im Netzwerk von {selected_network_ticker}.",
                                "risk": "-",
                                "importance": "Stage",
                                "signal": "Stage",
                                "rating": "-",
                                "score": "-",
                                "risk_level": "-",
                                "price": "-",
                                "crv": "-",
                                "can_drill": False
                            })
                            edges.append({"from": selected_network_ticker, "to": stage_id, "kind": "stage"})

                        for stage_name in stage_names:
                            group = [
                                row for row in spider_records_sorted
                                if str(row.get("supply_chain_stage", "99 - Sonstige Verbindung")) == stage_name
                            ]

                            stage_x, stage_y, base_angle, stage_id = stage_positions[stage_name]
                            count = max(len(group), 1)
                            spread = min(1.10, 0.20 * count)

                            for item_index, row in enumerate(group):
                                ticker = str(row.get("Ticker", row.get("target_ticker", ""))).strip()
                                if not ticker:
                                    continue

                                local_angle = base_angle if count == 1 else base_angle - spread / 2 + spread * item_index / max(count - 1, 1)
                                radius = stock_radius_inner if item_index % 2 == 0 else stock_radius_outer
                                node_x = center_x + radius * math.cos(local_angle)
                                node_y = center_y + radius * math.sin(local_angle)

                                connection_type = str(row.get("connection_type", "Strategische Verbindung"))
                                action_signal = str(row.get("Action Signal", ""))
                                badge, badge_color = get_signal_badge(action_signal)
                                color = get_connection_color(connection_type, action_signal)
                                importance = str(row.get("importance", ""))
                                node_w = 124
                                if importance.lower() in ["hoch", "high"]:
                                    node_w = 140
                                elif importance.lower() in ["mittel", "medium"]:
                                    node_w = 130

                                nodes.append({
                                    "id": ticker,
                                    "label": ticker,
                                    "name": str(row.get("Company", row.get("target_name", ticker))),
                                    "type": "stock",
                                    "x": node_x,
                                    "y": node_y,
                                    "w": node_w,
                                    "h": 50,
                                    "color": color,
                                    "badge": badge,
                                    "badge_color": badge_color,
                                    "stage": stage_name,
                                    "category": str(row.get("category", "")),
                                    "connection": connection_type,
                                    "relationship": str(row.get("relationship", "")),
                                    "risk": str(row.get("risk_note", "")),
                                    "importance": importance,
                                    "signal": action_signal if action_signal else "Nicht in Hauptliste",
                                    "rating": str(row.get("Rating", "")),
                                    "score": str(row.get("Score", "")),
                                    "risk_level": str(row.get("Risk Level", "")),
                                    "price": str(row.get("Price", "")),
                                    "crv": str(row.get("CRV", "")),
                                    "can_drill": ticker in available_source_tickers
                                })
                                edges.append({"from": stage_id, "to": ticker, "kind": "stock"})

                        nodes_json = json.dumps(nodes, ensure_ascii=False)
                        edges_json = json.dumps(edges, ensure_ascii=False)
                        center_id_json = json.dumps(selected_network_ticker, ensure_ascii=False)

                        network_html = f'''
                        <!DOCTYPE html>
                        <html>
                        <head>
                        <meta charset="utf-8" />
                        <style>
                            * {{ box-sizing: border-box; }}
                            body {{ margin: 0; background: #020617; color: #e5e7eb; font-family: Inter, Arial, sans-serif; }}
                            .terminal-wrap {{ width: 100%; height: 820px; display: grid; grid-template-columns: minmax(780px, 1fr) 390px; gap: 16px; background: radial-gradient(circle at 16% 16%, rgba(56,189,248,0.18), transparent 30%), radial-gradient(circle at 82% 10%, rgba(168,85,247,0.14), transparent 30%), linear-gradient(135deg, #020617, #0f172a 58%, #111827); border: 1px solid rgba(56,189,248,0.28); border-radius: 24px; padding: 16px; overflow: hidden; }}
                            .network-card {{ position: relative; min-width: 0; border: 1px solid rgba(148,163,184,0.20); border-radius: 20px; background: rgba(2,6,23,0.48); overflow: hidden; box-shadow: inset 0 0 80px rgba(14,165,233,0.06); }}
                            .detail-card {{ border: 1px solid rgba(148,163,184,0.22); border-radius: 20px; padding: 18px; background: rgba(15,23,42,0.90); box-shadow: 0 18px 42px rgba(0,0,0,0.30); overflow: auto; }}
                            .detail-kicker {{ color: #38bdf8; font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 900; }}
                            .detail-title {{ margin: 8px 0 4px; font-size: 27px; line-height: 1.05; font-weight: 950; color: #f8fafc; }}
                            .detail-subtitle {{ color: #cbd5e1; font-size: 14px; margin-bottom: 14px; }}
                            .pill-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 16px; }}
                            .pill {{ border-radius: 999px; border: 1px solid rgba(148,163,184,0.25); background: rgba(30,41,59,0.72); padding: 6px 9px; color: #e5e7eb; font-size: 12px; font-weight: 750; }}
                            .section {{ margin-top: 14px; padding-top: 10px; border-top: 1px solid rgba(148,163,184,0.14); }}
                            .section h4 {{ margin: 0 0 6px; color: #93c5fd; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; }}
                            .section p {{ margin: 0; color: #e5e7eb; font-size: 14px; line-height: 1.45; }}
                            .hint {{ position: absolute; top: 14px; left: 16px; color: #cbd5e1; background: rgba(2,6,23,0.74); border: 1px solid rgba(148,163,184,0.18); border-radius: 999px; padding: 8px 11px; font-size: 12px; z-index: 3; }}
                            .legend {{ position: absolute; left: 16px; bottom: 14px; display: flex; flex-wrap: wrap; gap: 8px; max-width: 720px; padding: 8px 10px; border-radius: 999px; background: rgba(2,6,23,0.74); border: 1px solid rgba(148,163,184,0.18); backdrop-filter: blur(10px); }}
                            .legend span {{ font-size: 11px; color: #cbd5e1; }}
                            .dot {{ display:inline-block; width:9px; height:9px; border-radius:999px; margin-right:5px; vertical-align:middle; }}
                            .tooltip {{ position: fixed; max-width: 360px; pointer-events: none; background: rgba(15,23,42,0.96); border: 1px solid rgba(56,189,248,0.30); color: #e5e7eb; border-radius: 14px; padding: 11px 12px; font-size: 12px; line-height: 1.35; box-shadow: 0 18px 42px rgba(0,0,0,0.38); opacity: 0; transform: translate(12px, 12px); transition: opacity .08s ease; z-index: 99; }}
                            .tooltip b {{ color: #f8fafc; font-size: 13px; }}
                            svg {{ width: 100%; height: 100%; display: block; }}
                            .edge {{ stroke: rgba(148,163,184,0.28); stroke-width: 1.5; fill: none; }}
                            .edge-stage {{ stroke: rgba(56,189,248,0.30); stroke-width: 1.9; stroke-dasharray: 7 8; }}
                            .node {{ cursor: pointer; transition: opacity .12s ease; }}
                            .node rect {{ stroke: rgba(248,250,252,0.60); stroke-width: 1.25; filter: drop-shadow(0 10px 14px rgba(0,0,0,0.35)); }}
                            .node text {{ pointer-events: none; font-weight: 900; fill: #f8fafc; paint-order: stroke; stroke: #020617; stroke-width: 3px; stroke-linejoin: round; }}
                            .node:hover rect {{ stroke: #f8fafc; stroke-width: 2.2; }}
                            .node.active rect {{ stroke: #f8fafc; stroke-width: 2.8; }}
                            .center-node rect {{ fill: #0ea5e9; stroke: #e0f2fe; stroke-width: 2.8; }}
                            .center-node text {{ font-size: 21px; }}
                            .stage-node rect {{ fill: rgba(15,23,42,0.94); stroke: rgba(56,189,248,0.58); stroke-width: 1.8; }}
                            .stage-node text {{ font-size: 11px; fill: #bfdbfe; }}
                            .stock-node text {{ font-size: 14px; }}
                            .badge-text {{ font-size: 9px; font-weight: 950; fill: #020617; stroke: none; paint-order: normal; }}
                            .drill {{ font-size: 10px; fill: #93c5fd; stroke: none; paint-order: normal; }}
                        </style>
                        </head>
                        <body>
                            <div class="terminal-wrap"><div class="network-card"><div class="hint">Klick = Detail · Zentrum wechseln über Buttons unter dem Netzwerk</div><svg viewBox="0 0 {width} {height}" id="networkSvg" preserveAspectRatio="xMidYMid meet"><g id="edges"></g><g id="nodes"></g></svg><div class="legend"><span><i class="dot" style="background:#22c55e"></i>Lieferant</span><span><i class="dot" style="background:#8b5cf6"></i>Kunde/Nachfrage</span><span><i class="dot" style="background:#f59e0b"></i>Infrastruktur/Energie</span><span><i class="dot" style="background:#f97316"></i>Konkurrenz</span><span><i class="dot" style="background:#ef4444"></i>Risk/Avoid</span><span><i class="dot" style="background:#38bdf8"></i>Strategisch</span></div><div class="tooltip" id="tooltip"></div></div>
                                <aside class="detail-card" id="detailCard"><div class="detail-kicker">Market Relationship Focus</div><div class="detail-title">{html.escape(selected_network_ticker)}</div><div class="detail-subtitle">Klicke auf eine Karte im Netzwerk, um die Verbindung im Detail zu sehen.</div><div class="pill-row"><span class="pill">Zentrum</span><span class="pill">Wertschöpfungskette</span></div><div class="section"><h4>Bedienung</h4><p>Mouseover zeigt Schnellinfos. Das Zentrum wechselst du über die Streamlit-Buttons unter dem Netzwerk.</p></div></aside></div>
                            <script>
                                const nodes = {nodes_json}; const edges = {edges_json}; const centerId = {center_id_json};
                                const nodesById = Object.fromEntries(nodes.map(n => [n.id, n]));
                                const edgeLayer = document.getElementById('edges'); const nodeLayer = document.getElementById('nodes'); const detailCard = document.getElementById('detailCard'); const tooltip = document.getElementById('tooltip');
                                function esc(value) {{ return String(value ?? '').replace(/[&<>'"]/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}}[ch])); }}
                                function detailHtml(n) {{ const typeLabel = n.type === 'center' ? 'Hauptaktie' : n.type === 'stage' ? 'Lieferkettenstufe' : 'Verbundene Aktie'; const drillInfo = n.can_drill ? '<span class="pill">Als Zentrum verfügbar</span>' : ''; return `<div class="detail-kicker">${{esc(typeLabel)}}</div><div class="detail-title">${{esc(n.label)}} <span style="font-size:16px;color:#94a3b8;">${{n.name && n.name !== n.label ? '— ' + esc(n.name) : ''}}</span></div><div class="detail-subtitle">${{esc(n.stage || '-')}}</div><div class="pill-row"><span class="pill" style="border-color:${{esc(n.color)}};">${{esc(n.connection || '-')}}</span><span class="pill">${{esc(n.category || '-')}}</span><span class="pill">Wichtigkeit: ${{esc(n.importance || '-')}}</span>${{drillInfo}}</div><div class="section"><h4>Warum verbunden?</h4><p>${{esc(n.relationship || '-')}}</p></div><div class="section"><h4>Risiko / Hinweis</h4><p>${{esc(n.risk || '-')}}</p></div><div class="section"><h4>Dashboard-Signal</h4><p>${{esc(n.signal || '-')}} · Rating: ${{esc(n.rating || '-')}} · Score: ${{esc(n.score || '-')}} · Risk: ${{esc(n.risk_level || '-')}}</p></div><div class="section"><h4>Kurs / CRV</h4><p>Preis: ${{esc(n.price || '-')}} · CRV: ${{esc(n.crv || '-')}}</p></div>`; }}
                                function tooltipHtml(n) {{ return `<b>${{esc(n.label)}}${{n.name && n.name !== n.label ? ' — ' + esc(n.name) : ''}}</b><br><span>Stufe: ${{esc(n.stage || '-')}}</span><br><span>Verbindung: ${{esc(n.connection || '-')}}</span><br><span>Signal: ${{esc(n.signal || '-')}} · Score: ${{esc(n.score || '-')}}</span><br><span>Warum: ${{esc(n.relationship || '-')}}</span>`; }}
                                function showDetails(nodeId) {{ const n = nodesById[nodeId]; if (!n) return; document.querySelectorAll('.node').forEach(el => el.classList.remove('active')); const active = document.querySelector(`[data-node-id="${{CSS.escape(nodeId)}}"]`); if (active) active.classList.add('active'); detailCard.innerHTML = detailHtml(n); }}
                                function navigateToTicker(ticker) {{
                                    const n = nodesById[ticker];
                                    if (!n || !n.can_drill) return;
                                    const targetUrl = `?network_ticker=${{encodeURIComponent(String(ticker).toUpperCase())}}&network_reset=1`;
                                    try {{
                                        window.top.location.assign(targetUrl);
                                    }} catch (e) {{
                                        try {{ window.open(targetUrl, '_top'); }} catch (e2) {{ window.location.href = targetUrl; }}
                                    }}
                                }}
                                function drawEdges() {{ edges.forEach(e => {{ const a = nodesById[e.from]; const b = nodesById[e.to]; if (!a || !b) return; const line = document.createElementNS('http://www.w3.org/2000/svg', 'line'); line.setAttribute('x1', a.x); line.setAttribute('y1', a.y); line.setAttribute('x2', b.x); line.setAttribute('y2', b.y); line.setAttribute('class', e.kind === 'stage' ? 'edge edge-stage' : 'edge'); edgeLayer.appendChild(line); }}); }}
                                function drawNodes() {{ nodes.forEach(n => {{ const g = document.createElementNS('http://www.w3.org/2000/svg', 'g'); g.setAttribute('class', `node ${{n.type}}-node`); g.setAttribute('data-node-id', n.id); g.setAttribute('transform', `translate(${{n.x}}, ${{n.y}})`); const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect'); rect.setAttribute('x', -n.w / 2); rect.setAttribute('y', -n.h / 2); rect.setAttribute('width', n.w); rect.setAttribute('height', n.h); rect.setAttribute('rx', n.type === 'center' ? 18 : 14); rect.setAttribute('fill', n.type === 'stage' ? 'rgba(15,23,42,0.94)' : n.color); g.appendChild(rect); const title = document.createElementNS('http://www.w3.org/2000/svg', 'text'); title.setAttribute('text-anchor', 'middle'); title.setAttribute('dominant-baseline', 'central'); title.setAttribute('y', n.type === 'stock' ? -5 : 0); title.textContent = n.label; g.appendChild(title); if (n.type === 'stock') {{ const badgeBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect'); badgeBg.setAttribute('x', -30); badgeBg.setAttribute('y', 11); badgeBg.setAttribute('width', 60); badgeBg.setAttribute('height', 16); badgeBg.setAttribute('rx', 8); badgeBg.setAttribute('fill', n.badge_color || '#64748b'); g.appendChild(badgeBg); const badgeText = document.createElementNS('http://www.w3.org/2000/svg', 'text'); badgeText.setAttribute('class', 'badge-text'); badgeText.setAttribute('text-anchor', 'middle'); badgeText.setAttribute('x', 0); badgeText.setAttribute('y', 22.5); badgeText.textContent = n.badge || 'N/A'; g.appendChild(badgeText); if (n.can_drill) {{ const drillText = document.createElementNS('http://www.w3.org/2000/svg', 'text'); drillText.setAttribute('class', 'drill'); drillText.setAttribute('text-anchor', 'middle'); drillText.setAttribute('x', 0); drillText.setAttribute('y', -19); drillText.textContent = '↻'; g.appendChild(drillText); }} }} g.addEventListener('click', () => showDetails(n.id)); g.addEventListener('dblclick', (ev) => {{ ev.preventDefault(); showDetails(n.id); }}); g.addEventListener('mouseenter', () => {{ tooltip.innerHTML = tooltipHtml(n); tooltip.style.opacity = '1'; }}); g.addEventListener('mousemove', (ev) => {{ tooltip.style.left = ev.clientX + 'px'; tooltip.style.top = ev.clientY + 'px'; }}); g.addEventListener('mouseleave', () => {{ tooltip.style.opacity = '0'; }}); nodeLayer.appendChild(g); }}); }}
                                drawEdges(); drawNodes(); showDetails(centerId);
                            </script>
                        </body>
                        </html>
                        '''

                        components.html(network_html, height=850, scrolling=False)

                        st.markdown(
                            """
                            <div class="terminal-panel" style="padding:14px 16px; margin-top:8px;">
                                <b>Bedienung:</b> Mouseover zeigt Schnellinfos. Klick zeigt Details rechts. Das Zentrum wechselst du über die Buttons unten — stabiler als Doppelklick im eingebetteten Netzwerk.
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        # Streamlit-native Navigation: zuverlässiger als JavaScript-Doppelklick im iframe.
                        drill_candidates = (
                            network_view["target_ticker"]
                            .dropna()
                            .astype(str)
                            .str.strip()
                            .str.upper()
                            .unique()
                            .tolist()
                        )

                        drill_candidates = [
                            ticker for ticker in drill_candidates
                            if ticker in available_network_tickers and ticker != selected_network_ticker
                        ]

                        if drill_candidates:
                            st.markdown("#### 🔁 Verbundene Aktie als neues Zentrum öffnen")
                            st.caption("Diese Auswahl setzt Kategorie-, Lieferketten- und Verbindungsfilter automatisch zurück.")

                            # Kompakte Button-Matrix
                            button_columns = st.columns(6)
                            for idx, ticker in enumerate(drill_candidates[:30]):
                                with button_columns[idx % 6]:
                                    st.link_button(
                                        f"↻ {ticker}",
                                        f"?network_ticker={ticker}&network_reset=1",
                                        use_container_width=True
                                    )
                        else:
                            st.caption("Keine verbundenen Aktien aus dieser Ansicht sind aktuell selbst als Hauptaktie im Mapping hinterlegt.")

                st.markdown("### 🧾 Detailtabelle")

                st.dataframe(
                    network_display,
                    width="stretch",
                    hide_index=True
                )

                with st.expander("🏭 Lieferkette als Stufenansicht anzeigen", expanded=True):

                    stage_groups = network_view.groupby("supply_chain_stage", sort=True)

                    for stage, stage_group in stage_groups:
                        st.markdown(f"### {stage}")

                        for _, rel_row in stage_group.iterrows():
                            ticker = rel_row.get("Ticker", "")
                            name = rel_row.get("Company", "")
                            category = rel_row.get("category", "")
                            connection_type = rel_row.get("connection_type", "")
                            importance = rel_row.get("importance", "")
                            relationship = rel_row.get("relationship", "")
                            risk_note = rel_row.get("risk_note", "")
                            action_signal = rel_row.get("Action Signal", "-")
                            rating = rel_row.get("Rating", "-")
                            score = rel_row.get("Score", "-")

                            st.markdown(
                                f"**{ticker} - {name}**  \n"
                                f"Kategorie: **{category}** | Verbindungsart: **{connection_type}** | Wichtigkeit: **{importance}**  \n"
                                f"Warum verbunden: {relationship}  \n"
                                f"Risiko: {risk_note}  \n"
                                f"Dashboard-Signal: **{action_signal}** | Rating: **{rating}** | Score: **{score}**"
                            )
                            st.divider()

                with st.expander("🧩 Netzwerk als Kategorienansicht anzeigen", expanded=False):

                    grouped_categories = network_view.groupby("category")

                    for category, group in grouped_categories:
                        st.markdown(f"### {category}")

                        for _, rel_row in group.iterrows():
                            ticker = rel_row.get("Ticker", "")
                            name = rel_row.get("Company", "")
                            stage = rel_row.get("supply_chain_stage", "")
                            connection_type = rel_row.get("connection_type", "")
                            importance = rel_row.get("importance", "")
                            relationship = rel_row.get("relationship", "")
                            risk_note = rel_row.get("risk_note", "")

                            st.markdown(
                                f"**{ticker} - {name}**  \n"
                                f"Stufe: **{stage}** | Verbindungsart: **{connection_type}** | Wichtigkeit: **{importance}**  \n"
                                f"Verbindung: {relationship}  \n"
                                f"Risiko: {risk_note}"
                            )
                            st.divider()

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

with st.expander("📅 Dividendenkalender", expanded=True):
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

with st.expander("📋 Gesamttabelle", expanded=False):
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
# ⭐ PERSÖNLICHE WATCHLIST & KAUFLIST
# ============================================================

with st.expander("⭐ Persönliche Watchlist & Kaufliste", expanded=True):
    st.divider()

    st.subheader("⭐ Persönliche Aktienlisten")

    current_user = st.session_state.get("current_user", "").strip()

    stock_options_df = df.dropna(subset=["Ticker"]).copy()
    stock_options_df["Ticker"] = stock_options_df["Ticker"].astype(str).str.strip()
    stock_options_df["Company"] = stock_options_df["Company"].astype(str).str.strip()

    # Doppelte Ticker vermeiden, damit die Auswahl stabil bleibt
    stock_options_df = stock_options_df.drop_duplicates(subset=["Ticker"])

    stock_options_df["display"] = (
        stock_options_df["Ticker"] + " - " + stock_options_df["Company"]
    )

    stock_options_df = stock_options_df.sort_values(by="display")

    ticker_to_display = dict(
        zip(stock_options_df["Ticker"], stock_options_df["display"])
    )

    display_to_ticker = dict(
        zip(stock_options_df["display"], stock_options_df["Ticker"])
    )

    all_displays = stock_options_df["display"].tolist()

    saved_watchlist_tickers = get_saved_tickers(
        current_user,
        "watchlist"
    )

    saved_buy_tickers = get_saved_tickers(
        current_user,
        "buy"
    )

    saved_watchlist_displays = [
        ticker_to_display[ticker]
        for ticker in saved_watchlist_tickers
        if ticker in ticker_to_display
    ]

    saved_buy_displays = [
        ticker_to_display[ticker]
        for ticker in saved_buy_tickers
        if ticker in ticker_to_display
    ]

    col_watchlist, col_buylist = st.columns(2)

    with col_watchlist:

        st.markdown("### ⭐ Watchlist-Aktien")

        selected_watchlist_displays = st.multiselect(
            "Aktien auswählen, die auf deiner Watchlist bleiben sollen",
            options=all_displays,
            default=saved_watchlist_displays,
            key=f"watchlist_select_{current_user}"
        )

        selected_watchlist_tickers = [
            display_to_ticker[item]
            for item in selected_watchlist_displays
        ]

        if st.button(
            "Watchlist speichern",
            key=f"save_watchlist_{current_user}"
        ):
            update_user_list(
                username=current_user,
                list_type="watchlist",
                selected_tickers=selected_watchlist_tickers,
                stock_df=df
            )

            st.success("Watchlist gespeichert.")
            st.rerun()

        if selected_watchlist_tickers:

            user_watchlist_df = df[
                df["Ticker"].astype(str).isin(selected_watchlist_tickers)
            ].copy()

            watchlist_columns = [
                "Ticker",
                "Company",
                "Action Signal",
                "Rating",
                "Score",
                "Risk Level",
                "Price",
                "CRV"
            ]

            watchlist_columns = [
                column for column in watchlist_columns
                if column in user_watchlist_df.columns
            ]

            st.dataframe(
                user_watchlist_df[watchlist_columns],
                width="stretch",
                hide_index=True
            )

        else:

            st.info("Noch keine Watchlist-Aktien ausgewählt.")


    with col_buylist:

        st.markdown("### 🛒 Kauf-Aktien")

        selected_buy_displays = st.multiselect(
            "Aktien auswählen, die auf deiner Kaufliste bleiben sollen",
            options=all_displays,
            default=saved_buy_displays,
            key=f"buy_select_{current_user}"
        )

        selected_buy_tickers = [
            display_to_ticker[item]
            for item in selected_buy_displays
        ]

        if st.button(
            "Kaufliste speichern",
            key=f"save_buy_{current_user}"
        ):
            update_user_list(
                username=current_user,
                list_type="buy",
                selected_tickers=selected_buy_tickers,
                stock_df=df
            )

            st.success("Kaufliste gespeichert.")
            st.rerun()

        if selected_buy_tickers:

            user_buy_df = df[
                df["Ticker"].astype(str).isin(selected_buy_tickers)
            ].copy()

            buy_columns = [
                "Ticker",
                "Company",
                "Action Signal",
                "Rating",
                "Score",
                "Risk Level",
                "Price",
                "CRV"
            ]

            buy_columns = [
                column for column in buy_columns
                if column in user_buy_df.columns
            ]

            st.dataframe(
                user_buy_df[buy_columns],
                width="stretch",
                hide_index=True
            )

        else:

            st.info("Noch keine Kauf-Aktien ausgewählt.")


# ============================================================
# 👑 SUPERUSER-ANSICHT
# ============================================================

superusers = st.secrets.get("app", {}).get("superusers", [])

if current_user in superusers:

    with st.expander("👑 Superuser-Übersicht", expanded=False):

        st.divider()

        st.subheader("👑 Superuser-Übersicht")

        all_user_lists = load_user_lists()

        if all_user_lists.empty:

            st.info("Noch keine gespeicherten Nutzerlisten vorhanden.")

        else:

            all_user_lists = all_user_lists.copy()

            all_user_lists["Liste"] = all_user_lists["list_type"].replace({
                "watchlist": "Watchlist",
                "buy": "Kauf"
            })

            all_user_lists = all_user_lists.rename(columns={
                "username": "User",
                "ticker": "Ticker",
                "name": "Company",
                "created_at": "Gespeichert am"
            })

            all_user_lists = all_user_lists[
                [
                    "Liste",
                    "Ticker",
                    "Company",
                    "User",
                    "Gespeichert am"
                ]
            ].sort_values(
                by=[
                    "Liste",
                    "User",
                    "Ticker"
                ]
            )

            st.dataframe(
                all_user_lists,
                width="stretch",
                hide_index=True
            )


# ============================================================
# AKTIENKARTEN
# ============================================================

with st.expander("🔥 Aktienübersicht / Karten", expanded=False):
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
