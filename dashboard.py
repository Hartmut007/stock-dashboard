import pandas as pd
import streamlit as st
import os
import subprocess
import hmac
import json
import hashlib
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from supabase import create_client, Client
import yfinance as yf
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
        padding-top: 0.8rem;
        padding-bottom: 1.6rem;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(15,23,42,0.98), rgba(30,41,59,0.94));
        border: 1px solid rgba(148,163,184,0.28);
        border-radius: 14px;
        padding: 9px 11px;
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
        font-size: 1.08rem;
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
        font-size: 0.72rem;
        font-weight: 700;
    }
    .legend-dot {
        display:inline-block;
        width:10px;
        height:10px;
        border-radius:50%;
        margin-right:6px;
    }


    /* Kompaktere Standardschrift im Dashboard */
    html, body, [class*="css"] {
        font-size: 14px;
    }

    .stMarkdown, .stText, p, li, span, div {
        font-size: 0.88rem;
    }

    h1 {
        font-size: 1.65rem !important;
        margin-bottom: 0.55rem !important;
    }

    h2 {
        font-size: 1.32rem !important;
        margin-top: 0.75rem !important;
        margin-bottom: 0.45rem !important;
    }

    h3 {
        font-size: 1.08rem !important;
        margin-top: 0.6rem !important;
        margin-bottom: 0.35rem !important;
    }

    div[data-testid="stMetric"] label {
        font-size: 0.70rem !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.05rem !important;
        line-height: 1.15 !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        font-size: 0.70rem !important;
    }

    /* Sidebar kompakter */
    section[data-testid="stSidebar"] {
        font-size: 0.80rem !important;
    }

    section[data-testid="stSidebar"] * {
        font-size: 0.80rem !important;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        font-size: 0.95rem !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.35rem !important;
    }

    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        font-size: 0.76rem !important;
    }

    section[data-testid="stSidebar"] div[data-baseweb="select"] * {
        font-size: 0.76rem !important;
    }

    section[data-testid="stSidebar"] input {
        font-size: 0.76rem !important;
        min-height: 32px !important;
    }

    section[data-testid="stSidebar"] button {
        font-size: 0.76rem !important;
        padding: 0.25rem 0.45rem !important;
        min-height: 32px !important;
    }

    /* Tabellen und Tabs kompakter */
    div[data-testid="stDataFrame"] {
        font-size: 0.78rem !important;
    }

    button[data-baseweb="tab"] p {
        font-size: 0.82rem !important;
        font-weight: 700 !important;
    }

    .terminal-panel {
        padding: 14px 16px;
        border-radius: 18px;
        margin: 8px 0 12px 0;
    }

    .terminal-panel p {
        font-size: 0.82rem;
        line-height: 1.35;
    }

    .terminal-chip {
        padding: 4px 8px;
        margin: 5px 4px 0 0;
        font-size: 0.68rem;
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
# LETZTE AKTUALISIERUNG / DATENSTATUS
# ============================================================

LOCAL_TZ = ZoneInfo("Europe/Berlin")
DASHBOARD_LOAD_TIME = datetime.now(LOCAL_TZ)
DATA_SOURCE_FILES = [
    "portfolio_analysis.csv",
    "clean_watchlist.csv",
    "stock_relationships.csv",
]
DATA_STATE_FILE = ".dashboard_data_state.json"
DATA_META_FILE = "data_update_meta.json"


def format_local_datetime(value):
    if value is None:
        return "-"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ)
    return value.astimezone(LOCAL_TZ).strftime("%d.%m.%Y %H:%M:%S")


def safe_parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=LOCAL_TZ)
        return parsed.astimezone(LOCAL_TZ)
    except Exception:
        return None


def load_json_file(path, default=None):
    if default is None:
        default = {}
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json_file(path, payload):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def file_fingerprint(path):
    """Erzeugt einen stabilen Inhalts-Fingerabdruck, damit echte Dateiänderungen erkannt werden."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def read_external_data_meta():
    """
    Optionaler echter Datenstand aus advanced_portfolio.py.
    Wenn advanced_portfolio.py eine data_update_meta.json schreibt, ist diese Zeit verlässlicher
    als die Cloud-Dateiänderungszeit. Unterstützte Formen:
    {"portfolio_analysis.csv": "2026-06-01T18:30:00+02:00"}
    oder {"files": {"portfolio_analysis.csv": {"updated_at": "..."}}}
    """
    raw = load_json_file(DATA_META_FILE, {})
    if not isinstance(raw, dict):
        return {}

    files = raw.get("files") if isinstance(raw.get("files"), dict) else raw
    result = {}
    for file_name, value in files.items():
        if isinstance(value, dict):
            value = value.get("updated_at") or value.get("generated_at") or value.get("last_update")
        parsed = safe_parse_datetime(value)
        if parsed is not None:
            result[file_name] = parsed
    return result


def get_data_update_status():
    """
    Ermittelt den Datenstand robuster als reine mtime:
    1) bevorzugt echte Meta-Zeit aus data_update_meta.json
    2) trackt Inhaltsänderungen per SHA-256 ab jetzt selbst
    3) zeigt die Cloud-Dateizeit nur noch als technische Zusatzinfo
    """

    rows = []
    newest_update = None
    state = load_json_file(DATA_STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}

    external_meta = read_external_data_meta()
    now_iso = DASHBOARD_LOAD_TIME.isoformat()

    for file_name in DATA_SOURCE_FILES:
        if not os.path.exists(file_name):
            rows.append({
                "Quelle": file_name,
                "Status": "Fehlt",
                "Echter Datenstand": "-",
                "Quelle der Zeit": "-",
                "Cloud-Dateizeit": "-",
            })
            continue

        cloud_mtime = datetime.fromtimestamp(os.path.getmtime(file_name), tz=LOCAL_TZ)
        current_hash = file_fingerprint(file_name)
        previous = state.get(file_name, {}) if isinstance(state.get(file_name), dict) else {}

        if file_name in external_meta:
            real_update = external_meta[file_name]
            time_source = "Analyse-Meta-Datei"
        elif previous.get("sha256") == current_hash and previous.get("content_changed_at"):
            real_update = safe_parse_datetime(previous.get("content_changed_at"))
            time_source = "Inhalt unverändert getrackt"
        elif previous.get("sha256") and previous.get("sha256") != current_hash:
            real_update = DASHBOARD_LOAD_TIME
            time_source = "Inhaltsänderung erkannt"
        else:
            # Beim allerersten Lauf kann die Vergangenheit nicht rekonstruiert werden.
            # Ab jetzt wird die Datei aber über ihren Inhalt weitergetrackt.
            real_update = None
            time_source = "ab jetzt getrackt"

        if real_update is not None and (newest_update is None or real_update > newest_update):
            newest_update = real_update

        state[file_name] = {
            "sha256": current_hash,
            "first_seen_at": previous.get("first_seen_at") or now_iso,
            "content_changed_at": real_update.isoformat() if real_update is not None else previous.get("content_changed_at"),
            "last_seen_at": now_iso,
            "cloud_mtime": cloud_mtime.isoformat(),
        }

        rows.append({
            "Quelle": file_name,
            "Status": "OK",
            "Echter Datenstand": format_local_datetime(real_update) if real_update else "Noch nicht historisch bekannt",
            "Quelle der Zeit": time_source,
            "Cloud-Dateizeit": format_local_datetime(cloud_mtime),
        })

    save_json_file(DATA_STATE_FILE, state)
    return rows, newest_update


DATA_UPDATE_ROWS, LAST_DATA_UPDATE = get_data_update_status()
LAST_DATA_UPDATE_TEXT = format_local_datetime(LAST_DATA_UPDATE) if LAST_DATA_UPDATE else "ab jetzt getrackt"
DASHBOARD_LOAD_TIME_TEXT = format_local_datetime(DASHBOARD_LOAD_TIME)

st.sidebar.caption(f"🕒 Datenstand: {LAST_DATA_UPDATE_TEXT}")
st.sidebar.caption(f"🔄 Dashboard geladen: {DASHBOARD_LOAD_TIME_TEXT}")


# ============================================================
# WÄHRUNG / CURRENCY ABSICHERN
# ============================================================

def infer_currency_from_row(row):
    """Leitet eine Währung aus vorhandener Currency-Spalte, Preistext oder Yahoo-Suffix ab."""

    # 1) Vorhandene Currency-/Währungsspalten nutzen, falls vorhanden.
    for column in row.index:
        if str(column).strip().lower() in ["currency", "währung", "waehrung"]:
            value = str(row.get(column, "")).strip().upper()
            if value and value not in ["-", "NAN", "NONE"]:
                return value

    # 2) Aus Preistext ableiten, wenn Symbol enthalten ist.
    price_text = str(row.get("Price", "")).upper()
    if "€" in price_text or " EUR" in price_text:
        return "EUR"
    if "$" in price_text or " USD" in price_text:
        return "USD"
    if "CHF" in price_text:
        return "CHF"
    if "GBP" in price_text or "£" in price_text:
        return "GBP"
    if "JPY" in price_text or "¥" in price_text:
        return "JPY"
    if "CAD" in price_text:
        return "CAD"
    if "AUD" in price_text:
        return "AUD"
    if "HKD" in price_text:
        return "HKD"
    if "CNY" in price_text:
        return "CNY"

    # 3) Aus Yahoo-Ticker-Suffix grob ableiten.
    ticker = str(row.get("Ticker", "")).upper().strip()
    suffix_currency_map = {
        ".DE": "EUR", ".F": "EUR", ".BE": "EUR", ".DU": "EUR", ".MU": "EUR", ".HM": "EUR", ".HA": "EUR", ".PA": "EUR", ".AS": "EUR", ".MC": "EUR", ".MI": "EUR", ".VI": "EUR", ".BR": "EUR", ".LS": "EUR",
        ".SW": "CHF",
        ".L": "GBP",
        ".TO": "CAD", ".V": "CAD",
        ".AX": "AUD",
        ".HK": "HKD",
        ".T": "JPY",
        ".SS": "CNY", ".SZ": "CNY",
        ".ST": "SEK", ".OL": "NOK", ".CO": "DKK",
    }
    for suffix, currency in suffix_currency_map.items():
        if ticker.endswith(suffix):
            return currency

    # 4) US-Ticker ohne Suffix als USD einordnen, sonst unbekannt.
    if ticker and "." not in ticker:
        return "USD"

    return "Unbekannt"

# Falls die Analyse-Datei keine Currency-Spalte enthält, wird sie robust ergänzt.
# Existierende Werte bleiben erhalten, leere Werte werden ergänzt.
if "Currency" not in df.columns:
    df["Currency"] = df.apply(infer_currency_from_row, axis=1)
else:
    df["Currency"] = df["Currency"].astype(str).str.strip().replace({"": "Unbekannt", "nan": "Unbekannt", "None": "Unbekannt", "-": "Unbekannt"})
    missing_currency_mask = df["Currency"].isin(["Unbekannt", "nan", "None", "-"])
    if missing_currency_mask.any():
        df.loc[missing_currency_mask, "Currency"] = df.loc[missing_currency_mask].apply(infer_currency_from_row, axis=1)



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
    "Volume Ratio",
    "EQS News Count 14D",
    "EQS News Score",
    "News Momentum Score",
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
# 💎 BEWERTUNGS-HINWEIS: UNTERBEWERTET / FAIR / ÜBERBEWERTET
# ============================================================

def build_valuation_status(row):
    """
    Einfache regelbasierte Bewertung.
    Kein echter Fair Value, sondern ein Hinweis aus Bewertung + Wachstum + Qualität.
    """

    forward_pe = safe_float(row.get("Forward PE"))
    trailing_pe = safe_float(row.get("Trailing PE"))
    peg_ratio = safe_float(row.get("PEG Ratio"))
    revenue_growth = safe_float(row.get("Revenue Growth"))
    earnings_growth = safe_float(row.get("Earnings Growth"))
    profit_margin = safe_float(row.get("Profit Margin"))
    free_cashflow = safe_float(row.get("Free Cashflow"))
    fundamental_score = safe_float(row.get("Fundamental Score"))

    valuation_points = 0
    reasons = []

    # ----------------------------
    # BEWERTUNG
    # ----------------------------

    if forward_pe is not None:
        if forward_pe <= 15:
            valuation_points += 2
            reasons.append("günstiges Forward KGV")
        elif forward_pe <= 25:
            valuation_points += 1
            reasons.append("moderates Forward KGV")
        elif forward_pe >= 40:
            valuation_points -= 2
            reasons.append("hohes Forward KGV")
        elif forward_pe >= 30:
            valuation_points -= 1
            reasons.append("erhöhtes Forward KGV")

    if trailing_pe is not None:
        if trailing_pe <= 18:
            valuation_points += 1
            reasons.append("moderates KGV")
        elif trailing_pe >= 45:
            valuation_points -= 1
            reasons.append("hohes KGV")

    if peg_ratio is not None and peg_ratio > 0:
        if peg_ratio <= 1:
            valuation_points += 2
            reasons.append("attraktives PEG Ratio")
        elif peg_ratio <= 2:
            valuation_points += 1
            reasons.append("PEG Ratio noch vertretbar")
        elif peg_ratio >= 3:
            valuation_points -= 2
            reasons.append("PEG Ratio hoch")
        elif peg_ratio > 2:
            valuation_points -= 1
            reasons.append("PEG Ratio erhöht")

    # ----------------------------
    # QUALITÄT / WACHSTUM
    # ----------------------------

    if revenue_growth is not None:
        if revenue_growth > 0:
            valuation_points += 1
            reasons.append("positives Umsatzwachstum")
        elif revenue_growth < 0:
            valuation_points -= 1
            reasons.append("negatives Umsatzwachstum")

    if earnings_growth is not None:
        if earnings_growth > 0:
            valuation_points += 1
            reasons.append("positives Gewinnwachstum")
        elif earnings_growth < 0:
            valuation_points -= 1
            reasons.append("negatives Gewinnwachstum")

    if profit_margin is not None:
        if profit_margin > 0:
            valuation_points += 1
            reasons.append("positive Gewinnmarge")
        elif profit_margin < 0:
            valuation_points -= 1
            reasons.append("negative Gewinnmarge")

    if free_cashflow is not None:
        if free_cashflow > 0:
            valuation_points += 1
            reasons.append("positiver Free Cashflow")
        elif free_cashflow < 0:
            valuation_points -= 1
            reasons.append("negativer Free Cashflow")

    if fundamental_score is not None:
        if fundamental_score >= 6:
            valuation_points += 1
            reasons.append("starker Fundamental Score")
        elif fundamental_score <= 2:
            valuation_points -= 1
            reasons.append("schwacher Fundamental Score")

    # ----------------------------
    # LABEL
    # ----------------------------

    if len(reasons) < 2:
        valuation_status = "❓ Unklar"
        valuation_summary = "Zu wenige Bewertungsdaten vorhanden."
    elif valuation_points >= 4:
        valuation_status = "💎 Eher unterbewertet"
        valuation_summary = "Bewertung wirkt im Verhältnis zu Qualität und Wachstum attraktiv."
    elif valuation_points >= 1:
        valuation_status = "⚖️ Fair bewertet"
        valuation_summary = "Bewertung wirkt grundsätzlich vertretbar."
    elif valuation_points <= -3:
        valuation_status = "🔥 Eher überbewertet"
        valuation_summary = "Bewertung wirkt im Verhältnis zu Qualität und Wachstum anspruchsvoll."
    else:
        valuation_status = "⚖️ Fair bis leicht teuer"
        valuation_summary = "Bewertung ist nicht extrem, aber nicht klar günstig."

    return pd.Series({
        "Valuation Status": valuation_status,
        "Valuation Score": valuation_points,
        "Valuation Reasons": " | ".join(unique_items(reasons)) if reasons else "-",
        "Valuation Summary": valuation_summary
    })


valuation_columns = df.apply(
    build_valuation_status,
    axis=1
)

df = pd.concat(
    [df, valuation_columns],
    axis=1
)

# ============================================================
# 🧭 TERMINAL SCORE / RESEARCH-GRADE
# ============================================================

def build_terminal_score(row):
    """Kompakter Research-Score aus Technik, Fundamental, Bewertung, CRV und Risiko.
    Hinweis: Regelbasiertes Ranking, kein Finanzrat und kein echtes Kurszielmodell.
    """

    tech_score = safe_float(row.get("Score"))
    fundamental_score = safe_float(row.get("Fundamental Score"))
    valuation_score = safe_float(row.get("Valuation Score"))
    crv = safe_float(row.get("CRV"))
    risk_level = str(row.get("Risk Level", ""))
    action_signal = str(row.get("Action Signal", ""))

    total = 0

    if tech_score is not None:
        total += max(0, min(tech_score, 8)) / 8 * 25

    if fundamental_score is not None:
        total += max(0, min(fundamental_score, 8)) / 8 * 20

    if valuation_score is not None:
        # Valuation Score grob von -5 bis +5 auf 0 bis 20 Punkte normalisieren.
        total += max(0, min((valuation_score + 5) / 10, 1)) * 20

    if crv is not None:
        total += max(0, min(crv / 3, 1)) * 15

    if risk_level == "LOW RISK":
        total += 10
    elif risk_level == "MEDIUM RISK":
        total += 5
    elif risk_level == "HIGH RISK":
        total -= 5

    if "BUY ZONE" in action_signal:
        total += 10
    elif "WATCH" in action_signal:
        total += 5
    elif "OVERHEATED" in action_signal or "TAKE PROFIT" in action_signal:
        total += 0
    elif "SELL" in action_signal or "AVOID" in action_signal:
        total -= 10

    total = int(round(max(0, min(total, 100))))

    if total >= 80:
        grade = "A · Stark"
        summary = "Sehr starkes Gesamtbild aus Signal, Qualität, Bewertung und Risiko."
    elif total >= 65:
        grade = "B · Interessant"
        summary = "Interessantes Setup, aber einzelne Punkte sollten geprüft werden."
    elif total >= 50:
        grade = "C · Beobachten"
        summary = "Gemischtes Bild. Eher Watchlist als klare Aktion."
    elif total >= 35:
        grade = "D · Schwach"
        summary = "Viele Signale sind noch nicht überzeugend. Vorsichtig bleiben."
    else:
        grade = "E · Meiden"
        summary = "Schwaches Gesamtbild oder zu viele Risikofaktoren."

    return pd.Series({
        "Terminal Score": total,
        "Terminal Grade": grade,
        "Terminal Summary": summary
    })


terminal_columns = df.apply(
    build_terminal_score,
    axis=1
)

df = pd.concat(
    [df, terminal_columns],
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
    "Operating Cashflow",
    "EQS Latest Title",
    "EQS Latest Date",
    "EQS Latest Source",
    "EQS Link",
    "EQS Search Query",
    "EQS Keywords",
    "EQS Signal",
    "News Momentum Signal"
]

for column in display_text_columns:
    if column in df.columns:
        df[column] = df[column].astype(str)


# ============================================================
# ℹ️ TABELLEN-HILFETEXTE / SPALTEN-TOOLTIPS
# ============================================================

COLUMN_HELP_TEXTS = {
    "Ticker": "Yahoo-Finance-Ticker beziehungsweise Börsenkürzel der Aktie, des ETFs oder des Basiswertes.",
    "Company": "Name des Unternehmens oder Fonds.",
    "Name": "Bezeichnung des Marktindikators, Rohstoffs, ETFs oder Datenpunkts.",
    "Currency": "Währung, in der Kurs- und Preisangaben interpretiert werden. Wird teils aus Yahoo-Daten oder Ticker-Suffix abgeleitet.",
    "Price": "Letzter verfügbarer Kurs aus der Analyse-Datei beziehungsweise aus Yahoo Finance.",
    "Last": "Letzter abgerufener Schlusskurs oder aktueller letzter Wert des jeweiligen Instruments.",
    "Rating": "Technische Ampelbewertung aus der Dashboard-Logik. Sie fasst mehrere technische Signale grob zusammen.",
    "Risk Level": "Einschätzung des Risikos aus Volatilität, Trendlage und weiteren Dashboard-Regeln.",
    "Score": "Technischer Score des Dashboards. Höhere Werte sprechen für ein stärkeres technisches Bild.",
    "Action Signal": "Regelbasiertes Handlungssignal des Dashboards, z. B. BUY ZONE, WATCH, TAKE PROFIT oder SELL / AVOID.",
    "Action Sort": "Interner Sortierwert für die Reihenfolge der Action-Signale.",
    "Strategy Mode": "Gewählter Anlagehorizont: kurzfristig, mittelfristig oder langfristig.",
    "Setup Quality": "Kurzbeschreibung der Qualität des aktuellen Setups, abhängig vom gewählten Strategie-Horizont.",
    "Terminal Score": "Gesamtscore von 0 bis 100 aus Technik, Fundamentaldaten, Bewertung, CRV, Risiko und Signal.",
    "Terminal Grade": "Kurzlabel zum Terminal Score, z. B. A · Stark oder C · Beobachten.",
    "Terminal Summary": "Kurzes Fazit zum Terminal Score und zur Gesamtlage der Aktie.",
    "Valuation Status": "Regelbasierte Bewertungseinordnung: eher unterbewertet, fair, fair bis leicht teuer oder eher überbewertet.",
    "Valuation Score": "Punktwert der Bewertungslogik. Positive Werte sprechen eher für attraktive Bewertung, negative für teuer/anspruchsvoll.",
    "Valuation Reasons": "Gründe, warum das Dashboard die Bewertung so einordnet, z. B. KGV, PEG, Wachstum, Marge oder Cashflow.",
    "Valuation Summary": "Kurze Zusammenfassung der Bewertungseinordnung.",
    "RSI": "Relative-Stärke-Index. Unter 30 oft überverkauft, über 70 oft überkauft; kein alleiniges Kaufsignal.",
    "EMA20": "Exponentieller gleitender Durchschnitt über 20 Tage. Hilft bei kurzfristiger Trendbeurteilung.",
    "EMA50": "Exponentieller gleitender Durchschnitt über 50 Tage. Hilft bei mittelfristiger Trendbeurteilung.",
    "EMA100": "Exponentieller gleitender Durchschnitt über 100 Tage. Hilft bei längerer Trendbeurteilung.",
    "SMA20": "Einfacher gleitender Durchschnitt über 20 Tage.",
    "SMA50": "Einfacher gleitender Durchschnitt über 50 Tage.",
    "SMA200": "Einfacher gleitender Durchschnitt über 200 Tage. Häufig als langfristiger Trendfilter genutzt.",
    "Trend": "Trendstatus im Verhältnis zu gleitenden Durchschnitten oder Momentum-Regeln.",
    "Signal": "Kurzsignal für den jeweiligen Datensatz, z. B. Risk-On, Stress, neutral oder Swing Long prüfen.",
    "1D %": "Performance gegenüber dem vorherigen Handelstag.",
    "5D %": "Performance der letzten ungefähr fünf Handelstage.",
    "1W %": "Performance der letzten ungefähr einen Woche.",
    "7D %": "Performance der letzten sieben Tage.",
    "24H %": "Performance der letzten 24 Stunden. Besonders relevant für Bitcoin/Krypto.",
    "1M %": "Performance der letzten ungefähr 21 Handelstage beziehungsweise eines Monats.",
    "3M %": "Performance der letzten ungefähr drei Monate.",
    "6M %": "Performance der letzten ungefähr sechs Monate.",
    "Dividend Yield %": "Dividendenrendite in Prozent. Hohe Werte sollten immer auf Nachhaltigkeit geprüft werden.",
    "Dividend Rate": "Erwartete oder zuletzt gemeldete jährliche Dividende je Aktie, soweit Yahoo Daten liefert.",
    "Ex Dividend Date": "Datum, ab dem die Aktie ohne Anspruch auf die nächste Dividende gehandelt wird.",
    "Dividend Year": "Jahr des Ex-Dividenden-Datums.",
    "Dividend Month": "Monat des Ex-Dividenden-Datums.",
    "Forward PE": "Erwartetes Kurs-Gewinn-Verhältnis auf Basis zukünftiger Gewinnschätzungen.",
    "Trailing PE": "Kurs-Gewinn-Verhältnis auf Basis vergangener Gewinne.",
    "PEG Ratio": "KGV im Verhältnis zum Wachstum. Niedrigere Werte können auf attraktivere Bewertung hindeuten.",
    "Revenue Growth": "Umsatzwachstum. Positive Werte zeigen steigende Erlöse.",
    "Earnings Growth": "Gewinnwachstum. Positive Werte zeigen steigende Gewinne.",
    "Profit Margin": "Gewinnmarge. Zeigt, wie viel vom Umsatz als Gewinn übrig bleibt.",
    "Debt To Equity": "Verschuldung im Verhältnis zum Eigenkapital. Sehr hohe Werte können riskant sein.",
    "Free Cashflow": "Freier Cashflow. Positiv ist grundsätzlich ein Qualitätsmerkmal.",
    "Operating Cashflow": "Operativer Cashflow aus dem Kerngeschäft.",
    "Fundamental Score": "Fundamentaler Score aus Kennzahlen wie Wachstum, Marge, Cashflow und Verschuldung.",
    "Fundamental Rating": "Textbewertung der Fundamentaldaten, z. B. SOLID oder WEAK / UNKNOWN.",
    "Fundamental Pros": "Positive fundamentale Auffälligkeiten aus der Analyse.",
    "Fundamental Cons": "Negative fundamentale Auffälligkeiten aus der Analyse.",
    "Pros": "Positive Argumente, die das Dashboard aus Technik, Bewertung und Fundamentaldaten ableitet.",
    "Cons": "Kritische Punkte, die das Dashboard aus Technik, Bewertung und Fundamentaldaten ableitet.",
    "Decision Summary": "Kurzes regelbasiertes Fazit zum aktuellen Setup.",
    "Entry Zone": "Grobe Einstiegszone um den aktuellen Kurs, abhängig vom gewählten Strategie-Horizont.",
    "Stop Loss New": "Regelbasiertes Stop-Loss-Niveau aus Preis und gleitenden Durchschnitten.",
    "Target 1": "Erstes regelbasiertes Kursziel, häufig auf 52W-Hoch oder Fallback-Ziel basiert.",
    "Target 2": "Zweites regelbasiertes Kursziel mit größerem Abstand.",
    "Target Basis": "Erklärung, ob das Kursziel z. B. auf dem 52W-Hoch oder einem Fallback-Modell basiert.",
    "CRV": "Chance-Risiko-Verhältnis. Werte über 1 bedeuten mehr potenzieller Gewinn als Risiko bis Stop-Loss.",
    "52W High": "Höchster Kurs der letzten 52 Wochen.",
    "52W Low": "Niedrigster Kurs der letzten 52 Wochen.",
    "Turnaround Candidate": "Markierung, ob das Dashboard eine mögliche Trendwende erkennt.",
    "Bereich": "Gruppierung des Marktindikators, z. B. Markt-Kern oder Rohstoffe / Themen.",
    "Volume Ratio": "Aktuelles Volumen im Verhältnis zum 20-Tage-Durchschnitt. Werte über 1,5 zeigen erhöhtes Marktinteresse.",
    "EQS News Count 14D": "Anzahl gefundener EQS-News-Treffer über Google News RSS in den letzten 14 Tagen.",
    "EQS Latest Title": "Neueste gefundene EQS-Schlagzeile zur Aktie. Treffer können je nach Google-Index verzögert oder unvollständig sein.",
    "EQS Latest Date": "Veröffentlichungszeitpunkt des neuesten EQS-Treffers, soweit Google News ihn liefert.",
    "EQS Latest Source": "Quelle des neuesten EQS-Treffers laut Google News RSS.",
    "EQS Link": "Link zur gefundenen EQS-News beziehungsweise zum Google-News-Treffer.",
    "EQS Search Query": "Verwendete Suchabfrage für die EQS-Suche über Google News RSS.",
    "EQS News Score": "Regelbasierter Keyword-Score der gefundenen EQS-Schlagzeilen. Positive Keywords wie Auftrag, Prognose angehoben oder Finanzierung erhöhen den Score; Warnwörter senken ihn.",
    "EQS Keywords": "Gefundene Signalwörter aus den EQS-Schlagzeilen, z. B. Auftrag, Finanzierung, Defence oder Verlustwarnung.",
    "EQS Signal": "Textsignal aus EQS-News-Score und Trefferanzahl. Es ist ein Katalysator-Hinweis, keine Kaufempfehlung.",
    "News Momentum Score": "Kombinierter Score aus EQS-News, Kursbewegung, Volumen, RSI und EMA20. Höher bedeutet: Bewegung plus News-Kontext ist auffällig.",
    "News Momentum Signal": "Frühwarnsignal für mögliche News-/Momentum-Bewegungen. Es zeigt Aufmerksamkeit, nicht automatisch Kaufen.",
    "Ticker ETF": "ETF-Ticker, der bei Yahoo Finance abgefragt wird.",
    "ETF": "Name oder Ticker des ETFs.",
    "Swing Score": "ETF-Swing-Score von 0 bis 10. Höhere Werte sprechen für ein stärkeres Swing-Setup.",
    "Swing Signal": "Regelbasiertes ETF-Swing-Signal, z. B. Long prüfen, Watch oder kein Long-Setup.",
    "Volume vs Avg": "Aktuelles Volumen im Verhältnis zum Durchschnitt. Auffällige Werte zeigen erhöhtes Interesse.",
    "Beta": "Schwankungsanfälligkeit im Verhältnis zum Markt. Über 1 meist volatiler als der Markt.",
    "Earnings Date": "Nächstes oder zuletzt bekanntes Earnings-Datum aus Yahoo/yfinance, soweit verfügbar.",
    "Days Until": "Anzahl Tage bis zum Earnings-Termin. Negative oder fehlende Werte bedeuten keine klare Zukunftsangabe.",
    "Time": "Zeitpunkt der Earnings, z. B. vor oder nach Börsenschluss, soweit verfügbar.",
    "EPS Estimate": "Erwarteter Gewinn je Aktie laut verfügbaren Yahoo-Schätzdaten.",
    "Revenue Estimate": "Erwarteter Umsatz laut verfügbaren Yahoo-Schätzdaten.",
    "Data Source": "Quelle oder Status der Datenabfrage, z. B. Earnings-Dates oder Calendar.",
    "Short Info": "Kompakte Zusammenfassung wichtiger Aktien-Signale im Earnings-Kontext.",
    "Quelle": "Datei oder Datenquelle, die für den Datenstand geprüft wird.",
    "Status": "Status der Datenquelle, z. B. OK oder Fehlt.",
    "Echter Datenstand": "Erkannter echter Aktualisierungszeitpunkt, soweit über Meta-Datei oder Inhaltsänderung feststellbar.",
    "Quelle der Zeit": "Erklärung, woher der angezeigte Datenstand kommt.",
    "Cloud-Dateizeit": "Technische Dateiänderungszeit auf Streamlit Cloud. Kann durch Deployment verfälscht sein.",
    "Liste": "Zeigt, ob ein Wert auf Watchlist, Kaufliste oder beiden Listen liegt.",
    "User": "Nutzer, zu dem der Listeneintrag gehört.",
    "Gespeichert am": "Zeitpunkt, zu dem der Listeneintrag gespeichert wurde.",
    "Prüfung": "System- oder Datenqualitätsprüfung im Adminbereich.",
    "BTC Ticker": "Bitcoin-Ticker, der über Yahoo Finance abgefragt wird, z. B. BTC-USD oder BTC-EUR.",
    "Bitcoin Score": "Regelbasierter Bitcoin-Score aus Momentum, Trend und RSI.",
    "Bitcoin Signal": "Regelbasierte Einschätzung für Bitcoin, z. B. bullisch, neutral oder schwach.",
}


def get_column_help(column_name):
    """Gibt einen kurzen Hilfetext für eine Tabellen-Spalte zurück."""
    column = str(column_name)
    if column in COLUMN_HELP_TEXTS:
        return COLUMN_HELP_TEXTS[column]

    # Fallbacks für häufige Spaltenmuster, damit wirklich jede Überschrift einen Hilfetext bekommt.
    lowered = column.lower()
    if "%" in column or "performance" in lowered:
        return "Performance- oder Prozentwert. Positive Werte sprechen für steigende Kurse, negative für fallende Kurse."
    if "score" in lowered:
        return "Regelbasierter Score des Dashboards. Höhere Werte sind grundsätzlich besser, sollten aber im Kontext geprüft werden."
    if "signal" in lowered:
        return "Regelbasiertes Signal aus der Dashboard-Logik. Es dient als Orientierung, nicht als alleinige Entscheidung."
    if "date" in lowered or "datum" in lowered:
        return "Datumsangabe aus der Analyse-Datei oder aus Yahoo/yfinance, soweit verfügbar."
    if "price" in lowered or "kurs" in lowered:
        return "Kurs- oder Preisangabe aus den verfügbaren Marktdaten."
    if "yield" in lowered or "dividend" in lowered:
        return "Dividendenbezogene Kennzahl. Hohe Werte sollten immer auf Nachhaltigkeit geprüft werden."
    if "risk" in lowered:
        return "Risikobezogene Einordnung aus der Dashboard-Logik."
    return "Zusatzspalte aus der Analyse- oder Datenquelle. Sie dient als ergänzende Information für die Einordnung."


def build_column_help_config(table_data):
    """Erzeugt Streamlit-Spaltenkonfiguration mit Hilfe-Tooltip für jede vorhandene Spalte."""
    try:
        if isinstance(table_data, pd.DataFrame):
            columns = list(table_data.columns)
        else:
            return {}

        return {
            column: st.column_config.Column(
                label=str(column),
                help=get_column_help(column)
            )
            for column in columns
        }
    except Exception:
        return {}


def smart_dataframe(table_data, **kwargs):
    """st.dataframe mit automatischen Spalten-Hilfetexten."""
    if "column_config" not in kwargs:
        kwargs["column_config"] = build_column_help_config(table_data)
    return st.dataframe(table_data, **kwargs)

# ============================================================
# 📆 EARNINGS-KALENDER HILFSFUNKTIONEN
# ============================================================

def _format_earnings_date(value):
    """Normalisiert Earnings-Daten aus unterschiedlichen Yahoo/yfinance-Formaten."""
    try:
        if value is None or value == "" or pd.isna(value):
            return None
    except Exception:
        pass

    try:
        if isinstance(value, (list, tuple)) and len(value) > 0:
            value = value[0]

        dt = pd.to_datetime(value, errors="coerce")

        if pd.isna(dt):
            return None

        if hasattr(dt, "tz_convert"):
            try:
                dt = dt.tz_convert(None)
            except Exception:
                try:
                    dt = dt.tz_localize(None)
                except Exception:
                    pass

        return dt

    except Exception:
        return None


def _format_estimate_value(value, suffix=""):
    """Formatiert Schätzwerte kompakt."""
    try:
        if value is None or pd.isna(value):
            return "-"

        numeric = float(value)

        if abs(numeric) >= 1_000_000_000:
            return f"{numeric / 1_000_000_000:.2f} Mrd.{suffix}"

        if abs(numeric) >= 1_000_000:
            return f"{numeric / 1_000_000:.2f} Mio.{suffix}"

        return f"{numeric:.2f}{suffix}"

    except Exception:
        if value in [None, "", "nan", "None"]:
            return "-"
        return str(value)


def _extract_estimate_from_frame(frame):
    """Versucht aus yfinance-Schätztabellen den aktuellen Durchschnittswert zu ziehen."""
    try:
        if frame is None or frame.empty:
            return None

        candidate_rows = [
            "current qtr", "current quarter", "0q",
            "next qtr", "next quarter", "+1q"
        ]
        candidate_cols = ["avg", "Avg", "Average", "average"]

        lower_index = {str(idx).strip().lower(): idx for idx in frame.index}

        for row_name in candidate_rows:
            if row_name in lower_index:
                row_idx = lower_index[row_name]
                for col in candidate_cols:
                    if col in frame.columns:
                        return frame.loc[row_idx, col]

        for col in candidate_cols:
            if col in frame.columns and len(frame[col].dropna()) > 0:
                return frame[col].dropna().iloc[0]

    except Exception:
        return None

    return None


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_earnings_snapshot(ticker):
    """
    Holt Earnings-Datum und Schätzwerte pro Ticker.
    Daten kommen über yfinance/Yahoo Finance und können je nach Börsenplatz fehlen.
    """

    result = {
        "ticker": ticker,
        "earnings_date": None,
        "earnings_time": "-",
        "eps_estimate": "-",
        "revenue_estimate": "-",
        "source_status": "keine Daten",
    }

    try:
        ticker_object = yf.Ticker(ticker)

        # 1) Hauptquelle: Earnings-Dates-Tabelle
        try:
            earnings_dates = ticker_object.get_earnings_dates(limit=12)

            if earnings_dates is not None and not earnings_dates.empty:
                dates_frame = earnings_dates.copy()
                dates_frame = dates_frame.reset_index()

                date_column = dates_frame.columns[0]
                dates_frame["_parsed_date"] = pd.to_datetime(
                    dates_frame[date_column],
                    errors="coerce"
                )

                today_ts = pd.Timestamp.today().normalize()
                future_dates = dates_frame[dates_frame["_parsed_date"] >= today_ts].copy()

                if not future_dates.empty:
                    selected_row = future_dates.sort_values("_parsed_date").iloc[0]
                else:
                    selected_row = dates_frame.sort_values("_parsed_date", ascending=False).iloc[0]

                result["earnings_date"] = _format_earnings_date(selected_row.get("_parsed_date"))

                for eps_col in ["EPS Estimate", "epsEstimate", "EPS Est."]:
                    if eps_col in selected_row.index and not pd.isna(selected_row.get(eps_col)):
                        result["eps_estimate"] = _format_estimate_value(selected_row.get(eps_col))
                        break

                for time_col in ["Time", "time"]:
                    if time_col in selected_row.index and not pd.isna(selected_row.get(time_col)):
                        result["earnings_time"] = str(selected_row.get(time_col))
                        break

                result["source_status"] = "Earnings-Dates"

        except Exception:
            pass

        # 2) Fallback: calendar dict
        if result["earnings_date"] is None:
            try:
                calendar_data = ticker_object.calendar

                if isinstance(calendar_data, dict):
                    earnings_date = (
                        calendar_data.get("Earnings Date")
                        or calendar_data.get("EarningsDate")
                        or calendar_data.get("earningsDate")
                    )
                    parsed_date = _format_earnings_date(earnings_date)

                    if parsed_date is not None:
                        result["earnings_date"] = parsed_date
                        result["source_status"] = "Calendar"

                    eps_average = (
                        calendar_data.get("Earnings Average")
                        or calendar_data.get("EarningsAverage")
                    )

                    if eps_average is not None and result["eps_estimate"] == "-":
                        result["eps_estimate"] = _format_estimate_value(eps_average)

                    revenue_average = (
                        calendar_data.get("Revenue Average")
                        or calendar_data.get("RevenueAverage")
                    )

                    if revenue_average is not None:
                        result["revenue_estimate"] = _format_estimate_value(revenue_average)

            except Exception:
                pass

        # 3) Zusatz: EPS-/Umsatz-Schätzungen, falls verfügbar
        try:
            earnings_estimate = ticker_object.get_earnings_estimate()
            eps_estimate = _extract_estimate_from_frame(earnings_estimate)

            if eps_estimate is not None and result["eps_estimate"] == "-":
                result["eps_estimate"] = _format_estimate_value(eps_estimate)
        except Exception:
            pass

        try:
            revenue_estimate = ticker_object.get_revenue_estimate()
            revenue_avg = _extract_estimate_from_frame(revenue_estimate)

            if revenue_avg is not None and result["revenue_estimate"] == "-":
                result["revenue_estimate"] = _format_estimate_value(revenue_avg)
        except Exception:
            pass

    except Exception as error:
        result["source_status"] = f"Fehler: {error}"

    return result


def build_earnings_calendar(universe_df, max_tickers):
    """Baut einen Earningskalender für die angezeigte/gewählte Aktienmenge."""

    if universe_df.empty or "Ticker" not in universe_df.columns:
        return pd.DataFrame()

    ticker_frame = universe_df.dropna(subset=["Ticker"]).copy()
    ticker_frame["Ticker"] = ticker_frame["Ticker"].astype(str).str.strip()
    ticker_frame = ticker_frame.drop_duplicates(subset=["Ticker"]).head(max_tickers)

    rows = []

    progress = st.progress(0, text="Earningskalender wird aktualisiert...")
    total = len(ticker_frame)

    for idx, (_, stock_row) in enumerate(ticker_frame.iterrows(), start=1):
        ticker = str(stock_row.get("Ticker", "")).strip()

        if ticker:
            snapshot = fetch_earnings_snapshot(ticker)
            earnings_date = snapshot.get("earnings_date")

            if earnings_date is not None:
                days_until = (pd.Timestamp(earnings_date).normalize() - pd.Timestamp.today().normalize()).days
                earnings_date_text = pd.Timestamp(earnings_date).strftime("%d.%m.%Y")
            else:
                days_until = None
                earnings_date_text = "-"

            rows.append({
                "Ticker": ticker,
                "Company": stock_row.get("Company", ticker),
                "Earnings Date": earnings_date_text,
                "Days Until": days_until if days_until is not None else "-",
                "Time": snapshot.get("earnings_time", "-"),
                "EPS Estimate": snapshot.get("eps_estimate", "-"),
                "Revenue Estimate": snapshot.get("revenue_estimate", "-"),
                "Action Signal": stock_row.get("Action Signal", "-"),
                "Terminal Grade": stock_row.get("Terminal Grade", "-"),
                "Terminal Score": stock_row.get("Terminal Score", "-"),
                "Valuation Status": stock_row.get("Valuation Status", "-"),
                "Setup Quality": stock_row.get("Setup Quality", "-"),
                "Risk Level": stock_row.get("Risk Level", "-"),
                "Short Info": (
                    f"{stock_row.get('Action Signal', '-')} | "
                    f"{stock_row.get('Valuation Status', '-')} | "
                    f"Setup: {stock_row.get('Setup Quality', '-')} | "
                    f"Risiko: {stock_row.get('Risk Level', '-')}"
                ),
                "Data Source": snapshot.get("source_status", "-"),
            })

        progress.progress(idx / total if total else 1, text=f"Earningskalender: {idx}/{total} Aktien geprüft")

    progress.empty()

    earnings_df = pd.DataFrame(rows)

    if earnings_df.empty:
        return earnings_df

    earnings_df["_sort_days"] = pd.to_numeric(earnings_df["Days Until"], errors="coerce")
    earnings_df = earnings_df.sort_values(
        by=["_sort_days", "Ticker"],
        ascending=[True, True],
        na_position="last"
    ).drop(columns=["_sort_days"])

    return earnings_df



# ============================================================
# 🐋 MARKT-TACHO / SMART-MONEY-LIGHT
# ============================================================

MARKET_SIGNAL_TICKERS = {
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "^VIX": "VIX Volatilität",
    "HYG": "High-Yield Bonds",
    "TLT": "US Langläufer-Bonds",
    "DX-Y.NYB": "US-Dollar Index",
    "GC=F": "Gold Future",
    "SI=F": "Silber Future",
    "CL=F": "WTI Öl Future",
    "NG=F": "Erdgas Future",
    "HG=F": "Kupfer Future",
    "PL=F": "Platin Future",
    "PA=F": "Palladium Future",
    "CC=F": "Kakao Future",
    "KC=F": "Kaffee Future",
    "DBA": "Agrarrohstoffe ETF",
    "URA": "Uran ETF",
    "LIT": "Lithium/Battery ETF"
}


def _pct_change_safe(series, periods):
    try:
        series = series.dropna()
        if len(series) <= periods:
            return None
        old = float(series.iloc[-periods - 1])
        new = float(series.iloc[-1])
        if old == 0:
            return None
        return ((new / old) - 1) * 100
    except Exception:
        return None


def _fetch_market_history(ticker, period="1y"):
    """Robuster yfinance-Download für Marktindikatoren."""
    try:
        hist = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
        if hist is not None and not hist.empty and "Close" in hist.columns and hist["Close"].dropna().shape[0] >= 5:
            return hist
    except Exception:
        pass

    try:
        hist = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=False, threads=False)
        if hist is not None and not hist.empty:
            if isinstance(hist.columns, pd.MultiIndex):
                # yfinance kann bei download MultiIndex-Spalten liefern
                if ("Close", ticker) in hist.columns:
                    hist = pd.DataFrame({"Close": hist[("Close", ticker)]})
                elif "Close" in hist.columns.get_level_values(0):
                    close_part = hist.xs("Close", axis=1, level=0)
                    hist = pd.DataFrame({"Close": close_part.iloc[:, 0]})
            if "Close" in hist.columns and hist["Close"].dropna().shape[0] >= 5:
                return hist
    except Exception:
        pass

    return pd.DataFrame()


@st.cache_data(ttl=60 * 60)
def load_market_mode_data():
    """Lädt Marktindikatoren und trennt Markt-Tacho von Rohstoff-Stress.

    Idee:
    - Der Markt-Tacho bewertet nur Kernsignale: Aktienindizes, VIX, High-Yield, Bonds, US-Dollar.
    - Rohstoffe liefern eigene Stress-/Inflationshinweise, drücken den Tacho aber nicht allein auf Panik.
    """

    rows = []
    market_points = 0
    commodity_points = 0
    notes = []
    market_notes = []
    commodity_notes = []

    core_tickers = {"SPY", "QQQ", "^VIX", "HYG", "TLT", "DX-Y.NYB"}

    for ticker, name in MARKET_SIGNAL_TICKERS.items():
        group = "Markt-Kern" if ticker in core_tickers else "Rohstoffe / Themen"
        row = {
            "Bereich": group,
            "Ticker": ticker,
            "Name": name,
            "Last": "-",
            "1M %": "-",
            "Trend": "Unklar",
            "Signal": "Neutral"
        }

        try:
            hist = _fetch_market_history(ticker, period="1y")
            if hist is None or hist.empty or "Close" not in hist.columns:
                rows.append(row)
                continue

            close = hist["Close"].dropna()
            if close.empty:
                rows.append(row)
                continue

            last = float(close.iloc[-1])
            sma50 = float(close.tail(50).mean()) if len(close) >= 50 else None
            sma200 = float(close.tail(200).mean()) if len(close) >= 200 else None
            perf_1m = _pct_change_safe(close, 21)

            row["Last"] = round(last, 2)
            row["1M %"] = round(perf_1m, 2) if perf_1m is not None else "-"

            above_50 = sma50 is not None and last >= sma50
            above_200 = sma200 is not None and last >= sma200

            if ticker == "^VIX":
                row["Trend"] = "Volatilität"
                if last >= 30:
                    row["Signal"] = "Stress"
                    market_points += 3
                    market_notes.append("VIX über 30: echter Marktstress erhöht")
                elif last >= 25:
                    row["Signal"] = "Risk-Off"
                    market_points += 2
                    market_notes.append("VIX über 25: Risikoappetit deutlich vorsichtiger")
                elif last >= 20:
                    row["Signal"] = "Erhöht"
                    market_points += 1
                    market_notes.append("VIX über 20: Volatilität erhöht")
                elif last <= 16:
                    row["Signal"] = "Ruhig"
                    market_points -= 1
                else:
                    row["Signal"] = "Normal"

            elif ticker in ["SPY", "QQQ"]:
                if above_50 and above_200:
                    row["Signal"] = "Risk-On"
                    market_points -= 2 if ticker == "SPY" else 1
                    row["Trend"] = "über SMA50/200"
                elif (not above_50) and above_200:
                    row["Signal"] = "Pullback / Abkühlung"
                    market_points += 1
                    market_notes.append(f"{ticker} unter SMA50, aber über SMA200: Pullback statt Panik")
                    row["Trend"] = "unter SMA50, über SMA200"
                elif not above_200 and sma200 is not None:
                    row["Signal"] = "Risk-Off"
                    market_points += 3 if ticker == "SPY" else 2
                    market_notes.append(f"{ticker} unter SMA200: mittelfristiges Trendrisiko erhöht")
                    row["Trend"] = "unter SMA200"
                else:
                    row["Signal"] = "Unklar"
                    row["Trend"] = "zu wenig Daten"

            elif ticker == "HYG":
                if above_50:
                    row["Signal"] = "Credit stabil"
                    market_points -= 1
                    row["Trend"] = "über SMA50"
                else:
                    row["Signal"] = "Credit vorsichtig"
                    market_points += 1
                    market_notes.append("High-Yield unter SMA50: Kreditrisiko beobachten")
                    row["Trend"] = "unter SMA50"

            elif ticker == "TLT":
                row["Trend"] = "über SMA50" if above_50 else "unter SMA50"
                if above_50 and perf_1m is not None and perf_1m > 4:
                    row["Signal"] = "Sicherheitsnachfrage"
                    market_points += 1
                    market_notes.append("US-Langläufer stark: Sicherheitsnachfrage / fallende Renditen beachten")
                elif above_50:
                    row["Signal"] = "Bonds stabil"
                else:
                    row["Signal"] = "Bonds schwach"

            elif ticker == "DX-Y.NYB":
                row["Trend"] = "1M Momentum"
                if perf_1m is not None and perf_1m > 3:
                    row["Signal"] = "Dollar-Stärke"
                    market_points += 1
                    market_notes.append("US-Dollar steigt deutlich: Gegenwind für Emerging Markets/Rohstoffe möglich")
                elif perf_1m is not None and perf_1m < -3:
                    row["Signal"] = "Dollar schwächer"
                    market_points -= 1
                else:
                    row["Signal"] = "Neutral"

            elif ticker in ["GC=F", "SI=F", "PL=F", "PA=F"]:
                row["Trend"] = "über SMA50" if above_50 else "unter SMA50"
                if above_50 and perf_1m is not None and perf_1m > 5:
                    row["Signal"] = "Edelmetall-Stärke"
                    commodity_points += 1
                    commodity_notes.append(f"{name} stark: Sicherheits-/Inflationssignal beobachten")
                elif above_50:
                    row["Signal"] = "Stabil / gefragt"
                else:
                    row["Signal"] = "Schwach"

            elif ticker in ["CL=F", "NG=F"]:
                row["Trend"] = "1M Momentum"
                if perf_1m is not None and perf_1m > 10:
                    row["Signal"] = "Energiepreis-Stress"
                    commodity_points += 2
                    commodity_notes.append(f"{name} stark gestiegen: Inflations-/Energieeffekt beachten")
                elif perf_1m is not None and perf_1m < -10:
                    row["Signal"] = "Energie schwach"
                    commodity_points -= 1
                elif above_50:
                    row["Signal"] = "Stabil"
                else:
                    row["Signal"] = "Neutral"

            elif ticker in ["HG=F", "URA", "LIT"]:
                row["Trend"] = "über SMA50" if above_50 else "unter SMA50"
                if above_50 and perf_1m is not None and perf_1m > 5:
                    row["Signal"] = "Wachstum / Nachfrage stark"
                    commodity_points -= 1
                elif perf_1m is not None and perf_1m < -8:
                    row["Signal"] = "Nachfrage schwach"
                    commodity_points += 1
                    commodity_notes.append(f"{name} schwach: zyklische Nachfrage beobachten")
                elif above_50:
                    row["Signal"] = "Stabil"
                else:
                    row["Signal"] = "Neutral"

            elif ticker in ["CC=F", "KC=F", "DBA"]:
                row["Trend"] = "1M Momentum"
                if perf_1m is not None and perf_1m > 10:
                    row["Signal"] = "Agrarpreis-Stress"
                    commodity_points += 1
                    commodity_notes.append(f"{name} stark: Nahrungsmittel-/Inflationssignal beobachten")
                elif perf_1m is not None and perf_1m < -10:
                    row["Signal"] = "Agrar schwach"
                elif above_50:
                    row["Signal"] = "Stabil"
                else:
                    row["Signal"] = "Neutral"

        except Exception:
            pass

        rows.append(row)

    # Markt-Level: bewusst nur Kernsignale. Rohstoffe werden separat ausgewiesen.
    if market_points <= -3:
        level = 1
        label = "🟢 Risk-On"
        interpretation = "Aktien-/Kredit-/Vola-Signale wirken konstruktiv. Gute Setups können aktiver geprüft werden."
    elif market_points <= -1:
        level = 2
        label = "🟢 Vorsichtig bullisch"
        interpretation = "Marktbild ist eher freundlich, aber nicht völlig risikofrei. Pullbacks können interessant sein."
    elif market_points <= 2:
        level = 3
        label = "🟡 Neutral / gemischt"
        interpretation = "Gemischtes Umfeld. Einzelaktien zählen, Positionsgröße und Risiko beachten."
    elif market_points <= 5:
        level = 4
        label = "🟠 Risk-Off"
        interpretation = "Marktrisiko erhöht. Neue Käufe strenger prüfen und schwache Setups meiden."
    else:
        level = 5
        label = "🔴 Stress / Panik"
        interpretation = "Kernmarkt-Signale zeigen Stress. Kapitalerhalt, Cash und defensive Sektoren priorisieren."

    if commodity_points <= 0:
        commodity_status = "🟢 niedrig / normal"
        commodity_interpretation = "Rohstoffe liefern aktuell keinen dominanten Zusatzstress."
    elif commodity_points <= 2:
        commodity_status = "🟡 erhöht"
        commodity_interpretation = "Einzelne Rohstoffe zeigen Preis-/Inflationsdruck. Als Warnhinweis beobachten, aber nicht als Paniksignal werten."
    else:
        commodity_status = "🟠 hoch"
        commodity_interpretation = "Mehrere Rohstoffe senden Stress-/Inflationssignale. Das kann Margen, Konsum und Zinserwartungen belasten."

    notes = (market_notes + commodity_notes)[:8]

    return {
        "level": level,
        "label": label,
        "interpretation": interpretation,
        "risk_points": market_points,
        "market_points": market_points,
        "commodity_points": commodity_points,
        "commodity_status": commodity_status,
        "commodity_interpretation": commodity_interpretation,
        "notes": notes,
        "market_notes": market_notes[:5],
        "commodity_notes": commodity_notes[:5],
        "details": rows
    }


def render_market_gauge(level, label):
    """Rendert einen einfachen 5-Stufen-Tacho als kompaktes HTML.

    Wichtig: Die Segment-HTMLs werden bewusst ohne eingerückte Mehrzeilen-Strings
    gebaut. Sonst interpretiert Streamlit/Markdown sie gelegentlich als Codeblock.
    """

    colors = ["#16a34a", "#22c55e", "#eab308", "#f97316", "#dc2626"]
    names = ["Risk-On", "Bullisch", "Neutral", "Risk-Off", "Stress"]

    segments = []

    for i in range(1, 6):
        active = i == level
        bg_color = colors[i - 1] if active else "#1e293b"
        font_weight = "850" if active else "600"
        border_color = "rgba(248,250,252,0.75)" if active else "rgba(148,163,184,0.28)"

        segments.append(
            "<div style=\"flex:1; padding:10px 8px; border-radius:12px; "
            f"text-align:center; background:{bg_color}; color:#f8fafc; "
            f"border:1px solid {border_color}; font-weight:{font_weight};\">"
            f"<div style=\"font-size:18px; line-height:1.1;\">{i}</div>"
            f"<div style=\"font-size:11px; line-height:1.2; margin-top:4px;\">{names[i - 1]}</div>"
            "</div>"
        )

    segments_html = "".join(segments)

    html = (
        "<div style=\"background:linear-gradient(135deg,#020617,#0f172a); "
        "border:1px solid rgba(148,163,184,0.3); border-radius:18px; "
        "padding:16px; margin:6px 0 12px 0;\">"
        "<div style=\"color:#e5e7eb; font-size:13px; font-weight:800; margin-bottom:8px;\">Markt-Tacho</div>"
        f"<div style=\"color:#f8fafc; font-size:25px; font-weight:900; margin-bottom:12px;\">{label}</div>"
        f"<div style=\"display:flex; gap:8px;\">{segments_html}</div>"
        "</div>"
    )

    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# 📈 ETF SWINGTRADE COCKPIT
# ============================================================

ETF_SWING_DEFAULTS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "IWM": "Russell 2000",
    "DIA": "Dow Jones",
    "XLK": "Technology",
    "SMH": "Semiconductors",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "HYG": "High Yield Bonds",
    "TLT": "US Long Bonds",
    "GLD": "Gold",
    "SLV": "Silver",
    "USO": "Oil",
    "URA": "Uranium",
    "LIT": "Lithium/Battery",
    "BOTZ": "Robotics/Automation",
    "ARKK": "Innovation/Growth",
    "EEM": "Emerging Markets",
    "EWJ": "Japan",
    "FXI": "China Large Cap",
    "VGK": "Europe",
    "IEVD.DE": "iShares Electric Vehicles & Driving Technology UCITS ETF",
    "VWCE.DE": "Vanguard FTSE All-World UCITS ETF Acc",
    "VWRL.DE": "Vanguard FTSE All-World UCITS ETF Dist",
    "EUNL.DE": "iShares Core MSCI World UCITS ETF Acc",
    "IWDA.AS": "iShares Core MSCI World UCITS ETF Acc",
    "XDWD.DE": "Xtrackers MSCI World UCITS ETF",
    "IUSQ.DE": "iShares MSCI ACWI UCITS ETF",
    "SXR8.DE": "iShares Core S&P 500 UCITS ETF",
    "DFEN.DE": "VanEck Defense UCITS ETF",
    "DFNS.PA": "VanEck Defense UCITS ETF",
    "L0CK.DE": "iShares Digital Security UCITS ETF",
    "IS3R.DE": "iShares Edge MSCI World Minimum Volatility UCITS ETF",
    "IS3Q.DE": "iShares Edge MSCI World Quality Factor UCITS ETF",
    "EUNA.DE": "iShares Core Global Aggregate Bond UCITS ETF",
    "JEDI.DE": "VanEck Space Innovators UCITS ETF",
    "XAIX.DE": "Xtrackers Artificial Intelligence & Big Data UCITS ETF"
}


def _calc_rsi_from_close(close, period=14):
    try:
        close = close.dropna()
        if len(close) <= period + 1:
            return None
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + rs))
        value = rsi.dropna().iloc[-1]
        return float(value)
    except Exception:
        return None


@st.cache_data(ttl=60 * 60)
def load_etf_swingtrade_data(tickers):
    """Lädt ETF-Daten über yfinance und baut daraus ein einfaches Swingtrade-Radar."""

    rows = []

    for raw_ticker in tickers:
        ticker = str(raw_ticker).strip().upper()
        if not ticker:
            continue

        name = ETF_SWING_DEFAULTS.get(ticker, ticker)
        row = {
            "Ticker": ticker,
            "Name": name,
            "Last": "-",
            "5D %": "-",
            "1M %": "-",
            "3M %": "-",
            "RSI": "-",
            "Trend": "Unklar",
            "Volumen": "-",
            "Swing Score": 0,
            "Signal": "⚪ Daten dünn",
            "Setup-Hinweis": "Zu wenig Daten oder Yahoo liefert keine Werte."
        }

        try:
            hist = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=False)
            if hist is None or hist.empty or "Close" not in hist.columns:
                rows.append(row)
                continue

            close = hist["Close"].dropna()
            if close.empty or len(close) < 60:
                rows.append(row)
                continue

            last = float(close.iloc[-1])
            sma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
            sma50 = float(close.tail(50).mean()) if len(close) >= 50 else None
            sma200 = float(close.tail(200).mean()) if len(close) >= 200 else None
            rsi = _calc_rsi_from_close(close, 14)
            perf_5d = _pct_change_safe(close, 5)
            perf_1m = _pct_change_safe(close, 21)
            perf_3m = _pct_change_safe(close, 63)

            vol_signal = "-"
            volume_ratio = None
            if "Volume" in hist.columns:
                volume = hist["Volume"].dropna()
                if len(volume) >= 21 and float(volume.tail(20).mean()) > 0:
                    volume_ratio = float(volume.iloc[-1]) / float(volume.tail(20).mean())
                    vol_signal = f"{round(volume_ratio, 2)}x Ø20"

            score = 0
            notes = []

            if sma20 is not None and last >= sma20:
                score += 1
                notes.append("über SMA20")
            else:
                notes.append("unter SMA20")

            if sma50 is not None and last >= sma50:
                score += 2
                notes.append("über SMA50")
            else:
                notes.append("unter SMA50")

            if sma200 is not None and last >= sma200:
                score += 2
                notes.append("über SMA200")
            elif sma200 is not None:
                notes.append("unter SMA200")

            if perf_1m is not None:
                if perf_1m > 5:
                    score += 2
                    notes.append("1M Momentum stark")
                elif perf_1m > 0:
                    score += 1
                    notes.append("1M Momentum positiv")
                elif perf_1m < -5:
                    score -= 1
                    notes.append("1M Momentum schwach")

            if perf_3m is not None and perf_3m > 8:
                score += 1
                notes.append("3M Trend stark")

            if rsi is not None:
                if 45 <= rsi <= 68:
                    score += 2
                    notes.append("RSI im Swing-Bereich")
                elif 68 < rsi <= 75:
                    score -= 1
                    notes.append("RSI leicht heiß")
                elif rsi > 75:
                    score -= 2
                    notes.append("RSI überhitzt")
                elif rsi < 35:
                    score -= 1
                    notes.append("RSI schwach")

            if volume_ratio is not None and volume_ratio >= 1.5 and perf_5d is not None and perf_5d > 0:
                score += 1
                notes.append("Volumen bestätigt Anstieg")

            if score >= 7:
                signal = "🟢 Swing Long prüfen"
            elif score >= 4:
                signal = "🟡 Watch / Pullback suchen"
            elif score >= 1:
                signal = "🟠 Neutral / noch warten"
            else:
                signal = "🔴 Kein Long-Setup"

            if rsi is not None and rsi > 75:
                signal = "🟠 Überhitzt / Rücksetzer abwarten"
            if sma50 is not None and last < sma50 and perf_1m is not None and perf_1m < 0:
                signal = "🔴 Kein Long-Setup"

            if sma20 is not None and sma50 is not None and sma200 is not None:
                if last >= sma20 >= sma50:
                    trend = "Kurztrend stark"
                elif last >= sma50 and last >= sma200:
                    trend = "Aufwärtstrend"
                elif last < sma50:
                    trend = "unter SMA50"
                else:
                    trend = "Gemischt"
            else:
                trend = "Gemischt"

            row.update({
                "Last": round(last, 2),
                "5D %": round(perf_5d, 2) if perf_5d is not None else "-",
                "1M %": round(perf_1m, 2) if perf_1m is not None else "-",
                "3M %": round(perf_3m, 2) if perf_3m is not None else "-",
                "RSI": round(rsi, 1) if rsi is not None else "-",
                "Trend": trend,
                "Volumen": vol_signal,
                "Swing Score": int(max(0, min(10, score))),
                "Signal": signal,
                "Setup-Hinweis": " | ".join(notes[:7]) if notes else "Neutral"
            })

        except Exception:
            pass

        rows.append(row)

    result = pd.DataFrame(rows)
    if not result.empty and "Swing Score" in result.columns:
        result = result.sort_values(by="Swing Score", ascending=False)
    return result


# ============================================================
# ₿ BITCOIN COCKPIT
# ============================================================

@st.cache_data(ttl=30 * 60, show_spinner=False)
def load_bitcoin_snapshot(ticker="BTC-USD"):
    """Lädt Bitcoin-Daten über Yahoo/yfinance und erstellt ein regelbasiertes Signal."""

    result = {
        "ticker": ticker,
        "last": None,
        "currency": "USD" if ticker == "BTC-USD" else "EUR" if ticker == "BTC-EUR" else "-",
        "perf_24h": None,
        "perf_7d": None,
        "perf_1m": None,
        "perf_3m": None,
        "rsi": None,
        "sma20": None,
        "sma50": None,
        "sma200": None,
        "score": 0,
        "signal": "⚪ Daten dünn",
        "recommendation": "Zu wenig Daten für eine belastbare Einordnung.",
        "notes": [],
        "history": pd.DataFrame(),
    }

    try:
        hist = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=False)
        if hist is None or hist.empty or "Close" not in hist.columns:
            return result

        close = hist["Close"].dropna()
        if close.empty or len(close) < 60:
            result["history"] = hist
            return result

        last = float(close.iloc[-1])
        sma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
        sma50 = float(close.tail(50).mean()) if len(close) >= 50 else None
        sma200 = float(close.tail(200).mean()) if len(close) >= 200 else None
        rsi = _calc_rsi_from_close(close, 14)

        perf_24h = _pct_change_safe(close, 1)
        perf_7d = _pct_change_safe(close, 7)
        perf_1m = _pct_change_safe(close, 21)
        perf_3m = _pct_change_safe(close, 63)

        score = 0
        notes = []

        if sma20 is not None and last >= sma20:
            score += 1
            notes.append("Kurs über SMA20")
        else:
            notes.append("Kurs unter SMA20")

        if sma50 is not None and last >= sma50:
            score += 2
            notes.append("Kurs über SMA50")
        else:
            notes.append("Kurs unter SMA50")

        if sma200 is not None and last >= sma200:
            score += 2
            notes.append("Kurs über SMA200")
        elif sma200 is not None:
            score -= 2
            notes.append("Kurs unter SMA200")

        if perf_7d is not None:
            if perf_7d > 5:
                score += 1
                notes.append("7D Momentum stark")
            elif perf_7d < -5:
                score -= 1
                notes.append("7D Momentum schwach")

        if perf_1m is not None:
            if perf_1m > 8:
                score += 2
                notes.append("1M Momentum stark")
            elif perf_1m > 0:
                score += 1
                notes.append("1M Momentum positiv")
            elif perf_1m < -8:
                score -= 2
                notes.append("1M Momentum deutlich negativ")

        if perf_3m is not None:
            if perf_3m > 15:
                score += 1
                notes.append("3M Trend stark")
            elif perf_3m < -15:
                score -= 1
                notes.append("3M Trend schwach")

        if rsi is not None:
            if 45 <= rsi <= 68:
                score += 2
                notes.append("RSI im gesunden Trendbereich")
            elif 68 < rsi <= 75:
                score -= 1
                notes.append("RSI leicht überhitzt")
            elif rsi > 75:
                score -= 3
                notes.append("RSI stark überhitzt")
            elif rsi < 35:
                score -= 1
                notes.append("RSI schwach / Risiko weiterer Druck")

        score = int(max(0, min(10, score)))

        if score >= 8:
            signal = "🟢 Bullisch / Long prüfen"
            recommendation = "Bitcoin wirkt technisch stark. Einstieg nur mit klarer Positionsgröße und Stop-/Rücksetzerplan prüfen. Nicht hinterherkaufen, wenn RSI heiß ist."
        elif score >= 5:
            signal = "🟡 Konstruktiv / Rücksetzer suchen"
            recommendation = "Bild ist konstruktiv, aber nicht perfekt. Besser Pullbacks an SMA20/SMA50 oder Bestätigung abwarten."
        elif score >= 3:
            signal = "🟠 Neutral / abwarten"
            recommendation = "Kein klares Chancenfenster. Beobachten, bis Trend oder Momentum eindeutiger werden."
        else:
            signal = "🔴 Schwach / kein Long-Setup"
            recommendation = "Bitcoin wirkt technisch angeschlagen. Für neue Longs eher auf Stabilisierung über wichtigen Durchschnitten warten."

        if rsi is not None and rsi > 75:
            signal = "🟠 Überhitzt / Rücksetzer abwarten"
            recommendation = "Momentum ist stark, aber überhitzt. Für neue Einstiege lieber Rücksetzer oder Konsolidierung abwarten."

        result.update({
            "last": round(last, 2),
            "perf_24h": round(perf_24h, 2) if perf_24h is not None else None,
            "perf_7d": round(perf_7d, 2) if perf_7d is not None else None,
            "perf_1m": round(perf_1m, 2) if perf_1m is not None else None,
            "perf_3m": round(perf_3m, 2) if perf_3m is not None else None,
            "rsi": round(rsi, 1) if rsi is not None else None,
            "sma20": round(sma20, 2) if sma20 is not None else None,
            "sma50": round(sma50, 2) if sma50 is not None else None,
            "sma200": round(sma200, 2) if sma200 is not None else None,
            "score": score,
            "signal": signal,
            "recommendation": recommendation,
            "notes": notes,
            "history": hist,
        })

    except Exception as error:
        result["recommendation"] = f"Bitcoin-Daten konnten nicht geladen werden: {error}"

    return result


def render_bitcoin_signal_card(snapshot):
    signal = snapshot.get("signal", "⚪ Daten dünn")
    score = snapshot.get("score", 0)
    recommendation = snapshot.get("recommendation", "-")
    notes = snapshot.get("notes", [])

    if "Bullisch" in signal:
        accent = "#22c55e"
    elif "Konstruktiv" in signal:
        accent = "#eab308"
    elif "Überhitzt" in signal or "Neutral" in signal:
        accent = "#f97316"
    else:
        accent = "#ef4444"

    notes_html = "".join([f"<span class='terminal-chip'>{note}</span>" for note in notes[:8]])

    st.markdown(
        f"""
        <div class="terminal-panel" style="border-color:{accent};">
            <h3>₿ Bitcoin Signal</h3>
            <p style="font-size:1.05rem; font-weight:850; color:#f8fafc; margin-bottom:8px;">{signal} · Score {score}/10</p>
            <p>{recommendation}</p>
            <div style="margin-top:8px;">{notes_html}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


@st.cache_data(ttl=30 * 60, show_spinner=False)
def build_bitcoin_chart_frame(ticker="BTC-USD"):
    snapshot = load_bitcoin_snapshot(ticker)
    hist = snapshot.get("history", pd.DataFrame())
    if hist is None or hist.empty or "Close" not in hist.columns:
        return pd.DataFrame()
    chart_df = hist[["Close"]].copy()
    chart_df["SMA20"] = chart_df["Close"].rolling(20).mean()
    chart_df["SMA50"] = chart_df["Close"].rolling(50).mean()
    chart_df["SMA200"] = chart_df["Close"].rolling(200).mean()
    return chart_df.tail(260)


@st.cache_data(ttl=60 * 60 * 6)
def load_smart_money_light(tickers):
    """Lädt grobe Short-/Institutional-/Volumen-Indikatoren über yfinance, soweit verfügbar."""

    rows = []

    for ticker in tickers:
        ticker = str(ticker).strip()
        if not ticker:
            continue

        row = {
            "Ticker": ticker,
            "Short % Float": None,
            "Short Ratio": None,
            "Institutional %": None,
            "Insider %": None,
            "Volume vs Avg": None,
            "Beta": None,
            "Smart Money Score": 0,
            "Smart Money Signal": "⚪ Daten dünn",
            "Smart Money Hinweise": "-"
        }

        notes = []
        score = 0

        try:
            yt = yf.Ticker(ticker)
            info = yt.get_info()

            short_pct = info.get("shortPercentOfFloat") or info.get("sharesPercentSharesOut")
            short_ratio = info.get("shortRatio")
            inst_pct = info.get("heldPercentInstitutions")
            insider_pct = info.get("heldPercentInsiders")
            beta = info.get("beta")
            volume = info.get("volume")
            avg_volume = info.get("averageVolume") or info.get("averageDailyVolume10Day")

            if short_pct is not None:
                row["Short % Float"] = round(float(short_pct) * 100, 2)
                if float(short_pct) >= 0.20:
                    score -= 2
                    notes.append("sehr hohe Shortquote")
                elif float(short_pct) >= 0.10:
                    score -= 1
                    notes.append("erhöhte Shortquote")
                elif float(short_pct) <= 0.03:
                    score += 1
                    notes.append("niedrige Shortquote")

            if short_ratio is not None:
                row["Short Ratio"] = round(float(short_ratio), 2)
                if float(short_ratio) >= 6:
                    score -= 1
                    notes.append("hohe Days-to-cover")
                elif float(short_ratio) <= 2:
                    score += 1
                    notes.append("niedrige Days-to-cover")

            if inst_pct is not None:
                row["Institutional %"] = round(float(inst_pct) * 100, 2)
                if float(inst_pct) >= 0.65:
                    score += 1
                    notes.append("hohe institutionelle Beteiligung")
                elif float(inst_pct) <= 0.15:
                    notes.append("geringe institutionelle Beteiligung")

            if insider_pct is not None:
                row["Insider %"] = round(float(insider_pct) * 100, 2)
                if float(insider_pct) >= 0.10:
                    score += 1
                    notes.append("relevante Insider-Beteiligung")

            if volume is not None and avg_volume not in [None, 0]:
                vol_ratio = float(volume) / float(avg_volume)
                row["Volume vs Avg"] = round(vol_ratio, 2)
                if vol_ratio >= 2.0:
                    notes.append("auffälliges Volumen")
                elif vol_ratio <= 0.6:
                    notes.append("ruhiges Volumen")

            if beta is not None:
                row["Beta"] = round(float(beta), 2)
                if float(beta) >= 1.8:
                    score -= 1
                    notes.append("hohes Beta")
                elif float(beta) <= 0.8:
                    score += 1
                    notes.append("defensiveres Beta")

        except Exception as error:
            notes.append("Daten nicht abrufbar")

        row["Smart Money Score"] = score

        if notes == []:
            row["Smart Money Signal"] = "⚪ Daten dünn"
            row["Smart Money Hinweise"] = "Zu wenige verwertbare Haifisch-Indikatoren."
        elif score >= 2:
            row["Smart Money Signal"] = "🟢 Rückenwind"
            row["Smart Money Hinweise"] = " | ".join(notes)
        elif score <= -2:
            row["Smart Money Signal"] = "🔴 Gegenwind"
            row["Smart Money Hinweise"] = " | ".join(notes)
        else:
            row["Smart Money Signal"] = "🟡 Gemischt"
            row["Smart Money Hinweise"] = " | ".join(notes)

        rows.append(row)

    return pd.DataFrame(rows)

# ============================================================
# TITEL
# ============================================================

st.title("📊 Hartmuts Dashboard")

# ============================================================
# TERMINAL DESIGN / COCKPIT
# ============================================================

st.markdown(
    """
<style>
    .terminal-hero {
        background: linear-gradient(135deg, #0f172a 0%, #111827 50%, #020617 100%);
        border: 1px solid rgba(148, 163, 184, 0.30);
        border-radius: 22px;
        padding: 22px 24px;
        margin: 12px 0 18px 0;
        box-shadow: 0 12px 34px rgba(2, 6, 23, 0.22);
    }
    .terminal-title {
        color: #f8fafc;
        font-size: 26px;
        font-weight: 850;
        margin-bottom: 5px;
        letter-spacing: -0.02em;
    }
    .terminal-subtitle {
        color: #cbd5e1;
        font-size: 15px;
        margin-bottom: 0;
    }
    .terminal-chip {
        display: inline-block;
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.28);
        color: #e5e7eb;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 12px;
        margin-right: 6px;
        margin-top: 8px;
    }
    .terminal-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.07);
        margin-bottom: 12px;
    }
    .terminal-card-title {
        font-size: 14px;
        color: #64748b;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 4px;
    }
    .terminal-card-value {
        font-size: 22px;
        color: #0f172a;
        font-weight: 850;
        margin-bottom: 4px;
    }
    .terminal-small {
        font-size: 13px;
        color: #64748b;
        line-height: 1.45;
    }
</style>
""",
    unsafe_allow_html=True
)

st.markdown(
    f"""
<div class="terminal-hero">
    <div class="terminal-title">🧭 Hartmut Research Terminal</div>
    <p class="terminal-subtitle">
        Deine zentrale Marktübersicht: Chancen, Risiken, News, Wirtschaftstermine, Dividenden, Earnings, Nutzerlisten und Lieferketten-Zusammenhänge in einem kompakten Cockpit.
    </p>
</div>
""",
    unsafe_allow_html=True
)


# ============================================================
# TERMINAL NAVIGATION / TABS
# ============================================================

# ============================================================
# INITIALER FILTER-FALLBACK
# ============================================================

# Einige Übersichtsmodule werden vor dem Sidebar-Filterblock gerendert.
# Damit diese Module nicht abbrechen, startet df_filtered zunächst als Kopie
# der vollständigen Analyse-Daten. Weiter unten wird df_filtered dann durch
# die echten Sidebar-Filter sauber überschrieben.
df_filtered = df.copy()

tab_overview, tab_news, tab_analysis, tab_network, tab_earnings, tab_dividends, tab_economic_calendar, tab_bitcoin, tab_etf_swing, tab_lists, tab_admin = st.tabs([
    "📊 Übersicht",
    "🚨 News Radar",
    "🧠 Analyse",
    "🕸️ Netzwerk",
    "📆 Earnings",
    "📅 Dividenden",
    "🌍 Wirtschaftskalender",
    "₿ Bitcoin",
    "📈 ETF Swingtrades",
    "⭐ Listen",
    "👑 Admin"
])

with tab_overview:

    # ============================================================
    # 🕒 LETZTE AKTUALISIERUNG
    # ============================================================

    with st.expander("🕒 Letzte Aktualisierung / Datenstand", expanded=False):
        update_col_1, update_col_2, update_col_3 = st.columns(3)

        update_col_1.metric("Echter Datenstand", LAST_DATA_UPDATE_TEXT)
        update_col_2.metric("Dashboard geladen", DASHBOARD_LOAD_TIME_TEXT)
        update_col_3.metric("Datenquellen", f"{sum(1 for row in DATA_UPDATE_ROWS if row['Status'] == 'OK')} / {len(DATA_UPDATE_ROWS)} OK")

        st.caption(
            "Die Cloud-Dateizeit kann durch Deployment/Neustart verfälscht sein. "
            "Darum trackt das Dashboard ab jetzt den Dateiinhalt per Fingerabdruck. "
            "Noch genauer wird es, wenn advanced_portfolio.py zusätzlich eine data_update_meta.json schreibt."
        )
        smart_dataframe(
            pd.DataFrame(DATA_UPDATE_ROWS),
            width="stretch",
            hide_index=True
        )

    # ============================================================
    # 🧭 MARKTSIGNALE / MARKT-TACHO
    # ============================================================

    with st.expander("🧭 Marktsignale / Markt-Tacho", expanded=False):
        market_data = load_market_mode_data()

        gauge_col, detail_col = st.columns([1, 1.7])

        with gauge_col:
            render_market_gauge(
                market_data["level"],
                market_data["label"]
            )
            st.info(market_data["interpretation"])

            st.markdown(
                f"""
                <div style="background:#f8fafc; border:1px solid rgba(148,163,184,0.35); border-radius:14px; padding:12px; margin-top:10px;">
                    <div style="font-size:12px; color:#64748b; font-weight:700;">Rohstoff-Stress separat</div>
                    <div style="font-size:20px; font-weight:900; color:#0f172a;">{market_data.get('commodity_status', '-')}</div>
                    <div style="font-size:12px; color:#334155; margin-top:4px;">{market_data.get('commodity_interpretation', '')}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with detail_col:
            st.caption(
                "Der Markt-Tacho bewertet nur die Kernsignale Aktienindizes, Volatilität, Kreditmarkt, Bonds und US-Dollar. Rohstoffe wie Gold, Silber, Öl, Gas, Kupfer, Kakao, Kaffee, Uran und Lithium laufen separat als Stress-/Inflationshinweise."
            )
            details_df = pd.DataFrame(market_data["details"])
            smart_dataframe(
                details_df,
                width="stretch",
                hide_index=True
            )

            if market_data["notes"]:
                st.markdown("**Auffällige Hinweise:**")
                for note in market_data["notes"]:
                    st.write(f"- {note}")
            else:
                st.caption("Keine starken Stress-Hinweise aus den verwendeten Marktindikatoren.")

    # ============================================================
    # 📡 TERMINAL-RADAR: CHANCEN / RISIKEN / DIVIDENDEN
    # ============================================================

    with st.expander("📡 Terminal-Radar: Chancen, Risiken & Dividenden", expanded=True):
        radar_df = df_filtered.copy()

        for radar_numeric_column in [
            "Score",
            "Fundamental Score",
            "Valuation Score",
            "1M %",
            "6M %",
            "RSI"
        ]:
            if radar_numeric_column in radar_df.columns:
                radar_df[radar_numeric_column] = pd.to_numeric(
                    radar_df[radar_numeric_column],
                    errors="coerce"
                ).fillna(0)

        if "CRV" in radar_df.columns:
            radar_df["CRV Radar"] = pd.to_numeric(
                radar_df["CRV"],
                errors="coerce"
            ).fillna(0)
        else:
            radar_df["CRV Radar"] = 0

        if "Dividend Yield %" in radar_df.columns:
            radar_df["Dividend Yield Radar"] = pd.to_numeric(
                radar_df["Dividend Yield %"]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", ".", regex=False)
                .replace("-", "0"),
                errors="coerce"
            ).fillna(0)
        else:
            radar_df["Dividend Yield Radar"] = 0

        radar_display_columns = [
            "Ticker",
            "Company",
            "Action Signal",
            "Valuation Status",
            "Score",
            "Fundamental Score",
            "Risk Level",
            "Price",
            "CRV",
            "Dividend Yield %",
            "Currency"
        ]

        radar_display_columns = [
            column for column in radar_display_columns
            if column in radar_df.columns
        ]

        # Radar bewusst untereinander statt nebeneinander anzeigen.
        # Dadurch sind die Tabellen besser lesbar, besonders bei 30 Einträgen.

        st.markdown("#### 🟢 Top-Chancen")
        top_opportunities = radar_df.copy()
        if "Action Signal" in top_opportunities.columns:
            top_opportunities = top_opportunities[
                top_opportunities["Action Signal"].astype(str).str.contains(
                    "BUY|TURNAROUND",
                    case=False,
                    na=False
                )
            ]
        top_opportunities = top_opportunities.sort_values(
            by=["Score", "Fundamental Score", "CRV Radar", "Valuation Score"],
            ascending=[False, False, False, False]
        ).head(30)

        if top_opportunities.empty:
            st.info("Keine klaren Top-Chancen im aktuellen Filter.")
        else:
            smart_dataframe(
                top_opportunities[radar_display_columns],
                width="stretch",
                hide_index=True
            )

        st.markdown("---")

        st.markdown("#### 🔴 Risiko-/Überhitzungsradar")
        risk_radar = radar_df.copy()
        risk_mask = pd.Series(False, index=risk_radar.index)

        if "Risk Level" in risk_radar.columns:
            risk_mask = risk_mask | (risk_radar["Risk Level"].astype(str) == "HIGH RISK")
        if "Action Signal" in risk_radar.columns:
            risk_mask = risk_mask | risk_radar["Action Signal"].astype(str).str.contains(
                "AVOID|OVERHEATED|TAKE PROFIT",
                case=False,
                na=False
            )
        if "Valuation Status" in risk_radar.columns:
            risk_mask = risk_mask | risk_radar["Valuation Status"].astype(str).str.contains(
                "überbewertet|teuer",
                case=False,
                na=False
            )

        risk_radar = risk_radar[risk_mask].sort_values(
            by=["Risk Level", "RSI", "1M %"],
            ascending=[True, False, False]
        ).head(30)

        if risk_radar.empty:
            st.info("Keine auffälligen Risiken im aktuellen Filter.")
        else:
            smart_dataframe(
                risk_radar[radar_display_columns],
                width="stretch",
                hide_index=True
            )

        st.markdown("---")

        st.markdown("#### 💸 Dividendenradar")
        dividend_radar = radar_df[radar_df["Dividend Yield Radar"] > 0].copy()
        dividend_radar = dividend_radar.sort_values(
            by=["Dividend Yield Radar", "Fundamental Score", "Score"],
            ascending=[False, False, False]
        ).head(30)

        if dividend_radar.empty:
            st.info("Keine Dividendenwerte im aktuellen Filter.")
        else:
            smart_dataframe(
                dividend_radar[radar_display_columns],
                width="stretch",
                hide_index=True
            )



    # ============================================================
    # LEGENDE
    # ============================================================

    with st.expander("📖 Dashboard Legende", expanded=False):

        st.markdown("""

        # 📖 Dashboard-Legende & Entscheidungslogik

        Dieses Dashboard ist als **Research-Terminal** gedacht. Es kombiniert technische Signale, Fundamentaldaten, Bewertungsindikatoren, Dividenden, Watchlists und Lieferketten-Mapping. Die Signale sind **keine Kaufempfehlung**, sondern eine strukturierte Vorauswahl, damit interessante Aktien schneller sichtbar werden.

        ---

        ## 🧭 Grundidee

        Eine Aktie wird nicht nur nach einem einzigen Wert beurteilt. Das Dashboard schaut gleichzeitig auf:

        - **Trend / Momentum**: Läuft die Aktie technisch stabil oder schwach?
        - **Risiko**: Ist sie überhitzt, volatil oder technisch angeschlagen?
        - **Fundamentaldaten**: Gibt es Wachstum, Marge, Cashflow und solide Bewertung?
        - **Bewertung**: Wirkt sie im Verhältnis zu Qualität und Wachstum eher günstig oder teuer?
        - **Chance-Risiko-Verhältnis**: Passt das mögliche Ziel zum angenommenen Risiko?
        - **Kontext**: Hängt die Aktie an starken Trends wie KI, Cloud, Energie, Defense oder Cybersecurity?

        ---

        ## 📈 Technischer Score / Score-System

        Der normale **Score** ist ein technischer Punktwert. Er misst, ob Trend und Momentum stimmen.

        Eine Aktie bekommt Punkte für:

        - Kurs über **EMA20**
        - Kurs über **EMA50**
        - Kurs über **EMA100**
        - **EMA20 > EMA50**
        - **EMA50 > EMA100**
        - positive Wochenperformance
        - positive Monatsperformance
        - RSI im gesunden Bereich

        **Maximaler Score: 8**

        Interpretation:

        - **0–2** → technisch schwach
        - **3–4** → gemischt / noch kein klares Setup
        - **5–6** → technisch interessant
        - **7–8** → technisch stark

        Wichtig: Ein hoher Score heißt nicht automatisch „kaufen“. Eine Aktie kann technisch stark sein, aber trotzdem teuer, überhitzt oder fundamental schwach.

        ---

        ## 🧬 Fundamental Score

        Der **Fundamental Score** bewertet grob die Qualität einer Aktie anhand vorhandener Daten wie:

        - Umsatzwachstum
        - Gewinnwachstum
        - Gewinnmarge
        - Free Cashflow
        - Operating Cashflow
        - Verschuldung
        - KGV / Forward KGV
        - PEG Ratio

        Interpretation:

        - **0–2** → schwach oder Daten fehlen
        - **3–4** → gemischt
        - **5–6** → solide
        - **7–8** → sehr solide

        Wenn Fundamentaldaten fehlen, wertet das Dashboard die Aktie nicht automatisch schlecht. Es zeigt dann eher „unvollständige Daten“ oder „Unklar“.

        ---

        ## 💎 Valuation Status / Bewertungshinweis

        Der **Valuation Status** ist eine regelbasierte Einordnung:

        - **💎 Eher unterbewertet** → Bewertung wirkt im Verhältnis zu Qualität, Wachstum und Cashflow attraktiv.
        - **⚖️ Fair bewertet** → Bewertung wirkt vertretbar, aber nicht extrem günstig.
        - **⚖️ Fair bis leicht teuer** → nicht dramatisch teuer, aber kein klarer Bewertungsabschlag.
        - **🔥 Eher überbewertet** → Bewertung wirkt anspruchsvoll, vor allem wenn KGV/PEG hoch sind.
        - **❓ Unklar** → zu wenige Daten vorhanden.

        Verwendete Faktoren:

        - Forward KGV
        - Trailing KGV
        - PEG Ratio
        - Umsatzwachstum
        - Gewinnwachstum
        - Gewinnmarge
        - Free Cashflow
        - Fundamental Score

        Wichtig: Das ist **kein echter Fair Value** und kein DCF-Modell. Es ist ein Bewertungsfilter, der dir hilft, teure Hype-Aktien und mögliche Preis-Leistungs-Chancen schneller zu erkennen.

        ---

        ## 🧮 Valuation Score

        Der **Valuation Score** ist der Zahlenwert hinter dem Bewertungshinweis.

        Grobe Interpretation:

        - **ab +4** → eher günstig im Verhältnis zur Qualität
        - **+1 bis +3** → fair / vertretbar
        - **0 bis -2** → fair bis teuer / gemischt
        - **ab -3** → eher teuer oder fundamental schwach

        Der Score wird besser, wenn z. B. KGV/PEG attraktiv sind, Wachstum positiv ist und Cashflow/Marge stimmen. Er wird schlechter, wenn Bewertung hoch ist, Wachstum negativ ist oder Cashflow/Marge schwach sind.

        ---

        ## 🧭 Setup Quality

        **Setup Quality** beschreibt die Qualität des aktuellen Setups abhängig vom gewählten Strategie-Horizont.

        Beispiele:

        - **Sehr gut** → Technik, Risiko, CRV und Fundamentaldaten passen gut zusammen.
        - **Kurzfristig stark** → gutes Momentum, gesunder RSI, Kurs über wichtigen EMAs.
        - **Langfristig solide** → Fundamentaldaten und Langfristtrend wirken stabil.
        - **Spekulativ** → Aktie könnte interessant sein, aber Risiko/Unsicherheit ist höher.
        - **Neutral / beobachten** → kein klares Kauf- oder Verkaufssignal.
        - **Überhitzt** → Aktie ist stark gelaufen, RSI und Momentum wirken heiß.
        - **Schwach** → technische oder fundamentale Warnsignale überwiegen.

        Setup Quality ist also die textliche Kurzbeschreibung des aktuellen Setups.

        ---

        ## 🎯 Action Signal

        Das **Action Signal** ist die wichtigste Ampel des Dashboards.

        ### 🟢 BUY ZONE

        Eine Aktie kommt in die BUY ZONE, wenn mehrere Bedingungen zusammenpassen:

        - technischer Score stark genug
        - Rating positiv
        - Risiko nicht zu hoch
        - RSI nicht überhitzt
        - Chance-Risiko-Verhältnis sinnvoll
        - je nach Strategie-Horizont auch Fundamentaldaten ausreichend solide

        Bedeutung: Die Aktie ist interessant genug, um genauer geprüft zu werden. Es ist keine automatische Kaufempfehlung.

        ### 🟡 WATCH

        WATCH bedeutet: Die Aktie ist interessant, aber ein wichtiger Baustein fehlt noch.

        Häufige Gründe:

        - CRV noch zu schwach
        - RSI zu hoch oder zu niedrig
        - Trend noch nicht bestätigt
        - Fundamentaldaten gemischt
        - Bewertung nicht klar attraktiv

        ### 🔵 TURNAROUND WATCH

        TURNAROUND WATCH ist für Aktien gedacht, die vorher deutlich gefallen sind, aber erste Stabilisierung zeigen.

        Typische Kriterien:

        - 6M Performance stark negativ
        - 1M Performance wieder positiv
        - Kurs zurück über EMA20
        - RSI erholt sich über 40

        Bedeutung: Erste Trendwende möglich, aber spekulativer als BUY ZONE. Hier ist Bestätigung besonders wichtig.

        ### 🟠 TAKE PROFIT / OVERHEATED

        Dieses Signal erscheint, wenn eine Aktie kurzfristig stark gelaufen ist.

        Typische Merkmale:

        - RSI über 72
        - starke 1M Performance
        - Kurs deutlich über kurzfristigen Durchschnitten

        Bedeutung: Nicht automatisch verkaufen, aber Risiko von Rücksetzern steigt.

        ### 🔴 SELL / AVOID

        SELL / AVOID erscheint bei klaren Warnsignalen:

        - technischer Score sehr schwach
        - Rating negativ
        - hohes Risiko plus schwache Performance
        - schwacher Fundamental Score
        - negativer Trend

        Bedeutung: Aktie aktuell eher meiden oder sehr kritisch prüfen.

        ---

        ## 🧭 Strategie-Horizont

        Der Sidebar-Schalter **Strategie-Horizont** verändert die Bewertung:

        - **Kurzfristig** → Fokus auf EMA20, RSI, 1M-Momentum, kurzfristigen Stop und CRV.
        - **Mittelfristig** → Mischung aus Technik, Risiko, CRV und Fundamentaldaten. Das ist der Standardmodus.
        - **Langfristig** → Fokus auf Fundamental Score, Cashflow, Marge, Wachstum, Verschuldung und EMA100.

        Dadurch kann dieselbe Aktie je nach Horizont unterschiedlich bewertet werden. Eine Aktie kann kurzfristig überhitzt sein, aber langfristig trotzdem solide.

        ---

        ## ⚖️ CRV / Chance-Risiko-Verhältnis

        Das **CRV** vergleicht mögliches Ziel mit möglichem Risiko.

        Vereinfacht:

        - **CRV unter 1,2** → eher schwach
        - **CRV 1,2 bis 1,5** → okay, aber nicht stark
        - **CRV ab 1,5** → interessant
        - **CRV ab 2,0** → sehr attraktiv, wenn die Annahmen realistisch sind

        Ziel 1 basiert bevorzugt auf dem **52-Wochen-Hoch**, sofern dieses sinnvoll über dem aktuellen Kurs liegt. Falls nicht, nutzt das Dashboard ein vorsichtiges Fallback-Ziel je nach Strategie-Horizont.

        ---

        ## 📉 RSI

        RSI = Relative Strength Index.

        - **unter 30** → überverkauft / sehr schwach
        - **30–40** → angeschlagen, aber mögliche Stabilisierung
        - **40–70** → gesunder Bereich
        - **über 70** → überkauft / heiß gelaufen
        - **über 72/78** → Risiko für Rücksetzer steigt je nach Strategie-Modus

        ---

        ## ⚠ Risk Level

        Das Risk Level betrachtet technische Risikofaktoren wie:

        - Abstand zum EMA20
        - RSI-Überhitzung
        - Volatilität
        - Beta
        - schwache Trendstruktur

        Interpretation:

        - **LOW RISK** → ruhigeres Setup
        - **MEDIUM RISK** → normales Risiko
        - **HIGH RISK** → größere Schwankungen oder technische Warnsignale

        ---

        ## 🧪 Terminal Score / Terminal Grade

        Der **Terminal Score** fasst mehrere Module zusammen:

        - Action Signal
        - technischer Score
        - Fundamental Score
        - Bewertung
        - Risiko
        - CRV

        Daraus entsteht ein Terminal Grade, z. B.:

        - **A · Stark** → viele Faktoren passen zusammen
        - **B · Interessant** → gutes Setup, aber nicht perfekt
        - **C · Beobachten** → gemischt, noch kein klarer Vorteil
        - **D · Schwach** → mehrere Warnsignale

        Der Terminal Score soll dir helfen, viele Aktien schneller zu sortieren.

        ---


        ---

        ## 📆 Earnings / Earningskalender

        Der **Earningskalender** zeigt kommende Quartalszahlen-Termine, soweit sie über die Datenquelle verfügbar sind. Er hilft dir, vor wichtigen Unternehmensereignissen nicht überrascht zu werden.

        Angezeigt werden unter anderem:

        - erwartetes Earnings-Datum
        - Tage bis zum Termin
        - verfügbare EPS-Schätzungen
        - verfügbare Umsatz-Schätzungen
        - aktuelles Terminal Grade / Terminal Score
        - Action Signal, Bewertung und Risiko der Aktie

        Interpretation:

        - **Kurz vor Earnings** können Kurse stärker schwanken.
        - Eine Aktie mit gutem Setup kann nach starken Zahlen weiterlaufen, aber bei Enttäuschung auch stark fallen.
        - Bei High-Risk- oder Turnaround-Aktien sind Earnings besonders wichtig, weil sie die These bestätigen oder zerstören können.
        - Fehlende Schätzwerte bedeuten nicht automatisch, dass keine Earnings existieren — manchmal liefert Yahoo/yfinance nur keine verwertbaren Daten.

        Der Earningskalender ist deshalb ein **Risikokalender** und kein Kaufsignal. Vor Earnings sollte man Positionsgröße, Stop-Loss und Erwartungshaltung prüfen.

        ## 🧭 Marktsignale / Markt-Tacho

        Die Marktsignale sind jetzt in zwei Ebenen getrennt:

        **1. Markt-Tacho**  
        Der Tacho bewertet nur die Kernsignale aus Aktienmarkt, Volatilität, Kreditmarkt, Bonds und US-Dollar. Dadurch wird der Markt nicht mehr nur wegen Kakao, Gas oder Öl automatisch als Panikmarkt eingestuft.

        - **1 Risk-On** → Markt wirkt konstruktiv, Risikoappetit vorhanden.
        - **2 Vorsichtig bullisch** → Umfeld freundlich, aber nicht ohne Risiko.
        - **3 Neutral / gemischt** → selektive Setups bevorzugen.
        - **4 Risk-Off** → neue Käufe strenger prüfen, High-Risk-Titel vorsichtiger behandeln.
        - **5 Stress / Panik** → Kapitalerhalt, Cash und defensive Sektoren priorisieren.

        Für den Markt-Tacho werden vor allem **SPY, QQQ, VIX, High-Yield-Bonds, US-Bonds und US-Dollar** verwendet.

        **2. Rohstoff-Stress separat**  
        Rohstoffe werden separat als Inflations-, Energie- oder Nachfragehinweis angezeigt. Sie können den Tacho ergänzen, aber nicht allein auf Stress/Panik drücken.

        Die Rohstoffwerte helfen dabei, Inflation, Energiepreise und Risikoappetit besser einzuordnen:

        - **Gold / Silber** → Sicherheits- und Inflationssignal. Stärke kann auf Unsicherheit, Zinserwartungen oder Absicherungsbedarf hindeuten.
        - **Öl / Gas** → Energie- und Inflationsdruck. Starke Bewegungen können Energieaktien, Industrie und Verbraucher belasten oder begünstigen.
        - **Kupfer** → Industrie- und Konjunktursignal. Kupferstärke kann auf Nachfrage aus Bau, Stromnetzen, Rechenzentren und Elektrifizierung hindeuten.
        - **Platin / Palladium** → Industrie-, Auto- und Spezialmetall-Signal.
        - **Kakao / Kaffee** → Agrar- und Lebensmittelpreissignal. Starke Preisanstiege können ein Hinweis auf Agrarpreis-Stress und mögliche Inflationseffekte sein.
        - **Uran / Lithium-Battery** → Zukunfts- und Energiewende-Themen. Uran steht eher für Atomstrom/Grundlast, Lithium/Battery für Batterien, Speicher und E-Mobilität.

        Der Markt-Tacho gewichtet diese Signale nicht als direkte Kaufempfehlung, sondern als **Umfeldanzeige**: In einem Risk-Off- oder Stress-Umfeld sollten spekulative, hoch bewertete oder schwache Aktien vorsichtiger behandelt werden; in einem Risk-On-Umfeld können gute Setups eher Rückenwind bekommen.

        ---

        ## 📡 Terminal-Radar

        Der Terminal-Radar zeigt schnelle Vorauswahlen:

        - **Top-Chancen** → Aktien mit BUY/TURNAROUND-Signal, hohem Score, guter Bewertung oder gutem CRV.
        - **Risiko-/Überhitzungsradar** → Aktien mit HIGH RISK, AVOID, TAKE PROFIT, OVERHEATED oder teurer Bewertung.
        - **Dividendenradar** → Aktien mit Dividendenrendite, sortiert nach Rendite und Qualität.

        Der Radar ersetzt keine Einzelprüfung, ist aber gut, um Kandidaten schneller zu finden.

        ---

        ## 📋 Analyse / Gesamttabelle

        Die Gesamttabelle startet bewusst in einer kompakten Entscheidungsansicht.
        Über **Tabellenansicht** kannst du zwischen **Kompakt**, **Bewertung**, **Technik**, **Dividende**, **Fundamental** und **Vollständig** wechseln.
        **Currency** wird in jeder Ansicht ganz hinten angezeigt, damit die wichtigsten Signale vorne bleiben.

        ---

        ## 🕸️ Netzwerk / Lieferketten-Mapping

        Das Mapping zeigt, welche Aktien miteinander verbunden sind.

        Beispiele:

        - **NVIDIA → TSMC / ASML / Micron / Vertiv / Microsoft**
        - **Apple → TSMC / Foxconn / Qualcomm / Broadcom**
        - **Defense → Rheinmetall / Hensoldt / Lockheed / RTX**

        Die Verbindung kann sein:

        - Lieferant / Zulieferer
        - Kunde / Nachfrage
        - Konkurrenz
        - Infrastruktur / Ermöglicher
        - Energie / Strombedarf
        - Speicher / HBM
        - Cloud / Plattform

        Ziel: Du sollst erkennen, **welche Aktien indirekt mit einem Trend oder einer Hauptaktie zusammenhängen**.

        ---

        ## 🍕 PizzINT / Geopolitischer Stress

        Der PizzINT-Bereich ist ein experimenteller externer OSINT-/Stimmungsindikator.
        Es gibt im Dashboard keine manuelle DOUGHCON-Bewertung mehr; der Bereich zeigt nur noch mögliche Markt-Fokusbereiche und eine kurze Watch-Einordnung.

        Die Idee dahinter:

        - bei höherem geopolitischem Stress defensive Sektoren stärker beobachten
        - Energie, Gold, Cybersecurity, Defense und Cash-Risiko stärker einordnen
        - spekulative High-Risk-/Turnaround-Aktien vorsichtiger bewerten

        ---

        ## 📅 Dividendenkalender

        Der Dividendenkalender filtert nach Ex-Dividenden-Datum. Wichtig: Der Kalender zeigt nur passende Dividendenereignisse, aber die Aktien bleiben in Übersicht und Gesamttabelle weiterhin sichtbar.

        ---

        ## Wichtig

        Alle Signale sind regelbasierte Orientierungshilfen. Sie ersetzen keine eigene Recherche, keine Fundamentalanalyse und keine Risikoprüfung. Das Dashboard soll helfen, schneller zu sortieren und Zusammenhänge zu erkennen.

        """)


    # ============================================================
    # 🍕 PIZZINT / GEOPOLITISCHER STRESS-INDIKATOR
    # ============================================================

    with st.expander("🍕 PizzINT / Geopolitischer Stress-Indikator", expanded=False):
        st.caption(
            "Experimenteller externer OSINT-/Stimmungsindikator. "
            "Hier wird kein DOUGHCON-Level mehr manuell eingeschätzt; "
            "der Bereich dient nur als Zusatzhinweis für mögliche Markt-Fokusbereiche."
        )

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

        smart_dataframe(
            geo_focus_df,
            width="stretch",
            hide_index=True
        )

        pizza_watch_df = pd.DataFrame([
            {
                "Signal": "Pizza-/OSINT-Aktivität",
                "Interpretation": "Kann als humorvoller externer Stimmungsindikator beobachtet werden.",
                "Relevanz fürs Portfolio": "Nur Zusatzsignal, niemals alleinige Entscheidungsbasis."
            },
            {
                "Signal": "Geopolitische Aufmerksamkeit nimmt zu",
                "Interpretation": "Defensive Sektoren, Energie, Gold, Cybersecurity und Defense stärker beobachten.",
                "Relevanz fürs Portfolio": "Risk-Management prüfen, spekulative Setups strenger bewerten."
            },
            {
                "Signal": "Geopolitische Aufmerksamkeit nimmt ab",
                "Interpretation": "Normale technische, fundamentale und Markt-Tacho-Signale wieder stärker gewichten.",
                "Relevanz fürs Portfolio": "Keine automatische Kaufentscheidung; nur Kontext."
            }
        ])

        st.markdown("### 🍕 PizzINT Watch")

        smart_dataframe(
            pizza_watch_df,
            width="stretch",
            hide_index=True
        )

        st.link_button(
            "🍕 PizzINT extern öffnen",
            "https://www.pizzint.watch/"
        )



with tab_network:
    # ============================================================
    # 🕸️ AKTIEN-NETZWERK / THEMEN-MAPPING
    # ============================================================

    with st.expander("🕸️ Aktien-Netzwerk / Themen-Mapping", expanded=True):
        st.markdown(
            """
            <div class="terminal-panel">
                <h3>Market Relationship Terminal</h3>
                <p>Wähle eine Hauptaktie und erkenne, welche Unternehmen in der Wertschöpfungskette, als Zulieferer, Kunden, Konkurrenz oder Infrastrukturpartner daran hängen.</p>
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

            def load_relationships_csv(file_path):
                """Lädt stock_relationships.csv robust, auch bei Excel-/BOM-/Semikolon-Problemen."""

                read_attempts = [
                    {"encoding": "utf-8-sig", "sep": None},
                    {"encoding": "utf-8-sig", "sep": ";"},
                    {"encoding": "utf-8-sig", "sep": ","},
                    {"encoding": "latin1", "sep": None},
                    {"encoding": "latin1", "sep": ";"},
                    {"encoding": "latin1", "sep": ","},
                ]

                last_error = None

                for attempt in read_attempts:
                    try:
                        loaded_df = pd.read_csv(
                            file_path,
                            encoding=attempt["encoding"],
                            sep=attempt["sep"],
                            engine="python"
                        )

                        # Header normalisieren: BOM, Leerzeichen, Excel-Varianten.
                        loaded_df.columns = [
                            str(column)
                            .replace("\ufeff", "")
                            .strip()
                            .lower()
                            .replace(" ", "_")
                            .replace("-", "_")
                            for column in loaded_df.columns
                        ]

                        # Falls Excel/CSV alles in eine einzige Spalte geschrieben hat,
                        # erneut mit dem sichtbaren Trennzeichen laden.
                        if len(loaded_df.columns) == 1:
                            only_column = loaded_df.columns[0]
                            if ";" in only_column or "," in only_column:
                                guessed_sep = ";" if ";" in only_column else ","
                                loaded_df = pd.read_csv(
                                    file_path,
                                    encoding=attempt["encoding"],
                                    sep=guessed_sep,
                                    engine="python"
                                )
                                loaded_df.columns = [
                                    str(column)
                                    .replace("\ufeff", "")
                                    .strip()
                                    .lower()
                                    .replace(" ", "_")
                                    .replace("-", "_")
                                    for column in loaded_df.columns
                                ]

                        column_aliases = {
                            "source": "source_ticker",
                            "source_symbol": "source_ticker",
                            "source_ticker_symbol": "source_ticker",
                            "ticker": "source_ticker",
                            "main_ticker": "source_ticker",
                            "hauptaktie": "source_ticker",
                            "haupt_ticker": "source_ticker",
                            "target": "target_ticker",
                            "target_symbol": "target_ticker",
                            "target_ticker_symbol": "target_ticker",
                            "ziel_ticker": "target_ticker",
                            "name": "target_name",
                            "target_company": "target_name",
                            "target_name_company": "target_name",
                            "ziel_name": "target_name",
                            "kategorie": "category",
                            "beziehung": "relationship",
                            "relation": "relationship",
                            "wichtigkeit": "importance",
                            "risiko": "risk_note",
                            "risk": "risk_note",
                            "risk_notes": "risk_note",
                        }

                        loaded_df = loaded_df.rename(
                            columns={column: column_aliases.get(column, column) for column in loaded_df.columns}
                        )

                        return loaded_df, None

                    except Exception as error:
                        last_error = error

                return pd.DataFrame(), last_error

            relationships_df, relationships_load_error = load_relationships_csv(RELATIONSHIPS_FILE)

            if relationships_load_error is not None and relationships_df.empty:
                st.error(f"stock_relationships.csv konnte nicht geladen werden: {relationships_load_error}")

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

                def reset_network_filters():
                    """Setzt die Netzwerkfilter zurück, bevor die Filter-Widgets neu aufgebaut werden."""
                    st.session_state["network_selected_category"] = "Alle"
                    st.session_state["network_selected_supply_chain_stage"] = "Alle"
                    st.session_state["network_selected_connection_type"] = "Alle"

                def switch_network_center(ticker):
                    """Wechselt das Netzwerk-Zentrum ohne URL-Wechsel, damit der Login erhalten bleibt."""
                    ticker = str(ticker).strip().upper()

                    if ticker in available_network_tickers:
                        st.session_state["_network_center_ticker"] = ticker
                        st.session_state["_network_picker"] = ticker
                        reset_network_filters()

                def on_network_picker_change():
                    """Reagiert auf manuelle Auswahl im Dropdown."""
                    ticker = str(st.session_state.get("_network_picker", "")).strip().upper()

                    if ticker in available_network_tickers:
                        st.session_state["_network_center_ticker"] = ticker
                        reset_network_filters()

                if "_network_center_ticker" not in st.session_state:
                    st.session_state["_network_center_ticker"] = available_network_tickers[0]

                if st.session_state["_network_center_ticker"] not in available_network_tickers:
                    st.session_state["_network_center_ticker"] = available_network_tickers[0]

                if "_network_picker" not in st.session_state:
                    st.session_state["_network_picker"] = st.session_state["_network_center_ticker"]

                if st.session_state["_network_picker"] not in available_network_tickers:
                    st.session_state["_network_picker"] = st.session_state["_network_center_ticker"]

                selected_index = available_network_tickers.index(
                    st.session_state["_network_center_ticker"]
                )

                selected_network_ticker = st.selectbox(
                    "Aktie für Netzwerk auswählen",
                    options=available_network_tickers,
                    index=selected_index,
                    key="_network_picker",
                    on_change=on_network_picker_change
                )

                selected_network_ticker = st.session_state.get(
                    "_network_center_ticker",
                    selected_network_ticker
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

                    with st.expander("🕸️ Netzwerk / Wertschöpfungskette anzeigen", expanded=False):
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
                            total_network_records = len(spider_records)

                            st.caption(
                                f"Für {selected_network_ticker} sind {total_network_records} Beziehungen vorhanden. "
                                "Für das Spinnennetz werden nur die wichtigsten angezeigt; die vollständige Liste bleibt unten als Tabelle sichtbar."
                            )

                            network_display_mode = st.radio(
                                "Darstellung im Spinnennetz",
                                options=[
                                    "Top-Beziehungen",
                                    "Ausbalanciert nach Lieferkettenstufen",
                                    "Alle gefilterten Beziehungen"
                                ],
                                index=0,
                                horizontal=True,
                                key=f"spider_display_mode_{selected_network_ticker}"
                            )

                            max_slider_upper = min(80, max(10, total_network_records))
                            default_nodes = min(28, max_slider_upper)

                            max_visible_nodes = st.slider(
                                "Maximale Aktien im Spinnennetz",
                                min_value=10,
                                max_value=max_slider_upper,
                                value=default_nodes,
                                step=5,
                                key=f"spider_max_nodes_static_{selected_network_ticker}"
                            )

                            def relationship_priority(row):
                                importance_sort = row.get("Importance Sort", 9)
                                try:
                                    importance_sort = int(float(importance_sort))
                                except Exception:
                                    importance_sort = 9

                                action_signal = str(row.get("Action Signal", "")).lower()
                                has_dashboard_signal = 0 if action_signal and action_signal not in ["nan", "none"] else 1

                                if "strong buy" in action_signal:
                                    signal_sort = 0
                                elif "buy" in action_signal:
                                    signal_sort = 1
                                elif "turnaround" in action_signal:
                                    signal_sort = 2
                                elif "watch" in action_signal:
                                    signal_sort = 3
                                elif "avoid" in action_signal or "sell" in action_signal:
                                    signal_sort = 5
                                else:
                                    signal_sort = 4

                                stage = str(row.get("supply_chain_stage", "99"))
                                category = str(row.get("category", ""))
                                ticker = str(row.get("Ticker", row.get("target_ticker", "")))

                                return (
                                    importance_sort,
                                    has_dashboard_signal,
                                    signal_sort,
                                    stage,
                                    category,
                                    ticker
                                )

                            prioritized_records = sorted(
                                spider_records,
                                key=relationship_priority
                            )

                            if network_display_mode == "Alle gefilterten Beziehungen":
                                spider_records_sorted = prioritized_records[:max_visible_nodes]

                            elif network_display_mode == "Ausbalanciert nach Lieferkettenstufen":
                                grouped_records = {}
                                for row in prioritized_records:
                                    stage_name = str(row.get("supply_chain_stage", "99 - Sonstige Verbindung"))
                                    grouped_records.setdefault(stage_name, []).append(row)

                                stage_count = max(1, len(grouped_records))
                                per_stage_limit = max(1, max_visible_nodes // stage_count)

                                balanced_records = []
                                used_tickers = set()

                                for stage_name in sorted(grouped_records.keys()):
                                    for row in grouped_records[stage_name][:per_stage_limit]:
                                        ticker = str(row.get("Ticker", row.get("target_ticker", "")))
                                        if ticker not in used_tickers:
                                            balanced_records.append(row)
                                            used_tickers.add(ticker)

                                if len(balanced_records) < max_visible_nodes:
                                    for row in prioritized_records:
                                        ticker = str(row.get("Ticker", row.get("target_ticker", "")))
                                        if ticker not in used_tickers:
                                            balanced_records.append(row)
                                            used_tickers.add(ticker)
                                        if len(balanced_records) >= max_visible_nodes:
                                            break

                                spider_records_sorted = balanced_records[:max_visible_nodes]

                            else:
                                # Empfohlener Modus: Wichtigkeit + vorhandenes Dashboard-Signal + saubere Sortierung.
                                spider_records_sorted = prioritized_records[:max_visible_nodes]

                            st.caption(
                                f"Im Spinnennetz sichtbar: {len(spider_records_sorted)} von {total_network_records} Beziehungen."
                            )

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
                                    <b>Bedienung:</b> Mouseover zeigt Schnellinfos. Klick zeigt Details rechts. Das Zentrum wechselst du über die Buttons unten — ohne URL-Wechsel, der Login bleibt erhalten.
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            # Streamlit-native Navigation: zuverlässig und ohne URL-Wechsel, damit der Login erhalten bleibt.
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
                                st.caption("Diese Auswahl setzt Kategorie-, Lieferketten- und Verbindungsfilter automatisch zurück, ohne den Login zu verlassen.")

                                # Kompakte Button-Matrix
                                button_columns = st.columns(6)
                                for idx, ticker in enumerate(drill_candidates[:30]):
                                    with button_columns[idx % 6]:
                                        st.button(
                                            f"↻ {ticker}",
                                            key=f"switch_network_center_{selected_network_ticker}_{ticker}",
                                            use_container_width=True,
                                            on_click=switch_network_center,
                                            args=(ticker,)
                                        )
                            else:
                                st.caption("Keine verbundenen Aktien aus dieser Ansicht sind aktuell selbst als Hauptaktie im Mapping hinterlegt.")

                    with st.expander("🧾 Detailtabelle anzeigen", expanded=False):

                        smart_dataframe(
                            network_display,
                            width="stretch",
                            hide_index=True
                        )

                    with st.expander("🏭 Lieferkette als Stufenansicht anzeigen", expanded=False):

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

                    signal_summary = network_view["Action Signal"].fillna("Nicht in Hauptliste").value_counts()

                    with st.expander("📊 Netzwerk-Signal anzeigen", expanded=False):
                        st.caption(
                            "Zählt die aktuellen Dashboard-Signale der verbundenen Aktien, "
                            "sofern sie in deiner Hauptliste vorhanden sind. Diese Auswertung steht bewusst unter der Detail- und Kategorienansicht, damit erst die Beziehungen sichtbar sind und danach die Zusammenfassung folgt."
                        )

                        signal_summary_df = signal_summary.reset_index()
                        signal_summary_df.columns = ["Action Signal", "Anzahl"]

                        smart_dataframe(
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

turnaround_only = st.sidebar.checkbox(
    "Nur Turnaround Kandidaten"
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

# ----------------------------
# Zusätzliche Bewertungs-/Preisfilter
# ----------------------------

if "Valuation Status" in df.columns:
    valuation_status_options = sorted(
        df["Valuation Status"].dropna().astype(str).unique().tolist()
    )
else:
    valuation_status_options = []

selected_valuation_status = st.sidebar.multiselect(
    "Valuation Status",
    options=valuation_status_options,
    default=valuation_status_options
)

if "Setup Quality" in df.columns:
    setup_quality_options = sorted(
        df["Setup Quality"].dropna().astype(str).unique().tolist()
    )
else:
    setup_quality_options = []

selected_setup_quality = st.sidebar.multiselect(
    "Setup Quality",
    options=setup_quality_options,
    default=setup_quality_options
)

# Preisbereich: Price ist im Dashboard eine Anzeige-Spalte und kann Text enthalten.
# Deshalb wird für den Filter eine separate numerische Serie verwendet.
price_filter_values = df["Price"].apply(safe_float) if "Price" in df.columns else pd.Series(dtype=float)
valid_price_values = price_filter_values.dropna()

if not valid_price_values.empty:
    price_min = float(valid_price_values.min())
    price_max = float(valid_price_values.max())
    price_step = max(round((price_max - price_min) / 200, 2), 0.01)

    st.sidebar.markdown("**Price Range**")
    price_col_1, price_col_2 = st.sidebar.columns(2)
    with price_col_1:
        selected_price_min = st.number_input(
            "Min",
            min_value=0.0,
            max_value=max(price_max, 0.0),
            value=max(price_min, 0.0),
            step=price_step,
            format="%.2f",
            key="price_range_min"
        )
    with price_col_2:
        selected_price_max = st.number_input(
            "Max",
            min_value=0.0,
            max_value=max(price_max, 0.0),
            value=max(price_max, 0.0),
            step=price_step,
            format="%.2f",
            key="price_range_max"
        )

    if selected_price_min > selected_price_max:
        st.sidebar.warning("Price Range: Minimum ist größer als Maximum.")

    selected_price_range = (
        min(float(selected_price_min), float(selected_price_max)),
        max(float(selected_price_min), float(selected_price_max))
    )
else:
    selected_price_range = None
    st.sidebar.caption("Price Range: keine verwertbaren Preisdaten")

# Währungsfilter direkt unter dem Preisbereich: erst Preisspanne, dann Markt-/Währungskontext.
currency_options = sorted(
    df["Currency"]
    .fillna("Unbekannt")
    .astype(str)
    .str.strip()
    .replace({"": "Unbekannt"})
    .unique()
    .tolist()
) if "Currency" in df.columns else []

selected_currencies = st.sidebar.multiselect(
    "Currency / Währung",
    options=currency_options,
    default=currency_options
)

valuation_score_values = (
    pd.to_numeric(df["Valuation Score"], errors="coerce")
    if "Valuation Score" in df.columns
    else pd.Series(dtype=float)
)
valid_valuation_scores = valuation_score_values.dropna()

if not valid_valuation_scores.empty:
    valuation_score_min = int(valid_valuation_scores.min())
    valuation_score_max = int(valid_valuation_scores.max())

    selected_valuation_score_range = st.sidebar.slider(
        "Valuation Score",
        min_value=valuation_score_min,
        max_value=valuation_score_max,
        value=(valuation_score_min, valuation_score_max),
        step=1
    )
else:
    selected_valuation_score_range = None
    st.sidebar.caption("Valuation Score: keine Daten")

sort_option = st.sidebar.selectbox(
    "Sortieren nach",
    [
        "Action Signal",
        "Terminal Score",
        "Valuation Score",
        "Valuation Status",
        "Setup Quality",
        "Price",
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

if selected_currencies and "Currency" in df_filtered.columns:
    df_filtered = df_filtered[
        df_filtered["Currency"].fillna("Unbekannt").astype(str).isin(selected_currencies)
    ]

if selected_valuation_status and "Valuation Status" in df_filtered.columns:
    df_filtered = df_filtered[
        df_filtered["Valuation Status"].astype(str).isin(selected_valuation_status)
    ]

if selected_setup_quality and "Setup Quality" in df_filtered.columns:
    df_filtered = df_filtered[
        df_filtered["Setup Quality"].astype(str).isin(selected_setup_quality)
    ]

if selected_price_range is not None and "Price" in df.columns:
    price_mask = price_filter_values.loc[df_filtered.index].between(
        selected_price_range[0],
        selected_price_range[1],
        inclusive="both"
    )
    df_filtered = df_filtered[price_mask.fillna(False)]

if selected_valuation_score_range is not None and "Valuation Score" in df.columns:
    valuation_score_mask = valuation_score_values.loc[df_filtered.index].between(
        selected_valuation_score_range[0],
        selected_valuation_score_range[1],
        inclusive="both"
    )
    df_filtered = df_filtered[valuation_score_mask.fillna(False)]

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

    elif sort_option == "Price":

        df_filtered["Price Numeric"] = df_filtered["Price"].apply(safe_float).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="Price Numeric",
            ascending=False
        )

    elif sort_option == "Valuation Score":

        df_filtered["Valuation Score Numeric"] = pd.to_numeric(
            df_filtered["Valuation Score"],
            errors="coerce"
        ).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="Valuation Score Numeric",
            ascending=False
        )

    elif sort_option == "Terminal Score":

        df_filtered["Terminal Score Numeric"] = pd.to_numeric(
            df_filtered["Terminal Score"],
            errors="coerce"
        ).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="Terminal Score Numeric",
            ascending=False
        )

    elif sort_option in ["Setup Quality", "Valuation Status"]:

        df_filtered = df_filtered.sort_values(
            by=sort_option,
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



with tab_overview:
    # ============================================================
    # METRICS
    # ============================================================

    with st.expander("📊 Markt-Metriken / Filter-Zusammenfassung", expanded=False):
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


with tab_news:
    st.markdown("## 🚨 News & Momentum Radar")
    st.caption(
        "Kombiniert EQS-Treffer über Google News RSS mit Kursbewegung, Volumen, RSI und EMA20. "
        "Das ist ein Frühwarnsystem für Bewegung — keine automatische Kaufempfehlung."
    )

    news_df = df_filtered.copy()

    required_news_columns = {
        "EQS News Count 14D": 0,
        "EQS News Score": 0,
        "News Momentum Score": 0,
        "EQS Signal": "⚪ Keine EQS-News",
        "News Momentum Signal": "⚪ Neutral",
        "EQS Keywords": "-",
        "EQS Latest Title": "-",
        "EQS Latest Date": "-",
        "EQS Latest Source": "-",
        "EQS Link": "-",
        "Volume Ratio": 0,
    }

    for column, default_value in required_news_columns.items():
        if column not in news_df.columns:
            news_df[column] = default_value

    for column in [
        "1D %", "1W %", "RSI", "Volume Ratio",
        "EQS News Count 14D", "EQS News Score", "News Momentum Score"
    ]:
        if column in news_df.columns:
            news_df[column] = pd.to_numeric(news_df[column], errors="coerce").fillna(0)

    metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
    metric_col_1.metric("🔥 News-Momentum", int(news_df["News Momentum Signal"].astype(str).str.contains("News-Momentum", na=False).sum()))
    metric_col_2.metric("🟠 Bewegung möglich", int(news_df["News Momentum Signal"].astype(str).str.contains("Bewegung möglich", na=False).sum()))
    metric_col_3.metric("EQS-Treffer 14T", int((news_df["EQS News Count 14D"] > 0).sum()))
    metric_col_4.metric("Ø News Score", round(news_df["News Momentum Score"].mean(), 2) if len(news_df) else 0)

    signal_options = ["Alle"] + sorted(news_df["News Momentum Signal"].dropna().astype(str).unique().tolist())
    eqs_options = ["Alle"] + sorted(news_df["EQS Signal"].dropna().astype(str).unique().tolist())

    filter_col_1, filter_col_2, filter_col_3 = st.columns([1.1, 1.1, 1.2])
    selected_news_signal = filter_col_1.selectbox("News-Momentum-Signal", signal_options, index=0)
    selected_eqs_signal = filter_col_2.selectbox("EQS-Signal", eqs_options, index=0)
    only_with_eqs = filter_col_3.checkbox("Nur Aktien mit EQS-Treffer", value=False)

    if selected_news_signal != "Alle":
        news_df = news_df[news_df["News Momentum Signal"].astype(str) == selected_news_signal]

    if selected_eqs_signal != "Alle":
        news_df = news_df[news_df["EQS Signal"].astype(str) == selected_eqs_signal]

    if only_with_eqs:
        news_df = news_df[news_df["EQS News Count 14D"] > 0]

    news_df = news_df.sort_values(
        by=["News Momentum Score", "EQS News Score", "1D %", "Volume Ratio"],
        ascending=[False, False, False, False]
    )

    news_display_columns = [
        "Ticker", "Company", "Price", "1D %", "1W %", "Volume Ratio", "RSI",
        "EQS News Count 14D", "EQS News Score", "EQS Keywords", "EQS Signal",
        "News Momentum Score", "News Momentum Signal",
        "EQS Latest Date", "EQS Latest Source", "EQS Latest Title", "EQS Link"
    ]
    news_display_columns = [column for column in news_display_columns if column in news_df.columns]

    st.markdown("### Auffällige Werte")
    if news_df.empty:
        st.info("Keine Aktien im aktuellen Filter mit auffälligem News-/Momentum-Signal.")
    else:
        column_config = build_column_help_config(news_df[news_display_columns])
        if "EQS Link" in news_display_columns:
            column_config["EQS Link"] = st.column_config.LinkColumn(
                "EQS Link",
                help=COLUMN_HELP_TEXTS.get("EQS Link", "Link zur gefundenen News."),
                display_text="Öffnen"
            )
        smart_dataframe(
            news_df[news_display_columns].head(100),
            width="stretch",
            hide_index=True,
            column_config=column_config
        )

    with st.expander("Wie wird das Signal berechnet?", expanded=False):
        st.markdown(
            """
            **EQS News Score** bewertet gefundene Schlagzeilen nach Keywords. Positive Wörter wie
            *Auftrag*, *Finanzierung*, *Prognose angehoben*, *Zulassung*, *Auslieferung* oder
            *Defence* erhöhen den Score. Warnwörter wie *Verlustwarnung*, *Insolvenz*,
            *Prognose gesenkt* oder *Verwässerung* senken ihn.

            **News Momentum Score** kombiniert diesen News-Score mit Tages-/Wochenperformance,
            Volumenfaktor, RSI und Kurs über EMA20. Dadurch erkennt das Dashboard nicht nur
            eine Meldung, sondern auch, ob der Markt bereits darauf reagiert.
            """
        )



with tab_economic_calendar:
    st.markdown("## 🌍 Wirtschaftskalender")
   
    econ_col_1, econ_col_2, econ_col_3, econ_col_4 = st.columns([1, 1, 1.2, 1.1])

    with econ_col_1:
        econ_theme = st.selectbox(
            "Hintergrund / Design",
            options=["light", "dark"],
            index=0,
            format_func=lambda value: "Hell / weiß" if value == "light" else "Dunkel",
            key="economic_calendar_theme"
        )

    with econ_col_2:
        econ_height = st.selectbox(
            "Kalenderhöhe",
            options=[650, 800, 950, 1100],
            index=1,
            format_func=lambda value: f"{value}px",
            key="economic_calendar_height"
        )

    with econ_col_3:
        econ_filter_profile = st.selectbox(
            "Länder- und Marktfokus",
            options=[
                "USA + Europa + Deutschland",
                "Global",
                "USA",
                "Europa + Deutschland",
                "Asien"
            ],
            index=0,
            key="economic_calendar_profile"
        )

    with econ_col_4:
        econ_importance_profile = st.selectbox(
            "Wichtigkeit",
            options=[
                "Nur hohe Wichtigkeit",
                "Mittel + hoch",
                "Alle Termine"
            ],
            index=0,
            help="Grundeinstellung: nur die wichtigsten Termine. So bleibt der Kalender übersichtlich.",
            key="economic_calendar_importance"
        )

    country_filters = {
        "USA + Europa + Deutschland": "us,eu,de",
        "Global": "us,eu,de,gb,ca,jp,cn,au,ch",
        "USA": "us",
        "Europa + Deutschland": "eu,de,gb,ch,fr,it,es",
        "Asien": "jp,cn,hk,kr,in"
    }

    selected_country_filter = country_filters.get(econ_filter_profile, "us,eu,de")

    importance_filters = {
        "Nur hohe Wichtigkeit": "1",
        "Mittel + hoch": "0,1",
        "Alle Termine": "-1,0,1"
    }

    selected_importance_filter = importance_filters.get(econ_importance_profile, "1")

    st.markdown("### 📅 Aktuelle Wirtschaftstermine")

    economic_calendar_html = f"""
    <div class="tradingview-widget-container" style="height:{econ_height}px;width:100%;">
      <div class="tradingview-widget-container__widget" style="height:calc(100% - 32px);width:100%;"></div>
      <div class="tradingview-widget-copyright">
        <a href="https://www.tradingview.com/economic-calendar/" rel="noopener nofollow" target="_blank">
          <span class="blue-text">Economic Calendar by TradingView</span>
        </a>
      </div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
      {{
        "colorTheme": "{econ_theme}",
        "isTransparent": false,
        "width": "100%",
        "height": "{econ_height}",
        "locale": "de",
        "importanceFilter": "{selected_importance_filter}",
        "countryFilter": "{selected_country_filter}"
      }}
      </script>
    </div>
    """

    components.html(
        economic_calendar_html,
        height=econ_height + 40,
        scrolling=True
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


with tab_etf_swing:
    with st.expander("📈 ETF Swingtrades / Marktrotation", expanded=True):
        st.markdown(
            """
            Dieses Fenster ist als eigene Arbeitsfläche für ETF-Swingtrades gedacht.  
            Ziel: nicht einzelne Aktien jagen, sondern Marktrotationen erkennen — z. B. Tech, Halbleiter, Energie, Bonds, Gold, Rohstoffe oder Regionen.
            """
        )

        preset_options = list(ETF_SWING_DEFAULTS.keys())
        default_etfs = [
            "SPY", "QQQ", "IWM", "SMH", "XLK", "XLE", "XLF", "HYG", "TLT", "GLD", "SLV", "URA", "LIT",
            "IEVD.DE", "VWCE.DE", "EUNL.DE", "DFEN.DE", "JEDI.DE", "XAIX.DE"
        ]

        col_etf_a, col_etf_b = st.columns([1.3, 1])

        with col_etf_a:
            selected_etfs = st.multiselect(
                "ETF-Universum auswählen",
                options=preset_options,
                default=[ticker for ticker in default_etfs if ticker in preset_options],
                format_func=lambda ticker: f"{ticker} · {ETF_SWING_DEFAULTS.get(ticker, ticker)}"
            )

            custom_etfs_text = st.text_input(
                "Zusätzliche ETF-Ticker, kommagetrennt",
                value="",
                placeholder="z. B. VOO, SOXX, XBI, KWEB, JEDI.DE, XAIX.DE"
            )

        with col_etf_b:
            st.info(
                "Swing-Idee: starke ETFs im Aufwärtstrend suchen, Rücksetzer an SMA20/SMA50 beobachten und überhitzte Setups nicht hinterherkaufen."
            )
            min_swing_score = st.slider(
                "Mindest-Swing-Score anzeigen",
                min_value=0,
                max_value=10,
                value=0,
                step=1
            )

        custom_etfs = [ticker.strip().upper() for ticker in custom_etfs_text.split(",") if ticker.strip()]
        etf_tickers = []
        for ticker in selected_etfs + custom_etfs:
            if ticker and ticker not in etf_tickers:
                etf_tickers.append(ticker)

        if not etf_tickers:
            st.warning("Bitte mindestens einen ETF auswählen oder eintragen.")
        else:
            etf_df = load_etf_swingtrade_data(etf_tickers)
            if etf_df.empty:
                st.warning("Für die ausgewählten ETFs konnten keine Daten geladen werden.")
            else:
                etf_df_filtered = etf_df[
                    pd.to_numeric(etf_df["Swing Score"], errors="coerce").fillna(0) >= min_swing_score
                ].copy()

                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                metric_col1.metric("ETFs geprüft", len(etf_df))
                metric_col2.metric(
                    "Swing Long prüfen",
                    int((etf_df["Signal"] == "🟢 Swing Long prüfen").sum())
                )
                metric_col3.metric(
                    "Watch / Pullback",
                    int((etf_df["Signal"] == "🟡 Watch / Pullback suchen").sum())
                )
                metric_col4.metric(
                    "Ø Swing Score",
                    round(pd.to_numeric(etf_df["Swing Score"], errors="coerce").fillna(0).mean(), 2)
                )

                smart_dataframe(
                    etf_df_filtered,
                    width="stretch",
                    hide_index=True
                )

                st.download_button(
                    "📥 ETF-Swingtrade-Radar als CSV herunterladen",
                    etf_df_filtered.to_csv(index=False).encode("utf-8-sig"),
                    "etf_swingtrade_radar.csv",
                    "text/csv"
                )

                chart_ticker = st.selectbox(
                    "ETF-Chart anzeigen",
                    options=etf_tickers,
                    format_func=lambda ticker: f"{ticker} · {ETF_SWING_DEFAULTS.get(ticker, ticker)}"
                )

                try:
                    chart_hist = yf.Ticker(chart_ticker).history(period="6mo", interval="1d", auto_adjust=False)
                    if chart_hist is not None and not chart_hist.empty and "Close" in chart_hist.columns:
                        chart_data = pd.DataFrame({
                            "Close": chart_hist["Close"].dropna()
                        })
                        chart_data["SMA20"] = chart_data["Close"].rolling(20).mean()
                        chart_data["SMA50"] = chart_data["Close"].rolling(50).mean()
                        st.line_chart(chart_data)
                    else:
                        st.caption("Für den ausgewählten ETF ist aktuell kein Chart verfügbar.")
                except Exception:
                    st.caption("Chart konnte aktuell nicht geladen werden.")

        st.markdown(
            """
            **Lesart:**  
            🟢 bedeutet nicht automatisch kaufen, sondern: Setup ist prüfenswert.  
            🟡 bedeutet: interessant, aber besser Rücksetzer/Bestätigung suchen.  
            🔴 bedeutet: aktuell kein sauberes Long-Setup nach dieser einfachen Swing-Logik.
            """
        )


with tab_earnings:
    # ============================================================
    # 📆 EARNINGSKALENDER
    # ============================================================

    with st.expander("📆 Earningskalender: Termine, Erwartungen & Kontext", expanded=True):
        st.caption(
            "Zeigt kommende Earnings-Termine und verfügbare EPS-/Umsatzschätzungen. "
            "Nicht jede Aktie liefert über Yahoo/yfinance saubere Zukunftsdaten; fehlende Werte werden bewusst als '-' angezeigt."
        )

        earnings_universe_mode = st.radio(
            "Earnings-Universum",
            options=[
                "Aktuell gefilterte Aktien",
                "Alle Aktien aus der Analyse"
            ],
            horizontal=True,
            key="earnings_universe_mode"
        )

        earnings_universe_df = df_filtered.copy() if earnings_universe_mode == "Aktuell gefilterte Aktien" else df.copy()

        earnings_universe_df = earnings_universe_df.dropna(subset=["Ticker"]).copy()
        earnings_universe_df["Ticker"] = earnings_universe_df["Ticker"].astype(str).str.strip()
        earnings_universe_df = earnings_universe_df.drop_duplicates(subset=["Ticker"])

        col_earn_1, col_earn_2, col_earn_3 = st.columns([1, 1, 2])

        with col_earn_1:
            earnings_days_forward = st.selectbox(
                "Zeitraum",
                options=[7, 14, 30, 60, 90, 180, 365],
                index=4,
                format_func=lambda value: f"nächste {value} Tage",
                key="earnings_days_forward"
            )

        with col_earn_2:
            earnings_count = len(earnings_universe_df)

            if earnings_count == 0:
                max_earnings_scan = 0
                st.warning("Keine Aktien für den Earnings-Scan verfügbar.")

            elif earnings_count == 1:
                max_earnings_scan = 1
                st.caption("1 Aktie für den Earnings-Scan verfügbar.")

            else:
                slider_max = earnings_count
                slider_default = min(200, slider_max)

                # Eigener Key je Universum/Anzahl, damit Streamlit keinen alten
                # Slider-Wert verwendet, der außerhalb der neuen Range liegt.
                earnings_slider_key = (
                    f"max_earnings_scan_{earnings_universe_mode}_{earnings_count}"
                    .replace(" ", "_")
                    .replace("ä", "ae")
                )

                max_earnings_scan = st.slider(
                    "Max. Aktien scannen",
                    min_value=1,
                    max_value=slider_max,
                    value=slider_default,
                    step=1 if slider_max < 50 else 10,
                    key=earnings_slider_key
                )

        with col_earn_3:
            st.info(
                "Für große Watchlists kann der Scan etwas dauern. "
                "Die Ergebnisse werden 6 Stunden gecacht."
            )

        run_earnings_scan = st.button(
            "📆 Earningskalender aktualisieren",
            key="run_earnings_scan"
        )

        if run_earnings_scan:
            earnings_calendar_df = build_earnings_calendar(
                earnings_universe_df,
                max_tickers=max_earnings_scan
            )

            st.session_state["earnings_calendar_df"] = earnings_calendar_df
        else:
            earnings_calendar_df = st.session_state.get(
                "earnings_calendar_df",
                pd.DataFrame()
            )

        if earnings_calendar_df.empty:
            st.info(
                "Noch keine Earnings-Daten geladen. Klicke auf 'Earningskalender aktualisieren'."
            )
        else:
            earnings_calendar_view = earnings_calendar_df.copy()

            earnings_calendar_view["Days Until Numeric"] = pd.to_numeric(
                earnings_calendar_view["Days Until"],
                errors="coerce"
            )

            earnings_calendar_view = earnings_calendar_view[
                (earnings_calendar_view["Days Until Numeric"].notna())
                &
                (earnings_calendar_view["Days Until Numeric"] >= 0)
                &
                (earnings_calendar_view["Days Until Numeric"] <= earnings_days_forward)
            ].copy()

            upcoming_count = len(earnings_calendar_view)
            next_7_count = int((earnings_calendar_view["Days Until Numeric"] <= 7).sum()) if upcoming_count else 0
            next_30_count = int((earnings_calendar_view["Days Until Numeric"] <= 30).sum()) if upcoming_count else 0

            e1, e2, e3, e4 = st.columns(4)
            e1.metric("Treffer im Zeitraum", upcoming_count)
            e2.metric("nächste 7 Tage", next_7_count)
            e3.metric("nächste 30 Tage", next_30_count)
            e4.metric("gescannte Aktien", len(earnings_calendar_df))

            display_earnings_columns = [
                "Ticker",
                "Company",
                "Currency",
                "Earnings Date",
                "Days Until",
                "Time",
                "EPS Estimate",
                "Revenue Estimate",
                "Terminal Grade",
                "Terminal Score",
                "Action Signal",
                "Valuation Status",
                "Setup Quality",
                "Risk Level",
                "Short Info",
                "Data Source"
            ]

            display_earnings_columns = [
                column for column in display_earnings_columns
                if column in earnings_calendar_view.columns
            ]

            smart_dataframe(
                earnings_calendar_view[display_earnings_columns],
                width="stretch",
                hide_index=True
            )

            st.download_button(
                "⬇️ Earningskalender als CSV exportieren",
                data=earnings_calendar_view[display_earnings_columns].to_csv(index=False, sep=";").encode("utf-8-sig"),
                file_name="hartmut_terminal_earningskalender.csv",
                mime="text/csv"
            )

            with st.expander("ℹ️ Hinweis zur Datenqualität", expanded=False):
                st.write(
                    "Earnings-Daten und Analystenerwartungen kommen über Yahoo/yfinance. "
                    "Bei deutschen Nebenwerten, exotischen Börsenplätzen oder sehr kleinen Titeln fehlen diese Daten häufig. "
                    "Ein '-' bedeutet daher nicht automatisch, dass keine Earnings existieren, sondern dass keine verwertbare Schätzung gefunden wurde."
                )


with tab_dividends:
    # ============================================================
    # DIVIDENDENKALENDER
    # ============================================================

    with st.expander("📅 Dividendenkalender", expanded=True):
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

        smart_dataframe(
            dividend_calendar,
            width="stretch"
        )

        st.download_button(
            "⬇️ Dividendenkalender als CSV exportieren",
            data=dividend_calendar.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name="hartmut_terminal_dividendenkalender.csv",
            mime="text/csv"
        )


with tab_bitcoin:
    with st.expander("₿ Bitcoin / Krypto-Signal", expanded=True):
        st.markdown(
            """
            Dieses Fenster zieht Bitcoin-Daten über Yahoo Finance und bewertet das Setup regelbasiert.  
            Es ist **keine Anlageberatung**, sondern ein technischer Kontext für Trend, Momentum und Überhitzung.
            """
        )

        btc_ticker = st.selectbox(
            "Bitcoin-Datenquelle",
            options=["BTC-USD", "BTC-EUR"],
            index=0,
            help="BTC-USD hat meist die stabilsten Yahoo-Daten. BTC-EUR ist praktisch, wenn du Euro-Kurse sehen willst."
        )

        bitcoin_snapshot = load_bitcoin_snapshot(btc_ticker)

        btc_col_1, btc_col_2, btc_col_3, btc_col_4, btc_col_5 = st.columns(5)
        btc_col_1.metric("BTC Kurs", f"{bitcoin_snapshot.get('last', '-') } {bitcoin_snapshot.get('currency', '-')}")
        btc_col_2.metric("24H %", bitcoin_snapshot.get("perf_24h", "-"))
        btc_col_3.metric("7D %", bitcoin_snapshot.get("perf_7d", "-"))
        btc_col_4.metric("1M %", bitcoin_snapshot.get("perf_1m", "-"))
        btc_col_5.metric("RSI", bitcoin_snapshot.get("rsi", "-"))

        render_bitcoin_signal_card(bitcoin_snapshot)

        btc_detail_df = pd.DataFrame([
            {
                "Ticker": btc_ticker,
                "Last": bitcoin_snapshot.get("last", "-"),
                "Currency": bitcoin_snapshot.get("currency", "-"),
                "24H %": bitcoin_snapshot.get("perf_24h", "-"),
                "7D %": bitcoin_snapshot.get("perf_7d", "-"),
                "1M %": bitcoin_snapshot.get("perf_1m", "-"),
                "3M %": bitcoin_snapshot.get("perf_3m", "-"),
                "RSI": bitcoin_snapshot.get("rsi", "-"),
                "SMA20": bitcoin_snapshot.get("sma20", "-"),
                "SMA50": bitcoin_snapshot.get("sma50", "-"),
                "SMA200": bitcoin_snapshot.get("sma200", "-"),
                "BTC Score": bitcoin_snapshot.get("score", 0),
                "Signal": bitcoin_snapshot.get("signal", "-"),
                "Empfehlungslogik": bitcoin_snapshot.get("recommendation", "-"),
            }
        ])

        smart_dataframe(btc_detail_df, width="stretch")

        chart_df = build_bitcoin_chart_frame(btc_ticker)
        if not chart_df.empty:
            st.markdown("#### Bitcoin Chart: Close, SMA20, SMA50, SMA200")
            st.line_chart(chart_df[["Close", "SMA20", "SMA50", "SMA200"]], height=320)
        else:
            st.warning("Für Bitcoin konnten aktuell keine Chartdaten geladen werden.")


with tab_analysis:
    # ============================================================
    # TABELLE
    # ============================================================

    with st.expander("📋 Gesamttabelle", expanded=False):
        st.caption(
            "Standard ist die kompakte Entscheidungsansicht. "
            "Für Detailprüfungen kannst du oben auf Bewertung, Technik, Dividende, Fundamental oder Vollständig wechseln."
        )

        table_view_mode = st.radio(
            "Tabellenansicht",
            [
                "Kompakt",
                "Bewertung",
                "Technik",
                "Dividende",
                "Fundamental",
                "Vollständig"
            ],
            index=0,
            horizontal=True,
            key="analysis_table_view_mode"
        )

        table_view_columns = {
            "Kompakt": [
                "Ticker",
                "Company",
                "Price",
                "Action Signal",
                "Terminal Grade",
                "Terminal Score",
                "Valuation Status",
                "Risk Level",
                "Setup Quality",
                "Score",
                "RSI",
                "1M %",
                "3M %",
                "CRV",
                "Dividend Yield %"
            ],
            "Bewertung": [
                "Ticker",
                "Company",
                "Price",
                "Valuation Status",
                "Valuation Score",
                "Valuation Reasons",
                "Forward PE",
                "Trailing PE",
                "PEG Ratio",
                "Revenue Growth",
                "Earnings Growth",
                "Profit Margin",
                "Free Cashflow",
                "Fundamental Score",
                "Terminal Grade",
                "Terminal Score"
            ],
            "Technik": [
                "Ticker",
                "Company",
                "Price",
                "Action Signal",
                "Setup Quality",
                "Score",
                "RSI",
                "EMA20",
                "EMA50",
                "EMA100",
                "1D %",
                "1W %",
                "1M %",
                "3M %",
                "6M %",
                "CRV",
                "Entry Zone",
                "Stop Loss New",
                "Target 1",
                "Target 2",
                "Target Basis"
            ],
            "Dividende": [
                "Ticker",
                "Company",
                "Price",
                "Dividend Yield %",
                "Dividend Rate",
                "Ex Dividend Date",
                "Dividend Month",
                "Dividend Year",
                "Rating",
                "Risk Level",
                "Terminal Grade",
                "Terminal Score"
            ],
            "Fundamental": [
                "Ticker",
                "Company",
                "Price",
                "Fundamental Score",
                "Fundamental Rating",
                "Fundamental Pros",
                "Fundamental Cons",
                "Forward PE",
                "Trailing PE",
                "PEG Ratio",
                "Revenue Growth",
                "Earnings Growth",
                "Profit Margin",
                "Debt To Equity",
                "Free Cashflow",
                "Operating Cashflow",
                "Valuation Status",
                "Valuation Score"
            ]
        }

        if table_view_mode == "Vollständig":
            priority_columns = [
                "Ticker",
                "Company",
                "Price",
                "Terminal Grade",
                "Terminal Score",
                "Action Signal",
                "Valuation Status",
                "Valuation Score",
                "Risk Level",
                "Setup Quality",
                "Strategy Mode"
            ]

            remaining_columns = [
                column for column in df_filtered.columns
                if column not in priority_columns and column != "Currency"
            ]

            table_columns = [
                column for column in priority_columns
                if column in df_filtered.columns
            ] + remaining_columns
        else:
            selected_columns = table_view_columns.get(table_view_mode, table_view_columns["Kompakt"])
            table_columns = [
                column for column in selected_columns
                if column in df_filtered.columns and column != "Currency"
            ]

        # Currency bewusst immer ganz hinten anzeigen, egal welche Ansicht gewählt ist.
        if "Currency" in df_filtered.columns:
            table_columns.append("Currency")

        if not table_columns:
            st.warning("Für diese Tabellenansicht sind in den aktuellen Daten keine passenden Spalten vorhanden.")
        else:
            smart_dataframe(
                df_filtered[table_columns],
                width="stretch"
            )

            export_name = table_view_mode.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
            st.download_button(
                f"⬇️ {table_view_mode}-Tabelle als CSV exportieren",
                data=df_filtered[table_columns].to_csv(index=False, sep=";").encode("utf-8-sig"),
                file_name=f"hartmut_terminal_gesamttabelle_{export_name}.csv",
                mime="text/csv"
            )


with tab_lists:
    # ============================================================
    # ⭐ PERSÖNLICHE WATCHLIST & KAUFLIST
    # ============================================================

    with st.expander("⭐ Persönliche Watchlist & Kaufliste", expanded=True):
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

                smart_dataframe(
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

                smart_dataframe(
                    user_buy_df[buy_columns],
                    width="stretch",
                    hide_index=True
                )

            else:

                st.info("Noch keine Kauf-Aktien ausgewählt.")


        # ============================================================
        # 📡 LISTEN-RADAR: EIGENE LISTEN MIT SIGNALEN
        # ============================================================

        st.markdown("### 📡 Listen-Radar")

        combined_user_tickers = sorted(
            set(selected_watchlist_tickers + selected_buy_tickers)
        )

        if not combined_user_tickers:
            st.caption("Noch keine Aktien in Watchlist oder Kaufliste gespeichert.")
        else:
            list_radar_df = df[
                df["Ticker"].astype(str).str.strip().isin(combined_user_tickers)
            ].copy()

            list_radar_df["Liste"] = list_radar_df["Ticker"].astype(str).apply(
                lambda ticker: "Watchlist & Kauf"
                if ticker in selected_watchlist_tickers and ticker in selected_buy_tickers
                else "Watchlist"
                if ticker in selected_watchlist_tickers
                else "Kauf"
            )

            list_radar_columns = [
                "Liste",
                "Ticker",
                "Company",
                "Terminal Grade",
                "Terminal Score",
                "Action Signal",
                "Valuation Status",
                "Score",
                "Fundamental Score",
                "Risk Level",
                "Price",
                "CRV",
                "Dividend Yield %"
            ]

            list_radar_columns = [
                column for column in list_radar_columns
                if column in list_radar_df.columns
            ]

            signal_counts = (
                list_radar_df["Action Signal"].astype(str).value_counts()
                if "Action Signal" in list_radar_df.columns
                else pd.Series(dtype=int)
            )

            lr1, lr2, lr3, lr4 = st.columns(4)
            lr1.metric("Listen-Aktien", len(list_radar_df))
            lr2.metric("BUY/STRONG", int(signal_counts[signal_counts.index.str.contains("BUY", case=False, na=False)].sum()) if not signal_counts.empty else 0)
            lr3.metric("WATCH", int(signal_counts[signal_counts.index.str.contains("WATCH", case=False, na=False)].sum()) if not signal_counts.empty else 0)
            lr4.metric("AVOID/RISK", int(signal_counts[signal_counts.index.str.contains("AVOID|SELL|OVERHEATED|TAKE", case=False, na=False)].sum()) if not signal_counts.empty else 0)

            smart_dataframe(
                list_radar_df[list_radar_columns],
                width="stretch",
                hide_index=True
            )


with tab_admin:
    # ============================================================
    # 👑 SUPERUSER-ANSICHT / SYSTEMSTATUS
    # ============================================================

    superusers = st.secrets.get("app", {}).get("superusers", [])

    if current_user in superusers:

        with st.expander("🩺 Systemstatus & Datenqualität", expanded=True):
            rel_file_exists = os.path.exists("stock_relationships.csv")
            portfolio_file_exists = os.path.exists("portfolio_analysis.csv")
            missing_fundamental = 0
            if "Fundamental Rating" in df.columns:
                missing_fundamental = (df["Fundamental Rating"].astype(str).isin(["WEAK / UNKNOWN", "UNKNOWN", "-"])).sum()

            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Aktien geladen", len(df))
            s2.metric("Beziehungen", len(relationships_df) if 'relationships_df' in globals() else 0)
            s3.metric("Unklare Fundamentals", int(missing_fundamental))
            s4.metric("Supabase", "aktiv" if "supabase" in st.secrets else "fehlt")

            status_df = pd.DataFrame([
                {"Prüfung": "portfolio_analysis.csv", "Status": "OK" if portfolio_file_exists else "Fehlt"},
                {"Prüfung": "stock_relationships.csv", "Status": "OK" if rel_file_exists else "Fehlt"},
                {"Prüfung": "Supabase Secrets", "Status": "OK" if "supabase" in st.secrets else "Fehlt"},
                {"Prüfung": "Nutzerlisten-Tabelle", "Status": "wird beim Laden geprüft"},
            ])
            smart_dataframe(status_df, width="stretch", hide_index=True)

        with st.expander("👑 Superuser-Übersicht", expanded=True):


            all_user_lists = load_user_lists()

            if all_user_lists.empty:

                st.info("Noch keine gespeicherten Nutzerlisten vorhanden.")

            else:

                all_user_lists = all_user_lists.copy()

                # ============================================================
                # 📡 SUPERUSER-LISTEN-RADAR
                # ============================================================
                # Gleiche Idee wie im Tab "Listen", aber für alle Nutzer.
                # Die Original-Superuser-Übersicht bleibt darunter erhalten.
                admin_lists_raw = all_user_lists.copy()
                admin_lists_raw["Ticker"] = admin_lists_raw["ticker"].astype(str).str.strip()
                admin_lists_raw["User"] = admin_lists_raw["username"].astype(str).str.strip()
                admin_lists_raw["Liste"] = admin_lists_raw["list_type"].replace({
                    "watchlist": "Watchlist",
                    "buy": "Kauf"
                })

                admin_signal_columns = [
                    "Ticker",
                    "Company",
                    "Terminal Grade",
                    "Terminal Score",
                    "Action Signal",
                    "Valuation Status",
                    "Valuation Score",
                    "Score",
                    "Fundamental Score",
                    "Risk Level",
                    "Price",
                    "CRV",
                    "Dividend Yield %"
                ]

                admin_signal_columns = [
                    column for column in admin_signal_columns
                    if column in df.columns
                ]

                admin_signal_df = df[admin_signal_columns].copy()
                admin_signal_df["Ticker"] = admin_signal_df["Ticker"].astype(str).str.strip()

                admin_radar_df = admin_lists_raw.merge(
                    admin_signal_df,
                    on="Ticker",
                    how="left"
                )

                if "Company" not in admin_radar_df.columns:
                    admin_radar_df["Company"] = admin_radar_df.get("name", "")
                else:
                    admin_radar_df["Company"] = admin_radar_df["Company"].fillna(
                        admin_radar_df.get("name", "")
                    )

                admin_radar_columns = [
                    "Liste",
                    "User",
                    "Ticker",
                    "Company",
                    "Terminal Grade",
                    "Terminal Score",
                    "Action Signal",
                    "Valuation Status",
                    "Valuation Score",
                    "Score",
                    "Fundamental Score",
                    "Risk Level",
                    "Price",
                    "CRV",
                    "Dividend Yield %"
                ]

                admin_radar_columns = [
                    column for column in admin_radar_columns
                    if column in admin_radar_df.columns
                ]

                st.markdown("### 📡 Superuser-Listen-Radar")

                admin_signal_counts = (
                    admin_radar_df["Action Signal"].astype(str).value_counts()
                    if "Action Signal" in admin_radar_df.columns
                    else pd.Series(dtype=int)
                )

                ar1, ar2, ar3, ar4, ar5 = st.columns(5)
                ar1.metric("Einträge", len(admin_radar_df))
                ar2.metric("Nutzer", admin_radar_df["User"].nunique() if "User" in admin_radar_df.columns else 0)
                ar3.metric("Ticker", admin_radar_df["Ticker"].nunique() if "Ticker" in admin_radar_df.columns else 0)
                ar4.metric(
                    "BUY/STRONG",
                    int(admin_signal_counts[admin_signal_counts.index.str.contains("BUY", case=False, na=False)].sum())
                    if not admin_signal_counts.empty else 0
                )
                ar5.metric(
                    "Risiko/Exit",
                    int(admin_signal_counts[admin_signal_counts.index.str.contains("AVOID|SELL|OVERHEATED|TAKE", case=False, na=False)].sum())
                    if not admin_signal_counts.empty else 0
                )

                smart_dataframe(
                    admin_radar_df[admin_radar_columns].sort_values(
                        by=[column for column in ["Liste", "User", "Terminal Score", "Ticker"] if column in admin_radar_columns],
                        ascending=[True, True, False, True][:len([column for column in ["Liste", "User", "Terminal Score", "Ticker"] if column in admin_radar_columns])]
                    ),
                    width="stretch",
                    hide_index=True
                )

                st.markdown("### 👑 Rohübersicht aller Nutzerlisten")

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

                smart_dataframe(
                    all_user_lists,
                    width="stretch",
                    hide_index=True
                )


with tab_analysis:
    # ============================================================
    # AKTIENKARTEN
    # ============================================================

    with st.expander("🔥 Aktienübersicht / Karten", expanded=False):
        for _, row in df_filtered.iterrows():

            color = get_border_color(row["Rating"])
            rating_light = get_rating_light(row["Rating"])
            risk_light = get_risk_light(row["Risk Level"])

            card_html = f"""
        <div style="background-color:#ffffff; padding:16px 18px; border-radius:16px; margin-bottom:16px; border-left:8px solid {color}; box-shadow:0 4px 14px rgba(0,0,0,0.10); font-family:Arial, sans-serif; color:#111827; line-height:1.55; overflow-wrap:break-word; word-break:break-word;">
        <h2 style="margin:0 0 16px 0; font-size:21px; font-weight:800;">{row['Ticker']} - {row['Company']}</h2>
        <hr style="border:none; border-top:2px solid #9ca3af; margin:0 0 20px 0;">

        <p style="font-size:14px; margin:0 0 10px 0;">💰 <b>Preis:</b> {row['Price']} | 🌍 <b>Währung:</b> {row.get('Currency', '-')}</p>


        <p style="font-size:14px; margin:0 0 10px 0;">⭐ <b>Rating:</b> {rating_light} {row['Rating']} | 📈 <b>Score:</b> {row['Score']} | ⚠️ <b>Risiko:</b> {risk_light} {row['Risk Level']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🎯 <b>Signal:</b> {row['Action Signal']} | 🧭 <b>Setup:</b> {row['Setup Quality']} | 🕒 <b>Horizont:</b> {row['Strategy Mode']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">📍 <b>Einstiegszone:</b> {row['Entry Zone']} | 🛑 <b>Stop:</b> {row['Stop Loss New']} | 🎯 <b>Ziel 1:</b> {row['Target 1']} | 🚀 <b>Ziel 2:</b> {row['Target 2']} | ⚖️ <b>CRV:</b> {row['CRV']} | 🧱 <b>Zielbasis:</b> {row['Target Basis']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">📊 <b>Performance:</b><br>1D: {row['1D %']}% | 1W: {row['1W %']}% | 1M: {row['1M %']}% | 3M: {row['3M %']}% | 6M: {row['6M %']}%</p>

        <p style="font-size:14px; margin:0 0 10px 0;">📉 <b>EMA:</b><br>EMA20: {row['EMA20']} | EMA50: {row['EMA50']} | EMA100: {row['EMA100']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">💵 <b>Dividende:</b> {row['Dividend Yield %']} | 📅 <b>Ex-Dividende:</b> {row['Ex Dividend Date']} | 🪙 <b>Dividendensatz:</b> {row['Dividend Rate']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🛑 <b>Stop-Loss-Idee:</b> {row['Stop Loss Idea']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🏢 <b>Market Cap:</b> {row['Market Cap Class']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🧾 <b>Fundamental:</b> {row['Fundamental Rating']} | 📊 <b>Fundamental Score:</b> {row['Fundamental Score']}/8</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🧭 <b>Terminal-Grade:</b> {row['Terminal Grade']} | Terminal Score: {row['Terminal Score']}/100</p>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#eef2ff; padding:9px 11px; border-radius:10px;">🧭 <b>Terminal-Fazit:</b> {row['Terminal Summary']}</div>

        <p style="font-size:14px; margin:0 0 10px 0;">💎 <b>Bewertungshinweis:</b> {row['Valuation Status']} | Punkte: {row['Valuation Score']}</p>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#f8fafc; padding:9px 11px; border-radius:10px;">💬 <b>Bewertungsgrund:</b> {row['Valuation Summary']}<br><b>Details:</b> {row['Valuation Reasons']}</div>

        <p style="font-size:14px; margin:0 0 10px 0;">🏦 <b>Bewertung:</b><br>Forward KGV: {row['Forward PE']} | KGV: {row['Trailing PE']} | PEG: {row['PEG Ratio']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">📈 <b>Fundamentales Wachstum:</b><br>Umsatzwachstum: {row['Revenue Growth']} | Gewinnwachstum: {row['Earnings Growth']} | Marge: {row['Profit Margin']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">💸 <b>Cashflow / Verschuldung:</b><br>Free Cashflow: {row['Free Cashflow']} | Operating Cashflow: {row['Operating Cashflow']} | Debt/Equity: {row['Debt To Equity']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🔄 <b>Turnaround:</b> {row['Turnaround Candidate']}</p>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#ecfdf5; padding:9px 11px; border-radius:10px;">✅ <b>Pro:</b> {row['Pros']}</div>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#fff7ed; padding:9px 11px; border-radius:10px;">⚠️ <b>Contra:</b> {row['Cons']}</div>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#eef2ff; padding:9px 11px; border-radius:10px;">🧭 <b>Entscheidung:</b> {row['Decision Summary']}</div>

        <div style="font-size:13px; margin:8px 0 0 0; background:#f3f4f6; padding:9px 11px; border-radius:10px;">🧠 <b>Analyse:</b> {row['Reason']}</div>
        </div>
        """

            st.markdown(card_html, unsafe_allow_html=True)
