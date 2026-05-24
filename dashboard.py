import pandas as pd
import streamlit as st
import os
import subprocess
import hmac
from datetime import datetime
from supabase import create_client, Client

# Optional für das interaktive Spinnennetz / Netzwerkdiagramm.
# Falls pyvis noch nicht installiert ist, läuft das Dashboard weiter und zeigt einen Hinweis.
try:
    from pyvis.network import Network
    import streamlit.components.v1 as components
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
                # 🕸️ INTERAKTIVES SPINNENNETZ / NETZWERKDIAGRAMM
                # ============================================================

                with st.expander("🕸️ Spinnennetz / Netzwerkdiagramm anzeigen", expanded=True):

                    if not PYVIS_AVAILABLE:
                        st.warning(
                            "Für das interaktive Spinnennetz fehlt noch das Paket `pyvis`. "
                            "Bitte ergänze `pyvis` und `networkx` in deiner requirements.txt und deploye neu."
                        )
                    else:
                        st.caption(
                            "Interaktives Beziehungsnetz: Mittelpunkt ist die ausgewählte Aktie. "
                            "Du kannst Knoten verschieben, zoomen und mit der Maus über Aktien fahren."
                        )

                        spider_col_1, spider_col_2 = st.columns([1, 1])

                        with spider_col_1:
                            spider_mode = st.radio(
                                "Darstellung",
                                options=[
                                    "Direkt: Hauptaktie → verbundene Aktien",
                                    "Lieferkette: Hauptaktie → Stufen → Aktien"
                                ],
                                index=1,
                                key="spider_network_mode"
                            )

                        with spider_col_2:
                            use_current_filters_for_spider = st.checkbox(
                                "Aktuelle Mapping-Filter verwenden",
                                value=True,
                                key="spider_use_current_filters"
                            )

                        spider_data = (
                            selected_relationships.copy()
                            if use_current_filters_for_spider
                            else selected_relationships_base.copy()
                        )

                        if spider_data.empty:
                            st.info("Für die aktuelle Filterauswahl gibt es keine Netzwerkdaten.")
                        else:
                            spider_network_view = spider_data.merge(
                                signal_df,
                                left_on="target_ticker",
                                right_on="Ticker",
                                how="left"
                            )

                            spider_network_view["Ticker"] = spider_network_view["target_ticker"]

                            if "Company" in spider_network_view.columns:
                                spider_network_view["Company"] = spider_network_view["Company"].fillna(
                                    spider_network_view["target_name"]
                                )
                            else:
                                spider_network_view["Company"] = spider_network_view["target_name"]

                            def get_node_color(connection_type, action_signal):
                                connection_text = str(connection_type).lower()
                                signal_text = str(action_signal).lower()

                                if "avoid" in signal_text or "sell" in signal_text:
                                    return "#ef4444"
                                if "konkurrenz" in connection_text or "substitution" in connection_text:
                                    return "#fb923c"
                                if "lieferant" in connection_text or "zulieferer" in connection_text:
                                    return "#22c55e"
                                if "kunde" in connection_text or "nachfrage" in connection_text:
                                    return "#a855f7"
                                if "infrastruktur" in connection_text or "energie" in connection_text:
                                    return "#f59e0b"
                                if "risiko" in connection_text or "makro" in connection_text:
                                    return "#f43f5e"

                                return "#38bdf8"

                            def get_node_size(importance, action_signal):
                                importance_text = str(importance).lower()
                                signal_text = str(action_signal).lower()

                                size = 18

                                if importance_text in ["hoch", "high"]:
                                    size = 28
                                elif importance_text in ["mittel", "medium"]:
                                    size = 22

                                if "strong buy" in signal_text or "buy zone" in signal_text:
                                    size += 4

                                return size

                            def build_tooltip(row):
                                ticker = row.get("Ticker", row.get("target_ticker", ""))
                                company = row.get("Company", row.get("target_name", ""))
                                category = row.get("category", "")
                                stage = row.get("supply_chain_stage", "")
                                connection_type = row.get("connection_type", "")
                                importance = row.get("importance", "")
                                relationship = row.get("relationship", "")
                                risk_note = row.get("risk_note", "")
                                action_signal = row.get("Action Signal", "Nicht in Hauptliste")
                                rating = row.get("Rating", "-")
                                score = row.get("Score", "-")
                                risk_level = row.get("Risk Level", "-")
                                price = row.get("Price", "-")
                                crv = row.get("CRV", "-")

                                return (
                                    f"<b>{ticker} - {company}</b><br>"
                                    f"<hr>"
                                    f"<b>Kategorie:</b> {category}<br>"
                                    f"<b>Lieferkettenstufe:</b> {stage}<br>"
                                    f"<b>Verbindungsart:</b> {connection_type}<br>"
                                    f"<b>Wichtigkeit:</b> {importance}<br><br>"
                                    f"<b>Warum verbunden?</b><br>{relationship}<br><br>"
                                    f"<b>Risiko:</b><br>{risk_note}<br><br>"
                                    f"<b>Dashboard:</b><br>"
                                    f"Signal: {action_signal}<br>"
                                    f"Rating: {rating}<br>"
                                    f"Score: {score}<br>"
                                    f"Risiko-Level: {risk_level}<br>"
                                    f"Preis: {price}<br>"
                                    f"CRV: {crv}"
                                )

                            net = Network(
                                height="820px",
                                width="100%",
                                bgcolor="#020617",
                                font_color="#e5e7eb",
                                directed=False
                            )

                            net.add_node(
                                selected_network_ticker,
                                label=selected_network_ticker,
                                title=f"<b>Hauptaktie: {selected_network_ticker}</b>",
                                size=58,
                                color={"background": "#0ea5e9", "border": "#e0f2fe", "highlight": {"background": "#38bdf8", "border": "#ffffff"}},
                                borderWidth=4,
                                shape="dot"
                            )

                            added_nodes = {selected_network_ticker}

                            if spider_mode.startswith("Direkt"):
                                for _, spider_row in spider_network_view.iterrows():
                                    target_ticker = str(spider_row.get("target_ticker", "")).strip()

                                    if not target_ticker:
                                        continue

                                    if target_ticker not in added_nodes:
                                        net.add_node(
                                            target_ticker,
                                            label=target_ticker,
                                            title=build_tooltip(spider_row),
                                            size=get_node_size(
                                                spider_row.get("importance", ""),
                                                spider_row.get("Action Signal", "")
                                            ),
                                            color=get_node_color(
                                                spider_row.get("connection_type", ""),
                                                spider_row.get("Action Signal", "")
                                            ),
                                            shape="dot"
                                        )
                                        added_nodes.add(target_ticker)

                                    edge_label = str(spider_row.get("connection_type", ""))
                                    edge_title = str(spider_row.get("relationship", ""))

                                    net.add_edge(
                                        selected_network_ticker,
                                        target_ticker,
                                        title=edge_title,
                                        label=edge_label[:28],
                                        color={"color": "rgba(148,163,184,0.42)", "highlight": "#38bdf8"}
                                    )

                            else:
                                stage_color_map = {
                                    "1": "#f59e0b",
                                    "2": "#f97316",
                                    "3": "#22c55e",
                                    "4": "#10b981",
                                    "5": "#3b82f6",
                                    "6": "#06b6d4",
                                    "7": "#8b5cf6",
                                    "8": "#ec4899",
                                    "9": "#ef4444",
                                    "10": "#dc2626",
                                    "99": "#6b7280"
                                }

                                for stage in sorted(spider_network_view["supply_chain_stage"].dropna().astype(str).unique().tolist()):
                                    stage_node_id = f"STAGE::{stage}"
                                    stage_prefix = stage.split(" - ")[0].strip()
                                    stage_color = stage_color_map.get(stage_prefix, "#6b7280")

                                    if stage_node_id not in added_nodes:
                                        net.add_node(
                                            stage_node_id,
                                            label=stage,
                                            title=f"Lieferkettenstufe: {stage}",
                                            size=30,
                                            color=stage_color,
                                            shape="box"
                                        )
                                        added_nodes.add(stage_node_id)

                                    net.add_edge(
                                        selected_network_ticker,
                                        stage_node_id,
                                        title=f"{selected_network_ticker} → {stage}",
                                        color=stage_color
                                    )

                                for _, spider_row in spider_network_view.iterrows():
                                    target_ticker = str(spider_row.get("target_ticker", "")).strip()
                                    stage = str(spider_row.get("supply_chain_stage", "99 - Sonstige Verbindung")).strip()
                                    stage_node_id = f"STAGE::{stage}"

                                    if not target_ticker:
                                        continue

                                    if target_ticker not in added_nodes:
                                        net.add_node(
                                            target_ticker,
                                            label=target_ticker,
                                            title=build_tooltip(spider_row),
                                            size=get_node_size(
                                                spider_row.get("importance", ""),
                                                spider_row.get("Action Signal", "")
                                            ),
                                            color=get_node_color(
                                                spider_row.get("connection_type", ""),
                                                spider_row.get("Action Signal", "")
                                            ),
                                            shape="dot"
                                        )
                                        added_nodes.add(target_ticker)

                                    edge_label = str(spider_row.get("connection_type", ""))
                                    edge_title = str(spider_row.get("relationship", ""))

                                    net.add_edge(
                                        stage_node_id,
                                        target_ticker,
                                        title=edge_title,
                                        label=edge_label[:24],
                                        color={"color": "rgba(148,163,184,0.42)", "highlight": "#38bdf8"}
                                    )

                            net.repulsion(
                                node_distance=230,
                                central_gravity=0.18,
                                spring_length=190,
                                spring_strength=0.04,
                                damping=0.09
                            )

                            net.set_options("""
                            {
                              "nodes": {
                                "font": {
                                  "size": 18,
                                  "face": "Inter, Arial",
                                  "color": "#e5e7eb",
                                  "strokeWidth": 4,
                                  "strokeColor": "#020617"
                                },
                                "borderWidth": 2,
                                "shadow": {
                                  "enabled": true,
                                  "color": "rgba(0,0,0,0.45)",
                                  "size": 18,
                                  "x": 0,
                                  "y": 6
                                }
                              },
                              "edges": {
                                "font": {
                                  "size": 11,
                                  "align": "middle",
                                  "color": "#cbd5e1",
                                  "strokeWidth": 4,
                                  "strokeColor": "#020617"
                                },
                                "smooth": {
                                  "enabled": true,
                                  "type": "continuous",
                                  "roundness": 0.45
                                },
                                "width": 1.8,
                                "selectionWidth": 3.5,
                                "hoverWidth": 3
                              },
                              "interaction": {
                                "hover": true,
                                "tooltipDelay": 90,
                                "navigationButtons": true,
                                "keyboard": true,
                                "multiselect": true
                              },
                              "physics": {
                                "enabled": true,
                                "solver": "forceAtlas2Based",
                                "forceAtlas2Based": {
                                  "gravitationalConstant": -80,
                                  "centralGravity": 0.018,
                                  "springLength": 180,
                                  "springConstant": 0.055,
                                  "damping": 0.42,
                                  "avoidOverlap": 0.85
                                },
                                "stabilization": {
                                  "enabled": true,
                                  "iterations": 260,
                                  "updateInterval": 25
                                }
                              }
                            }
                            """)

                            try:
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
                                    net.save_graph(tmp_file.name)
                                    with open(tmp_file.name, "r", encoding="utf-8") as html_file:
                                        html_content = html_file.read()

                                pro_network_css = """
                                <style>
                                body {
                                    margin: 0 !important;
                                    background: radial-gradient(circle at 20% 10%, rgba(14,165,233,0.18), transparent 28%),
                                                radial-gradient(circle at 80% 20%, rgba(168,85,247,0.13), transparent 25%),
                                                #020617 !important;
                                    color: #e5e7eb !important;
                                    font-family: Inter, Arial, sans-serif !important;
                                }
                                #mynetwork {
                                    border-radius: 22px;
                                    border: 1px solid rgba(56,189,248,0.35);
                                    box-shadow: inset 0 0 60px rgba(14,165,233,0.08), 0 24px 60px rgba(2,6,23,0.55);
                                    overflow: hidden;
                                }
                                .vis-tooltip {
                                    background: rgba(15,23,42,0.96) !important;
                                    color: #f8fafc !important;
                                    border: 1px solid rgba(56,189,248,0.45) !important;
                                    border-radius: 14px !important;
                                    padding: 12px 14px !important;
                                    box-shadow: 0 18px 40px rgba(0,0,0,0.35) !important;
                                    max-width: 420px !important;
                                    white-space: normal !important;
                                    font-size: 13px !important;
                                    line-height: 1.45 !important;
                                }
                                div.vis-network div.vis-navigation div.vis-button {
                                    background-color: rgba(15,23,42,0.82) !important;
                                    border: 1px solid rgba(148,163,184,0.35) !important;
                                    border-radius: 12px !important;
                                    box-shadow: 0 10px 24px rgba(0,0,0,0.24) !important;
                                }
                                </style>
                                """
                                html_content = html_content.replace("</head>", pro_network_css + "</head>")

                                components.html(
                                    html_content,
                                    height=850,
                                    scrolling=True
                                )

                            except Exception as error:
                                st.error(f"Spinnennetz konnte nicht erstellt werden: {error}")

                        st.markdown(
                            """
                            <div class="terminal-panel" style="padding:14px 16px; margin-top:8px;">
                                <b>Legende:</b>
                                <span class="terminal-chip"><span class="legend-dot" style="background:#22c55e"></span>Lieferant / Zulieferer</span>
                                <span class="terminal-chip"><span class="legend-dot" style="background:#a855f7"></span>Kunde / Nachfrage</span>
                                <span class="terminal-chip"><span class="legend-dot" style="background:#f59e0b"></span>Infrastruktur / Energie</span>
                                <span class="terminal-chip"><span class="legend-dot" style="background:#fb923c"></span>Konkurrenz</span>
                                <span class="terminal-chip"><span class="legend-dot" style="background:#f43f5e"></span>Risiko / Schwach</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

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
