from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from clean_ip_tables import (
    CLEANED_CSV_DIR,
    CORE_COLUMNS,
    OUTPUT_ROOT,
    TRACEABILITY_COLUMNS,
    normalize_text,
    parse_csv_identity,
)


MASTER_DIR = OUTPUT_ROOT / "master"
PLAN_CATALOG_PATH = MASTER_DIR / "plan_catalog.csv"
BENEFITS_MASTER_PATH = MASTER_DIR / "benefits_master.csv"
PREMIUMS_MASTER_PATH = MASTER_DIR / "premiums_master.csv"
CPF_MASTER_PATH = MASTER_DIR / "cpf_limits_master.csv"
CPF_SOURCE_PATH = OUTPUT_ROOT / "cpf_limits.csv"

TIER_CONFIG = {
    "basic": {
        "tier_code": "basic",
        "tier_label": "Basic Plans",
        "summary_file": "page_005_table_01.csv",
    },
    "standard_integrated_shield_plans": {
        "tier_code": "standard",
        "tier_label": "Standard Integrated Shield Plans",
        "summary_file": "page_003_table_01.csv",
    },
    "class_b1_plans": {
        "tier_code": "class_b1",
        "tier_label": "Class B1 Plans",
        "summary_file": "page_006_table_01.csv",
    },
    "class_a_plans": {
        "tier_code": "class_a",
        "tier_label": "Class A Plans",
        "summary_file": "page_006_table_01.csv",
    },
    "private_hospital_plans": {
        "tier_code": "private",
        "tier_label": "Private Hospital Plans",
        "summary_file": "page_007_table_01.csv",
    },
}

AGE_BANDS = [
    "1 to 20",
    "21 to 30",
    "31 to 40",
    "41 to 50",
    "51 to 60",
    "61 to 65",
    "66 to 70",
    "71 to 73",
    "74 to 75",
    "76 to 78",
    "79 to 80",
    "81 to 83",
    "84 to 85",
    "86 to 90",
    "Premiums above age 90",
]

PREMIUM_DETAIL_CHUNKS = {
    "standard_integrated_shield_plans/page_004_table_01.csv": [
        "[Income] IncomeShield Standard Plan",
        "[AIA] HealthShield Gold Max Standard Plan",
    ],
    "standard_integrated_shield_plans/page_004_table_02.csv": [
        "[Great Eastern] GREAT SupremeHealth STANDARD",
        "[Prudential] PRUShield Standard Plan",
    ],
    "standard_integrated_shield_plans/page_005_table_01.csv": [
        "[Singlife] Singlife Shield Standard Plan",
        "[HSBC Life] HSBC Life Shield Standard Plan",
    ],
    "standard_integrated_shield_plans/page_005_table_02.csv": [
        "[Raffles Health Insurance] Raffles Shield Standard Plan",
    ],
    "class_a_plans/page_007_table_01.csv": [
        "[Income] IncomeShield Plan A*",
        "[Income] Enhanced IncomeShield Advantage",
    ],
    "class_a_plans/page_007_table_02.csv": [
        "[AIA] HealthShield Gold Max B",
        "[Great Eastern] GREAT SupremeHealth A PLUS",
    ],
    "class_a_plans/page_008_table_01.csv": [
        "[Prudential] PRUShield A*",
        "[Prudential] PRUShield Plus",
    ],
    "class_a_plans/page_008_table_02.csv": [
        "[Singlife] Singlife Shield Plan 2",
        "[HSBC Life] HSBC Life Shield Plan B",
        "[Raffles Health Insurance] Raffles Shield A",
    ],
    "class_b1_plans/page_007_table_01.csv": [
        "[Income] IncomeShield Plan B*",
        "[Income] Enhanced IncomeShield Basic",
    ],
    "class_b1_plans/page_007_table_02.csv": [
        "[AIA] HealthShield Gold Max C*",
        "[AIA] HealthShield Gold Max B Lite",
    ],
    "class_b1_plans/page_008_table_01.csv": [
        "[Great Eastern] GREAT SupremeHealth B*",
        "[Great Eastern] GREAT SupremeHealth B PLUS",
    ],
    "class_b1_plans/page_008_table_02.csv": [
        "[Prudential] PRUShield B*",
        "[Singlife] Singlife Shield Plan 3",
        "[Raffles Health Insurance] Raffles Shield B",
    ],
    "private_hospital_plans/page_008_table_01.csv": [
        "[Income] IncomeShield Plan P*",
        "[Income] Enhanced IncomeShield Preferred",
    ],
    "private_hospital_plans/page_008_table_02.csv": [
        "[AIA] HealthShield Gold Max A",
        "[Great Eastern] GREAT SupremeHealth A*",
        "[Great Eastern] GREAT SupremeHealth P PLUS",
    ],
    "private_hospital_plans/page_009_table_01.csv": [
        "[Prudential] PRUShield Premier",
        "[Singlife] Singlife Shield Plan 1",
        "[Singlife] Singlife Shield Starter",
    ],
    "private_hospital_plans/page_009_table_02.csv": [
        "[HSBC Life] HSBC Life Shield Plan A",
        "[Raffles Health Insurance] Raffles Shield Private",
    ],
}

CORE_AND_TRACEABILITY = set(CORE_COLUMNS + TRACEABILITY_COLUMNS)
VALIDATION_TIERS = {
    "standard_integrated_shield_plans",
    "class_a_plans",
    "class_b1_plans",
}

EXPECTED_PLAN_COUNT = 39
EXPECTED_BENEFIT_ROWS = 1736
EXPECTED_PREMIUM_ROWS = 570
EXPECTED_CPF_ROWS = 3


def ensure_master_dir() -> None:
    if MASTER_DIR.exists():
        shutil.rmtree(MASTER_DIR)
    MASTER_DIR.mkdir(parents=True, exist_ok=True)


def data_columns(dataframe: pd.DataFrame) -> List[str]:
    return [column for column in dataframe.columns.tolist() if column not in CORE_AND_TRACEABILITY]


def sort_csv_paths(paths: Sequence[Path]) -> List[Path]:
    return sorted(paths, key=parse_csv_identity)


def is_metric_column(column: str) -> bool:
    return "IP Premium" in column or "Annual change in IP premium" in column


def metric_kind(column: str) -> str:
    normalized = normalize_text(column)
    if "Annual change in IP premium" in normalized:
        return "annual_change"
    if "IP Premium (excl. MSHL)" in normalized:
        return "premium_excl_mshl"
    if "IP Premium (incl. MSHL)" in normalized:
        return "premium_total"
    raise ValueError(f"Unrecognized premium metric column: {column}")


def metric_plan_label(column: str) -> Optional[str]:
    normalized = normalize_text(column)
    for marker in (" - IP Premium", " - Annual change in IP premium"):
        if marker in normalized:
            return normalized.split(marker, 1)[0]
    return None


def is_age_band_table(dataframe: pd.DataFrame) -> bool:
    values = [normalize_text(value) for value in dataframe["benefit"].fillna("").tolist()]
    return values == AGE_BANDS


def classify_table(dataframe: pd.DataFrame) -> str:
    columns = data_columns(dataframe)
    if is_age_band_table(dataframe):
        if any(is_metric_column(column) for column in columns):
            return "premium_detail"
        return "premium_summary"
    return "benefit_table"


def normalize_lookup_text(value: object) -> str:
    lowered = normalize_text(value).lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def slugify(text: str) -> str:
    return normalize_lookup_text(text).replace(" ", "_")


def plan_parts(label: str) -> Tuple[str, str, bool, str]:
    normalized = normalize_text(label)
    if normalized == "MediShield Life":
        return "", normalized, True, "medishield_life"
    if normalized == "Standard IP":
        return "", normalized, True, "standard_ip"

    match = re.match(r"^\[(?P<insurer>[^\]]+)\]\s*(?P<product>.+)$", normalized)
    if not match:
        raise ValueError(f"Unable to parse plan label: {label}")
    return match.group("insurer"), match.group("product"), False, ""


def plan_id_for_label(tier_code: str, label: str) -> str:
    normalized = normalize_text(label)
    if normalized == "MediShield Life":
        return "basic__medishield_life"
    if normalized == "Standard IP":
        return "standard__standard_ip"

    insurer_name, product_name, _, _ = plan_parts(normalized)
    return f"{tier_code}__{slugify(insurer_name)}__{slugify(product_name)}"


def parse_age_band(age_band_raw: str) -> Tuple[int, Optional[int], bool]:
    normalized = normalize_text(age_band_raw)
    match = re.fullmatch(r"(\d+)\s+to\s+(\d+)", normalized)
    if match:
        return int(match.group(1)), int(match.group(2)), False
    if normalized == "Premiums above age 90":
        return 91, None, True
    raise ValueError(f"Unsupported age band: {age_band_raw}")


def parse_money_range(value: str) -> Tuple[Optional[int], Optional[int]]:
    normalized = normalize_text(value)
    if not normalized:
        return None, None

    range_match = re.fullmatch(r"(\d[\d,]*)\s*-\s*(\d[\d,]*)", normalized)
    if range_match:
        return (
            int(range_match.group(1).replace(",", "")),
            int(range_match.group(2).replace(",", "")),
        )

    scalar_match = re.fullmatch(r"\d[\d,]*", normalized)
    if scalar_match:
        amount = int(normalized.replace(",", ""))
        return amount, amount

    return None, None


def parse_percent_range(value: str) -> Tuple[Optional[float], Optional[float]]:
    normalized = normalize_text(value)
    if not normalized:
        return None, None

    range_match = re.fullmatch(r"(-?\d+(?:\.\d+)?)%\s+to\s+(-?\d+(?:\.\d+)?)%", normalized)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    scalar_match = re.fullmatch(r"(-?\d+(?:\.\d+)?)%", normalized)
    if scalar_match:
        percent = float(scalar_match.group(1))
        return percent, percent

    return None, None


def availability_note_from_values(*values: str) -> str:
    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        if parse_money_range(normalized) != (None, None):
            continue
        if parse_percent_range(normalized) != (None, None):
            continue
        return normalized
    return ""


def canonical_money_range(value: str) -> Optional[Tuple[int, int]]:
    lower, upper = parse_money_range(value)
    if lower is None or upper is None:
        return None
    return lower, upper


def load_cleaned_tables() -> Dict[str, Dict[str, List[Tuple[Path, pd.DataFrame]]]]:
    grouped: Dict[str, Dict[str, List[Tuple[Path, pd.DataFrame]]]] = {}
    for tier_slug in TIER_CONFIG:
        tier_dir = CLEANED_CSV_DIR / tier_slug
        categorized = {
            "benefit_table": [],
            "premium_summary": [],
            "premium_detail": [],
        }
        for csv_path in sort_csv_paths(list(tier_dir.glob("page_*_table_*.csv"))):
            dataframe = pd.read_csv(csv_path, dtype=str).fillna("")
            categorized[classify_table(dataframe)].append((csv_path, dataframe))
        grouped[tier_slug] = categorized
    return grouped


def summary_plan_order(summary_df: pd.DataFrame) -> List[str]:
    return data_columns(summary_df)


def build_plan_lookup(
    tables_by_tier: Dict[str, Dict[str, List[Tuple[Path, pd.DataFrame]]]]
) -> Tuple[List[dict], Dict[Tuple[str, str], str], Dict[str, List[str]]]:
    catalog_rows: List[dict] = []
    plan_id_lookup: Dict[Tuple[str, str], str] = {}
    ordered_labels_by_tier: Dict[str, List[str]] = {}
    seen_plan_ids: set[str] = set()

    for tier_slug, tier_config in TIER_CONFIG.items():
        summary_entries = tables_by_tier[tier_slug]["premium_summary"]
        if len(summary_entries) != 1:
            raise ValueError(f"Expected exactly one premium summary table for {tier_slug}")

        summary_path, summary_df = summary_entries[0]
        if summary_path.name != tier_config["summary_file"]:
            raise ValueError(
                f"Unexpected premium summary file for {tier_slug}: {summary_path.name}"
            )

        summary_labels = summary_plan_order(summary_df)
        benefit_labels: List[str] = []
        for _, benefit_df in tables_by_tier[tier_slug]["benefit_table"]:
            for label in data_columns(benefit_df):
                if label not in benefit_labels:
                    benefit_labels.append(label)

        ordered_labels = [label for label in benefit_labels if label not in summary_labels] + summary_labels
        ordered_labels_by_tier[tier_slug] = ordered_labels

        for label in ordered_labels:
            tier_code = tier_config["tier_code"]
            plan_id = plan_id_for_label(tier_code, label)
            if plan_id in seen_plan_ids:
                raise ValueError(f"Duplicate plan_id generated: {plan_id}")

            insurer_name, product_name, is_baseline, baseline_type = plan_parts(label)
            catalog_rows.append(
                {
                    "plan_id": plan_id,
                    "tier_code": tier_code,
                    "tier_slug": tier_slug,
                    "tier_label": tier_config["tier_label"],
                    "insurer_name": insurer_name,
                    "product_name": product_name,
                    "display_name": normalize_text(label),
                    "is_baseline": is_baseline,
                    "baseline_type": baseline_type,
                    "has_benefits": False,
                    "has_premium_data": False,
                }
            )
            plan_id_lookup[(tier_slug, label)] = plan_id
            seen_plan_ids.add(plan_id)

    return catalog_rows, plan_id_lookup, ordered_labels_by_tier


def validate_premium_chunk_mappings(
    tables_by_tier: Dict[str, Dict[str, List[Tuple[Path, pd.DataFrame]]]],
    summary_orders: Dict[str, List[str]],
) -> None:
    actual_keys = {
        f"{tier_slug}/{path.name}"
        for tier_slug, grouped in tables_by_tier.items()
        for path, _ in grouped["premium_detail"]
    }
    expected_keys = set(PREMIUM_DETAIL_CHUNKS)
    if actual_keys != expected_keys:
        missing = sorted(actual_keys - expected_keys)
        extra = sorted(expected_keys - actual_keys)
        raise ValueError(
            f"Premium detail mapping mismatch. missing={missing} extra={extra}"
        )

    for tier_slug, grouped in tables_by_tier.items():
        detail_entries = grouped["premium_detail"]
        if not detail_entries:
            continue

        concatenated_labels: List[str] = []
        for path, dataframe in detail_entries:
            file_key = f"{tier_slug}/{path.name}"
            expected_labels = PREMIUM_DETAIL_CHUNKS[file_key]
            metric_columns = [column for column in data_columns(dataframe) if is_metric_column(column)]
            if len(metric_columns) != len(expected_labels) * 3:
                raise ValueError(
                    f"Unexpected metric column count for {file_key}: {len(metric_columns)}"
                )

            explicit_labels: List[str] = []
            for index, expected_label in enumerate(expected_labels):
                group = metric_columns[index * 3 : (index + 1) * 3]
                kinds = [metric_kind(column) for column in group]
                if kinds != ["premium_total", "premium_excl_mshl", "annual_change"]:
                    raise ValueError(f"Unexpected metric order for {file_key}: {group}")

                parsed_label = metric_plan_label(group[0])
                if parsed_label is not None:
                    explicit_labels.append(parsed_label)
                    if parsed_label != expected_label:
                        raise ValueError(
                            f"Explicit premium label mismatch in {file_key}: "
                            f"{parsed_label} != {expected_label}"
                        )

            if explicit_labels and explicit_labels != expected_labels:
                raise ValueError(
                    f"Explicit premium chunk order mismatch in {file_key}: {explicit_labels}"
                )

            concatenated_labels.extend(expected_labels)

        if concatenated_labels != summary_orders[tier_slug]:
            raise ValueError(
                f"Summary order does not match premium detail chunks for {tier_slug}: "
                f"{concatenated_labels} != {summary_orders[tier_slug]}"
            )


def build_benefits_master(
    tables_by_tier: Dict[str, Dict[str, List[Tuple[Path, pd.DataFrame]]]],
    plan_id_lookup: Dict[Tuple[str, str], str],
) -> pd.DataFrame:
    rows: List[dict] = []
    for tier_slug, grouped in tables_by_tier.items():
        tier_code = TIER_CONFIG[tier_slug]["tier_code"]
        for _, dataframe in grouped["benefit_table"]:
            plan_columns = data_columns(dataframe)
            for _, row in dataframe.iterrows():
                section_raw = normalize_text(row.get("section", ""))
                benefit_raw = normalize_text(row.get("benefit", ""))
                notes_raw = normalize_text(row.get("notes", ""))
                source_pdf = normalize_text(row.get("source_pdf", ""))
                source_slug = normalize_text(row.get("source_slug", ""))
                source_page = int(row.get("source_page", 0))
                source_table = int(row.get("source_table", 0))
                repair_flags = normalize_text(row.get("repair_flags", ""))

                for plan_label in plan_columns:
                    coverage_value_raw = normalize_text(row.get(plan_label, ""))
                    search_text_raw = " ".join(
                        part
                        for part in (
                            section_raw,
                            benefit_raw,
                            notes_raw,
                            coverage_value_raw,
                        )
                        if part
                    )
                    rows.append(
                        {
                            "plan_id": plan_id_lookup[(tier_slug, plan_label)],
                            "tier_code": tier_code,
                            "tier_slug": tier_slug,
                            "section_raw": section_raw,
                            "benefit_raw": benefit_raw,
                            "notes_raw": notes_raw,
                            "coverage_value_raw": coverage_value_raw,
                            "is_blank_value": coverage_value_raw == "",
                            "section_norm": normalize_lookup_text(section_raw),
                            "benefit_norm": normalize_lookup_text(benefit_raw),
                            "search_text_norm": normalize_lookup_text(search_text_raw),
                            "source_pdf": source_pdf,
                            "source_page": source_page,
                            "source_table": source_table,
                            "source_slug": source_slug,
                            "repair_flags": repair_flags,
                        }
                    )

    columns = [
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
    ]
    return pd.DataFrame(rows, columns=columns)


def premium_record(
    *,
    plan_id: str,
    tier_code: str,
    tier_slug: str,
    age_band_raw: str,
    premium_total_raw: str,
    premium_excl_mshl_raw: str,
    annual_change_raw: str,
    source_kind: str,
    source_pdf: str,
    source_page: int,
    source_table: int,
    source_slug: str,
    repair_flags: str,
) -> dict:
    age_start, age_end, age_open_ended = parse_age_band(age_band_raw)
    premium_total_min, premium_total_max = parse_money_range(premium_total_raw)
    premium_excl_min, premium_excl_max = parse_money_range(premium_excl_mshl_raw)
    annual_change_min, annual_change_max = parse_percent_range(annual_change_raw)

    premium_available = premium_total_min is not None and premium_total_max is not None
    availability_note = ""
    if not premium_available:
        availability_note = availability_note_from_values(
            premium_total_raw,
            premium_excl_mshl_raw,
            annual_change_raw,
        )
        premium_total_min = None
        premium_total_max = None
        premium_excl_min = None
        premium_excl_max = None
        annual_change_min = None
        annual_change_max = None

    return {
        "plan_id": plan_id,
        "tier_code": tier_code,
        "tier_slug": tier_slug,
        "age_band_raw": age_band_raw,
        "age_start": age_start,
        "age_end": age_end,
        "age_open_ended": age_open_ended,
        "premium_total_raw": premium_total_raw,
        "premium_total_min": premium_total_min,
        "premium_total_max": premium_total_max,
        "premium_excl_mshl_raw": premium_excl_mshl_raw,
        "premium_excl_mshl_min": premium_excl_min,
        "premium_excl_mshl_max": premium_excl_max,
        "annual_change_raw": annual_change_raw,
        "annual_change_min_pct": annual_change_min,
        "annual_change_max_pct": annual_change_max,
        "premium_available": premium_available,
        "availability_note": availability_note,
        "source_kind": source_kind,
        "source_pdf": source_pdf,
        "source_page": source_page,
        "source_table": source_table,
        "source_slug": source_slug,
        "repair_flags": repair_flags,
    }


def build_premiums_master(
    tables_by_tier: Dict[str, Dict[str, List[Tuple[Path, pd.DataFrame]]]],
    plan_id_lookup: Dict[Tuple[str, str], str],
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    rows: List[dict] = []
    summary_tables: Dict[str, pd.DataFrame] = {}

    for tier_slug, grouped in tables_by_tier.items():
        tier_code = TIER_CONFIG[tier_slug]["tier_code"]
        summary_entries = grouped["premium_summary"]
        summary_path, summary_df = summary_entries[0]
        summary_tables[tier_slug] = summary_df

        if tier_slug == "basic":
            for _, row in summary_df.iterrows():
                age_band_raw = normalize_text(row.get("benefit", ""))
                source_pdf = normalize_text(row.get("source_pdf", ""))
                source_slug = normalize_text(row.get("source_slug", ""))
                source_page = int(row.get("source_page", 0))
                source_table = int(row.get("source_table", 0))
                repair_flags = normalize_text(row.get("repair_flags", ""))

                for plan_label in summary_plan_order(summary_df):
                    rows.append(
                        premium_record(
                            plan_id=plan_id_lookup[(tier_slug, plan_label)],
                            tier_code=tier_code,
                            tier_slug=tier_slug,
                            age_band_raw=age_band_raw,
                            premium_total_raw=normalize_text(row.get(plan_label, "")),
                            premium_excl_mshl_raw="",
                            annual_change_raw="",
                            source_kind="premium_summary",
                            source_pdf=source_pdf,
                            source_page=source_page,
                            source_table=source_table,
                            source_slug=source_slug,
                            repair_flags=repair_flags,
                        )
                    )
            continue

        for path, dataframe in grouped["premium_detail"]:
            file_key = f"{tier_slug}/{path.name}"
            plan_labels = PREMIUM_DETAIL_CHUNKS[file_key]
            metric_columns = [column for column in data_columns(dataframe) if is_metric_column(column)]
            for _, row in dataframe.iterrows():
                age_band_raw = normalize_text(row.get("benefit", ""))
                source_pdf = normalize_text(row.get("source_pdf", ""))
                source_slug = normalize_text(row.get("source_slug", ""))
                source_page = int(row.get("source_page", 0))
                source_table = int(row.get("source_table", 0))
                repair_flags = normalize_text(row.get("repair_flags", ""))

                for index, plan_label in enumerate(plan_labels):
                    group = metric_columns[index * 3 : (index + 1) * 3]
                    rows.append(
                        premium_record(
                            plan_id=plan_id_lookup[(tier_slug, plan_label)],
                            tier_code=tier_code,
                            tier_slug=tier_slug,
                            age_band_raw=age_band_raw,
                            premium_total_raw=normalize_text(row.get(group[0], "")),
                            premium_excl_mshl_raw=normalize_text(row.get(group[1], "")),
                            annual_change_raw=normalize_text(row.get(group[2], "")),
                            source_kind="premium_detail",
                            source_pdf=source_pdf,
                            source_page=source_page,
                            source_table=source_table,
                            source_slug=source_slug,
                            repair_flags=repair_flags,
                        )
                    )

    columns = [
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
    ]
    return pd.DataFrame(rows, columns=columns), summary_tables


def build_cpf_limits_master() -> pd.DataFrame:
    dataframe = pd.read_csv(CPF_SOURCE_PATH, dtype=str).fillna("")
    rows = []
    for _, row in dataframe.iterrows():
        rows.append(
            {
                "age_start": int(normalize_text(row["Age_Band_Start"])),
                "age_end": int(normalize_text(row["Age_Band_End"])),
                "max_withdrawal_limit": int(normalize_text(row["Max_Withdrawal_Limit"])),
            }
        )
    return pd.DataFrame(rows, columns=["age_start", "age_end", "max_withdrawal_limit"])


def apply_catalog_flags(
    catalog_rows: List[dict],
    benefits_df: pd.DataFrame,
    premiums_df: pd.DataFrame,
) -> pd.DataFrame:
    benefit_plan_ids = set(benefits_df["plan_id"].unique())
    premium_plan_ids = set(premiums_df["plan_id"].unique())
    for row in catalog_rows:
        row["has_benefits"] = row["plan_id"] in benefit_plan_ids
        row["has_premium_data"] = row["plan_id"] in premium_plan_ids
    return pd.DataFrame(
        catalog_rows,
        columns=[
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
        ],
    )


def validate_summary_values(
    premiums_df: pd.DataFrame,
    summary_tables: Dict[str, pd.DataFrame],
    plan_id_lookup: Dict[Tuple[str, str], str],
) -> None:
    premium_lookup = premiums_df.set_index(["plan_id", "age_band_raw"])["premium_total_raw"].to_dict()

    for tier_slug in VALIDATION_TIERS:
        summary_df = summary_tables[tier_slug]
        for _, row in summary_df.iterrows():
            age_band_raw = normalize_text(row.get("benefit", ""))
            for plan_label in summary_plan_order(summary_df):
                summary_value = normalize_text(row.get(plan_label, ""))
                detail_value = normalize_text(
                    premium_lookup[(plan_id_lookup[(tier_slug, plan_label)], age_band_raw)]
                )
                if canonical_money_range(summary_value) != canonical_money_range(detail_value):
                    raise ValueError(
                        f"Premium summary mismatch for {tier_slug} {plan_label} {age_band_raw}: "
                        f"{summary_value} != {detail_value}"
                    )


def validate_outputs(
    catalog_df: pd.DataFrame,
    benefits_df: pd.DataFrame,
    premiums_df: pd.DataFrame,
    cpf_df: pd.DataFrame,
) -> None:
    if len(catalog_df) != EXPECTED_PLAN_COUNT:
        raise ValueError(f"Expected {EXPECTED_PLAN_COUNT} catalog rows, found {len(catalog_df)}")
    if catalog_df["plan_id"].nunique() != EXPECTED_PLAN_COUNT:
        raise ValueError("plan_catalog.csv contains duplicate plan_id values")

    if len(benefits_df) != EXPECTED_BENEFIT_ROWS:
        raise ValueError(f"Expected {EXPECTED_BENEFIT_ROWS} benefit rows, found {len(benefits_df)}")

    if len(premiums_df) != EXPECTED_PREMIUM_ROWS:
        raise ValueError(f"Expected {EXPECTED_PREMIUM_ROWS} premium rows, found {len(premiums_df)}")
    if premiums_df.duplicated(subset=["plan_id", "age_band_raw"]).any():
        duplicates = premiums_df[premiums_df.duplicated(subset=["plan_id", "age_band_raw"], keep=False)]
        raise ValueError(f"Duplicate premium keys found: {duplicates[['plan_id', 'age_band_raw']].to_dict('records')[:5]}")

    if len(cpf_df) != EXPECTED_CPF_ROWS:
        raise ValueError(f"Expected {EXPECTED_CPF_ROWS} CPF rows, found {len(cpf_df)}")

    if "basic__medishield_life" not in set(catalog_df["plan_id"]):
        raise ValueError("Missing basic__medishield_life in plan catalog")
    if "standard__standard_ip" not in set(catalog_df["plan_id"]):
        raise ValueError("Missing standard__standard_ip in plan catalog")
    if "basic__medishield_life" not in set(premiums_df["plan_id"]):
        raise ValueError("Missing basic__medishield_life premiums")
    if "standard__standard_ip" in set(premiums_df["plan_id"]):
        raise ValueError("standard__standard_ip should not have premium rows")
    if "standard__standard_ip" not in set(benefits_df["plan_id"]):
        raise ValueError("Missing standard__standard_ip benefit rows")


def write_outputs(
    catalog_df: pd.DataFrame,
    benefits_df: pd.DataFrame,
    premiums_df: pd.DataFrame,
    cpf_df: pd.DataFrame,
) -> None:
    catalog_df.to_csv(PLAN_CATALOG_PATH, index=False)
    benefits_df.to_csv(BENEFITS_MASTER_PATH, index=False)
    premiums_df.to_csv(PREMIUMS_MASTER_PATH, index=False)
    cpf_df.to_csv(CPF_MASTER_PATH, index=False)


def main() -> int:
    ensure_master_dir()

    tables_by_tier = load_cleaned_tables()
    summary_orders = {
        tier_slug: summary_plan_order(grouped["premium_summary"][0][1])
        for tier_slug, grouped in tables_by_tier.items()
    }
    validate_premium_chunk_mappings(tables_by_tier, summary_orders)

    catalog_rows, plan_id_lookup, _ = build_plan_lookup(tables_by_tier)
    benefits_df = build_benefits_master(tables_by_tier, plan_id_lookup)
    premiums_df, summary_tables = build_premiums_master(tables_by_tier, plan_id_lookup)
    cpf_df = build_cpf_limits_master()

    validate_summary_values(premiums_df, summary_tables, plan_id_lookup)

    catalog_df = apply_catalog_flags(catalog_rows, benefits_df, premiums_df)
    validate_outputs(catalog_df, benefits_df, premiums_df, cpf_df)
    write_outputs(catalog_df, benefits_df, premiums_df, cpf_df)

    print("Master table normalization complete")
    print(f"Plan catalog: {PLAN_CATALOG_PATH} | rows={len(catalog_df)}")
    print(f"Benefits master: {BENEFITS_MASTER_PATH} | rows={len(benefits_df)}")
    print(f"Premiums master: {PREMIUMS_MASTER_PATH} | rows={len(premiums_df)}")
    print(f"CPF limits master: {CPF_MASTER_PATH} | rows={len(cpf_df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
