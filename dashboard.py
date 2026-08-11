from __future__ import annotations

import json
import os
import re
import subprocess
import hmac
import math
from html import escape
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf
import streamlit.components.v1 as st_components

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except Exception:
    create_client = None
    Client = object
    SUPABASE_AVAILABLE = False

BASE = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Berlin")
PORTFOLIO_FILE = BASE / "portfolio_analysis.csv"
WATCHLIST_FILE = BASE / "clean_watchlist.csv"
REL_FILE = BASE / "stock_relationships_v3.csv"
META_FILE = BASE / "app_meta.json"
DATA_META_FILE = BASE / "data_update_meta.json"
USER_LIST_FILE = BASE / "user_stock_lists.csv"
TRADE_JOURNAL_FILE = BASE / "user_trade_journal.csv"
SUPABASE_TABLE = "user_stock_lists"
TRADE_JOURNAL_TABLE = "user_trade_journal"
USER_LIST_COLUMNS = ["username", "list_type", "ticker", "name", "created_at"]
TRADE_COLUMNS = [
    "id", "username", "ticker", "name", "direction", "status", "entry_date",
    "entry_price", "stop_loss", "target_price", "position_size", "exit_date",
    "exit_price", "notes", "created_at"
]

st.set_page_config(page_title="Hartmut Börsentool 3.1", page_icon="📈", layout="wide")

st.markdown("""
<style>
:root { --line:#e5e7eb; --muted:#6b7280; --soft:#f8fafc; --ink:#111827; --green:#166534; --greenbg:#f0fdf4; --amber:#92400e; --amberbg:#fffbeb; --red:#991b1b; --redbg:#fef2f2; --blue:#1d4ed8; --bluebg:#eff6ff; }
.block-container {padding-top: 1rem; max-width: 1500px;}
.hb-top {border:1px solid var(--line);border-radius:14px;padding:12px 16px;background:white;margin-bottom:14px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.hb-title {font-size:1.28rem;font-weight:800;color:var(--ink)}
.hb-meta {font-size:.76rem;color:var(--muted);margin-top:4px;}
.hb-stockhead {border:1px solid var(--line);border-radius:16px;padding:16px 18px;background:white;margin:6px 0 12px 0;box-shadow:0 1px 3px rgba(15,23,42,.05)}
.hb-stockname {font-size:1.34rem;font-weight:850;color:var(--ink);line-height:1.1}
.hb-ticker {font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.78rem;border:1px solid var(--line);border-radius:7px;padding:2px 7px;margin-left:6px;background:var(--soft)}
.hb-price {font-size:1.42rem;font-weight:850;margin-top:8px}.hb-positive{color:var(--green)}.hb-negative{color:var(--red)}
.hb-hero {border:1px solid var(--line);border-radius:18px;padding:20px;background:linear-gradient(135deg,#fff,#f8fafc);margin:8px 0 14px 0;box-shadow:0 2px 6px rgba(15,23,42,.05)}
.hb-verdict {font-size:1.45rem;font-weight:850;margin:3px 0 7px}.hb-sub {color:#4b5563;font-size:.9rem;line-height:1.55;max-width:900px}
.hb-scoregrid {display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:10px 0 16px}.hb-scorecard{border:1px solid var(--line);border-radius:14px;padding:12px;background:white}.hb-scorelabel{font-size:.69rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-weight:700}.hb-scorevalue{font-size:1.12rem;font-weight:850;margin-top:2px}.hb-bar{height:6px;background:#eef2f7;border-radius:99px;overflow:hidden;margin-top:8px}.hb-fill{height:100%;background:#374151;border-radius:99px}
.hb-chip {display:inline-block;padding:4px 8px;border:1px solid var(--line);border-radius:999px;margin:2px 4px 2px 0;font-size:.73rem;background:var(--soft)}
.hb-section {font-size:1.02rem;font-weight:800;margin:18px 0 8px 0}.hb-note{border:1px solid var(--line);border-radius:12px;padding:11px 13px;background:var(--soft);font-size:.82rem;line-height:1.45}.hb-alert{border-left:4px solid #d97706;background:var(--amberbg);padding:10px 12px;border-radius:10px;font-size:.82rem}.hb-ok{border-left:4px solid #16a34a;background:var(--greenbg);padding:10px 12px;border-radius:10px;font-size:.82rem}
.hb-relcard{border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:white;margin-bottom:7px}.hb-relname{font-weight:800;font-size:.88rem}.hb-relmeta{font-size:.7rem;color:var(--muted);margin-top:2px}.hb-reldesc{font-size:.76rem;color:#4b5563;line-height:1.35;margin-top:5px}.hb-scorepill{float:right;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:800;border:1px solid var(--line);border-radius:8px;padding:2px 6px;background:var(--soft)}
[data-testid="stMetric"] {border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:white;}[data-testid="stMetric"] label {font-size:.72rem !important;color:var(--muted) !important;text-transform:uppercase;}[data-testid="stMetricValue"] {font-size:1.15rem !important;}
.hb-scancard{border:1px solid var(--line);border-radius:14px;padding:12px 13px;background:white;min-height:142px;margin-bottom:6px;box-shadow:0 1px 2px rgba(15,23,42,.035)}
.hb-scanname{font-weight:850;font-size:.9rem;padding-right:50px}.hb-scanmeta{font-size:.71rem;color:var(--muted);margin:3px 0 7px}.hb-scanwhy{font-size:.76rem;color:#4b5563;line-height:1.38}.hb-bigpill{display:inline-block;font-size:.7rem;border-radius:999px;padding:3px 8px;background:var(--soft);border:1px solid var(--line);margin-right:4px}.hb-kpi{border:1px solid var(--line);border-radius:14px;padding:13px;background:white}.hb-kpi-label{font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:750}.hb-kpi-value{font-size:1.3rem;font-weight:900;color:var(--ink);margin-top:2px}.hb-kpi-sub{font-size:.72rem;color:var(--muted);margin-top:2px}.hb-minirow{display:flex;justify-content:space-between;border-bottom:1px solid #f1f5f9;padding:5px 0;font-size:.77rem}.hb-system{border:1px solid var(--line);border-radius:12px;background:#f8fafc;padding:10px 12px;font-size:.75rem;color:#4b5563}
@media (max-width:900px){.hb-scoregrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
""", unsafe_allow_html=True)



def _secret_dict(name):
    try:
        value = st.secrets.get(name, {})
        return dict(value) if value else {}
    except Exception:
        return {}


def check_password():
    """Login über [users] in Streamlit Secrets. Lokal ohne Secrets: Entwicklungsmodus."""
    users = _secret_dict("users")
    if not users:
        st.session_state.setdefault("current_user", "hartmut")
        st.session_state["password_correct"] = True
        return True

    def password_entered():
        username = st.session_state.get("username", "").strip()
        password = st.session_state.get("password", "")
        expected = users.get(username)
        ok = expected is not None and hmac.compare_digest(str(password), str(expected))
        st.session_state["password_correct"] = ok
        if ok:
            st.session_state["current_user"] = username
            st.session_state.pop("password", None)

    if st.session_state.get("password_correct", False):
        return True

    st.title("🔐 Hartmut Börsentool")
    st.caption("Bitte anmelden, um persönliche Watchlists und das Trade-Journal zu laden.")
    st.text_input("Benutzername", key="username")
    st.text_input("Passwort", type="password", key="password")
    st.button("Einloggen", on_click=password_entered, type="primary")
    if st.session_state.get("password_correct") is False:
        st.error("Benutzername oder Passwort falsch.")
    return False


def supabase_configured():
    if not SUPABASE_AVAILABLE:
        return False
    cfg = _secret_dict("supabase")
    return bool(cfg.get("url") and cfg.get("key"))


@st.cache_resource(show_spinner=False)
def get_supabase_client():
    cfg = _secret_dict("supabase")
    if not (SUPABASE_AVAILABLE and cfg.get("url") and cfg.get("key")):
        raise RuntimeError("Supabase ist nicht konfiguriert")
    return create_client(cfg["url"], cfg["key"])


def storage_mode():
    return "Supabase" if supabase_configured() else "Lokal (CSV)"


def _empty_user_lists():
    return pd.DataFrame(columns=USER_LIST_COLUMNS)


def _normalize_user_lists(data):
    if data is None or data.empty:
        return _empty_user_lists()
    data = data.copy()
    for c in USER_LIST_COLUMNS:
        if c not in data.columns:
            data[c] = ""
    return data[USER_LIST_COLUMNS]


def load_user_lists():
    if supabase_configured():
        try:
            resp = get_supabase_client().table(SUPABASE_TABLE).select(
                "username,list_type,ticker,name,created_at"
            ).execute()
            return _normalize_user_lists(pd.DataFrame(resp.data)), None
        except Exception as exc:
            # Automatischer Fallback, damit eine pausierte DB das Tool nicht blockiert.
            fallback, _ = load_user_lists_local()
            return fallback, f"Supabase nicht erreichbar – lokaler Fallback aktiv: {exc}"
    return load_user_lists_local()


def load_user_lists_local():
    try:
        if USER_LIST_FILE.exists():
            data = pd.read_csv(USER_LIST_FILE)
            return _normalize_user_lists(data), None
    except Exception as exc:
        return _empty_user_lists(), str(exc)
    return _empty_user_lists(), None


def get_saved_tickers(username, list_type):
    data, _ = load_user_lists()
    if data.empty:
        return []
    subset = data[
        data["username"].astype(str).eq(str(username))
        & data["list_type"].astype(str).eq(str(list_type))
    ]
    return list(dict.fromkeys(subset["ticker"].dropna().astype(str).tolist()))


def update_user_list(username, list_type, selected_tickers, stock_df):
    selected_tickers = list(dict.fromkeys(str(t).strip() for t in selected_tickers if str(t).strip()))
    rows = []
    now = datetime.now(TZ).isoformat()
    for ticker in selected_tickers:
        hit = stock_df[stock_df["Ticker"].astype(str).eq(ticker)]
        name = hit.iloc[0].get("Company", ticker) if not hit.empty else ticker
        rows.append({
            "username": username, "list_type": list_type, "ticker": ticker,
            "name": str(name), "created_at": now,
        })

    if supabase_configured():
        try:
            sb = get_supabase_client()
            sb.table(SUPABASE_TABLE).delete().eq("username", username).eq("list_type", list_type).execute()
            if rows:
                sb.table(SUPABASE_TABLE).insert(rows).execute()
            return "Supabase", None
        except Exception as exc:
            # Fallback schreiben, aber den Nutzer über den Wechsel informieren.
            err = _update_user_list_local(username, list_type, rows)
            return "Lokal (Fallback)", f"Supabase-Fehler: {exc}" if err is None else f"Supabase: {exc}; Lokal: {err}"

    err = _update_user_list_local(username, list_type, rows)
    return "Lokal (CSV)", err


def _update_user_list_local(username, list_type, rows):
    try:
        existing, _ = load_user_lists_local()
        keep = existing[
            ~(existing["username"].astype(str).eq(str(username))
              & existing["list_type"].astype(str).eq(str(list_type)))
        ].copy()
        add = pd.DataFrame(rows, columns=USER_LIST_COLUMNS)
        result = pd.concat([keep, add], ignore_index=True)
        result.to_csv(USER_LIST_FILE, index=False, encoding="utf-8-sig")
        return None
    except Exception as exc:
        return str(exc)


def toggle_user_ticker(username, list_type, ticker, stock_df):
    current = get_saved_tickers(username, list_type)
    if ticker in current:
        current = [t for t in current if t != ticker]
        added = False
    else:
        current.append(ticker)
        added = True
    mode, err = update_user_list(username, list_type, current, stock_df)
    return added, mode, err


def _empty_trades():
    return pd.DataFrame(columns=TRADE_COLUMNS)


def _normalize_trades(data):
    if data is None or data.empty:
        return _empty_trades()
    data = data.copy()
    for c in TRADE_COLUMNS:
        if c not in data.columns:
            data[c] = None
    return data[TRADE_COLUMNS]


def load_trade_journal(username):
    if supabase_configured():
        try:
            resp = (get_supabase_client().table(TRADE_JOURNAL_TABLE).select("*")
                    .eq("username", username).order("created_at", desc=True).execute())
            return _normalize_trades(pd.DataFrame(resp.data)), None, "Supabase"
        except Exception as exc:
            local, local_err = load_trade_journal_local(username)
            return local, f"Supabase-Journal nicht erreichbar – lokaler Fallback: {exc}", "Lokal (Fallback)"
    local, err = load_trade_journal_local(username)
    return local, err, "Lokal (CSV)"


def load_trade_journal_local(username):
    try:
        if not TRADE_JOURNAL_FILE.exists():
            return _empty_trades(), None
        data = _normalize_trades(pd.read_csv(TRADE_JOURNAL_FILE))
        data = data[data["username"].astype(str).eq(str(username))].copy()
        return data, None
    except Exception as exc:
        return _empty_trades(), str(exc)


def add_trade_journal_entry(entry):
    if supabase_configured():
        try:
            payload = {k: v for k, v in entry.items() if k != "id"}
            get_supabase_client().table(TRADE_JOURNAL_TABLE).insert(payload).execute()
            return "Supabase", None
        except Exception as exc:
            local_err = _add_trade_local(entry)
            return "Lokal (Fallback)", f"Supabase-Fehler: {exc}" if local_err is None else f"Supabase: {exc}; Lokal: {local_err}"
    return "Lokal (CSV)", _add_trade_local(entry)


def _add_trade_local(entry):
    try:
        if TRADE_JOURNAL_FILE.exists():
            all_rows = _normalize_trades(pd.read_csv(TRADE_JOURNAL_FILE))
        else:
            all_rows = _empty_trades()
        numeric_ids = pd.to_numeric(all_rows["id"], errors="coerce") if not all_rows.empty else pd.Series(dtype=float)
        next_id = int(numeric_ids.max()) + 1 if not numeric_ids.empty and numeric_ids.notna().any() else 1
        row = {c: None for c in TRADE_COLUMNS}
        row.update(entry)
        row["id"] = next_id
        all_rows = pd.concat([all_rows, pd.DataFrame([row])], ignore_index=True)
        all_rows.to_csv(TRADE_JOURNAL_FILE, index=False, encoding="utf-8-sig")
        return None
    except Exception as exc:
        return str(exc)


def update_trade_journal_entry(entry_id, username, updates):
    if supabase_configured():
        try:
            get_supabase_client().table(TRADE_JOURNAL_TABLE).update(updates).eq("id", entry_id).eq("username", username).execute()
            return "Supabase", None
        except Exception as exc:
            local_err = _update_trade_local(entry_id, username, updates)
            return "Lokal (Fallback)", f"Supabase-Fehler: {exc}" if local_err is None else f"Supabase: {exc}; Lokal: {local_err}"
    return "Lokal (CSV)", _update_trade_local(entry_id, username, updates)


def _update_trade_local(entry_id, username, updates):
    try:
        if not TRADE_JOURNAL_FILE.exists():
            return "Lokale Journaldatei fehlt"
        data = _normalize_trades(pd.read_csv(TRADE_JOURNAL_FILE))
        mask = data["id"].astype(str).eq(str(entry_id)) & data["username"].astype(str).eq(str(username))
        for key, value in updates.items():
            if key in data.columns:
                data.loc[mask, key] = value
        data.to_csv(TRADE_JOURNAL_FILE, index=False, encoding="utf-8-sig")
        return None
    except Exception as exc:
        return str(exc)


def delete_trade_journal_entry(entry_id, username):
    if supabase_configured():
        try:
            get_supabase_client().table(TRADE_JOURNAL_TABLE).delete().eq("id", entry_id).eq("username", username).execute()
            return "Supabase", None
        except Exception as exc:
            local_err = _delete_trade_local(entry_id, username)
            return "Lokal (Fallback)", f"Supabase-Fehler: {exc}" if local_err is None else f"Supabase: {exc}; Lokal: {local_err}"
    return "Lokal (CSV)", _delete_trade_local(entry_id, username)


def _delete_trade_local(entry_id, username):
    try:
        if not TRADE_JOURNAL_FILE.exists():
            return None
        data = _normalize_trades(pd.read_csv(TRADE_JOURNAL_FILE))
        keep = ~(data["id"].astype(str).eq(str(entry_id)) & data["username"].astype(str).eq(str(username)))
        data.loc[keep].to_csv(TRADE_JOURNAL_FILE, index=False, encoding="utf-8-sig")
        return None
    except Exception as exc:
        return str(exc)


def trade_pnl(row):
    entry = safe_float(row.get("entry_price"))
    exit_price = safe_float(row.get("exit_price"))
    size = safe_float(row.get("position_size"))
    if entry is None or exit_price is None:
        return None, None
    direction = str(row.get("direction", "Long"))
    pct = ((exit_price - entry) / entry * 100) if direction == "Long" else ((entry - exit_price) / entry * 100)
    amount = None
    if size is not None:
        amount = (exit_price - entry) * size if direction == "Long" else (entry - exit_price) * size
    return pct, amount


def safe_float(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in {"", "-", "nan", "None"}:
        return None
    s = re.sub(r"(EUR|USD|GBP|CHF|JPY|CAD|AUD|HKD|CNY|KRW|SEK|NOK|DKK|€|\$|£|¥|%)", "", s).strip()
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def fmt_dt(v):
    if not v:
        return "noch nicht gesetzt"
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(v)


def latest_git_commit_time():
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI"], cwd=BASE, text=True, stderr=subprocess.DEVNULL
        ).strip()
        return out or None
    except Exception:
        return None


def load_meta():
    meta = json.loads(META_FILE.read_text(encoding="utf-8")) if META_FILE.exists() else {}
    git_time = latest_git_commit_time()
    if git_time:
        meta["deployment_at_detected"] = git_time
    return meta


def data_timestamp():
    if DATA_META_FILE.exists():
        try:
            raw = json.loads(DATA_META_FILE.read_text(encoding="utf-8"))
            for key in ["updated_at", "generated_at", "last_update"]:
                if raw.get(key):
                    return raw[key]
            files = raw.get("files") if isinstance(raw.get("files"), dict) else {}
            item = files.get(PORTFOLIO_FILE.name) if isinstance(files, dict) else None
            if isinstance(item, dict):
                for key in ["updated_at", "generated_at", "last_update"]:
                    if item.get(key):
                        return item[key]
        except Exception:
            pass
    if PORTFOLIO_FILE.exists():
        return datetime.fromtimestamp(PORTFOLIO_FILE.stat().st_mtime, tz=TZ).isoformat()
    return None


@st.cache_data(ttl=300, show_spinner=False)
def load_data():
    p = pd.read_csv(PORTFOLIO_FILE, sep=";")
    w = pd.read_csv(WATCHLIST_FILE, sep=";")
    # Metadaten aus der Master-Watchlist ergänzen, wenn ein älterer Analysebestand
    # diese Spalten noch nicht enthält. So bleibt der Final-Build rückwärtskompatibel.
    for col in ["Liquidity", "Exchange", "Avg Dollar Volume"]:
        if col not in p.columns and col in w.columns:
            p = p.merge(w[["Ticker", col]].drop_duplicates("Ticker"), on="Ticker", how="left")
    r = pd.read_csv(REL_FILE, sep=";") if REL_FILE.exists() else pd.DataFrame()
    return p, w, r


@st.cache_data(ttl=3600, show_spinner=False)
def selected_live_data(ticker):
    result = {"earnings": None, "ex_dividend": None, "dividend_rate": None, "history": None, "target_mean": None, "recommendation": None}
    try:
        stock = yf.Ticker(ticker)
        try:
            cal = stock.calendar
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date") or cal.get("EarningsDate")
                if isinstance(ed, (list, tuple)) and ed:
                    ed = ed[0]
                result["earnings"] = ed
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                for idx in cal.index:
                    if "earn" in str(idx).lower():
                        val = cal.loc[idx].iloc[0] if hasattr(cal.loc[idx], "iloc") else cal.loc[idx]
                        result["earnings"] = val
                        break
        except Exception:
            pass
        try:
            info = stock.info
            ts = info.get("exDividendDate")
            if ts:
                result["ex_dividend"] = datetime.fromtimestamp(ts, tz=TZ)
            if result.get("earnings") is None:
                ets = info.get("earningsTimestampStart") or info.get("earningsTimestamp") or info.get("earningsTimestampEnd")
                if ets:
                    result["earnings"] = datetime.fromtimestamp(ets, tz=TZ)
            result["dividend_rate"] = info.get("dividendRate")
            result["target_mean"] = info.get("targetMeanPrice")
            result["recommendation"] = info.get("recommendationKey")
        except Exception:
            pass
        try:
            hist = stock.history(period="2y", auto_adjust=False)
            if not hist.empty:
                result["history"] = hist[["Close", "Volume"]]
        except Exception:
            pass
    except Exception:
        pass
    return result


def quality_score(row):
    vals = []
    rev = safe_float(row.get("Revenue Growth Raw"))
    earn = safe_float(row.get("Earnings Growth Raw"))
    margin = safe_float(row.get("Profit Margin Raw"))
    debt = safe_float(row.get("Debt To Equity"))
    fcf = safe_float(row.get("Free Cashflow Raw"))
    if rev is not None: vals.append(clamp((rev + .05) / .30 * 100))
    if earn is not None: vals.append(clamp((earn + .05) / .40 * 100))
    if margin is not None: vals.append(clamp((margin + .05) / .30 * 100))
    if debt is not None: vals.append(clamp(100 - max(0, debt - 50) * .55))
    if fcf is not None: vals.append(85 if fcf > 0 else 15)
    return (sum(vals)/len(vals) if vals else 50), len(vals)


def valuation_score(row):
    vals = []
    fpe = safe_float(row.get("Forward PE"))
    tpe = safe_float(row.get("Trailing PE"))
    peg = safe_float(row.get("PEG Ratio"))
    if fpe is not None and fpe > 0:
        vals.append(clamp(105 - fpe * 2.1))
    if tpe is not None and tpe > 0:
        vals.append(clamp(105 - tpe * 1.8))
    if peg is not None and peg > 0:
        vals.append(clamp(110 - peg * 30))
    return (sum(vals)/len(vals) if vals else 50), len(vals)


def timing_score(row):
    vals = []
    score = safe_float(row.get("Score"))
    early = safe_float(row.get("Early Signal Score"))
    rs = safe_float(row.get("RS Percentile"))
    market_rs = safe_float(row.get("Market RS 1M"))
    rsi = safe_float(row.get("RSI"))
    rvol = safe_float(row.get("RVOL"))
    p1m = safe_float(row.get("1M %"))
    if score is not None: vals.append(clamp(score / 8 * 100))
    if early is not None: vals.append(clamp(early / 10 * 100))
    if rs is not None: vals.append(clamp(rs))
    if market_rs is not None: vals.append(clamp(50 + market_rs * 3))
    if rsi is not None: vals.append(90 if 48 <= rsi <= 68 else (65 if 40 <= rsi <= 75 else 35))
    if rvol is not None: vals.append(clamp(45 + (rvol - 1) * 45))
    if p1m is not None: vals.append(clamp(50 + p1m * 2))
    return (sum(vals)/len(vals) if vals else 50), len(vals)


def risk_penalty(row):
    risk = str(row.get("Risk Level", "")).upper()
    penalty = 14 if "HIGH" in risk else (7 if "MEDIUM" in risk else 0)
    label = "HOCH" if "HIGH" in risk else ("MITTEL" if "MEDIUM" in risk else "NIEDRIG")
    liquidity = str(row.get("Liquidity", "")).upper()
    cap_class = str(row.get("Market Cap Class", "")).upper()
    if "NIEDRIG" in liquidity or "LOW" in liquidity:
        penalty += 8
        label = "HOCH" if label == "MITTEL" else ("MITTEL" if label == "NIEDRIG" else label)
    if "MICRO" in cap_class:
        penalty += 5
        if label == "NIEDRIG": label = "MITTEL"
    return min(penalty, 24), label


def opportunity_components(row, horizon):
    q, qn = quality_score(row)
    v, vn = valuation_score(row)
    t, tn = timing_score(row)
    penalty, risk = risk_penalty(row)
    weights = {
        "Kurzfristig": (0.15, 0.10, 0.75),
        "Mittelfristig": (0.25, 0.20, 0.55),
        "Langfristig": (0.45, 0.35, 0.20),
    }[horizon]
    opp = q*weights[0] + v*weights[1] + t*weights[2] - penalty
    datapoints = qn + vn + tn
    confidence = clamp(45 + datapoints * 3.5, 45, 98)
    return round(clamp(opp), 1), round(q, 1), round(v, 1), round(t, 1), risk, round(confidence, 0)


def verdict(score, timing, valuation, risk):
    if risk == "HOCH" and score < 70:
        return "🔴 EHER MEIDEN", "Risiko ist hoch und der Gesamtvorteil reicht aktuell nicht aus."
    if score >= 78 and timing >= 72:
        return "🟢 INTERESSANT", "Qualität, Bewertung und Timing ergeben aktuell ein überdurchschnittliches Setup."
    if score >= 65:
        return "🟡 BEOBACHTEN", "Interessant, aber für einen Einstieg fehlt noch ein klarer Vorteil beim Timing oder Preis."
    return "⚪ KEIN KLARES SETUP", "Aktuell ergibt sich aus den verfügbaren Daten kein überzeugendes Chance-Risiko-Profil."


def profile_reasons(row, q, v, t):
    pros, warns = [], []
    rs = safe_float(row.get("RS Percentile"))
    fcf = safe_float(row.get("Free Cashflow Raw"))
    rev = safe_float(row.get("Revenue Growth Raw"))
    rsi = safe_float(row.get("RSI"))
    market_rs = safe_float(row.get("Market RS 1M"))
    if t >= 70: pros.append("Timing und Trendbild sind überdurchschnittlich")
    if rs is not None and rs >= 80: pros.append(f"Top {100-rs:.0f}% im eigenen Sektor")
    if market_rs is not None and market_rs > 0: pros.append("relative Stärke gegenüber dem Markt positiv")
    if q >= 70: pros.append("Unternehmensqualität wirkt stark")
    if fcf is not None and fcf > 0: pros.append("positiver Free Cashflow")
    if rev is not None and rev > .10: pros.append("zweistelliges Umsatzwachstum")
    if v < 45: warns.append("Bewertung ist anspruchsvoll")
    if rsi is not None and rsi > 72: warns.append("RSI zeigt kurzfristige Überhitzung")
    if str(row.get("Risk Level", "")) == "HIGH RISK": warns.append("erhöhte Volatilität / Risikoprofil")
    if "NIEDRIG" in str(row.get("Liquidity","")).upper(): warns.append("niedrige Handelsliquidität")
    if "MICRO" in str(row.get("Market Cap Class","")).upper(): warns.append("Micro-Cap-Risiko")
    return pros[:3], warns[:3]


def trade_plan(row, horizon):
    price = safe_float(row.get("Raw Price")) or safe_float(row.get("Price"))
    ema20 = safe_float(row.get("EMA20")); ema50 = safe_float(row.get("EMA50")); ema100 = safe_float(row.get("EMA100"))
    high = safe_float(row.get("52W High Raw")) or safe_float(row.get("52W High"))
    if not price: return None
    if horizon == "Kurzfristig":
        support = ema20 or ema50 or price*.95; stop = support*.97
    elif horizon == "Langfristig":
        support = ema100 or ema50 or price*.90; stop = support*.94
    else:
        support = ema50 or ema100 or price*.92; stop = support*.97
    entry_low = min(price, support*1.02)
    entry_high = max(price*1.01, support*1.04)
    target1 = high if high and high > price*1.03 else price*(1.10 if horizon!="Langfristig" else 1.20)
    risk = price-stop
    crv = (target1-price)/risk if risk > 0 and target1 > price else None
    return entry_low, entry_high, support, stop, target1, crv


def score_label(value):
    try: value=float(value)
    except Exception: return "Unklar"
    if value >= 80: return "Sehr stark"
    if value >= 68: return "Stark"
    if value >= 55: return "Solide"
    if value >= 42: return "Neutral"
    return "Schwach"


def score_card_html(label, value, suffix="/100", sub=None):
    try: numeric=max(0,min(100,float(value)))
    except Exception: numeric=0
    display=f"{numeric:.0f}{suffix}" if suffix else f"{numeric:.0f}"
    sub = sub or score_label(numeric)
    return (f'<div class="hb-scorecard"><div class="hb-scorelabel">{label}</div>'
            f'<div class="hb-scorevalue">{display}</div><div style="font-size:.72rem;color:#6b7280">{sub}</div>'
            f'<div class="hb-bar"><div class="hb-fill" style="width:{numeric:.0f}%"></div></div></div>')


def risk_card_html(risk):
    mapping={"NIEDRIG":(82,"Niedrig"),"MITTEL":(55,"Mittel"),"HOCH":(25,"Hoch")}
    bar, label=mapping.get(str(risk).upper(),(50,str(risk)))
    return (f'<div class="hb-scorecard"><div class="hb-scorelabel">Risiko</div>'
            f'<div class="hb-scorevalue">{label}</div><div style="font-size:.72rem;color:#6b7280">Risikofilter</div>'
            f'<div class="hb-bar"><div class="hb-fill" style="width:{bar}%"></div></div></div>')


def parse_event_date(value):
    if value is None or (isinstance(value,float) and pd.isna(value)): return None
    try:
        dt=pd.to_datetime(value)
        if pd.isna(dt): return None
        if getattr(dt, 'tzinfo', None) is not None:
            dt=dt.tz_convert(TZ).tz_localize(None)
        return dt.to_pydatetime()
    except Exception:
        return None


def days_until(value):
    dt=parse_event_date(value)
    if not dt: return None
    return (dt.date()-datetime.now(TZ).date()).days


def event_text(value, fallback="-"):
    dt=parse_event_date(value)
    if not dt: return fallback
    d=(dt.date()-datetime.now(TZ).date()).days
    suffix = "heute" if d==0 else (f"in {d} Tagen" if d>0 else f"vor {abs(d)} Tagen")
    return f"{dt.strftime('%d.%m.%Y')} · {suffix}"


def live_snapshot(row, live):
    hist=live.get("history") if isinstance(live,dict) else None
    result={"price": safe_float(row.get("Raw Price")) or safe_float(row.get("Price")), "day_change": safe_float(row.get("1D %")), "ema20": safe_float(row.get("EMA20")), "ema50": safe_float(row.get("EMA50")), "ema200": safe_float(row.get("EMA200")), "history": hist}
    if isinstance(hist,pd.DataFrame) and len(hist)>=2 and "Close" in hist:
        close=hist["Close"].dropna()
        if len(close)>=2:
            result["price"]=float(close.iloc[-1]); result["day_change"]=(float(close.iloc[-1])/float(close.iloc[-2])-1)*100
            result["ema20"]=float(close.ewm(span=20,adjust=False).mean().iloc[-1])
            result["ema50"]=float(close.ewm(span=50,adjust=False).mean().iloc[-1])
            result["ema200"]=float(close.ewm(span=200,adjust=False).mean().iloc[-1])
            if len(close) > 22: result["p1m"]=(float(close.iloc[-1])/float(close.iloc[-22])-1)*100
            if len(close) > 66: result["p3m"]=(float(close.iloc[-1])/float(close.iloc[-66])-1)*100
            delta=close.diff(); gain=delta.clip(lower=0); loss=(-delta).clip(lower=0)
            avg_gain=gain.ewm(alpha=1/14,adjust=False).mean(); avg_loss=loss.ewm(alpha=1/14,adjust=False).mean().replace(0,float("nan"))
            result["rsi"]=float((100-(100/(1+avg_gain/avg_loss))).iloc[-1])
            if "Volume" in hist and hist["Volume"].tail(20).mean()>0:
                result["rvol"]=float(hist["Volume"].iloc[-1]/hist["Volume"].tail(20).mean())
    return result


def profile_timing_score(row, snap):
    vals=[]
    price=snap.get("price"); e20=snap.get("ema20"); e50=snap.get("ema50"); e200=snap.get("ema200")
    rsi=snap.get("rsi") or safe_float(row.get("RSI")); p1m=snap.get("p1m"); p3m=snap.get("p3m"); rvol=snap.get("rvol") or safe_float(row.get("RVOL"))
    if price is not None and e20 is not None: vals.append(85 if price>=e20 else 35)
    if price is not None and e50 is not None: vals.append(88 if price>=e50 else 30)
    if price is not None and e200 is not None: vals.append(90 if price>=e200 else 25)
    if e20 is not None and e50 is not None: vals.append(82 if e20>=e50 else 40)
    if e50 is not None and e200 is not None: vals.append(85 if e50>=e200 else 38)
    if rsi is not None: vals.append(92 if 48<=rsi<=68 else (68 if 40<=rsi<=75 else 35))
    if p1m is not None: vals.append(clamp(50+p1m*2))
    if p3m is not None: vals.append(clamp(50+p3m*0.8))
    if rvol is not None: vals.append(clamp(45+(rvol-1)*45))
    rs=safe_float(row.get("RS Percentile")); mrs=safe_float(row.get("Market RS 1M")); early=safe_float(row.get("Early Signal Score"))
    if rs is not None: vals.append(clamp(rs))
    if mrs is not None: vals.append(clamp(50+mrs*3))
    if early is not None: vals.append(clamp(early/10*100))
    return (sum(vals)/len(vals) if vals else safe_float(row.get("Timing Score")) or 50), len(vals)


def recompute_profile_opportunity(q, v, timing, row, horizon):
    penalty, risk=risk_penalty(row)
    weights={"Kurzfristig":(0.15,0.10,0.75),"Mittelfristig":(0.25,0.20,0.55),"Langfristig":(0.45,0.35,0.20)}[horizon]
    return round(clamp(q*weights[0]+v*weights[1]+timing*weights[2]-penalty),1), risk


def profile_data_health(row, snap):
    important=[snap.get("price"), snap.get("ema20"), snap.get("ema50"), safe_float(row.get("RSI")), safe_float(row.get("Revenue Growth Raw")), safe_float(row.get("Free Cashflow Raw")), safe_float(row.get("Forward PE")), safe_float(row.get("PEG Ratio"))]
    present=sum(v is not None and not (isinstance(v,float) and pd.isna(v)) for v in important)
    pct=round(present/len(important)*100)
    return pct, "HOCH" if pct>=85 else ("MITTEL" if pct>=60 else "NIEDRIG")


def profile_action_hint(row, opp, timing, valuation, risk, snap, horizon):
    price=snap.get("price"); e20=snap.get("ema20"); rsi=safe_float(row.get("RSI"))
    if risk=="HOCH" and opp < 72: return "Aktuell eher meiden – Risiko zuerst reduzieren."
    stretched = price and e20 and price > e20*1.10
    if opp>=78 and timing>=72 and not stretched and (rsi is None or rsi<72): return "Setup ist attraktiv – Einstieg kann geprüft werden."
    if opp>=68 and (stretched or (rsi is not None and rsi>70)): return "Gute Aktie, aber nicht hinterherlaufen – Rücksetzer bevorzugen."
    if valuation<42 and opp>=65: return "Qualität/Timing passen, Bewertung verlangt aber Disziplin beim Einstieg."
    if timing<55: return "Unternehmen kann interessant sein, das Timing ist aktuell noch nicht sauber."
    return "Beobachten – auf einen klareren Vorteil bei Preis oder Timing warten."


def relation_priority(value):
    order={"LIEFERANT / LIEFERKETTE":0,"KUNDE / NACHFRAGE":1,"WERTSCHÖPFUNGSKETTE":2,"NACHFRAGE / PROFITEUR":3,"STRATEGISCH":4,"INFRASTRUKTUR / PROFITEUR":5,"KONKURRENT":6,"PEER / VERGLEICH":8,"THEMA / CLUSTER":9}
    return order.get(str(value),7)


def ecosystem_rows(relations, selected, include_thematic=False):
    if relations is None or relations.empty: return pd.DataFrame()
    rel=relations[(relations["source_ticker"].astype(str)==selected)|(relations["target_ticker"].astype(str)==selected)].copy()
    if not include_thematic:
        rel=rel[rel["default_visible"].astype(str).str.lower().isin(["true","1"])]
    if rel.empty: return rel
    # Peer-Fallback nur nutzen, wenn es für den gewählten Titel keine stärkere
    # wirtschaftliche Beziehung gibt. Eingehende Peer-Kanten werden ignoriert,
    # damit beliebte Vergleichstitel nicht künstlich riesige Netze bekommen.
    non_peer = rel[~rel["relation_class"].astype(str).eq("PEER / VERGLEICH")]
    if not non_peer.empty:
        rel = non_peer
    else:
        rel = rel[rel["source_ticker"].astype(str).eq(selected)]
    if rel.empty: return rel
    rel["counterpart"]=rel.apply(lambda r: str(r["target_ticker"]) if str(r["source_ticker"])==selected else str(r["source_ticker"]),axis=1)
    rel["_prio"]=rel["relation_class"].map(relation_priority)
    rel["_specific"]=(rel["evidence_quality"].astype(str)=="SPEZIFISCH").astype(int) if "evidence_quality" in rel.columns else 0
    # Mehrfachrollen (z.B. Kunde + Konkurrent) behalten, aber nur eine Karte je Gegenpartei anzeigen.
    def _tags(group):
        vals=list(dict.fromkeys(group["relation_class"].dropna().astype(str).tolist()))
        vals=sorted(vals,key=relation_priority)
        return " · ".join(vals[:3])
    tags=rel.groupby("counterpart",sort=False)["relation_class"].apply(lambda x: " · ".join(sorted(list(dict.fromkeys(x.dropna().astype(str).tolist())), key=relation_priority)[:3])).to_dict()
    counts=rel.groupby("counterpart").size().to_dict()
    # eine zentrale Kante je Gegenpartei, damit Gegenrichtungen/Doppelklassen das Profil nicht fluten
    rel=rel.sort_values(["_specific","network_weight","_prio"],ascending=[False,False,True]).drop_duplicates("counterpart")
    rel["relation_tags"]=rel["counterpart"].map(tags)
    rel["relation_count"]=rel["counterpart"].map(counts)
    return rel.sort_values(["_prio","network_weight"],ascending=[True,False])


def opportunity_status(score):
    try: score=float(score)
    except Exception: return "⚪"
    if score>=78: return "🟢"
    if score>=65: return "🟡"
    return "⚪"



def apply_sector_relative_valuation(view, horizon):
    """Korrigiert die absolute Bewertung moderat relativ zum eigenen Sektor.
    Kein Fair-Value-Modell: nur ein Vergleichsfilter, um völlig unterschiedliche
    Bewertungsniveaus verschiedener Branchen nicht gleich zu behandeln.
    """
    d=view.copy()
    d["_fpe_num"]=d["Forward PE"].apply(safe_float) if "Forward PE" in d else None
    d["_peg_num"]=d["PEG Ratio"].apply(safe_float) if "PEG Ratio" in d else None
    d["Sector Forward PE Median"]=d.groupby("Sector")["_fpe_num"].transform("median")
    d["Sector PEG Median"]=d.groupby("Sector")["_peg_num"].transform("median")
    adjusted=[]
    for _,r in d.iterrows():
        base=safe_float(r.get("Valuation Score")) or 50
        adj=0.0
        fpe=safe_float(r.get("_fpe_num")); med=safe_float(r.get("Sector Forward PE Median"))
        if fpe and med and fpe>0 and med>0:
            ratio=fpe/med
            if ratio<=.70: adj+=10
            elif ratio<=.88: adj+=5
            elif ratio>=1.55: adj-=10
            elif ratio>=1.25: adj-=5
        peg=safe_float(r.get("_peg_num")); pmed=safe_float(r.get("Sector PEG Median"))
        if peg and pmed and peg>0 and pmed>0:
            ratio=peg/pmed
            if ratio<=.70: adj+=5
            elif ratio>=1.50: adj-=5
        adjusted.append(round(clamp(base+adj),1))
    d["Valuation Score"]=adjusted
    weights={"Kurzfristig":(0.15,0.10,0.75),"Mittelfristig":(0.25,0.20,0.55),"Langfristig":(0.45,0.35,0.20)}[horizon]
    new_opp=[]; new_risk=[]
    for _,r in d.iterrows():
        penalty,risk=risk_penalty(r)
        new_opp.append(round(clamp(float(r["Quality Score"])*weights[0]+float(r["Valuation Score"])*weights[1]+float(r["Timing Score"])*weights[2]-penalty),1))
        new_risk.append(risk)
    d["Opportunity Score"]=new_opp; d["Risk V3"]=new_risk
    return d.drop(columns=["_fpe_num","_peg_num"],errors="ignore")

def scanner_reason(row, mode):
    bits=[]
    if mode=="Top Chancen":
        if safe_float(row.get("Timing Score")) and safe_float(row.get("Timing Score"))>=72: bits.append("starkes Timing")
        if safe_float(row.get("Quality Score")) and safe_float(row.get("Quality Score"))>=68: bits.append("gute Qualität")
        rs=safe_float(row.get("RS Percentile"));
        if rs is not None and rs>=75: bits.append("stark vs. Sektor")
    elif mode=="Early Signals":
        bits.append(str(row.get("Early Signal Label","Early Signal")))
        rvol=safe_float(row.get("RVOL"));
        if rvol is not None and rvol>=1.1: bits.append(f"RVOL {rvol:.1f}")
    elif mode=="Rücksetzer":
        d=safe_float(row.get("Distance EMA20 %"));
        if d is not None: bits.append(f"{d:+.1f}% zu EMA20")
        bits.append("starke Basis, näher am Support")
    elif mode=="Turnarounds":
        bits.append("Trendwende-Kandidat")
        p1=safe_float(row.get("1M %"));
        if p1 is not None: bits.append(f"1M {p1:+.1f}%")
    elif mode=="Überhitzt":
        rsi=safe_float(row.get("RSI"));
        if rsi is not None: bits.append(f"RSI {rsi:.0f}")
        d=safe_float(row.get("Distance EMA20 %"));
        if d is not None: bits.append(f"{d:+.1f}% zu EMA20")
    return " · ".join(bits[:3]) or "regelbasiertes Scanner-Signal"


def scanner_subset(view, mode):
    d=view.copy()
    early=pd.to_numeric(d.get("Early Signal Score",0),errors="coerce").fillna(0)
    rsi=pd.to_numeric(d.get("RSI",0),errors="coerce").fillna(0)
    dist=pd.to_numeric(d.get("Distance EMA20 %",0),errors="coerce").fillna(0)
    if mode=="Top Chancen":
        return d[(d["Opportunity Score"]>=74)&(d["Timing Score"]>=66)&(d["Risk V3"]!="HOCH")].sort_values(["Opportunity Score","Timing Score"],ascending=False)
    if mode=="Early Signals":
        return d[(early>=5)&(rsi<72)&(d["Opportunity Score"]>=52)].sort_values(["Early Signal Score","Opportunity Score"],ascending=False)
    if mode=="Rücksetzer":
        return d[(d["Quality Score"]>=62)&(d["Opportunity Score"]>=58)&(dist.between(-5,4))&(rsi.between(38,70))].sort_values(["Opportunity Score","Quality Score"],ascending=False)
    if mode=="Turnarounds":
        mask=d.get("Turnaround Candidate",pd.Series(index=d.index,dtype=str)).astype(str).str.upper().eq("YES")
        return d[mask].sort_values(["Opportunity Score","Timing Score"],ascending=False)
    if mode=="Überhitzt":
        return d[(rsi>=72)|(dist>=12)].sort_values(["Opportunity Score","RSI"],ascending=False)
    return d.sort_values("Opportunity Score",ascending=False)


def render_scanner_cards(frame, mode, key_prefix, limit=12):
    if frame.empty:
        st.info("Für diesen Filter gibt es aktuell keine Treffer.")
        return
    cols=st.columns(3)
    for i,(_,r) in enumerate(frame.head(limit).iterrows()):
        ticker=str(r.get("Ticker","-")); company=escape(str(r.get("Company",ticker)))
        opp=safe_float(r.get("Opportunity Score")); timing=safe_float(r.get("Timing Score")); val=safe_float(r.get("Valuation Score")); conf=safe_float(r.get("Confidence"))
        score=f"{opp:.0f}" if opp is not None else "-"
        t=f"{timing:.0f}" if timing is not None else "-"; v=f"{val:.0f}" if val is not None else "-"; c=f"{conf:.0f}%" if conf is not None else "-"
        reason=escape(scanner_reason(r,mode))
        with cols[i%3]:
            st.markdown(f'<div class="hb-scancard"><span class="hb-scorepill">{opportunity_status(opp)} {score}</span><div class="hb-scanname">{ticker} · {company}</div><div class="hb-scanmeta">{escape(str(r.get("Sector","-")))} · Risiko {escape(str(r.get("Risk V3","-")))}</div><div><span class="hb-bigpill">Timing {t}</span><span class="hb-bigpill">Bewertung {v}</span><span class="hb-bigpill">Conf. {c}</span></div><div class="hb-scanwhy">{reason}</div></div>',unsafe_allow_html=True)
            if st.button(f"{ticker} öffnen",key=f"{key_prefix}_{mode}_{ticker}_{i}",use_container_width=True):
                st.session_state["selected_ticker"]=ticker
                st.session_state["jump_to_profile"]=True
                st.rerun()


def market_breadth(view):
    n=max(1,len(view))
    score=pd.to_numeric(view.get("Score",0),errors="coerce").fillna(0)
    p1=pd.to_numeric(view.get("1M %",0),errors="coerce").fillna(0)
    rsi=pd.to_numeric(view.get("RSI",0),errors="coerce").fillna(0)
    strong=(score>=5).sum()/n*100
    positive=(p1>0).sum()/n*100
    hot=(rsi>=72).sum()/n*100
    return round(strong), round(positive), round(hot)


def ecosystem_map_html(eco, selected, view, max_nodes=12):
    if eco is None or eco.empty:
        return ""
    score_map=dict(zip(view["Ticker"].astype(str),pd.to_numeric(view["Opportunity Score"],errors="coerce")))
    rows=eco.copy()
    rows["opp"]=rows["counterpart"].map(score_map)
    rows=rows.sort_values(["network_weight","opp"],ascending=[False,False]).head(max_nodes)
    W,H=900,500; cx,cy=W/2,H/2; radius=190
    class_colors={"LIEFERANT / LIEFERKETTE":"#2563eb","KUNDE / NACHFRAGE":"#059669","NACHFRAGE / PROFITEUR":"#059669","WERTSCHÖPFUNGSKETTE":"#7c3aed","INFRASTRUKTUR / PROFITEUR":"#d97706","STRATEGISCH":"#0f766e","KONKURRENT":"#dc2626","PEER / VERGLEICH":"#64748b","THEMA / CLUSTER":"#94a3b8"}
    parts=[f'<svg viewBox="0 0 {W} {H}" width="100%" height="500" style="font-family:Inter,Arial,sans-serif">', '<rect width="100%" height="100%" rx="18" fill="#ffffff" stroke="#e5e7eb"/>']
    nodes=[]
    count=len(rows)
    for i,(_,r) in enumerate(rows.iterrows()):
        ang=(-math.pi/2)+(2*math.pi*i/max(1,count)); x=cx+radius*math.cos(ang); y=cy+radius*math.sin(ang)
        cls=str(r.get("relation_class","")); color=class_colors.get(cls,"#64748b"); cp=str(r.get("counterpart","-")); sc=safe_float(r.get("opp"))
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{color}" stroke-opacity=".42" stroke-width="{max(1.5,min(5,float(r.get("network_weight",50))/24)):.1f}"/>')
        nodes.append((x,y,cp,sc,color,cls))
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="58" fill="#111827"/><text x="{cx}" y="{cy-3}" text-anchor="middle" fill="white" font-size="20" font-weight="800">{escape(selected)}</text><text x="{cx}" y="{cy+18}" text-anchor="middle" fill="#d1d5db" font-size="11">ÖKOSYSTEM</text>')
    for x,y,cp,sc,color,cls in nodes:
        score="-" if sc is None else f"{sc:.0f}"
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="38" fill="white" stroke="{color}" stroke-width="3"/><text x="{x:.1f}" y="{y-2:.1f}" text-anchor="middle" fill="#111827" font-size="13" font-weight="800">{escape(cp)}</text><text x="{x:.1f}" y="{y+15:.1f}" text-anchor="middle" fill="#6b7280" font-size="10">Score {score}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def upcoming_date_frame(frame, col):
    if col not in frame.columns:
        return pd.DataFrame()
    d=frame.copy()
    d["_event"]=pd.to_datetime(d[col],format="%d.%m.%Y",errors="coerce",dayfirst=True)
    today=pd.Timestamp(datetime.now(TZ).date())
    return d[d["_event"].notna()&(d["_event"]>=today)].sort_values("_event")


def live_events_for(tickers, max_count=20):
    rows=[]
    for ticker in list(dict.fromkeys([str(x) for x in tickers]))[:max_count]:
        live=selected_live_data(ticker)
        rows.append({"Ticker":ticker,"Earnings":event_text(live.get("earnings"),"-"),"Earnings in Tagen":days_until(live.get("earnings")),"Ex-Dividende":event_text(live.get("ex_dividend"),"-"),"Analystenziel":live.get("target_mean"),"Empfehlung":live.get("recommendation")})
    return pd.DataFrame(rows)


def system_health(portfolio, watchlist, relations, meta):
    analyzed=len(portfolio); master=len(watchlist); missing=max(0,master-analyzed)
    visible=0
    if relations is not None and not relations.empty and "default_visible" in relations:
        visible=relations["default_visible"].astype(str).str.lower().isin(["true","1"]).sum()
    return analyzed, master, missing, visible


if not check_password():
    st.stop()

current_user = st.session_state.get("current_user", "hartmut")
st.sidebar.success(f"👤 {current_user}")
if _secret_dict("users") and st.sidebar.button("Ausloggen"):
    for key in ["password_correct", "current_user", "username", "password"]:
        st.session_state.pop(key, None)
    st.rerun()

portfolio, watchlist, relations = load_data()
meta = load_meta()
horizon = st.sidebar.selectbox("Strategie-Horizont", ["Kurzfristig", "Mittelfristig", "Langfristig"], index=1)
st.sidebar.caption(f"💾 Persönliche Daten: {storage_mode()}")
if not _secret_dict("users"):
    st.sidebar.caption("🔓 Entwicklungsmodus: keine [users]-Secrets gefunden")

# Scores nur aus unabhängigen Rohkomponenten aufbauen.
score_components = portfolio.apply(lambda r: opportunity_components(r, horizon), axis=1, result_type="expand")
score_components.columns = ["Opportunity Score", "Quality Score", "Valuation Score", "Timing Score", "Risk V3", "Confidence"]
view = pd.concat([portfolio.reset_index(drop=True), score_components], axis=1)
view = apply_sector_relative_valuation(view, horizon)

all_tickers = view["Ticker"].astype(str).tolist()
def_idx = all_tickers.index("NVDA") if "NVDA" in all_tickers else 0
if "selected_ticker" not in st.session_state or st.session_state.get("selected_ticker") not in all_tickers:
    st.session_state["selected_ticker"] = all_tickers[def_idx]
selected = st.sidebar.selectbox("Aktie", all_tickers, key="selected_ticker", format_func=lambda t: f"{t} · {view.loc[view['Ticker'].eq(t), 'Company'].iloc[0]}")

build_at = fmt_dt(meta.get("code_build_at"))
deploy_at = fmt_dt(meta.get("deployment_at_detected") or meta.get("deployment_at"))
data_at = fmt_dt(data_timestamp())
now_text = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
st.markdown(
    f'<div class="hb-top"><div class="hb-title">📈 {meta.get("app_name","Hartmut Börsentool")} · v{meta.get("version","3.1.0")}</div>'
    f'<div class="hb-meta">Build {meta.get("build_id","-")} · VS-Code/Code-Stand: {build_at} · Git/Upload: {deploy_at} · Marktdaten: {data_at} · Seite geladen: {now_text}</div></div>',
    unsafe_allow_html=True,
)

tabs = st.tabs(["🎯 Chancen", "🔎 Aktienprofil", "🌐 Markt & Sektoren", "🕸 Ökosystem", "📅 Events", "⭐ Mein Bereich"])

with tabs[0]:
    st.subheader("🎯 Chancen · täglicher Scanner")
    strong_breadth,pos_breadth,hot_breadth=market_breadth(view)
    k1,k2,k3,k4=st.columns(4)
    top_count=len(scanner_subset(view,"Top Chancen")); early_count=len(scanner_subset(view,"Early Signals")); pull_count=len(scanner_subset(view,"Rücksetzer")); turn_count=len(scanner_subset(view,"Turnarounds"))
    k1.markdown(f'<div class="hb-kpi"><div class="hb-kpi-label">Top Chancen</div><div class="hb-kpi-value">{top_count}</div><div class="hb-kpi-sub">starkes Gesamtsetup</div></div>',unsafe_allow_html=True)
    k2.markdown(f'<div class="hb-kpi"><div class="hb-kpi-label">Early Signals</div><div class="hb-kpi-value">{early_count}</div><div class="hb-kpi-sub">Aufbau-/Pre-Breakout</div></div>',unsafe_allow_html=True)
    k3.markdown(f'<div class="hb-kpi"><div class="hb-kpi-label">Rücksetzer</div><div class="hb-kpi-value">{pull_count}</div><div class="hb-kpi-sub">nahe EMA20/Support</div></div>',unsafe_allow_html=True)
    k4.markdown(f'<div class="hb-kpi"><div class="hb-kpi-label">Marktbreite</div><div class="hb-kpi-value">{strong_breadth}%</div><div class="hb-kpi-sub">technisch Score ≥5</div></div>',unsafe_allow_html=True)

    f1,f2,f3,f4=st.columns([1.2,1,1,1])
    scan_mode=f1.selectbox("Scanner",["Top Chancen","Early Signals","Rücksetzer","Turnarounds","Überhitzt"])
    risk_filter=f2.selectbox("Max. Risiko",["Alle","NIEDRIG","MITTEL","HOCH"],key="scan_risk")
    sector_options=["Alle"]+sorted(view["Sector"].dropna().astype(str).unique().tolist())
    sector_filter=f3.selectbox("Sektor",sector_options,key="scan_sector")
    min_conf=f4.slider("Min. Confidence",45,98,60)
    scan=scanner_subset(view,scan_mode)
    if risk_filter!="Alle":
        allowed={"NIEDRIG":["NIEDRIG"],"MITTEL":["NIEDRIG","MITTEL"],"HOCH":["NIEDRIG","MITTEL","HOCH"]}[risk_filter]
        scan=scan[scan["Risk V3"].isin(allowed)]
    if sector_filter!="Alle": scan=scan[scan["Sector"].astype(str).eq(sector_filter)]
    scan=scan[pd.to_numeric(scan["Confidence"],errors="coerce").fillna(0)>=min_conf]
    st.caption(f"{len(scan)} Treffer · Opportunity ist ein Ranking aus unabhängigen Komponenten; fehlende Daten senken die Confidence.")
    render_scanner_cards(scan,scan_mode,"scanner",12)
    with st.expander("Alle Treffer als Tabelle"):
        show_cols=[c for c in ["Ticker","Company","Sector","Price","Opportunity Score","Quality Score","Valuation Score","Timing Score","Risk V3","Confidence","Early Signal Score","RS Percentile","1M %","RSI"] if c in scan.columns]
        st.dataframe(scan[show_cols].head(100),use_container_width=True,hide_index=True)

with tabs[1]:
    row = view[view["Ticker"].astype(str).eq(selected)].iloc[0]
    opp,q,v,t,risk,conf = [row[x] for x in ["Opportunity Score","Quality Score","Valuation Score","Timing Score","Risk V3","Confidence"]]
    live = selected_live_data(selected)
    snap = live_snapshot(row, live)
    health_pct, health_label = profile_data_health(row, snap)
    live_timing, live_timing_points = profile_timing_score(row, snap)
    if isinstance(snap.get("history"), pd.DataFrame) and not snap.get("history").empty and live_timing_points >= 5:
        t = round(live_timing,1)
        opp, risk = recompute_profile_opportunity(q,v,t,row,horizon)
        conf = round(min(98,max(45,(conf*0.35)+(health_pct*0.65))))
    verdict_text, verdict_sub = verdict(opp,t,v,risk)
    price=snap.get("price"); day_change=snap.get("day_change"); currency=str(row.get("Currency","") or "").strip()
    price_txt=f"{price:,.2f} {currency}" if price is not None else str(row.get("Price","-")); day_txt=f"{day_change:+.2f}%" if day_change is not None else "Tagesänderung n/a"; day_class="hb-positive" if (day_change or 0)>=0 else "hb-negative"
    st.markdown(f'<div class="hb-stockhead"><div class="hb-stockname">{escape(str(row.get("Company",selected)))} <span class="hb-ticker">{escape(selected)}</span></div><div style="font-size:.78rem;color:#6b7280;margin-top:5px">{escape(str(row.get("Sector","-")))} · {escape(str(row.get("Industry","-")))} · Strategie: {horizon}</div><div class="hb-price">{price_txt} <span class="{day_class}" style="font-size:.86rem;margin-left:6px">{day_txt}</span></div></div>',unsafe_allow_html=True)
    saved_watch_now=get_saved_tickers(current_user,"watchlist"); saved_buy_now=get_saved_tickers(current_user,"buy")
    qa,qb,qc=st.columns([1,1,4])
    if qa.button("✓ Watchlist" if selected in saved_watch_now else "⭐ Watchlist",key=f"toggle_watch_{selected}"):
        added,mode,err=toggle_user_ticker(current_user,"watchlist",selected,view); st.warning(err) if err else st.toast(("Zur Watchlist hinzugefügt" if added else "Von Watchlist entfernt")+f" · {mode}"); st.rerun()
    if qb.button("✓ Kaufliste" if selected in saved_buy_now else "🛒 Kaufliste",key=f"toggle_buy_{selected}"):
        added,mode,err=toggle_user_ticker(current_user,"buy",selected,view); st.warning(err) if err else st.toast(("Zur Kaufliste hinzugefügt" if added else "Von Kaufliste entfernt")+f" · {mode}"); st.rerun()
    qc.caption(f"Datenqualität Profil: {health_pct}% · {health_label} · Confidence {conf:.0f}%")
    action_hint=profile_action_hint(row,opp,t,v,risk,snap,horizon)
    earnings_for_action=live.get("earnings") or row.get("Next Earnings Date")
    earnings_for_action_days=days_until(earnings_for_action)
    if earnings_for_action_days is not None and 0 <= earnings_for_action_days <= 7:
        action_hint=f"Earnings in {earnings_for_action_days} Tagen – neues Risiko bewusst abwägen; " + action_hint
    st.markdown(f'<div class="hb-hero"><div style="font-size:.72rem;color:#6b7280;text-transform:uppercase;letter-spacing:.06em;font-weight:700">Haupturteil · Opportunity {opp:.0f}/100</div><div class="hb-verdict">{verdict_text}</div><div class="hb-sub">{verdict_sub}<br><b>Aktion:</b> {escape(action_hint)}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="hb-scoregrid">'+score_card_html("Qualität",q)+score_card_html("Bewertung",v)+score_card_html("Timing",t)+risk_card_html(risk)+score_card_html("Confidence",conf,"%",health_label+" Datenbasis")+'</div>',unsafe_allow_html=True)

    earnings=live.get("earnings") or row.get("Next Earnings Date"); earnings_days=days_until(earnings)
    st.markdown('<div class="hb-section">Heute wichtig</div>',unsafe_allow_html=True)
    i1,i2,i3=st.columns(3); e200=snap.get("ema200"); e50=snap.get("ema50"); trend_good=price is not None and e50 is not None and price>=e50 and (e200 is None or price>=e200); live_rsi=snap.get("rsi") or safe_float(row.get("RSI")); rsi_txt=f"{live_rsi:.1f}" if live_rsi is not None else "-"
    i1.markdown(f'<div class="{"hb-ok" if trend_good else "hb-alert"}"><b>📈 {"Trend intakt" if trend_good else "Trend noch nicht sauber"}</b><br>RSI {rsi_txt} · RS Sektor {row.get("RS Percentile","-")}</div>',unsafe_allow_html=True)
    i2.markdown(f'<div class="{"hb-alert" if earnings_days is not None and 0<=earnings_days<=10 else "hb-note"}"><b>📅 Earnings</b><br>{event_text(earnings,"keine Angabe")}</div>',unsafe_allow_html=True)
    rs=safe_float(row.get("RS Percentile")); market_rs=safe_float(row.get("Market RS 1M")); rs_txt=(f"Top {max(1,100-rs):.0f}% im Sektor" if rs is not None else "Sektor-RS fehlt"); mkt_txt=(f"Markt-RS {market_rs:+.1f}%" if market_rs is not None else "Markt-RS fehlt")
    i3.markdown(f'<div class="hb-note"><b>📡 Relative Stärke</b><br>{rs_txt} · {mkt_txt}</div>',unsafe_allow_html=True)

    pros,warns=profile_reasons(row,q,v,t); left,right=st.columns(2)
    with left:
        st.markdown("**Warum interessant?**"); [st.write(f"✓ {x}") for x in pros] if pros else st.write("Noch kein klarer positiver Schwerpunkt aus den vorhandenen Daten.")
    with right:
        st.markdown("**Was spricht dagegen?**"); [st.write(f"⚠ {x}") for x in warns]
        if health_pct<75: st.write("⚠ Mehrere Kerndaten fehlen – Confidence entsprechend niedriger bewerten.")
        if not warns and health_pct>=75: st.write("Keine zentrale Warnung aus den vorhandenen Daten.")

    plan=trade_plan(row,horizon)
    if plan is None and price is not None:
        support=(snap.get("ema20") if horizon=="Kurzfristig" else snap.get("ema200") if horizon=="Langfristig" else snap.get("ema50")) or price*.92; stop=support*(.94 if horizon=="Langfristig" else .97); hist=snap.get("history"); live_high=safe_float(hist["Close"].tail(252).max()) if isinstance(hist,pd.DataFrame) and not hist.empty else None; target=live_high if live_high and live_high>price*1.03 else price*(1.20 if horizon=="Langfristig" else 1.12); lo=min(price,support*1.02); hi=max(price*1.01,support*1.04); risk_amt=price-stop; crv=(target-price)/risk_amt if risk_amt>0 and target>price else None; plan=(lo,hi,support,stop,target,crv)
    if plan and price is not None:
        lo,hi,support,stop,target,crv=plan
        if snap.get("ema20") is not None and horizon=="Kurzfristig": support=snap["ema20"]; stop=support*.97
        elif snap.get("ema50") is not None and horizon=="Mittelfristig": support=snap["ema50"]; stop=support*.97
        elif snap.get("ema200") is not None and horizon=="Langfristig": support=snap["ema200"]; stop=support*.94
        lo=min(price,support*1.02); hi=max(price*1.01,support*1.04); risk_amt=price-stop; crv=(target-price)/risk_amt if risk_amt>0 and target>price else crv
        st.markdown('<div class="hb-section">🎯 Handelsplan</div>',unsafe_allow_html=True); p1,p2,p3,p4,p5=st.columns(5); p1.metric("Einstieg",f"{lo:.2f} – {hi:.2f}"); p2.metric("Support",f"{support:.2f}"); p3.metric("Stop-Idee",f"{stop:.2f}"); p4.metric("Ziel 1",f"{target:.2f}"); p5.metric("CRV",f"{crv:.2f}" if crv else "-"); st.caption("Regelbasierte Orientierung aus Trend/Support; kein Kurszielmodell.")

    st.markdown('<div class="hb-section">📅 Earnings & Dividende</div>',unsafe_allow_html=True); x1,x2,x3,x4,x5=st.columns(5); x1.metric("Nächste Earnings",event_text(earnings,"keine Angabe")); exd=live.get("ex_dividend") or row.get("Ex Dividend Date"); x2.metric("Ex-Dividende",event_text(exd,str(row.get("Ex Dividend Date","-")))); x3.metric("Dividendenrendite",str(row.get("Dividend Yield %","-"))); event_risk="HOCH" if earnings_days is not None and 0<=earnings_days<=10 else ("MITTEL" if earnings_days is not None and 0<=earnings_days<=30 else "NORMAL"); x4.metric("Event-Risiko",event_risk); target_mean=safe_float(live.get("target_mean")); x5.metric("Analysten-Mittelziel",f"{target_mean:.2f}" if target_mean else "-")

    with st.expander("📈 Technik & Timing",expanded=True):
        tech_rows=[("Kurs",price_txt),("RSI",f"{snap.get('rsi'):.2f}" if snap.get("rsi") is not None else row.get("RSI","-")),("EMA20",f"{snap.get('ema20'):.2f}" if snap.get("ema20") else row.get("EMA20","-")),("EMA50",f"{snap.get('ema50'):.2f}" if snap.get("ema50") else row.get("EMA50","-")),("EMA200",f"{snap.get('ema200'):.2f}" if snap.get("ema200") else row.get("EMA200","-")),("1M",f"{snap.get('p1m'):+.2f}%" if snap.get("p1m") is not None else row.get("1M %","-")),("3M",f"{snap.get('p3m'):+.2f}%" if snap.get("p3m") is not None else row.get("3M %","-")),("RS Sektor",row.get("RS Percentile","-")),("RS Markt 1M",row.get("Market RS 1M","-")),("RVOL",f"{snap.get('rvol'):.2f}" if snap.get("rvol") is not None else row.get("RVOL","-")),("Early Signal",f"{row.get('Early Signal Score','-')} · {row.get('Early Signal Label','-')}")]
        st.dataframe(pd.DataFrame(tech_rows,columns=["Kennzahl","Wert"]),use_container_width=True,hide_index=True); hist=snap.get("history")
        if isinstance(hist,pd.DataFrame) and not hist.empty:
            h=hist.copy(); h["EMA20"]=h["Close"].ewm(span=20,adjust=False).mean(); h["EMA50"]=h["Close"].ewm(span=50,adjust=False).mean(); h["EMA200"]=h["Close"].ewm(span=200,adjust=False).mean(); st.line_chart(h[["Close","EMA20","EMA50","EMA200"]].tail(260),height=320)
    with st.expander("🏢 Unternehmensqualität"):
        qual_rows=[("Umsatzwachstum",row.get("Revenue Growth","-")),("Gewinnwachstum",row.get("Earnings Growth","-")),("Gewinnmarge",row.get("Profit Margin","-")),("Free Cashflow",row.get("Free Cashflow","-")),("Operating Cashflow",row.get("Operating Cashflow","-")),("Debt/Equity",row.get("Debt To Equity","-")),("Fundamental Rating",row.get("Fundamental Rating","-")),("Liquidität",row.get("Liquidity","-"))]; st.dataframe(pd.DataFrame(qual_rows,columns=["Kennzahl","Wert"]),use_container_width=True,hide_index=True)
    with st.expander("💰 Bewertung"):
        val_rows=[("Forward KGV",row.get("Forward PE","-")),("Sektor-Median Forward KGV",f"{safe_float(row.get('Sector Forward PE Median')):.2f}" if safe_float(row.get('Sector Forward PE Median')) else "-"),("Trailing KGV",row.get("Trailing PE","-")),("PEG Ratio",row.get("PEG Ratio","-")),("Sektor-Median PEG",f"{safe_float(row.get('Sector PEG Median')):.2f}" if safe_float(row.get('Sector PEG Median')) else "-"),("Market Cap",row.get("Market Cap Class","-")),("Bewertungs-Score",f"{v:.0f}/100")]; st.dataframe(pd.DataFrame(val_rows,columns=["Kennzahl","Wert"]),use_container_width=True,hide_index=True)
    with st.expander("🏛 Smart Money"):
        sm_rows=[("Signal",row.get("Smart Money Signal","-")),("Institutionell",row.get("Institutional %","-")),("Insider Käufe 6M",row.get("Insider Buys 6M","-")),("Insider Verkäufe 6M",row.get("Insider Sells 6M","-")),("Short % Float",row.get("Short % Float","-")),("Short Ratio",row.get("Short Ratio","-"))]; st.dataframe(pd.DataFrame(sm_rows,columns=["Kennzahl","Wert"]),use_container_width=True,hide_index=True)

    eco=ecosystem_rows(relations,selected,False)
    if not eco.empty:
        st.markdown('<div class="hb-section">🕸 Wichtigste Aktien im Ökosystem</div>',unsafe_allow_html=True); top_eco=eco.head(6).copy(); score_map=view.set_index(view["Ticker"].astype(str))["Opportunity Score"].to_dict(); ec_cols=st.columns(3)
        for idx,(_,rr) in enumerate(top_eco.iterrows()):
            cp=str(rr["counterpart"]); hit=view[view["Ticker"].astype(str)==cp]; cname=hit.iloc[0].get("Company",cp) if not hit.empty else cp; sc=score_map.get(cp); score_text=f"{float(sc):.0f}" if sc is not None and not pd.isna(sc) else "-"
            with ec_cols[idx%3]:
                st.markdown(f'<div class="hb-relcard"><span class="hb-scorepill">{opportunity_status(sc)} {score_text}</span><div class="hb-relname">{escape(cp)} · {escape(str(cname))}</div><div class="hb-relmeta">{escape(str(rr.get("relation_tags",rr.get("relation_class","-"))))} · Gewicht {rr.get("network_weight","-")}</div><div class="hb-reldesc">{escape(str(rr.get("relationship","-")))}</div></div>',unsafe_allow_html=True)
                if cp in all_tickers and st.button(f"{cp} öffnen",key=f"profile_jump_{selected}_{cp}_{idx}"): st.session_state["selected_ticker"]=cp; st.rerun()

with tabs[2]:
    st.subheader("🌐 Markt & Sektoren")
    strong,positive,hot=market_breadth(view); m1,m2,m3,m4=st.columns(4); m1.metric("Technisch stark",f"{strong}%",help="Anteil mit technischem Score ≥5"); m2.metric("1M positiv",f"{positive}%"); m3.metric("Überhitzt",f"{hot}%",help="RSI ≥72"); m4.metric("Analysiert",len(view))
    sector_view=view.groupby("Sector",dropna=False).agg(Aktien=("Ticker","count"),Opportunity=("Opportunity Score","mean"),Timing=("Timing Score","mean"),Qualität=("Quality Score","mean"),Bewertung=("Valuation Score","mean"),Performance_1M=("1M %","mean"),Performance_3M=("3M %","mean")).reset_index(); sector_view["Stärke"]=(sector_view["Opportunity"]*.55+sector_view["Timing"]*.45).round(1); sector_view=sector_view.sort_values("Stärke",ascending=False)
    a,b=st.columns(2)
    with a:
        st.markdown("### 🔥 Stärkste Sektoren"); st.dataframe(sector_view.head(10).round(1),use_container_width=True,hide_index=True)
    with b:
        st.markdown("### 🧊 Schwächste Sektoren"); st.dataframe(sector_view.tail(10).sort_values("Stärke").round(1),use_container_width=True,hide_index=True)
    st.markdown("### Sektor-Ranking"); chart=sector_view.set_index("Sector")[["Opportunity","Timing"]].head(15); st.bar_chart(chart,height=340); st.dataframe(sector_view.round(1),use_container_width=True,hide_index=True)

with tabs[3]:
    st.subheader(f"🕸 Ökosystem · {selected}")
    st.caption("Final: direkte/ökonomische Beziehungen im Vordergrund; reine Themencluster bleiben standardmäßig verborgen.")
    if relations.empty: st.info("stock_relationships_v3.csv fehlt.")
    else:
        show_topics=st.checkbox("Auch reine Themen-/Clusterbeziehungen anzeigen",value=False); eco=ecosystem_rows(relations,selected,show_topics)
        if eco.empty: st.info("Für diese Aktie sind noch keine Beziehungen vorhanden.")
        else:
            score_map=view.set_index(view["Ticker"].astype(str))["Opportunity Score"].to_dict(); timing_map=view.set_index(view["Ticker"].astype(str))["Timing Score"].to_dict(); eco["Opportunity Score"]=eco["counterpart"].map(score_map); eco["Timing Score"]=eco["counterpart"].map(timing_map)
            st.markdown(f'<div class="hb-note"><b>{escape(selected)}</b> im Zentrum · {len(eco)} eindeutige Gegenparteien. Linienstärke im Netz entspricht der Beziehungsrelevanz.</div>',unsafe_allow_html=True)
            svg=ecosystem_map_html(eco,selected,view,12)
            if svg: st_components.html(svg,height=525,scrolling=False)
            classes=[c for c in ["LIEFERANT / LIEFERKETTE","KUNDE / NACHFRAGE","WERTSCHÖPFUNGSKETTE","NACHFRAGE / PROFITEUR","STRATEGISCH","INFRASTRUKTUR / PROFITEUR","KONKURRENT","PEER / VERGLEICH","THEMA / CLUSTER"] if c in eco["relation_class"].astype(str).unique()]; label_map={"LIEFERANT / LIEFERKETTE":"🔗 Lieferkette","KUNDE / NACHFRAGE":"🛒 Kunden/Nachfrage","WERTSCHÖPFUNGSKETTE":"🏭 Wertschöpfung","NACHFRAGE / PROFITEUR":"📈 Nachfrage / Profiteure","STRATEGISCH":"🤝 Strategisch","INFRASTRUKTUR / PROFITEUR":"⚡ Infrastruktur","KONKURRENT":"⚔ Konkurrenten","PEER / VERGLEICH":"↔ Branchen-Peers","THEMA / CLUSTER":"🧩 Themencluster"}
            for cls in classes:
                group=eco[eco["relation_class"].astype(str)==cls].head(8)
                if group.empty: continue
                st.markdown(f"### {label_map.get(cls,cls)}"); cards=st.columns(4)
                for idx,(_,rr) in enumerate(group.iterrows()):
                    cp=str(rr["counterpart"]); hit=view[view["Ticker"].astype(str)==cp]; cname=hit.iloc[0].get("Company",cp) if not hit.empty else cp; sc=rr.get("Opportunity Score"); ts=rr.get("Timing Score"); score_text=f"{float(sc):.0f}" if sc is not None and not pd.isna(sc) else "-"; timing_text=f"{float(ts):.0f}" if ts is not None and not pd.isna(ts) else "-"
                    with cards[idx%4]:
                        st.markdown(f'<div class="hb-relcard"><span class="hb-scorepill">{opportunity_status(sc)} {score_text}</span><div class="hb-relname">{escape(cp)} · {escape(str(cname))}</div><div class="hb-relmeta">Timing {timing_text} · {escape(str(rr.get("relation_tags",rr.get("relation_class","-"))))} · Gewicht {rr.get("network_weight","-")}</div><div class="hb-reldesc">{escape(str(rr.get("relationship","-")))}</div></div>',unsafe_allow_html=True)
                        if cp in all_tickers and st.button(f"{cp} analysieren",key=f"eco_jump_{selected}_{cls}_{cp}_{idx}"): st.session_state["selected_ticker"]=cp; st.rerun()
            st.markdown("### 💡 Beste Chancen im Ökosystem"); candidates=eco[eco["Opportunity Score"].notna()].sort_values(["Opportunity Score","network_weight"],ascending=[False,False]).copy()
            if not candidates.empty:
                names=view.set_index(view["Ticker"].astype(str))["Company"].to_dict(); candidates["Company"]=candidates["counterpart"].map(names); show=candidates[["counterpart","Company","relation_class","relation_tags","Opportunity Score","Timing Score","network_weight","relationship"]].head(20).rename(columns={"counterpart":"Ticker","relation_class":"Hauptbeziehung","relation_tags":"Rollen","network_weight":"Netzgewicht"}); st.dataframe(show,use_container_width=True,hide_index=True)

with tabs[4]:
    st.subheader("📅 Events")
    ev1,ev2=st.tabs(["📊 Earnings", "💰 Dividenden"])
    with ev1:
        if "Next Earnings Date" in view.columns:
            earn_df=upcoming_date_frame(view,"Next Earnings Date"); cols=[c for c in ["Ticker","Company","Next Earnings Date","Opportunity Score","Timing Score","Risk V3","Confidence"] if c in earn_df.columns]; st.dataframe(earn_df[cols].head(100),use_container_width=True,hide_index=True) if not earn_df.empty else st.info("Im letzten Analysebestand sind keine zukünftigen Earnings-Termine gespeichert. Nach dem nächsten Lauf von advanced_portfolio.py werden sie – soweit Yahoo sie liefert – mitgeschrieben.")
        else:
            st.info("Die hochgeladene Analyse stammt noch vor dem finalen Earnings-Feld. Der Final-Analyzer schreibt es beim nächsten Datenlauf automatisch mit.")
        st.markdown("**Live-Eventcheck für deine wichtigen Titel**")
        watch_now=get_saved_tickers(current_user,"watchlist"); buy_now=get_saved_tickers(current_user,"buy"); focus=list(dict.fromkeys([selected]+watch_now+buy_now))[:20]; st.caption(f"Ausgewählte Aktie + Watchlist/Kaufliste · maximal 20 Titel · aktuell {len(focus)}")
        if st.button("Live-Earnings prüfen",key="live_events_btn"):
            with st.spinner("Live-Events werden geladen …"):
                live_events=live_events_for(focus,20); st.session_state["live_event_frame"]=live_events
        if isinstance(st.session_state.get("live_event_frame"),pd.DataFrame): st.dataframe(st.session_state["live_event_frame"],use_container_width=True,hide_index=True)
    with ev2:
        div_df=upcoming_date_frame(view,"Ex Dividend Date"); cols=[c for c in ["Ticker","Company","Ex Dividend Date","Dividend Yield %","Opportunity Score","Risk V3"] if c in div_df.columns]; st.dataframe(div_df[cols].head(150),use_container_width=True,hide_index=True) if not div_df.empty else st.info("Keine zukünftigen Ex-Dividenden-Termine im Bestand.")

with tabs[5]:
    st.subheader("⭐ Mein Bereich")
    list_data,list_warning=load_user_lists(); st.warning(list_warning) if list_warning else None; st.caption(f"Angemeldet als **{current_user}** · Speicher: **{storage_mode()}**")
    my_watch,my_buy,my_journal,my_system=st.tabs(["⭐ Watchlist","🛒 Kaufliste","📓 Trade-Journal","⚙ Systemstatus"])
    option_df=view[["Ticker","Company"]].drop_duplicates().copy(); option_df["display"]=option_df["Ticker"].astype(str)+" · "+option_df["Company"].astype(str); display_to_ticker=dict(zip(option_df["display"],option_df["Ticker"].astype(str))); ticker_to_display=dict(zip(option_df["Ticker"].astype(str),option_df["display"])); all_displays=option_df["display"].tolist()
    def render_personal_list(list_type,title,key_prefix):
        saved=get_saved_tickers(current_user,list_type); defaults=[ticker_to_display[t] for t in saved if t in ticker_to_display]; selected_displays=st.multiselect(f"{title} bearbeiten",all_displays,default=defaults,key=f"{key_prefix}_select_{current_user}",placeholder="Aktien suchen …"); selected_tickers=[display_to_ticker[x] for x in selected_displays]
        if st.button(f"{title} speichern",key=f"{key_prefix}_save_{current_user}",type="primary"):
            mode,err=update_user_list(current_user,list_type,selected_tickers,view); st.warning(err) if err else st.success(f"Gespeichert · {mode}"); st.rerun()
        if selected_tickers:
            cols=["Ticker","Company","Sector","Price","Opportunity Score","Timing Score","Valuation Score","Risk V3","Confidence"]; personal=view[view["Ticker"].astype(str).isin(selected_tickers)][cols].copy(); st.dataframe(personal.sort_values("Opportunity Score",ascending=False),use_container_width=True,hide_index=True)
        else: st.info(f"Deine {title} ist noch leer.")
    with my_watch: render_personal_list("watchlist","Watchlist","watch")
    with my_buy: render_personal_list("buy","Kaufliste","buy")
    with my_journal:
        trades,journal_warning,journal_mode=load_trade_journal(current_user); st.warning(journal_warning) if journal_warning else None; st.caption(f"Journal-Speicher: {journal_mode}")
        with st.expander("➕ Neuen Trade anlegen",expanded=trades.empty):
            with st.form(f"new_trade_{current_user}",clear_on_submit=True):
                f1,f2,f3=st.columns(3); trade_ticker=f1.selectbox("Aktie",all_tickers,index=def_idx,format_func=lambda t:ticker_to_display.get(t,t)); direction=f2.selectbox("Richtung",["Long","Short"]); entry_date=f3.date_input("Einstiegsdatum",value=date.today()); p1,p2,p3,p4=st.columns(4); entry_price=p1.number_input("Einstiegspreis",min_value=0.0,value=0.0,step=0.01); stop_loss=p2.number_input("Stop-Loss",min_value=0.0,value=0.0,step=0.01); target_price=p3.number_input("Ziel",min_value=0.0,value=0.0,step=0.01); position_size=p4.number_input("Stückzahl",min_value=0.0,value=0.0,step=1.0); notes=st.text_area("Notiz / These",placeholder="Warum kaufe ich? Was muss passieren, damit die These ungültig wird?"); submitted=st.form_submit_button("Trade speichern",type="primary")
                if submitted:
                    company_hit=view[view["Ticker"].astype(str).eq(str(trade_ticker))]; company=company_hit.iloc[0].get("Company",trade_ticker) if not company_hit.empty else trade_ticker; entry={"username":current_user,"ticker":trade_ticker,"name":str(company),"direction":direction,"status":"Open","entry_date":entry_date.isoformat(),"entry_price":entry_price if entry_price>0 else None,"stop_loss":stop_loss if stop_loss>0 else None,"target_price":target_price if target_price>0 else None,"position_size":position_size if position_size>0 else None,"exit_date":None,"exit_price":None,"notes":notes,"created_at":datetime.now(TZ).isoformat()}; mode,err=add_trade_journal_entry(entry); st.warning(err) if err else st.success(f"Trade gespeichert · {mode}"); st.rerun()
        if trades.empty: st.info("Noch keine Trades im Journal.")
        else:
            display=trades.copy(); pnl_values=display.apply(trade_pnl,axis=1); display["P/L %"]=[round(x[0],2) if x[0] is not None else None for x in pnl_values]; display["P/L Betrag"]=[round(x[1],2) if x[1] is not None else None for x in pnl_values]; show_cols=["id","ticker","name","direction","status","entry_date","entry_price","stop_loss","target_price","position_size","exit_date","exit_price","P/L %","P/L Betrag","notes"]; st.dataframe(display[show_cols],use_container_width=True,hide_index=True); open_trades=trades[trades["status"].astype(str).str.lower().eq("open")]
            if not open_trades.empty:
                ids=open_trades["id"].tolist(); edit_id=st.selectbox("Offenen Trade bearbeiten",ids,format_func=lambda x:f"#{x} · {open_trades.loc[open_trades['id'].eq(x),'ticker'].iloc[0]}"); trade_row=open_trades[open_trades["id"].eq(edit_id)].iloc[0]; e1,e2,e3=st.columns(3); new_stop=e1.number_input("Neuer Stop",min_value=0.0,value=safe_float(trade_row.get("stop_loss")) or 0.0,step=0.01,key=f"edit_stop_{edit_id}"); new_target=e2.number_input("Neues Ziel",min_value=0.0,value=safe_float(trade_row.get("target_price")) or 0.0,step=0.01,key=f"edit_target_{edit_id}"); exit_price=e3.number_input("Ausstiegspreis",min_value=0.0,value=0.0,step=0.01,key=f"exit_{edit_id}"); b1,b2,b3=st.columns(3)
                if b1.button("Stop/Ziel aktualisieren",key=f"update_trade_{edit_id}"): mode,err=update_trade_journal_entry(edit_id,current_user,{"stop_loss":new_stop if new_stop>0 else None,"target_price":new_target if new_target>0 else None}); st.warning(err) if err else st.success(f"Aktualisiert · {mode}"); st.rerun()
                if b2.button("Trade schließen",key=f"close_trade_{edit_id}",disabled=exit_price<=0): mode,err=update_trade_journal_entry(edit_id,current_user,{"status":"Closed","exit_date":date.today().isoformat(),"exit_price":exit_price}); st.warning(err) if err else st.success(f"Trade geschlossen · {mode}"); st.rerun()
                if b3.button("Trade löschen",key=f"delete_trade_{edit_id}"): mode,err=delete_trade_journal_entry(edit_id,current_user); st.warning(err) if err else st.success(f"Trade gelöscht · {mode}"); st.rerun()
    with my_system:
        analyzed,master,missing,visible=system_health(portfolio,watchlist,relations,meta); s1,s2,s3,s4=st.columns(4); s1.metric("Analysiert",analyzed); s2.metric("Master-Watchlist",master); s3.metric("Fehlen im Scan",missing); s4.metric("Netz-Kanten sichtbar",visible); st.markdown(f'<div class="hb-system"><b>Version:</b> v{meta.get("version","3.1.0")} · Build {meta.get("build_id","-")}<br><b>VS-Code/Code:</b> {build_at}<br><b>Git/Upload:</b> {deploy_at}<br><b>Marktdaten:</b> {data_at}<br><b>Persönliche Daten:</b> {storage_mode()}</div>',unsafe_allow_html=True)

st.caption(f'Hartmut Börsentool v{meta.get("version","3.1.0")} · Build {meta.get("build_id","-")} · Code {build_at} · Git/Upload {deploy_at} · Daten {data_at} · {len(view)} Aktien')
