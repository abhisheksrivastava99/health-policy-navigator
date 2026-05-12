from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT_DIR / "ip_plan_tables"
RAW_CSV_DIR = OUTPUT_ROOT / "csv"
CLEANED_CSV_DIR = OUTPUT_ROOT / "cleaned_csv"
PDF_DIR = OUTPUT_ROOT / "pdfs"

PDF_SOURCES = [
    ("basic", "01_basic.pdf"),
    ("standard_integrated_shield_plans", "02_standard_integrated_shield_plans.pdf"),
    ("class_b1_plans", "03_class_b1_plans.pdf"),
    ("class_a_plans", "04_class_a_plans.pdf"),
    ("private_hospital_plans", "05_private_hospital_plans.pdf"),
]

PAGE_PATTERN = re.compile(r"page_(\d{3})_table_(\d{2})\.csv$")
TRACEABILITY_COLUMNS = [
    "source_pdf",
    "source_slug",
    "source_page",
    "source_table",
    "repair_flags",
]
CORE_COLUMNS = ["section", "benefit", "notes"]


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""

    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(part.strip() for part in text.splitlines() if part.strip())
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def condensed_text(value: object) -> str:
    normalized = normalize_text(value).lower()
    return re.sub(r"[^a-z0-9]+", "", normalized)


def parse_csv_identity(csv_path: Path) -> Tuple[int, int]:
    match = PAGE_PATTERN.search(csv_path.name)
    if not match:
        raise ValueError(f"Unexpected CSV filename: {csv_path.name}")
    return int(match.group(1)), int(match.group(2))


def ensure_output_dir() -> None:
    if CLEANED_CSV_DIR.exists():
        shutil.rmtree(CLEANED_CSV_DIR)
    CLEANED_CSV_DIR.mkdir(parents=True, exist_ok=True)


def unique_headers(headers: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    result: List[str] = []
    for index, header in enumerate(headers, start=1):
        base = normalize_text(header) or f"column_{index}"
        count = seen.get(base, 0)
        if count:
            result.append(f"{base} ({count + 1})")
        else:
            result.append(base)
        seen[base] = count + 1
    return result


def promote_header_row(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    columns = [normalize_text(column) for column in dataframe.columns.tolist()]
    unnamed_columns = sum(1 for column in columns if not column or column.lower().startswith("unnamed:"))
    first_row = [normalize_text(value) for value in dataframe.iloc[0].tolist()]
    nonempty_first_row = sum(1 for value in first_row if value)

    if unnamed_columns >= max(1, len(columns) // 2) and nonempty_first_row >= max(2, len(columns) - 1):
        dataframe = dataframe.iloc[1:].reset_index(drop=True).copy()
        dataframe.columns = unique_headers(first_row)
    else:
        dataframe = dataframe.copy()
        dataframe.columns = unique_headers(columns)

    return dataframe


def normalize_embedded_header_rows(slug: str, page_number: int, table_number: int, dataframe: pd.DataFrame) -> pd.DataFrame:
    if len(dataframe) < 2:
        return dataframe

    first_row = [normalize_text(value) for value in dataframe.iloc[0].tolist()]
    second_row = [normalize_text(value) for value in dataframe.iloc[1].tolist()]
    plan_columns = dataframe.columns.tolist()[1:]

    if not first_row[0] and second_row[0]:
        first_row_plan_values = first_row[1:]
        second_row_plan_values = second_row[1:]
        nonempty_first_row_plan_values = [value for value in first_row_plan_values if value]
        nonempty_second_row_plan_values = [value for value in second_row_plan_values if value]

        if nonempty_second_row_plan_values and len(nonempty_second_row_plan_values) == len(plan_columns):
            if nonempty_first_row_plan_values and len(plan_columns) % len(nonempty_first_row_plan_values) == 0:
                chunk_size = len(plan_columns) // len(nonempty_first_row_plan_values)
                composed_headers = []
                for index, metric_name in enumerate(second_row_plan_values):
                    group_name = nonempty_first_row_plan_values[min(index // chunk_size, len(nonempty_first_row_plan_values) - 1)]
                    composed_headers.append(f"{group_name} - {metric_name}" if metric_name else group_name)
                dataframe = dataframe.iloc[2:].reset_index(drop=True).copy()
                dataframe.columns = unique_headers([second_row[0]] + composed_headers)
                return dataframe

        if second_row[0].endswith(":") and not any(second_row_plan_values):
            fallback_headers = {
                ("basic", 5, 1): ["Age Next Birthday:", "MediShield Life"],
            }
            headers = [second_row[0]]
            for index, (column_name, embedded_value) in enumerate(zip(plan_columns, first_row_plan_values), start=1):
                if embedded_value:
                    headers.append(embedded_value)
                else:
                    fallback = fallback_headers.get((slug, page_number, table_number), [])
                    if index < len(fallback):
                        headers.append(fallback[index])
                    else:
                        cleaned_column_name = normalize_text(column_name)
                        headers.append(cleaned_column_name if not cleaned_column_name.lower().startswith("unnamed:") else f"column_{index + 1}")
            dataframe = dataframe.iloc[2:].reset_index(drop=True).copy()
            dataframe.columns = unique_headers(headers)
            return dataframe

    return dataframe


def is_empty(value: object) -> bool:
    return normalize_text(value) == ""


def is_section_row(label: str, other_values: List[str]) -> bool:
    return bool(label) and all(not value for value in other_values)


def is_note_row(label: str, other_values: List[str]) -> bool:
    nonempty = [value for value in other_values if value]
    if label:
        return False
    if not nonempty:
        return False
    if len(nonempty) == 1 and (nonempty[0].startswith(("*", "^")) or len(nonempty[0]) > 20):
        return True
    return all(value.startswith(("*", "^")) for value in nonempty)


def combine_section(current_section: str, section_label: str) -> str:
    section_label = normalize_text(section_label)
    if not current_section:
        return section_label
    if section_label in current_section:
        return current_section
    return f"{current_section} | {section_label}"


def is_data_benefit(benefit: str) -> bool:
    benefit = normalize_text(benefit)
    if not benefit:
        return False
    if benefit.endswith(":"):
        return False
    return True


def first_token(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"^\-\s*", "", text)
    parts = text.split()
    return parts[0].lower() if parts else ""


def shared_value_marker(value: str) -> bool:
    lowered = normalize_text(value).lower()
    markers = [
        "as charged",
        "up to",
        "including",
        "covered under",
        "note",
        "private hospitals",
        "public hospitals",
        "days",
        "year",
        "yr",
    ]
    return any(marker in lowered for marker in markers)


def format_repair_flags(repair_flags: List[str]) -> str:
    unique = []
    for flag in repair_flags:
        if flag not in unique:
            unique.append(flag)
    return "|".join(unique)


def apply_specific_overrides(slug: str, page_number: int, table_number: int, rows: List[dict], plan_columns: List[str]) -> None:
    key = (slug, page_number, table_number)
    if key == ("basic", 1, 1):
        benefit_to_index = {row["benefit"]: index for index, row in enumerate(rows)}
        first_key = "- Community Hospital (Rehabilitative)"
        second_key = "- Community Hospital (Sub-acute)"
        if first_key in benefit_to_index and second_key in benefit_to_index:
            first_row = rows[benefit_to_index[first_key]]
            second_row = rows[benefit_to_index[second_key]]
            for column in plan_columns[1:]:
                if not normalize_text(second_row.get(column, "")) and normalize_text(first_row.get(column, "")):
                    second_row[column] = first_row[column]
                    second_row["_repair_flags"].append(f"override_fill_from_previous:{column}")


def apply_generic_span_repairs(rows: List[dict], plan_columns: List[str]) -> None:
    for index in range(1, len(rows)):
        previous_row = rows[index - 1]
        current_row = rows[index]

        if previous_row["section"] != current_row["section"]:
            continue
        if not is_data_benefit(previous_row["benefit"]) or not is_data_benefit(current_row["benefit"]):
            continue

        previous_nonempty = [column for column in plan_columns if normalize_text(previous_row.get(column, ""))]
        current_nonempty = [column for column in plan_columns if normalize_text(current_row.get(column, ""))]
        fill_candidates = [
            column for column in plan_columns
            if not normalize_text(current_row.get(column, "")) and normalize_text(previous_row.get(column, ""))
        ]

        if not previous_nonempty or not current_nonempty or not fill_candidates:
            continue
        if len(current_nonempty) >= len(previous_nonempty):
            continue

        shared_prefix = first_token(previous_row["benefit"]) == first_token(current_row["benefit"])
        marker_candidate = any(shared_value_marker(previous_row[column]) for column in fill_candidates)
        if not shared_prefix and not marker_candidate:
            continue

        for column in fill_candidates:
            current_row[column] = previous_row[column]
            current_row["_repair_flags"].append(f"forward_fill_from_previous:{column}")


def build_clean_rows(
    slug: str,
    source_pdf: str,
    page_number: int,
    table_number: int,
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    dataframe = dataframe.fillna("")
    headers = dataframe.columns.tolist()
    plan_columns = headers[1:]
    current_section = ""
    rows: List[dict] = []

    for _, raw_row in dataframe.iterrows():
        label = normalize_text(raw_row.iloc[0])
        other_values = [normalize_text(value) for value in raw_row.iloc[1:].tolist()]

        if not label and not any(other_values):
            continue

        if is_section_row(label, other_values):
            current_section = combine_section(current_section, label)
            continue

        if is_note_row(label, other_values):
            note_text = " ".join(value for value in other_values if value)
            if rows:
                existing = rows[-1]["notes"]
                rows[-1]["notes"] = f"{existing} {note_text}".strip() if existing else note_text
                rows[-1]["_repair_flags"].append("attached_note_row")
            continue

        record = {
            "section": current_section,
            "benefit": label,
            "notes": "",
            "source_pdf": source_pdf,
            "source_slug": slug,
            "source_page": page_number,
            "source_table": table_number,
            "_repair_flags": [],
        }

        for column_name, value in zip(plan_columns, other_values):
            record[column_name] = value

        rows.append(record)

    apply_specific_overrides(slug, page_number, table_number, rows, plan_columns)
    apply_generic_span_repairs(rows, plan_columns)

    cleaned_rows = []
    for row in rows:
        output_row = {
            "section": row["section"],
            "benefit": row["benefit"],
            "notes": row["notes"],
        }
        for column in plan_columns:
            output_row[column] = row.get(column, "")
        output_row["source_pdf"] = row["source_pdf"]
        output_row["source_slug"] = row["source_slug"]
        output_row["source_page"] = row["source_page"]
        output_row["source_table"] = row["source_table"]
        output_row["repair_flags"] = format_repair_flags(row["_repair_flags"])
        cleaned_rows.append(output_row)

    ordered_columns = CORE_COLUMNS + plan_columns + TRACEABILITY_COLUMNS
    return pd.DataFrame(cleaned_rows, columns=ordered_columns)


def clean_table(slug: str, source_pdf: str, csv_path: Path) -> pd.DataFrame:
    dataframe = pd.read_csv(csv_path, dtype=str)
    dataframe = promote_header_row(dataframe)
    page_number, table_number = parse_csv_identity(csv_path)
    dataframe = normalize_embedded_header_rows(slug, page_number, table_number, dataframe)
    return build_clean_rows(slug, source_pdf, page_number, table_number, dataframe)


def main() -> int:
    ensure_output_dir()
    summary = []

    source_pdf_by_slug = {slug: filename for slug, filename in PDF_SOURCES}
    for slug, _ in PDF_SOURCES:
        raw_slug_dir = RAW_CSV_DIR / slug
        cleaned_slug_dir = CLEANED_CSV_DIR / slug
        cleaned_slug_dir.mkdir(parents=True, exist_ok=True)

        cleaned_count = 0
        for csv_path in sorted(raw_slug_dir.glob("page_*_table_*.csv")):
            cleaned = clean_table(slug, source_pdf_by_slug[slug], csv_path)
            cleaned.to_csv(cleaned_slug_dir / csv_path.name, index=False)
            cleaned_count += 1

        summary.append((slug, cleaned_count, cleaned_slug_dir))

    print("Cleaning summary")
    print(f"Raw CSV input: {RAW_CSV_DIR}")
    print(f"Cleaned CSV output: {CLEANED_CSV_DIR}")
    print()
    for slug, cleaned_count, cleaned_slug_dir in summary:
        print(f"{slug}: cleaned_tables={cleaned_count} | cleaned_dir={cleaned_slug_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
