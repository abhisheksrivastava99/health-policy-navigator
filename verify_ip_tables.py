from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from pypdf import PdfReader


ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT_DIR / "ip_plan_tables"
PDF_DIR = OUTPUT_ROOT / "pdfs"
CSV_DIR = OUTPUT_ROOT / "csv"
REPORT_JSON = OUTPUT_ROOT / "verification_report.json"
REPORT_CSV = OUTPUT_ROOT / "verification_report.csv"

PDF_SOURCES = [
    ("basic", "01_basic.pdf"),
    ("standard_integrated_shield_plans", "02_standard_integrated_shield_plans.pdf"),
    ("class_b1_plans", "03_class_b1_plans.pdf"),
    ("class_a_plans", "04_class_a_plans.pdf"),
    ("private_hospital_plans", "05_private_hospital_plans.pdf"),
]

PAGE_PATTERN = re.compile(r"page_(\d{3})_table_(\d{2})\.csv$")


@dataclass
class TableVerification:
    slug: str
    csv_file: str
    page_number: int
    table_number: int
    rows: int
    columns: int
    total_nonempty_cells: int
    matched_nonempty_cells: int
    cell_match_rate: float
    total_first_column_values: int
    matched_first_column_values: int
    first_column_match_rate: float
    total_header_values: int
    matched_header_values: int
    header_match_rate: float
    status: str
    missing_samples: List[str]


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""

    text = str(value).lower()
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9%$./+\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def condensed_text(value: object) -> str:
    normalized = normalize_text(value)
    return re.sub(r"[^a-z0-9]+", "", normalized)


def load_pdf_pages(pdf_path: Path) -> Dict[int, str]:
    reader = PdfReader(str(pdf_path))
    return {
        index + 1: normalize_text(page.extract_text() or "")
        for index, page in enumerate(reader.pages)
    }


def parse_csv_identity(csv_path: Path) -> Tuple[int, int]:
    match = PAGE_PATTERN.search(csv_path.name)
    if not match:
        raise ValueError(f"Unexpected CSV filename: {csv_path.name}")
    return int(match.group(1)), int(match.group(2))


def iter_nonempty_cells(dataframe: pd.DataFrame) -> Iterable[str]:
    for row in dataframe.itertuples(index=False, name=None):
        for value in row:
            normalized = normalize_text(value)
            if normalized:
                yield normalized


def iter_first_column_values(dataframe: pd.DataFrame) -> Iterable[str]:
    if dataframe.shape[1] == 0:
        return []

    values: List[str] = []
    for value in dataframe.iloc[:, 0].tolist():
        normalized = normalize_text(value)
        if normalized:
            values.append(normalized)
    return values


def iter_header_values(dataframe: pd.DataFrame) -> Iterable[str]:
    values: List[str] = []
    for value in dataframe.columns.tolist():
        normalized = normalize_text(value)
        if normalized and not normalized.startswith("unnamed"):
            values.append(normalized)
    return values


def score_matches(values: Iterable[str], page_text: str) -> Tuple[int, int, List[str]]:
    total = 0
    matched = 0
    missing_samples: List[str] = []
    condensed_page_text = condensed_text(page_text)

    for value in values:
        total += 1
        if value in page_text:
            matched += 1
            continue

        condensed_value = condensed_text(value)
        if condensed_value and condensed_value in condensed_page_text:
            matched += 1
        elif len(missing_samples) < 5:
            missing_samples.append(value[:120])

    return matched, total, missing_samples


def determine_status(
    cell_match_rate: float,
    first_column_match_rate: float,
    header_match_rate: float,
) -> str:
    if cell_match_rate >= 0.92 and first_column_match_rate >= 0.95 and header_match_rate >= 0.8:
        return "pass"
    if cell_match_rate >= 0.75 and first_column_match_rate >= 0.85:
        return "warn"
    return "fail"


def verify_table(slug: str, csv_path: Path, page_text: str) -> TableVerification:
    dataframe = pd.read_csv(csv_path)
    page_number, table_number = parse_csv_identity(csv_path)

    all_values = list(iter_nonempty_cells(dataframe))
    first_column_values = list(iter_first_column_values(dataframe))
    header_values = list(iter_header_values(dataframe))

    matched_cells, total_cells, cell_missing = score_matches(all_values, page_text)
    matched_first, total_first, first_missing = score_matches(first_column_values, page_text)
    matched_headers, total_headers, header_missing = score_matches(header_values, page_text)

    cell_rate = matched_cells / total_cells if total_cells else 1.0
    first_rate = matched_first / total_first if total_first else 1.0
    header_rate = matched_headers / total_headers if total_headers else 1.0
    status = determine_status(cell_rate, first_rate, header_rate)

    missing_samples = []
    for sample in cell_missing + first_missing + header_missing:
        if sample not in missing_samples:
            missing_samples.append(sample)
        if len(missing_samples) == 5:
            break

    return TableVerification(
        slug=slug,
        csv_file=str(csv_path.relative_to(ROOT_DIR)),
        page_number=page_number,
        table_number=table_number,
        rows=int(dataframe.shape[0]),
        columns=int(dataframe.shape[1]),
        total_nonempty_cells=total_cells,
        matched_nonempty_cells=matched_cells,
        cell_match_rate=round(cell_rate, 4),
        total_first_column_values=total_first,
        matched_first_column_values=matched_first,
        first_column_match_rate=round(first_rate, 4),
        total_header_values=total_headers,
        matched_header_values=matched_headers,
        header_match_rate=round(header_rate, 4),
        status=status,
        missing_samples=missing_samples,
    )


def main() -> int:
    results: List[TableVerification] = []

    for slug, pdf_filename in PDF_SOURCES:
        pdf_pages = load_pdf_pages(PDF_DIR / pdf_filename)
        csv_paths = sorted((CSV_DIR / slug).glob("page_*_table_*.csv"))

        for csv_path in csv_paths:
            page_number, _ = parse_csv_identity(csv_path)
            page_text = pdf_pages.get(page_number, "")
            results.append(verify_table(slug, csv_path, page_text))

    results_df = pd.DataFrame(
        [
            {
                **asdict(result),
                "missing_samples": json.dumps(result.missing_samples),
            }
            for result in results
        ]
    )
    results_df.to_csv(REPORT_CSV, index=False)
    REPORT_JSON.write_text(
        json.dumps([asdict(result) for result in results], indent=2),
        encoding="utf-8",
    )

    status_counts = results_df["status"].value_counts().to_dict()
    print("Verification summary")
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
                f"- {result.csv_file}: cell_match_rate={result.cell_match_rate:.2%}, "
                f"first_column_match_rate={result.first_column_match_rate:.2%}, "
                f"header_match_rate={result.header_match_rate:.2%}, "
                f"missing_samples={result.missing_samples}"
            )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
