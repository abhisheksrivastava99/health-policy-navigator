from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from pypdf import PdfReader

from clean_ip_tables import (
    CLEANED_CSV_DIR,
    CORE_COLUMNS,
    OUTPUT_ROOT,
    PDF_DIR,
    PDF_SOURCES,
    TRACEABILITY_COLUMNS,
    condensed_text,
    first_token,
    normalize_text,
    parse_csv_identity,
)


REPORT_CSV = OUTPUT_ROOT / "cleaned_verification_report.csv"
REPORT_JSON = OUTPUT_ROOT / "cleaned_verification_report.json"


@dataclass
class CleanedVerification:
    slug: str
    csv_file: str
    page_number: int
    table_number: int
    row_count: int
    plan_column_count: int
    repaired_row_count: int
    benefit_match_rate: float
    value_match_rate: float
    note_match_rate: float
    structural_issue_count: int
    status: str
    issue_samples: List[str]


def load_pdf_pages(pdf_path: Path) -> Dict[int, str]:
    reader = PdfReader(str(pdf_path))
    return {index + 1: normalize_text(page.extract_text() or "") for index, page in enumerate(reader.pages)}


def get_plan_columns(dataframe: pd.DataFrame) -> List[str]:
    excluded = set(CORE_COLUMNS + TRACEABILITY_COLUMNS)
    return [column for column in dataframe.columns.tolist() if column not in excluded]


def page_contains(page_text: str, value: object) -> bool:
    normalized = normalize_text(value).lower()
    if not normalized:
        return True
    if normalized in page_text.lower():
        return True
    condensed_page = condensed_text(page_text)
    condensed_value = condensed_text(value)
    return bool(condensed_value) and condensed_value in condensed_page


def collect_structural_issues(dataframe: pd.DataFrame, plan_columns: List[str]) -> List[str]:
    issues: List[str] = []
    required_columns = CORE_COLUMNS + TRACEABILITY_COLUMNS

    for column in required_columns:
        if column not in dataframe.columns:
            issues.append(f"missing_required_column:{column}")

    if not plan_columns:
        issues.append("missing_plan_columns")

    previous_row = None
    for row_number, (_, row) in enumerate(dataframe.iterrows(), start=1):
        benefit = normalize_text(row.get("benefit", ""))
        notes = normalize_text(row.get("notes", ""))
        section = normalize_text(row.get("section", ""))
        repair_flags = normalize_text(row.get("repair_flags", ""))

        if not benefit:
            issues.append(f"row_{row_number}:empty_benefit")

        nonempty_plan_columns = [column for column in plan_columns if normalize_text(row.get(column, ""))]
        if not nonempty_plan_columns and not notes:
            issues.append(f"row_{row_number}:no_plan_values")

        if previous_row is not None and section == previous_row["section"]:
            previous_nonempty = [column for column in plan_columns if normalize_text(previous_row.get(column, ""))]
            current_nonempty = nonempty_plan_columns
            if previous_nonempty and current_nonempty and len(current_nonempty) < len(previous_nonempty):
                suspicious = [
                    column
                    for column in previous_nonempty
                    if not normalize_text(row.get(column, "")) and normalize_text(previous_row.get(column, ""))
                ]
                if (
                    first_token(row.get("benefit", "")) == first_token(previous_row.get("benefit", ""))
                    and first_token(row.get("benefit", ""))
                    and
                    len(suspicious) >= 2
                    and "forward_fill_from_previous" not in repair_flags
                    and "override_fill_from_previous" not in repair_flags
                ):
                    issues.append(f"row_{row_number}:suspicious_blanks:{','.join(suspicious[:3])}")

        previous_row = row.to_dict()

    return issues


def score_table(dataframe: pd.DataFrame, plan_columns: List[str], page_text: str) -> Tuple[float, float, float]:
    benefit_total = 0
    benefit_matches = 0
    note_total = 0
    note_matches = 0
    value_total = 0
    value_matches = 0

    for _, row in dataframe.iterrows():
        benefit = row.get("benefit", "")
        benefit_total += 1
        if page_contains(page_text, benefit):
            benefit_matches += 1

        notes = row.get("notes", "")
        if normalize_text(notes):
            note_total += 1
            if page_contains(page_text, notes):
                note_matches += 1

        for column in plan_columns:
            value = row.get(column, "")
            if normalize_text(value):
                value_total += 1
                if page_contains(page_text, value):
                    value_matches += 1

    benefit_rate = benefit_matches / benefit_total if benefit_total else 1.0
    note_rate = note_matches / note_total if note_total else 1.0
    value_rate = value_matches / value_total if value_total else 1.0
    return benefit_rate, value_rate, note_rate


def determine_status(benefit_rate: float, value_rate: float, note_rate: float, issues: List[str]) -> str:
    if benefit_rate < 0.95 or value_rate < 0.9:
        return "fail"
    if issues or note_rate < 0.9:
        return "warn"
    return "pass"


def verify_table(slug: str, csv_path: Path, pdf_pages: Dict[int, str]) -> CleanedVerification:
    dataframe = pd.read_csv(csv_path, dtype=str).fillna("")
    page_number, table_number = parse_csv_identity(csv_path)
    page_text = pdf_pages.get(page_number, "")
    plan_columns = get_plan_columns(dataframe)

    issues = collect_structural_issues(dataframe, plan_columns)
    benefit_rate, value_rate, note_rate = score_table(dataframe, plan_columns, page_text)
    repaired_row_count = int((dataframe["repair_flags"].fillna("") != "").sum()) if "repair_flags" in dataframe else 0
    status = determine_status(benefit_rate, value_rate, note_rate, issues)

    return CleanedVerification(
        slug=slug,
        csv_file=str(csv_path),
        page_number=page_number,
        table_number=table_number,
        row_count=int(len(dataframe)),
        plan_column_count=int(len(plan_columns)),
        repaired_row_count=repaired_row_count,
        benefit_match_rate=round(benefit_rate, 4),
        value_match_rate=round(value_rate, 4),
        note_match_rate=round(note_rate, 4),
        structural_issue_count=len(issues),
        status=status,
        issue_samples=issues[:5],
    )


def main() -> int:
    results: List[CleanedVerification] = []

    for slug, pdf_filename in PDF_SOURCES:
        pdf_pages = load_pdf_pages(PDF_DIR / pdf_filename)
        for csv_path in sorted((CLEANED_CSV_DIR / slug).glob("page_*_table_*.csv")):
            results.append(verify_table(slug, csv_path, pdf_pages))

    results_df = pd.DataFrame(
        [{**asdict(result), "issue_samples": json.dumps(result.issue_samples)} for result in results]
    )
    results_df.to_csv(REPORT_CSV, index=False)
    REPORT_JSON.write_text(
        json.dumps([asdict(result) for result in results], indent=2),
        encoding="utf-8",
    )

    status_counts = results_df["status"].value_counts().to_dict() if not results_df.empty else {}
    print("Cleaned verification summary")
    print(f"Report CSV: {REPORT_CSV}")
    print(f"Report JSON: {REPORT_JSON}")
    print(f"Total tables checked: {len(results)}")
    print(f"Status counts: {status_counts}")
    print()

    for status in ("fail", "warn"):
        subset = [result for result in results if result.status == status]
        if not subset:
            continue
        print(f"{status.upper()} tables:")
        for result in subset:
            print(
                f"- {result.csv_file}: benefit_match_rate={result.benefit_match_rate:.2%}, "
                f"value_match_rate={result.value_match_rate:.2%}, "
                f"note_match_rate={result.note_match_rate:.2%}, "
                f"issue_samples={result.issue_samples}"
            )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
