from __future__ import annotations

import os
import time
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st
from dotenv import load_dotenv

from data_loader import clean_text, get_master_data_store


ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
API_TIMEOUT_SECONDS = 30
BASELINE_INSURER_VALUE = "__baseline__"
STANDARD_BASELINE_PLAN_ID = "standard__standard_ip"

load_dotenv(ENV_PATH)


def _streamlit_secret_value(key: str) -> Optional[str]:
    try:
        if key in st.secrets:
            value = st.secrets[key]
            return value if isinstance(value, str) else str(value)
    except Exception:
        return None
    return None


def _setting_value(key: str, default: str = "") -> str:
    env_value = os.getenv(key, "").strip()
    if env_value:
        return env_value

    secret_value = _streamlit_secret_value(key)
    if secret_value:
        return secret_value.strip()

    return default


API_BASE_URL = _setting_value("API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
SHOW_DEBUG_PAYLOADS = _setting_value("SHOW_DEBUG_PAYLOADS", "").lower() in {"1", "true", "yes", "on"}

EXAMPLE_PROMPTS = [
    "I am 45, how much cash do I pay for Prudential Class A?",
    "What is the premium for Singlife Shield Plan 1 if I am 62?",
    "What does the Standard plan cover for ICU?",
    "I am 26 years old, what insurance should I buy?",
]

INSURER_LABELS = {
    "": "Any insurer",
    BASELINE_INSURER_VALUE: "Baseline / MOH",
    "Income": "Income",
    "AIA": "AIA",
    "Great Eastern": "Great Eastern",
    "Prudential": "Prudential",
    "Singlife": "Singlife",
    "HSBC Life": "HSBC Life",
    "Raffles Health Insurance": "Raffles Health Insurance",
}

TIER_OPTIONS = [
    ("Any tier", ""),
    ("Basic / Plan C", "basic"),
    ("Standard", "standard"),
    ("Class B1", "class_b1"),
    ("Class A", "class_a"),
    ("Private Hospital", "private"),
]

TIER_LABELS = {value: label for label, value in TIER_OPTIONS}

SESSION_DEFAULTS = {
    "chat_history": [],
    "chat_draft": "",
    "chat_clear_after_send": False,
    "pending_recommendation": None,
    "premium_lookup_payload": None,
    "benefit_lookup_payload": None,
    "premium_submitted_filters": None,
    "benefit_submitted_filters": None,
    "premium_tier": "",
    "premium_insurer": "",
    "premium_plan_selection": "__auto__",
    "premium_age": 45,
    "benefit_tier": "",
    "benefit_insurer": "",
    "benefit_plan_selection": "__auto__",
    "benefit_keyword": "",
    "backend_refresh_notice": "",
    "backend_refresh_notice_level": "info",
}

APP_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

:root {
  --page: #eef4fb;
  --page-soft: #f9fbfe;
  --surface: rgba(248, 251, 255, 0.94);
  --surface-strong: rgba(255, 255, 255, 0.98);
  --surface-muted: rgba(236, 243, 250, 0.88);
  --ink: #11233a;
  --ink-soft: rgba(17, 35, 58, 0.8);
  --teal: #1c5f82;
  --teal-deep: #153c5b;
  --teal-soft: rgba(28, 95, 130, 0.10);
  --gold: #af7f2f;
  --gold-soft: rgba(171, 123, 44, 0.12);
  --line: rgba(17, 35, 58, 0.12);
  --line-strong: rgba(28, 95, 130, 0.22);
  --danger: #9b4f3f;
  --danger-soft: rgba(155, 79, 63, 0.10);
  --ok-soft: rgba(28, 95, 130, 0.10);
  --shadow-lg: 0 24px 56px rgba(17, 35, 58, 0.08);
  --shadow-md: 0 14px 32px rgba(17, 35, 58, 0.06);
  --radius-xl: 24px;
  --radius-lg: 18px;
  --radius-md: 14px;
}

.stApp {
  background:
    radial-gradient(circle at top right, rgba(28, 95, 130, 0.10), transparent 24%),
    radial-gradient(circle at top left, rgba(103, 133, 187, 0.10), transparent 30%),
    linear-gradient(180deg, var(--page-soft) 0%, var(--page) 100%);
}

html, body, [class*="css"] {
  font-family: "IBM Plex Sans", sans-serif;
  color: var(--ink);
}

body, p, li, label, span, div, small {
  color: var(--ink);
}

h1, h2, h3, h4 {
  font-family: "Fraunces", serif;
  color: var(--ink);
}

.block-container {
  max-width: 1440px;
  padding-top: 1.4rem;
  padding-bottom: 2.5rem;
}

[data-testid="stHeader"] {
  background: rgba(249, 251, 254, 0.86);
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #eef4fb 0%, #e4edf7 100%);
  border-right: 1px solid rgba(17, 35, 58, 0.08);
}

[data-testid="stSidebar"] * {
  color: var(--ink) !important;
}

.shell-header {
  background: linear-gradient(145deg, rgba(255,255,255,0.90) 0%, rgba(243,248,253,0.92) 100%);
  border: 1px solid rgba(17, 35, 58, 0.08);
  border-radius: 28px;
  padding: 1.3rem 1.35rem 1.2rem 1.35rem;
  box-shadow: var(--shadow-lg);
  margin-bottom: 1rem;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.73rem;
  color: rgba(17, 35, 58, 0.58);
  margin-bottom: 0.45rem;
}

.title-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: start;
}

.title-block h1 {
  font-size: 2.25rem;
  line-height: 1.02;
  margin: 0 0 0.35rem 0;
}

.lede {
  color: var(--ink-soft);
  font-size: 1rem;
  line-height: 1.55;
  max-width: 56rem;
}

.badge-cluster {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.status-pill,
.info-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.72rem;
  border-radius: 999px;
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--ink) !important;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.92);
}

.status-pill.ok {
  background: rgba(28, 95, 130, 0.12);
  border-color: rgba(28, 95, 130, 0.18);
  color: var(--teal-deep);
}

.status-pill.warn {
  background: rgba(155, 79, 63, 0.10);
  border-color: rgba(155, 79, 63, 0.16);
  color: var(--danger);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.85rem;
  margin-top: 1rem;
}

.mini-stat {
  background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(245,249,254,0.96) 100%);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 0.9rem 0.95rem;
}

.mini-stat-label {
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: rgba(17, 35, 58, 0.58);
  margin-bottom: 0.45rem;
}

.mini-stat-value {
  font-size: 1.45rem;
  font-weight: 700;
  color: var(--ink);
}

.mini-stat-copy {
  margin-top: 0.35rem;
  color: var(--ink-soft);
  font-size: 0.9rem;
}

.sidebar-card,
.panel-card,
.message-card,
.summary-card,
.preview-card,
.helper-card {
  background: var(--surface-strong);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.sidebar-card {
  padding: 1rem;
  margin-bottom: 0.8rem;
  background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(243,248,253,0.98) 100%);
  border-color: rgba(17, 35, 58, 0.14);
}

.sidebar-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: rgba(17, 35, 58, 0.72);
  font-weight: 700;
}

.sidebar-value {
  margin-top: 0.22rem;
  font-size: 1rem;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.45;
}

.sidebar-value code {
  display: inline-block;
  max-width: 100%;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  background: rgba(28, 95, 130, 0.10);
  color: var(--teal-deep);
  border: 1px solid rgba(28, 95, 130, 0.12);
  padding: 0.3rem 0.45rem;
}

.sidebar-status {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.22rem;
  padding: 0.4rem 0.65rem;
  border-radius: 999px;
  font-size: 0.88rem;
  font-weight: 700;
  border: 1px solid rgba(17, 35, 58, 0.12);
}

.sidebar-status.online {
  background: rgba(28, 95, 130, 0.12);
  border-color: rgba(28, 95, 130, 0.20);
  color: var(--teal-deep);
}

.sidebar-status.offline {
  background: rgba(155, 79, 63, 0.10);
  border-color: rgba(155, 79, 63, 0.18);
  color: var(--danger);
}

.sidebar-note {
  margin-top: 0.8rem;
  font-size: 0.87rem;
  line-height: 1.5;
  color: var(--ink-soft);
}

.panel-card {
  padding: 1rem 1rem 0.95rem 1rem;
}

.chat-frame {
  background: linear-gradient(180deg, rgba(255,255,255,0.86) 0%, rgba(243,248,253,0.76) 100%);
  border: 1px solid rgba(17, 35, 58, 0.08);
  border-radius: 26px;
  padding: 1rem;
  box-shadow: var(--shadow-lg);
}

.section-label {
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(17, 35, 58, 0.60);
  margin-bottom: 0.3rem;
}

.section-title {
  font-family: "Fraunces", serif;
  font-size: 1.85rem;
  margin: 0 0 0.35rem 0;
}

.section-copy {
  color: var(--ink-soft);
  line-height: 1.6;
  font-size: 0.97rem;
}

.example-note,
.helper-note {
  color: rgba(17, 35, 58, 0.76);
  font-size: 0.88rem;
  margin-bottom: 0.55rem;
}

.message-card {
  padding: 0.95rem 1rem;
  margin-bottom: 0.9rem;
}

.message-card.user {
  background: linear-gradient(145deg, rgba(28, 95, 130, 0.12) 0%, rgba(255,255,255,0.98) 100%);
  border-color: rgba(28, 95, 130, 0.16);
}

.message-card.assistant {
  background: linear-gradient(180deg, rgba(255,255,255,0.99) 0%, rgba(245,249,254,0.94) 100%);
}

.message-meta {
  font-size: 0.76rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(17, 35, 58, 0.56);
  margin-bottom: 0.45rem;
}

.message-title {
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 0.35rem;
}

.message-body {
  color: var(--ink);
  line-height: 1.6;
}

.summary-card {
  padding: 0.95rem 1rem;
  margin-bottom: 0.8rem;
}

.summary-label {
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: rgba(17, 35, 58, 0.56);
  margin-bottom: 0.4rem;
}

.summary-copy {
  color: var(--ink);
  line-height: 1.65;
}

.metric-card {
  background: var(--surface-strong);
  border: 1px solid var(--line-strong);
  border-radius: 18px;
  padding: 0.95rem;
  box-shadow: var(--shadow-md);
  min-height: 130px;
}

.metric-label {
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.11em;
  color: rgba(24, 49, 58, 0.56);
  margin-bottom: 0.45rem;
}

.metric-value {
  font-size: 1.38rem;
  line-height: 1.18;
  font-weight: 700;
  color: var(--ink);
}

.metric-caption {
  margin-top: 0.55rem;
  font-size: 0.92rem;
  color: var(--ink-soft);
}

.chip-row {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
  margin: 0.55rem 0 0.25rem 0;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.36rem 0.66rem;
  border-radius: 999px;
  background: var(--teal-soft);
  color: var(--teal-deep);
  border: 1px solid rgba(28, 95, 130, 0.14);
  font-size: 0.82rem;
}

.chip.warning {
  background: var(--gold-soft);
  border-color: rgba(171, 123, 44, 0.14);
  color: #7f5b1d;
}

.guidance-card {
  background: linear-gradient(180deg, rgba(255,255,255,0.99) 0%, rgba(249,251,255,0.96) 100%);
  border: 1px solid rgba(171, 123, 44, 0.18);
  border-radius: var(--radius-lg);
  padding: 0.95rem 1rem;
  box-shadow: var(--shadow-md);
  margin-bottom: 0.8rem;
}

.guidance-card.error {
  background: linear-gradient(180deg, rgba(255,255,255,0.99) 0%, rgba(251,239,235,0.96) 100%);
  border-color: rgba(155, 79, 63, 0.18);
}

.guidance-title {
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 0.32rem;
}

.guidance-copy {
  color: var(--ink-soft);
  line-height: 1.58;
}

.preview-card {
  padding: 0.95rem 1rem;
  margin-bottom: 0.85rem;
}

.preview-title {
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 0.35rem;
}

.preview-copy {
  color: var(--ink-soft);
  line-height: 1.58;
  font-size: 0.94rem;
}

.preview-list {
  margin: 0.75rem 0 0 0;
  padding-left: 1rem;
  color: var(--ink-soft);
}

.empty-state {
  border: 1px dashed rgba(28, 95, 130, 0.22);
  background: rgba(255,255,255,0.82);
  border-radius: 18px;
  padding: 1rem;
  margin-top: 0.75rem;
}

.empty-title {
  font-weight: 700;
  margin-bottom: 0.3rem;
  color: var(--ink);
}

.empty-copy {
  color: var(--ink-soft);
  line-height: 1.6;
}

.stButton > button,
[data-testid="stFormSubmitButton"] button,
[data-testid="baseButton-secondary"],
[data-testid="baseButton-primary"] {
  border-radius: 14px !important;
  border: 1px solid rgba(28, 95, 130, 0.18) !important;
  background: linear-gradient(135deg, var(--teal) 0%, var(--teal-deep) 100%) !important;
  color: #ffffff !important;
  box-shadow: 0 12px 28px rgba(21, 60, 91, 0.16);
}

.stButton > button:hover,
[data-testid="stFormSubmitButton"] button:hover {
  background: linear-gradient(135deg, #194f6b 0%, #122f47 100%) !important;
  color: #ffffff !important;
}

.stButton > button *,
[data-testid="stFormSubmitButton"] button *,
[data-testid="baseButton-secondary"] *,
[data-testid="baseButton-primary"] * {
  color: #ffffff !important;
}

.stButton > button p,
.stButton > button div,
.stButton > button span,
[data-testid="stFormSubmitButton"] button p,
[data-testid="stFormSubmitButton"] button div,
[data-testid="stFormSubmitButton"] button span,
[data-testid="baseButton-secondary"] p,
[data-testid="baseButton-secondary"] div,
[data-testid="baseButton-secondary"] span,
[data-testid="baseButton-primary"] p,
[data-testid="baseButton-primary"] div,
[data-testid="baseButton-primary"] span {
  color: #ffffff !important;
}

.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"] > div {
  background: rgba(255,255,255,0.98) !important;
  border-radius: 14px !important;
  border: 1px solid rgba(17, 35, 58, 0.16) !important;
  color: var(--ink) !important;
}

.stSelectbox div[data-baseweb="select"] svg {
  color: rgba(17, 35, 58, 0.72) !important;
  fill: rgba(17, 35, 58, 0.72) !important;
}

[data-baseweb="popover"] [role="listbox"],
div[data-baseweb="menu"] {
  background: rgba(255,255,255,0.99) !important;
  border: 1px solid rgba(17, 35, 58, 0.14) !important;
  border-radius: 16px !important;
  box-shadow: 0 20px 40px rgba(17, 35, 58, 0.14) !important;
  padding: 0.3rem !important;
}

[data-baseweb="popover"] [role="option"],
div[data-baseweb="menu"] ul li,
div[data-baseweb="menu"] li {
  background: transparent !important;
  color: var(--ink) !important;
  border-radius: 12px !important;
}

[data-baseweb="popover"] [role="option"] *,
div[data-baseweb="menu"] ul li *,
div[data-baseweb="menu"] li * {
  color: var(--ink) !important;
}

[data-baseweb="popover"] [role="option"][aria-selected="true"],
div[data-baseweb="menu"] ul li[aria-selected="true"],
div[data-baseweb="menu"] li[aria-selected="true"] {
  background: rgba(28, 95, 130, 0.12) !important;
}

[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [role="option"][data-highlighted="true"],
div[data-baseweb="menu"] ul li:hover,
div[data-baseweb="menu"] li:hover {
  background: rgba(28, 95, 130, 0.08) !important;
}

.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
  color: rgba(17, 35, 58, 0.58) !important;
}

[data-testid="stWidgetLabel"] *,
.stCaption,
[data-testid="stMarkdownContainer"] p {
  color: var(--ink) !important;
}

[data-testid="stWidgetLabel"] p {
  font-weight: 600 !important;
}

[data-testid="stTabs"] {
  gap: 0.5rem;
}

[data-testid="stTabs"] button {
  background: rgba(255,255,255,0.92) !important;
  border: 1px solid rgba(17, 35, 58, 0.10) !important;
  border-radius: 14px 14px 0 0 !important;
  color: rgba(17, 35, 58, 0.80) !important;
  padding: 0.6rem 1rem !important;
}

[data-testid="stTabs"] button p {
  color: rgba(17, 35, 58, 0.80) !important;
  font-weight: 600 !important;
}

[data-testid="stTabs"] button[aria-selected="true"] {
  background: linear-gradient(135deg, var(--teal) 0%, var(--teal-deep) 100%) !important;
  color: #ffffff !important;
}

[data-testid="stTabs"] button[aria-selected="true"] p {
  color: #ffffff !important;
}

[data-testid="stExpander"] {
  background: rgba(255,255,255,0.85);
  border: 1px solid rgba(17, 35, 58, 0.08);
  border-radius: 16px;
}

.helper-card {
  padding: 0.95rem 1rem;
  margin-top: 0.65rem;
  background: rgba(255,255,255,0.92);
}

code {
  background: rgba(20, 95, 91, 0.08);
  color: var(--ink);
  border-radius: 6px;
  padding: 0.12rem 0.34rem;
}

@media (max-width: 1100px) {
  .title-row {
    flex-direction: column;
  }

  .badge-cluster {
    justify-content: flex-start;
  }

  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }

  .title-block h1 {
    font-size: 1.9rem;
  }
}
</style>
"""


st.set_page_config(
    page_title="Singapore Health Policy Navigator",
    page_icon="SHPN",
    layout="wide",
)

st.markdown(APP_STYLES, unsafe_allow_html=True)


def _initialize_session_state() -> None:
    for key, default_value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def _api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


def _is_render_backend() -> bool:
    return "onrender.com" in API_BASE_URL


def _backend_unreachable_message() -> str:
    if _is_render_backend():
        return (
            f"Could not reach the backend at {API_BASE_URL}. If this Render free service is sleeping, "
            "use `Refresh backend status` and give it about 30 to 60 seconds to wake."
        )
    return (
        f"Could not reach the backend at {API_BASE_URL}. Start FastAPI with "
        f"`python3 -m uvicorn main:app --host 127.0.0.1 --port 8000`."
    )


def _request_json(
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        response = requests.request(
            method=method,
            url=_api_url(path),
            json=payload,
            timeout=API_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return None, _backend_unreachable_message()

    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text.strip()}

    if response.status_code >= 400:
        if isinstance(body, dict) and body.get("detail"):
            return None, str(body["detail"])
        return None, f"Backend returned HTTP {response.status_code}."

    if not isinstance(body, dict):
        return None, "Backend returned an unexpected response shape."

    return body, None


@st.cache_data(ttl=5, show_spinner=False)
def _fetch_health_status() -> Dict[str, Any]:
    payload, error = _request_json("GET", "/health")
    if error:
        return {"available": False, "message": error}
    return {"available": True, "payload": payload}


def _wake_backend_status() -> Dict[str, Any]:
    attempts = 4 if _is_render_backend() else 1
    wait_seconds = 5 if _is_render_backend() else 0
    latest_error = _backend_unreachable_message()

    for attempt in range(attempts):
        payload, error = _request_json("GET", "/health")
        if not error and payload:
            _fetch_health_status.clear()
            return {"available": True, "payload": payload}

        if error:
            latest_error = error

        if attempt < attempts - 1:
            time.sleep(wait_seconds)

    return {"available": False, "message": latest_error}


@st.cache_data(show_spinner=False)
def _local_master_stats() -> Dict[str, int]:
    store = get_master_data_store()
    return {
        "plans": int(store.plan_catalog.shape[0]),
        "benefits": int(store.benefits_master.shape[0]),
        "premiums": int(store.premiums_master.shape[0]),
        "cpf": int(store.cpf_limits_master.shape[0]),
    }


def _currency(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    rounded = int(value)
    if float(value) == float(rounded):
        return f"${rounded:,}"
    return f"${value:,.2f}"


def _currency_span(min_value: Optional[float], max_value: Optional[float]) -> str:
    if min_value is None or max_value is None:
        return "N/A"
    if min_value == max_value:
        return _currency(min_value)
    return f"{_currency(min_value)} to {_currency(max_value)}"


def _source_text(source_pdf: str, source_page: int, source_table: int) -> str:
    return f"{source_pdf}, Page {source_page}, Table {source_table}"


def _display_benefit_name(raw_label: str) -> str:
    return clean_text(raw_label).lstrip("- ").strip() or "Matched benefit"


def _premium_summary_text(
    resolution: Dict[str, Any],
    premium_result: Dict[str, Any],
    cpf_limit: Dict[str, Any],
) -> str:
    if not premium_result["premium_available"]:
        return (
            f"{resolution['requested_display_name']} at age {premium_result['age']} falls in the "
            f"{premium_result['age_band_raw']} band, but the source table marks this premium as unavailable."
        )

    return (
        f"{resolution['requested_display_name']} at age {premium_result['age']} falls in the "
        f"{premium_result['age_band_raw']} band. Total premium is "
        f"{_currency_span(premium_result['premium_total_min'], premium_result['premium_total_max'])}, "
        f"with a CPF withdrawal limit of {_currency(cpf_limit['max_withdrawal_limit'])} and cash payable of "
        f"{_currency_span(premium_result['cash_payable_min'], premium_result['cash_payable_max'])}."
    )


def _benefit_summary_text(
    resolution: Dict[str, Any],
    best_match: Dict[str, Any],
) -> str:
    benefit_name = _display_benefit_name(best_match["benefit_raw"])
    if resolution.get("used_fallback"):
        return (
            f"{resolution['requested_display_name']} uses the shared {resolution['effective_display_name']} "
            f"schedule for this lookup. The matched coverage for {benefit_name} is "
            f"{best_match['coverage_value_raw']}."
        )
    return (
        f"For {resolution['requested_display_name']}, the matched coverage for {benefit_name} is "
        f"{best_match['coverage_value_raw']}."
    )


def _html_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return escape(text).replace("\n", "<br>")


def _render_metric_card(title: str, value: str, caption: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{escape(title)}</div>
          <div class="metric-value">{_html_text(value)}</div>
          <div class="metric-caption">{_html_text(caption)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_pill_row(items: List[Tuple[str, str]]) -> None:
    if not items:
        return
    st.markdown(
        "<div class='chip-row'>"
        + "".join(
            f"<span class='chip {escape(kind)}'>{_html_text(label)}</span>"
            for label, kind in items
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_message_shell(role_label: str, title: str, body: str, role_class: str) -> None:
    st.markdown(
        f"""
        <div class="message-card {escape(role_class)}">
          <div class="message-meta">{escape(role_label)}</div>
          <div class="message-title">{escape(title)}</div>
          <div class="message-body">{_html_text(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_summary_card(label: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="summary-card">
          <div class="summary-label">{escape(label)}</div>
          <div class="summary-copy">{_html_text(copy)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _maybe_render_raw_payload(payload: Dict[str, Any]) -> None:
    if not SHOW_DEBUG_PAYLOADS:
        return
    with st.expander("Raw payload", expanded=False):
        st.json(payload)


def _recommendation_field_label(field_name: str) -> str:
    return {
        "age": "Age",
        "budget_preference": "Budget preference",
        "ward_preference": "Ward preference",
        "coverage_style": "Coverage style",
    }.get(field_name, field_name.replace("_", " ").title())


def _recommendation_value_label(field_name: str, value: Any) -> str:
    if field_name == "budget_preference":
        return {
            "low_cost": "Keep premiums low",
            "balanced": "Balanced cost and coverage",
            "coverage_flexible": "Coverage matters more",
        }.get(str(value), str(value))
    if field_name == "ward_preference":
        return {
            "basic": "Basic / Plan C",
            "standard": "Standard",
            "class_b1": "Class B1",
            "class_a": "Class A",
            "private": "Private hospital",
            "unsure": "Not sure yet",
        }.get(str(value), str(value))
    if field_name == "coverage_style":
        return {
            "lowest_cost": "Lowest cost",
            "balanced": "Balanced",
            "strongest_coverage": "Strongest coverage",
        }.get(str(value), str(value))
    if field_name == "age":
        return str(value)
    return str(value)


def _chat_conversation_state() -> Dict[str, Any]:
    pending_recommendation = st.session_state.get("pending_recommendation")
    if pending_recommendation:
        return {"recommendation_context": pending_recommendation}
    return {}


def _update_chat_state_from_payload(payload: Dict[str, Any]) -> None:
    extracted_data = payload.get("extracted_data", {})
    conversation_state = extracted_data.get("conversation_state", {})
    recommendation_context = conversation_state.get("recommendation_context")
    if recommendation_context and recommendation_context.get("pending"):
        st.session_state.pending_recommendation = recommendation_context
        return
    st.session_state.pending_recommendation = None


def _friendly_error_content(code: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    details = details or {}
    message_map = {
        "transport_error": {
            "title": "The app could not reach the backend.",
            "body": "The assistant needs the FastAPI service to answer questions. Start the backend, then refresh the status panel.",
            "suggestions": [
                "Run `python3 -m uvicorn main:app --host 127.0.0.1 --port 8000`.",
                "Use the refresh button in the sidebar after the service is up.",
            ],
        },
        "ambiguous_plan": {
            "title": "More than one plan matches this request.",
            "body": "Narrow the selection with insurer, tier, or a specific plan so the answer stays tied to one schedule.",
            "suggestions": details.get("candidates", []),
        },
        "plan_not_found": {
            "title": "No plan matched that combination.",
            "body": "Try widening the filters first, then choose a plan from the guided selector.",
            "suggestions": details.get("candidates", []),
        },
        "benefit_not_found": {
            "title": "No benefit row matched that keyword.",
            "body": "Try a simpler term such as `ICU`, `psychiatric`, or `ward`, then refine from the supporting match list.",
            "suggestions": [],
        },
        "missing_age": {
            "title": "Age is required for premium questions.",
            "body": "Add the person's age so the app can resolve the correct premium band and CPF withdrawal limit.",
            "suggestions": [],
        },
        "missing_benefit_keyword": {
            "title": "A benefit keyword is required.",
            "body": "Enter a short benefit term such as `ICU`, `psychiatric`, `ward`, or `cancer`.",
            "suggestions": [],
        },
        "unsupported_intent": {
            "title": "This assistant focuses on Integrated Shield Plan questions.",
            "body": "Ask about premiums, cash payable, coverage, or plan benefits to get a structured answer.",
            "suggestions": EXAMPLE_PROMPTS,
        },
        "local_validation": {
            "title": "A few details are still missing.",
            "body": "Complete the highlighted input before sending the request so the result is deterministic.",
            "suggestions": [],
        },
    }
    return message_map.get(
        code,
        {
            "title": "The request could not be completed cleanly.",
            "body": "Adjust the filters or try a more specific question. Technical details are available in the raw payload if you need them.",
            "suggestions": details.get("candidates", []),
        },
    )


def _render_guidance_card(code: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    content = _friendly_error_content(code, details)
    body = message if message else content["body"]
    st.markdown(
        f"""
        <div class="guidance-card error">
          <div class="guidance-title">{escape(content['title'])}</div>
          <div class="guidance-copy">{_html_text(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    suggestions = [item for item in content.get("suggestions", []) if item]
    if suggestions:
        _render_pill_row([(suggestion, "warning") for suggestion in suggestions])


def _render_empty_state(title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="empty-state">
          <div class="empty-title">{escape(title)}</div>
          <div class="empty-copy">{_html_text(copy)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_recommendation_context(context: Dict[str, Any]) -> None:
    context_items: List[Tuple[str, str]] = []
    for field_name in ["age", "budget_preference", "ward_preference", "coverage_style"]:
        value = context.get(field_name)
        if value is None:
            continue
        context_items.append(
            (
                f"{_recommendation_field_label(field_name)}: {_recommendation_value_label(field_name, value)}",
                "",
            )
        )
    if context_items:
        _render_pill_row(context_items)


def _render_recommendation_card(recommendation: Dict[str, Any]) -> None:
    summary = (
        f"{recommendation.get('display_name', 'Suggested plan')} from "
        f"{recommendation.get('insurer_name') or 'baseline schedule'}."
    )
    _render_summary_card(
        f"Option {recommendation.get('rank', '?')}",
        f"{summary} {recommendation.get('rationale', '')}".strip(),
    )
    metric_columns = st.columns(4)
    with metric_columns[0]:
        _render_metric_card(
            "Plan",
            recommendation.get("display_name", "N/A"),
            _tier_badge_text(recommendation.get("tier_code", "")),
        )
    with metric_columns[1]:
        _render_metric_card(
            "Annual premium",
            recommendation.get("annual_premium_display", "N/A"),
            recommendation.get("monthly_premium_display", ""),
        )
    with metric_columns[2]:
        _render_metric_card(
            "Cash payable",
            recommendation.get("cash_payable_display", "N/A"),
            f"Age band {recommendation.get('age_band_raw', 'N/A')}",
        )
    with metric_columns[3]:
        _render_metric_card(
            "Fit profile",
            f"{recommendation.get('heuristic_score', 0):.2f}",
            (
                f"Tier {recommendation.get('tier_fit', 0):.2f} · "
                f"Cost {recommendation.get('affordability_fit', 0):.2f} · "
                f"Coverage {recommendation.get('coverage_fit', 0):.2f}"
            ),
        )
    _render_pill_row(
        [
            (
                f"Source: {_source_text(recommendation['source_pdf'], recommendation['source_page'], recommendation['source_table'])}",
                "",
            )
        ]
    )


def _insurer_value_from_label(label: str) -> Optional[str]:
    if not label or label == "":
        return None
    if label == BASELINE_INSURER_VALUE:
        return None
    return label


def _insurer_badge_text(label: str) -> str:
    return INSURER_LABELS.get(label, "Any insurer")


def _tier_badge_text(code: str) -> str:
    return TIER_LABELS.get(code, "Any tier")


def _plan_catalog_rows(capability: str) -> List[Dict[str, Any]]:
    store = get_master_data_store()
    rows: List[Dict[str, Any]] = []
    for row in store.plan_rows:
        include_row = False
        if capability == "premium":
            include_row = bool(row.get("has_premium_data"))
        elif capability == "benefit":
            include_row = bool(row.get("has_benefits")) or clean_text(row.get("tier_code")) == "standard"
        if not include_row:
            continue

        rows.append(
            {
                "plan_id": clean_text(row.get("plan_id")),
                "display_name": clean_text(row.get("display_name")),
                "insurer_name": clean_text(row.get("insurer_name")),
                "tier_code": clean_text(row.get("tier_code")),
            }
        )

    rows.sort(key=lambda row: (row["tier_code"], row["insurer_name"], row["display_name"]))
    return rows


def _selected_plan_row(candidates: List[Dict[str, Any]], selection: str) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    if len(candidates) == 1 or selection == "__auto__":
        return candidates[0]
    for row in candidates:
        if row["plan_id"] == selection:
            return row
    return None


def _effective_benefit_plan_row(selected_plan: Dict[str, Any]) -> Tuple[Dict[str, Any], bool, str]:
    store = get_master_data_store()
    requested_plan = store.plan_by_id[selected_plan["plan_id"]]
    effective_plan = requested_plan
    used_fallback = False
    fallback_reason = ""

    if clean_text(requested_plan.get("tier_code")) == "standard" and not bool(requested_plan.get("has_benefits")):
        effective_plan = store.plan_by_id[STANDARD_BASELINE_PLAN_ID]
        used_fallback = True
        fallback_reason = (
            "Standard-tier insurer plans share the baseline Standard IP benefit schedule, "
            "so browsing uses the shared Standard rows."
        )

    return effective_plan, used_fallback, fallback_reason


def _candidate_plans(
    capability: str,
    insurer_filter: str,
    tier_filter: str,
) -> List[Dict[str, Any]]:
    candidates = _plan_catalog_rows(capability)
    if tier_filter:
        candidates = [row for row in candidates if row["tier_code"] == tier_filter]
    if insurer_filter == BASELINE_INSURER_VALUE:
        candidates = [row for row in candidates if not row["insurer_name"]]
    elif insurer_filter:
        candidates = [row for row in candidates if row["insurer_name"] == insurer_filter]
    return candidates


def _plan_selectbox_options(candidates: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, str], bool]:
    if not candidates:
        return ["__none__"], {"__none__": "No plans available for these filters"}, True
    if len(candidates) == 1:
        return ["__auto__"], {"__auto__": "Any matching plan"}, True

    option_labels = {"__choose__": "Choose a plan"}
    option_keys = ["__choose__"]
    for row in candidates:
        option_keys.append(row["plan_id"])
        option_labels[row["plan_id"]] = row["display_name"]
    return option_keys, option_labels, False


def _current_filter_snapshot(prefix: str, extra: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = {
        "insurer": st.session_state.get(f"{prefix}_insurer", ""),
        "tier": st.session_state.get(f"{prefix}_tier", ""),
        "plan_selection": st.session_state.get(f"{prefix}_plan_selection", "__auto__"),
    }
    snapshot.update(extra)
    return snapshot


def _normalize_endpoint_error(message: str, code: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "response": message,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def _submitted_plan_name(selection: str, candidates: List[Dict[str, Any]]) -> Optional[str]:
    if selection in {"__auto__", "__choose__", "__none__"}:
        return None
    for row in candidates:
        if row["plan_id"] == selection:
            return row["display_name"]
    return None


def _build_benefit_catalog_payload(selected_plan: Dict[str, Any]) -> Dict[str, Any]:
    store = get_master_data_store()
    effective_plan, used_fallback, fallback_reason = _effective_benefit_plan_row(selected_plan)
    benefit_rows = [
        row for row in store.benefit_rows if clean_text(row.get("plan_id")) == clean_text(effective_plan.get("plan_id"))
    ]
    unique_sections = []
    seen_sections = set()
    for row in benefit_rows:
        section = clean_text(row.get("section_raw")) or "General benefits"
        if section not in seen_sections:
            seen_sections.add(section)
            unique_sections.append(section)

    catalog_rows = [
        {
            "Section": clean_text(row.get("section_raw")) or "General benefits",
            "Benefit": _display_benefit_name(clean_text(row.get("benefit_raw"))),
            "Coverage": clean_text(row.get("coverage_value_raw")),
            "Notes": clean_text(row.get("notes_raw")),
        }
        for row in benefit_rows
    ]

    requested_display = selected_plan["display_name"]
    effective_display = clean_text(effective_plan.get("display_name"))
    response = (
        f"Showing {len(catalog_rows)} available benefit rows for {requested_display}."
        if not used_fallback
        else f"Showing {len(catalog_rows)} available benefit rows for {requested_display} using the shared {effective_display} schedule."
    )

    return {
        "mode": "catalog",
        "response": response,
        "plan_resolution": {
            "requested_plan_id": selected_plan["plan_id"],
            "effective_plan_id": clean_text(effective_plan.get("plan_id")),
            "requested_display_name": requested_display,
            "effective_display_name": effective_display,
            "tier_code": selected_plan["tier_code"],
            "insurer_name": selected_plan["insurer_name"],
            "used_fallback": used_fallback,
            "fallback_reason": fallback_reason,
        },
        "benefit_catalog": {
            "total_rows": len(catalog_rows),
            "sections": unique_sections,
            "rows": catalog_rows,
        },
    }


def _render_header(health_status: Dict[str, Any], local_stats: Dict[str, int]) -> bool:
    backend_available = bool(health_status.get("available"))
    model_name = "Unavailable"
    if backend_available:
        model_name = health_status["payload"]["model"]

    status_badge_class = "ok" if backend_available else "warn"
    status_text = "Backend online" if backend_available else "Backend offline"
    st.markdown(
        f"""
        <section class="shell-header">
          <div class="eyebrow">Singapore Integrated Shield Plans</div>
          <div class="title-row">
            <div class="title-block">
              <h1>Health Policy Navigator</h1>
              <div class="lede">
                Ask questions about premiums, cash payable, benefits, and what coverage to consider without digging through raw tables.
                Chat handles natural-language lookups and guided recommendations, while the explorer tabs provide deterministic tools.
              </div>
            </div>
            <div class="badge-cluster">
              <span class="status-pill {status_badge_class}">{escape(status_text)}</span>
              <span class="info-pill">Model: {escape(model_name)}</span>
              <span class="info-pill">Source-backed answers</span>
            </div>
          </div>
          <div class="stat-grid">
            <div class="mini-stat">
              <div class="mini-stat-label">Plans</div>
              <div class="mini-stat-value">{local_stats['plans']}</div>
              <div class="mini-stat-copy">Catalog entries available for selection.</div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-label">Benefit Rows</div>
              <div class="mini-stat-value">{local_stats['benefits']:,}</div>
              <div class="mini-stat-copy">Grounded coverage rows across the normalized tables.</div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-label">Premium Rows</div>
              <div class="mini-stat-value">{local_stats['premiums']:,}</div>
              <div class="mini-stat-copy">Age-band premium rows used for deterministic quoting.</div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-label">CPF Bands</div>
              <div class="mini-stat-value">{local_stats['cpf']}</div>
              <div class="mini-stat-copy">Withdrawal-limit brackets used in cash-payable estimates.</div>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    return backend_available


def _render_sidebar(backend_available: bool) -> None:
    status_class = "online" if backend_available else "offline"
    status_text = "Online" if backend_available else "Sleeping or offline"
    st.sidebar.markdown("## Control Room")
    st.sidebar.markdown(
        f"""
        <div class="sidebar-card">
          <div class="sidebar-label">Backend URL</div>
          <div class="sidebar-value"><code>{escape(API_BASE_URL)}</code></div>
          <div class="sidebar-label" style="margin-top:0.75rem;">Status</div>
          <div class="sidebar-status {status_class}">{escape(status_text)}</div>
          <div class="sidebar-note">
            {'Render free services may sleep when idle. Use the refresh button to wake the backend.' if _is_render_backend() else 'Use the refresh button after starting the local FastAPI backend.'}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.sidebar.button("Refresh backend status", use_container_width=True):
        with st.spinner("Checking backend status..."):
            refreshed_status = _wake_backend_status()
        if refreshed_status.get("available"):
            st.session_state.backend_refresh_notice = "Backend is online and ready."
            st.session_state.backend_refresh_notice_level = "success"
        else:
            st.session_state.backend_refresh_notice = refreshed_status.get(
                "message",
                "Backend is still unavailable. If this is Render free tier, wait a little longer and try again.",
            )
            st.session_state.backend_refresh_notice_level = "warning"
        _fetch_health_status.clear()
        st.rerun()

    notice = clean_text(st.session_state.get("backend_refresh_notice"))
    if notice:
        level = clean_text(st.session_state.get("backend_refresh_notice_level")) or "info"
        if level == "success":
            st.sidebar.success(notice)
        elif level == "warning":
            st.sidebar.warning(notice)
        else:
            st.sidebar.info(notice)

    if st.sidebar.button("Clear conversation", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.chat_draft = ""
        st.session_state.pending_recommendation = None
        st.rerun()

    st.sidebar.markdown("### Workflow")
    st.sidebar.markdown(
        "- Use **Chat** for natural-language premium, benefit, and recommendation questions.\n"
        "- Use **Premium Explorer** for guided deterministic premium quotes.\n"
        "- Use **Benefit Explorer** for exact coverage lookups with source citations."
    )


def _append_chat_message(role: str, content: str, payload: Optional[Dict[str, Any]] = None) -> None:
    history = list(st.session_state.chat_history)
    message: Dict[str, Any] = {"role": role, "content": content}
    if payload is not None:
        message["payload"] = payload
    history.append(message)
    st.session_state.chat_history = history


def _submit_chat_draft() -> None:
    prompt = clean_text(st.session_state.chat_draft)
    if not prompt:
        return

    _append_chat_message("user", prompt)
    st.session_state.chat_clear_after_send = True

    with st.spinner("Preparing an answer..."):
        payload, error = _request_json(
            "POST",
            "/chat",
            {
                "message": prompt,
                "conversation_state": _chat_conversation_state(),
            },
        )

    if error:
        transport_payload = {
            "response": error,
            "tool_used": None,
            "extracted_data": {
                "extraction": {},
                "result": {
                    "kind": "error",
                    "code": "transport_error",
                    "message": error,
                    "details": {},
                },
            },
        }
        _append_chat_message("assistant", error, transport_payload)
        st.rerun()

    _update_chat_state_from_payload(payload)
    _append_chat_message("assistant", payload["response"], payload)
    st.rerun()


def _render_chat_assistant_result(payload: Dict[str, Any], message_index: int = 0) -> None:
    result = payload.get("extracted_data", {}).get("result", {})
    result_kind = result.get("kind")
    response_text = payload.get("response", "")

    if result_kind == "premium":
        resolution = result["plan_resolution"]
        premium_result = result["premium_result"]
        cpf_limit = result["cpf_limit"]
        _render_summary_card("Answer", _premium_summary_text(resolution, premium_result, cpf_limit))
        metric_columns = st.columns(4)
        with metric_columns[0]:
            _render_metric_card("Matched plan", resolution["requested_display_name"], _tier_badge_text(resolution["tier_code"]))
        with metric_columns[1]:
            _render_metric_card("Age band", premium_result["age_band_raw"], f"Age {premium_result['age']}")
        with metric_columns[2]:
            _render_metric_card(
                "Total premium",
                _currency_span(premium_result["premium_total_min"], premium_result["premium_total_max"]),
                premium_result["premium_total_raw"],
            )
        with metric_columns[3]:
            _render_metric_card(
                "Cash payable",
                _currency_span(premium_result["cash_payable_min"], premium_result["cash_payable_max"]),
                f"CPF limit {_currency(cpf_limit['max_withdrawal_limit'])}",
            )
        _render_pill_row(
            [
                (f"Source: {_source_text(premium_result['source_pdf'], premium_result['source_page'], premium_result['source_table'])}", ""),
                (f"Premium shape: {premium_result['premium_shape']}", ""),
            ]
        )
        if not premium_result["premium_available"]:
            _render_guidance_card(
                "premium_not_available",
                premium_result.get("availability_note") or "The source table marks this premium as unavailable.",
                {},
            )

    elif result_kind == "benefit":
        resolution = result["plan_resolution"]
        best_match = result["benefit_result"]["best_match"]
        _render_summary_card("Answer", _benefit_summary_text(resolution, best_match))
        metric_columns = st.columns(3)
        with metric_columns[0]:
            _render_metric_card("Matched plan", resolution["requested_display_name"], f"Effective schedule: {resolution['effective_display_name']}")
        with metric_columns[1]:
            _render_metric_card("Matched benefit", _display_benefit_name(best_match["benefit_raw"]), best_match["match_reason"])
        with metric_columns[2]:
            _render_metric_card("Coverage", best_match["coverage_value_raw"], f"Score {best_match['match_score']:.1f}")
        pills = [(f"Source: {_source_text(best_match['source_pdf'], best_match['source_page'], best_match['source_table'])}", "")]
        if resolution.get("used_fallback"):
            pills.append((f"Shared Standard schedule used: {resolution['effective_display_name']}", "warning"))
        _render_pill_row(pills)
        if best_match.get("notes_raw"):
            _render_summary_card("Supporting note", best_match["notes_raw"])
        supporting_matches = result["benefit_result"].get("top_matches", [])[1:]
        if supporting_matches:
            st.markdown("#### Nearby matches")
            for match in supporting_matches[:3]:
                st.markdown(
                    f"- **{_display_benefit_name(match['benefit_raw'])}**: {match['coverage_value_raw']} "
                    f"({_source_text(match['source_pdf'], match['source_page'], match['source_table'])})"
                )

    elif result_kind == "unsupported":
        _render_guidance_card(result.get("code", "unsupported_intent"), result.get("message", response_text), result.get("details", {}))

    elif result_kind == "recommendation_intake":
        _render_summary_card("Recommendation intake", result.get("message", response_text))
        recommendation_context = result.get("recommendation_context", {})
        _render_recommendation_context(recommendation_context)
        missing_fields = result.get("missing_fields", [])
        if missing_fields:
            _render_pill_row(
                [
                    (f"Still needed: {_recommendation_field_label(field_name)}", "warning")
                    for field_name in missing_fields
                ]
            )
        options = result.get("options", [])
        if options:
            st.markdown("#### Quick replies")
            option_columns = st.columns(len(options))
            for index, option in enumerate(options):
                if option_columns[index].button(
                    option.get("label", option.get("reply_text", "Use option")),
                    key=f"recommendation_option_{message_index}_{index}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state.chat_draft = option.get("reply_text", "")
                    st.rerun()

    elif result_kind == "recommendation":
        _render_summary_card("Recommendation shortlist", result.get("message", response_text))
        recommendation_context = result.get("recommendation_context", {})
        _render_recommendation_context(recommendation_context)
        _render_pill_row(
            [
                (f"Recommended tier: {_tier_badge_text(result.get('recommended_tier', ''))}", ""),
            ]
        )
        for recommendation in result.get("recommendations", [])[:3]:
            _render_recommendation_card(recommendation)
        decision_factors = [factor for factor in result.get("decision_factors", []) if factor]
        if decision_factors:
            st.markdown("#### Why these plans")
            for factor in decision_factors:
                st.markdown(f"- {factor}")
        if result.get("disclaimer"):
            _render_summary_card("Important note", result["disclaimer"])

    elif result_kind == "error" or result.get("code"):
        _render_guidance_card(result.get("code", "unknown_error"), result.get("message", response_text), result.get("details", {}))

    else:
        _render_summary_card("Assistant reply", response_text or "No structured response was returned.")

    _maybe_render_raw_payload(payload)


def _render_chat_tab(backend_available: bool) -> None:
    if st.session_state.get("chat_clear_after_send"):
        st.session_state.chat_draft = ""
        st.session_state.chat_clear_after_send = False

    pending_recommendation = st.session_state.get("pending_recommendation") or {}
    composer_placeholder = "Example: I am 45, how much cash do I pay for Prudential Class A?"
    if pending_recommendation.get("pending"):
        composer_placeholder = "Reply to the recommendation question, or ask a new policy question to start over."

    left_col, right_col = st.columns([1.7, 1], gap="large")
    with left_col:
        st.markdown(
            """
            <div class="chat-frame">
              <div class="section-label">Primary Workspace</div>
              <div class="section-title">Chat Assistant</div>
              <div class="section-copy">
                Ask a natural-language question and get a structured answer with citations, matched plan context,
                and clear next steps when something is ambiguous.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        st.markdown("<div class='example-note'>Prefill examples. Clicking a prompt only loads it into the composer.</div>", unsafe_allow_html=True)
        example_columns = st.columns(len(EXAMPLE_PROMPTS))
        for index, example_prompt in enumerate(EXAMPLE_PROMPTS):
            if example_columns[index].button(
                example_prompt,
                key=f"example_prompt_{index}",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state.chat_draft = example_prompt

        st.markdown("<div style='height:0.55rem'></div>", unsafe_allow_html=True)
        if not st.session_state.chat_history:
            _render_empty_state(
                "No conversation yet",
                "Start with a premium, benefit, or recommendation question. The app will turn the backend payload into a cleaner answer card instead of dumping raw text.",
            )
        elif pending_recommendation.get("pending"):
            _render_summary_card(
                "Recommendation in progress",
                "The assistant is collecting a few preferences before it ranks a shortlist.",
            )
            _render_recommendation_context(pending_recommendation)

        for message_index, message in enumerate(st.session_state.chat_history):
            role = message["role"]
            if role == "user":
                _render_message_shell("You", "Question", message["content"], "user")
            else:
                if message.get("payload"):
                    _render_chat_assistant_result(message["payload"], message_index=message_index)
                else:
                    _render_summary_card("Assistant reply", message["content"])

        st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
        st.text_area(
            "Ask about premiums, cash payable, plan benefits, or what coverage to consider",
            key="chat_draft",
            height=100,
            disabled=not backend_available,
            placeholder=composer_placeholder,
        )
        if not backend_available:
            _render_guidance_card(
                "transport_error",
                "The backend is offline right now, so chat is temporarily read-only.",
                {},
            )
        send_disabled = (not backend_available) or (not clean_text(st.session_state.chat_draft))
        if st.button("Send query", use_container_width=True, disabled=send_disabled):
            _submit_chat_draft()

    with right_col:
        st.markdown(
            """
            <div class="panel-card">
              <div class="section-label">Supporting Tools</div>
              <div class="preview-title">Explorer tools</div>
              <div class="preview-copy">
                Use the side tabs when you want guided lookups instead of open-ended chat. These routes bypass the LLM and resolve against the master tables directly.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="preview-card">
              <div class="preview-title">Premium Explorer</div>
              <div class="preview-copy">Pick age, insurer, tier, and plan from guided selectors. The result returns premium, CPF limit, and cash payable without any plan-name guesswork.</div>
              <ul class="preview-list">
                <li>Deterministic route</li>
                <li>Guided plan narrowing</li>
                <li>Cash-payable breakdown</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="preview-card">
              <div class="preview-title">Benefit Explorer</div>
              <div class="preview-copy">Search exact benefit coverage with a keyword, or leave the keyword blank to browse the full benefit schedule for the selected plan.</div>
              <ul class="preview-list">
                <li>Guided plan filters</li>
                <li>Source-backed coverage text</li>
                <li>Optional keyword browse mode</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_premium_payload(payload: Dict[str, Any]) -> None:
    error = payload.get("error")
    if error:
        _render_guidance_card(error["code"], error["message"], error.get("details", {}))
        _maybe_render_raw_payload(payload)
        return

    premium_result = payload["premium_result"]
    resolution = payload["plan_resolution"]
    cpf_limit = payload["cpf_limit"]
    _render_summary_card("Premium quote", _premium_summary_text(resolution, premium_result, cpf_limit))

    metric_columns = st.columns(4)
    with metric_columns[0]:
        _render_metric_card("Matched plan", resolution["requested_display_name"], _tier_badge_text(resolution["tier_code"]))
    with metric_columns[1]:
        _render_metric_card("Age band", premium_result["age_band_raw"], f"Age {premium_result['age']}")
    with metric_columns[2]:
        _render_metric_card(
            "Total premium",
            _currency_span(premium_result["premium_total_min"], premium_result["premium_total_max"]),
            premium_result["premium_total_raw"],
        )
    with metric_columns[3]:
        _render_metric_card(
            "Cash payable",
            _currency_span(premium_result["cash_payable_min"], premium_result["cash_payable_max"]),
            f"CPF limit {_currency(cpf_limit['max_withdrawal_limit'])}",
        )

    _render_pill_row(
        [
            (f"Source: {_source_text(premium_result['source_pdf'], premium_result['source_page'], premium_result['source_table'])}", ""),
            (f"Premium shape: {premium_result['premium_shape']}", ""),
        ]
    )
    if not premium_result["premium_available"]:
        _render_guidance_card(
            "premium_not_available",
            premium_result.get("availability_note") or "The source table marks this premium as unavailable.",
            {},
        )
    _maybe_render_raw_payload(payload)


def _render_benefit_payload(payload: Dict[str, Any]) -> None:
    error = payload.get("error")
    if error:
        _render_guidance_card(error["code"], error["message"], error.get("details", {}))
        _maybe_render_raw_payload(payload)
        return

    if payload.get("mode") == "catalog":
        resolution = payload["plan_resolution"]
        catalog = payload["benefit_catalog"]
        _render_summary_card("Benefit catalog", payload["response"])

        metric_columns = st.columns(3)
        with metric_columns[0]:
            _render_metric_card("Selected plan", resolution["requested_display_name"], _tier_badge_text(resolution["tier_code"]))
        with metric_columns[1]:
            _render_metric_card("Benefit rows", str(catalog["total_rows"]), f"{len(catalog['sections'])} sections available")
        with metric_columns[2]:
            _render_metric_card("Schedule used", resolution["effective_display_name"], "Shared Standard fallback" if resolution.get("used_fallback") else "Direct plan schedule")

        if resolution.get("used_fallback"):
            _render_guidance_card(
                "catalog_fallback",
                resolution.get("fallback_reason") or "This browse view uses the shared Standard schedule for the selected insurer plan.",
                {},
            )

        _render_pill_row([(section, "") for section in catalog["sections"][:8]])
        st.dataframe(catalog["rows"], use_container_width=True, hide_index=True)
        _maybe_render_raw_payload(payload)
        return

    resolution = payload["plan_resolution"]
    best_match = payload["benefit_result"]["best_match"]
    _render_summary_card("Benefit result", _benefit_summary_text(resolution, best_match))

    metric_columns = st.columns(3)
    with metric_columns[0]:
        _render_metric_card("Matched plan", resolution["requested_display_name"], f"Effective schedule: {resolution['effective_display_name']}")
    with metric_columns[1]:
        _render_metric_card("Matched benefit", _display_benefit_name(best_match["benefit_raw"]), best_match["match_reason"])
    with metric_columns[2]:
        _render_metric_card("Coverage", best_match["coverage_value_raw"], f"Score {best_match['match_score']:.1f}")

    pills = [(f"Source: {_source_text(best_match['source_pdf'], best_match['source_page'], best_match['source_table'])}", "")]
    if resolution.get("used_fallback"):
        pills.append((f"Shared Standard schedule used: {resolution['effective_display_name']}", "warning"))
    _render_pill_row(pills)

    if best_match.get("notes_raw"):
        _render_summary_card("Supporting note", best_match["notes_raw"])

    supporting_matches = payload["benefit_result"].get("top_matches", [])[1:]
    if supporting_matches:
        st.markdown("#### Nearby matches")
        for match in supporting_matches[:3]:
            st.markdown(
                f"- **{_display_benefit_name(match['benefit_raw'])}**: {match['coverage_value_raw']} "
                f"({_source_text(match['source_pdf'], match['source_page'], match['source_table'])})"
            )
    _maybe_render_raw_payload(payload)


def _reset_stale_result(prefix: str, current_snapshot: Dict[str, Any]) -> None:
    submitted_key = f"{prefix}_submitted_filters"
    payload_key = f"{prefix}_lookup_payload"
    submitted_snapshot = st.session_state.get(submitted_key)
    if submitted_snapshot and submitted_snapshot != current_snapshot:
        st.session_state[submitted_key] = None
        st.session_state[payload_key] = None


def _render_plan_helper(capability: str, insurer_filter: str, tier_filter: str, candidates: List[Dict[str, Any]]) -> None:
    scope_bits: List[str] = []
    if insurer_filter:
        scope_bits.append(_insurer_badge_text(insurer_filter))
    if tier_filter:
        scope_bits.append(_tier_badge_text(tier_filter))
    scope_text = " + ".join(scope_bits) if scope_bits else "all filters"

    if not candidates:
        _render_guidance_card(
            "plan_not_found",
            f"No plans are available for {scope_text}. Adjust the insurer or tier filters.",
            {},
        )
        return

    if len(candidates) == 1:
        st.markdown(
            f"<div class='helper-note'>1 plan available for {escape(scope_text)}. The request will automatically resolve to <strong>{escape(candidates[0]['display_name'])}</strong>.</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"<div class='helper-note'>{len(candidates)} plans available for {escape(scope_text)}. Choose one plan before submitting so the result stays precise.</div>",
        unsafe_allow_html=True,
    )


def _render_premium_tab(backend_available: bool) -> None:
    st.markdown("### Premium Explorer")
    st.caption("Deterministic premium quotes with guided plan narrowing. This route does not rely on LLM synthesis.")

    left, right = st.columns(2)
    with left:
        st.number_input("Age", min_value=1, max_value=120, step=1, key="premium_age")
        st.selectbox(
            "Insurer",
            options=list(INSURER_LABELS.keys()),
            format_func=lambda value: INSURER_LABELS[value],
            key="premium_insurer",
        )
    with right:
        st.selectbox(
            "Tier",
            options=[value for _, value in TIER_OPTIONS],
            format_func=lambda value: TIER_LABELS[value],
            key="premium_tier",
        )

    candidates = _candidate_plans("premium", st.session_state.premium_insurer, st.session_state.premium_tier)
    option_keys, option_labels, plan_disabled = _plan_selectbox_options(candidates)
    current_plan_selection = st.session_state.get("premium_plan_selection", "__auto__")
    if current_plan_selection not in option_keys:
        st.session_state.premium_plan_selection = option_keys[0]

    st.selectbox(
        "Plan",
        options=option_keys,
        format_func=lambda value: option_labels[value],
        key="premium_plan_selection",
        disabled=plan_disabled,
    )
    _render_plan_helper("premium", st.session_state.premium_insurer, st.session_state.premium_tier, candidates)

    current_snapshot = _current_filter_snapshot("premium", {"age": int(st.session_state.premium_age)})
    _reset_stale_result("premium", current_snapshot)

    can_submit = backend_available and bool(candidates) and (
        len(candidates) == 1 or st.session_state.premium_plan_selection not in {"__choose__", "__none__"}
    )
    if st.button("Get premium quote", use_container_width=True, disabled=not can_submit):
        plan_name = _submitted_plan_name(st.session_state.premium_plan_selection, candidates)
        request_payload = {
            "age": int(st.session_state.premium_age),
            "insurer": _insurer_value_from_label(st.session_state.premium_insurer),
            "tier": st.session_state.premium_tier or None,
            "plan_name": plan_name,
        }
        with st.spinner("Resolving premium quote..."):
            payload, error = _request_json("POST", "/premium/quote", request_payload)
        st.session_state.premium_lookup_payload = (
            payload if payload is not None else _normalize_endpoint_error(error or "Unknown error", "transport_error")
        )
        st.session_state.premium_submitted_filters = current_snapshot
        st.rerun()

    if not backend_available:
        _render_guidance_card("transport_error", "The backend is offline, so premium requests are temporarily unavailable.", {})
    elif not candidates:
        pass
    elif len(candidates) > 1 and st.session_state.premium_plan_selection in {"__choose__", "__none__"}:
        _render_empty_state(
            "Choose a specific plan",
            "The insurer and tier filters still match multiple plans. Pick one plan above to unlock the deterministic quote.",
        )

    if st.session_state.get("premium_lookup_payload"):
        st.markdown("### Premium Quote")
        _render_premium_payload(st.session_state.premium_lookup_payload)


def _render_benefit_tab(backend_available: bool) -> None:
    st.markdown("### Benefit Explorer")
    st.caption("Search a specific benefit keyword, or leave it blank to browse the available benefit schedule for the selected plan.")

    left, right = st.columns(2)
    with left:
        st.text_input(
            "Benefit keyword (optional)",
            key="benefit_keyword",
            placeholder="Example: ICU, psychiatric, ward",
        )
        st.selectbox(
            "Insurer",
            options=list(INSURER_LABELS.keys()),
            format_func=lambda value: INSURER_LABELS[value],
            key="benefit_insurer",
        )
    with right:
        st.selectbox(
            "Tier",
            options=[value for _, value in TIER_OPTIONS],
            format_func=lambda value: TIER_LABELS[value],
            key="benefit_tier",
        )

    candidates = _candidate_plans("benefit", st.session_state.benefit_insurer, st.session_state.benefit_tier)
    option_keys, option_labels, plan_disabled = _plan_selectbox_options(candidates)
    current_plan_selection = st.session_state.get("benefit_plan_selection", "__auto__")
    if current_plan_selection not in option_keys:
        st.session_state.benefit_plan_selection = option_keys[0]

    st.selectbox(
        "Plan",
        options=option_keys,
        format_func=lambda value: option_labels[value],
        key="benefit_plan_selection",
        disabled=plan_disabled,
    )
    _render_plan_helper("benefit", st.session_state.benefit_insurer, st.session_state.benefit_tier, candidates)

    current_snapshot = _current_filter_snapshot("benefit", {"benefit_keyword": clean_text(st.session_state.benefit_keyword)})
    _reset_stale_result("benefit", current_snapshot)

    keyword = clean_text(st.session_state.benefit_keyword)
    selection_ready = bool(candidates) and (
        len(candidates) == 1 or st.session_state.benefit_plan_selection not in {"__choose__", "__none__"}
    )
    can_submit = backend_available and selection_ready

    button_label = "Browse benefit schedule" if not keyword else "Search benefits"

    if st.button(button_label, use_container_width=True, disabled=not can_submit):
        if not keyword:
            selected_plan = _selected_plan_row(candidates, st.session_state.benefit_plan_selection)
            if selected_plan is None:
                st.session_state.benefit_lookup_payload = _normalize_endpoint_error(
                    "Choose a plan before browsing the benefit schedule.",
                    "local_validation",
                )
            else:
                st.session_state.benefit_lookup_payload = _build_benefit_catalog_payload(selected_plan)
        else:
            plan_name = _submitted_plan_name(st.session_state.benefit_plan_selection, candidates)
            request_payload = {
                "benefit_keyword": keyword,
                "insurer": _insurer_value_from_label(st.session_state.benefit_insurer),
                "tier": st.session_state.benefit_tier or None,
                "plan_name": plan_name,
            }
            with st.spinner("Searching benefit rows..."):
                payload, error = _request_json("POST", "/benefit/search", request_payload)
            st.session_state.benefit_lookup_payload = (
                payload if payload is not None else _normalize_endpoint_error(error or "Unknown error", "transport_error")
            )
        st.session_state.benefit_submitted_filters = current_snapshot
        st.rerun()

    if not backend_available:
        _render_guidance_card("transport_error", "The backend is offline, so benefit searches are temporarily unavailable.", {})
    elif not candidates:
        pass
    elif len(candidates) > 1 and st.session_state.benefit_plan_selection in {"__choose__", "__none__"}:
        _render_empty_state(
            "Choose a specific plan",
            "These filters still match multiple schedules. Pick one plan above so the benefit result cites the right source rows.",
        )
    elif not keyword:
        _render_empty_state(
            "Browse or search benefits",
            "Leave the keyword blank to browse the full schedule for the selected plan, or add a keyword such as ICU, psychiatric, or ward to jump straight to a specific benefit.",
        )

    if st.session_state.get("benefit_lookup_payload"):
        st.markdown("### Benefit Search")
        _render_benefit_payload(st.session_state.benefit_lookup_payload)


def main() -> None:
    _initialize_session_state()
    health_status = _fetch_health_status()
    local_stats = _local_master_stats()
    backend_available = _render_header(health_status, local_stats)
    _render_sidebar(backend_available)

    tabs = st.tabs(["Chat", "Premium Explorer", "Benefit Explorer"])
    with tabs[0]:
        _render_chat_tab(backend_available)
    with tabs[1]:
        _render_premium_tab(backend_available)
    with tabs[2]:
        _render_benefit_tab(backend_available)


main()
