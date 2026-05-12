from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent
MASTER_DIR = ROOT_DIR / "ip_plan_tables" / "master"

PLAN_CATALOG_PATH = MASTER_DIR / "plan_catalog.csv"
BENEFITS_MASTER_PATH = MASTER_DIR / "benefits_master.csv"
PREMIUMS_MASTER_PATH = MASTER_DIR / "premiums_master.csv"
CPF_LIMITS_MASTER_PATH = MASTER_DIR / "cpf_limits_master.csv"

REQUIRED_COLUMNS = {
    PLAN_CATALOG_PATH: {
        "plan_id",
        "tier_code",
        "tier_slug",
        "tier_label",
        "insurer_name",
        "product_name",
        "display_name",
        "is_baseline",
        "baseline_type",
        "has_benefits",
        "has_premium_data",
    },
    BENEFITS_MASTER_PATH: {
        "plan_id",
        "tier_code",
        "tier_slug",
        "section_raw",
        "benefit_raw",
        "notes_raw",
        "coverage_value_raw",
        "is_blank_value",
        "section_norm",
        "benefit_norm",
        "search_text_norm",
        "source_pdf",
        "source_page",
        "source_table",
        "source_slug",
        "repair_flags",
    },
    PREMIUMS_MASTER_PATH: {
        "plan_id",
        "tier_code",
        "tier_slug",
        "age_band_raw",
        "age_start",
        "age_end",
        "age_open_ended",
        "premium_total_raw",
        "premium_total_min",
        "premium_total_max",
        "premium_excl_mshl_raw",
        "premium_excl_mshl_min",
        "premium_excl_mshl_max",
        "annual_change_raw",
        "annual_change_min_pct",
        "annual_change_max_pct",
        "premium_available",
        "availability_note",
        "source_kind",
        "source_pdf",
        "source_page",
        "source_table",
        "source_slug",
        "repair_flags",
    },
    CPF_LIMITS_MASTER_PATH: {
        "age_start",
        "age_end",
        "max_withdrawal_limit",
    },
}


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\r\n", "\n").replace("\r", "\n").split()).strip()


def normalize_key(value: Any) -> str:
    normalized = clean_text(value).lower()
    normalized = normalized.replace("&", " and ")
    normalized = pd.Series([normalized]).str.replace(r"[^a-z0-9]+", " ", regex=True).iloc[0]
    normalized = " ".join(normalized.split())
    return normalized


def text_tokens(*values: Any) -> Set[str]:
    tokens: Set[str] = set()
    for value in values:
        normalized = normalize_key(value)
        if not normalized:
            continue
        tokens.add(normalized)
        tokens.update(normalized.split())
    return tokens


def clean_scalar(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _coerce_boolean_columns(dataframe: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    for column in columns:
        if column not in dataframe.columns:
            continue
        dataframe[column] = dataframe[column].map(
            lambda value: str(value).strip().lower() in {"true", "1", "yes"}
        )
    return dataframe


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Required master table not found: {path}. "
            "Run normalize_master_tables.py first."
        )

    dataframe = pd.read_csv(path)
    missing = REQUIRED_COLUMNS[path] - set(dataframe.columns)
    if missing:
        raise RuntimeError(
            f"{path.name} is missing required columns: {sorted(missing)}"
        )
    return dataframe


def _records(dataframe: pd.DataFrame) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for record in dataframe.to_dict(orient="records"):
        rows.append({key: clean_scalar(value) for key, value in record.items()})
    return rows


@dataclass(frozen=True)
class MasterDataStore:
    plan_catalog: pd.DataFrame
    benefits_master: pd.DataFrame
    premiums_master: pd.DataFrame
    cpf_limits_master: pd.DataFrame
    plan_rows: List[Dict[str, Any]]
    benefit_rows: List[Dict[str, Any]]
    premium_rows: List[Dict[str, Any]]
    cpf_limit_rows: List[Dict[str, Any]]
    plan_by_id: Dict[str, Dict[str, Any]]
    plans_by_tier: Dict[str, List[Dict[str, Any]]]
    plans_by_token: Dict[str, List[Dict[str, Any]]]
    premiums_by_key: Dict[Tuple[str, str], Dict[str, Any]]
    cpf_limits_sorted: List[Dict[str, Any]]


@lru_cache(maxsize=1)
def get_master_data_store() -> MasterDataStore:
    plan_catalog = _coerce_boolean_columns(
        _load_csv(PLAN_CATALOG_PATH),
        ("is_baseline", "has_benefits", "has_premium_data"),
    )
    benefits_master = _coerce_boolean_columns(
        _load_csv(BENEFITS_MASTER_PATH),
        ("is_blank_value",),
    )
    premiums_master = _coerce_boolean_columns(
        _load_csv(PREMIUMS_MASTER_PATH),
        ("age_open_ended", "premium_available"),
    )
    cpf_limits_master = _load_csv(CPF_LIMITS_MASTER_PATH)

    if plan_catalog["plan_id"].duplicated().any():
        raise RuntimeError("plan_catalog.csv contains duplicate plan_id values")
    if premiums_master.duplicated(subset=["plan_id", "age_band_raw"]).any():
        raise RuntimeError(
            "premiums_master.csv contains duplicate (plan_id, age_band_raw) rows"
        )

    plan_rows = _records(plan_catalog)
    benefit_rows = _records(benefits_master)
    premium_rows = _records(premiums_master)
    cpf_limit_rows = _records(cpf_limits_master)

    plan_by_id = {row["plan_id"]: row for row in plan_rows}

    plans_by_tier: Dict[str, List[Dict[str, Any]]] = {}
    plans_by_token: Dict[str, List[Dict[str, Any]]] = {}
    for row in plan_rows:
        tier_code = clean_text(row.get("tier_code"))
        plans_by_tier.setdefault(tier_code, []).append(row)

        for token in text_tokens(
            row.get("insurer_name"),
            row.get("product_name"),
            row.get("display_name"),
            row.get("tier_code"),
            row.get("tier_slug"),
            row.get("tier_label"),
            row.get("baseline_type"),
        ):
            plans_by_token.setdefault(token, []).append(row)

    premiums_by_key = {
        (clean_text(row["plan_id"]), clean_text(row["age_band_raw"])): row
        for row in premium_rows
    }
    cpf_limits_sorted = sorted(cpf_limit_rows, key=lambda row: int(row["age_start"]))

    return MasterDataStore(
        plan_catalog=plan_catalog,
        benefits_master=benefits_master,
        premiums_master=premiums_master,
        cpf_limits_master=cpf_limits_master,
        plan_rows=plan_rows,
        benefit_rows=benefit_rows,
        premium_rows=premium_rows,
        cpf_limit_rows=cpf_limit_rows,
        plan_by_id=plan_by_id,
        plans_by_tier=plans_by_tier,
        plans_by_token=plans_by_token,
        premiums_by_key=premiums_by_key,
        cpf_limits_sorted=cpf_limits_sorted,
    )


def clear_master_data_store_cache() -> None:
    get_master_data_store.cache_clear()
