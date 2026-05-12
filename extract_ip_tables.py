from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import tabula
from pypdf import PdfReader


ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT_DIR / "ip_plan_tables"
PDF_DIR = OUTPUT_ROOT / "pdfs"
CSV_DIR = OUTPUT_ROOT / "csv"

PDF_SOURCES = [
    (
        "basic",
        "01_basic.pdf",
        "https://isomer-user-content.by.gov.sg/3/b894c65e-8bc2-4bbe-99e9-796460727bee/Comparison%20of%20IPs%20(Jan%202025)(Basic).pdf",
    ),
    (
        "standard_integrated_shield_plans",
        "02_standard_integrated_shield_plans.pdf",
        "https://isomer-user-content.by.gov.sg/3/1c4d1d1a-18d5-457d-9e2b-295da535a5c9/Comparison%20of%20IPs%20(Jan%202025)(Std%20IP).pdf",
    ),
    (
        "class_b1_plans",
        "03_class_b1_plans.pdf",
        "https://isomer-user-content.by.gov.sg/3/4909bb61-2d04-46af-9694-1cea017d2b3c/Comparison%20of%20IPs%20(Jan%202025)(Class%20B1%20IP).pdf",
    ),
    (
        "class_a_plans",
        "04_class_a_plans.pdf",
        "https://isomer-user-content.by.gov.sg/3/abba3002-6370-4e6b-b7e5-7ab0e8fa095d/Comparison%20of%20IPs%20(Jan%202025)(Class%20A%20IP).pdf",
    ),
    (
        "private_hospital_plans",
        "05_private_hospital_plans.pdf",
        "https://isomer-user-content.by.gov.sg/3/bbc1316b-67bd-4ec6-8cbc-e1ca88248ef6/Comparison%20of%20IPs%20(Jan%202025)(Private%20hospital%20IP).pdf",
    ),
]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def ensure_output_dirs() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)


def reset_csv_dir(target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)


def download_pdf(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request) as response:
        destination.write_bytes(response.read())


def clean_dataframe(dataframe: pd.DataFrame) -> Optional[pd.DataFrame]:
    cleaned = dataframe.copy()
    cleaned = cleaned.replace(r"^\s*$", pd.NA, regex=True)
    cleaned = cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")

    if cleaned.empty or cleaned.shape[1] == 0:
        return None

    cleaned = cleaned.apply(lambda column: column.map(normalize_text))
    cleaned.columns = [
        normalize_text(column) if column is not None else ""
        for column in cleaned.columns
    ]
    return cleaned.reset_index(drop=True)


def normalize_text(value: object) -> object:
    if pd.isna(value):
        return pd.NA

    if not isinstance(value, str):
        return value

    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = " ".join(part.strip() for part in normalized.splitlines() if part.strip())
    return normalized.strip()


def get_page_count(pdf_path: Path) -> int:
    with pdf_path.open("rb") as handle:
        reader = PdfReader(handle)
        return len(reader.pages)


def extract_tables_for_mode(pdf_path: Path, *, lattice: bool, stream: bool) -> Dict[int, List[pd.DataFrame]]:
    page_count = get_page_count(pdf_path)
    extracted: Dict[int, List[pd.DataFrame]] = {}

    for page_number in range(1, page_count + 1):
        tables = tabula.read_pdf(
            str(pdf_path),
            pages=page_number,
            multiple_tables=True,
            lattice=lattice,
            stream=stream,
            pandas_options={"dtype": str},
            silent=True,
        )

        cleaned_tables: List[pd.DataFrame] = []
        for table in tables:
            cleaned = clean_dataframe(table)
            if cleaned is not None:
                cleaned_tables.append(cleaned)

        if cleaned_tables:
            extracted[page_number] = cleaned_tables

    return extracted


def write_tables(slug: str, tables_by_page: Dict[int, List[pd.DataFrame]]) -> int:
    target_dir = CSV_DIR / slug
    reset_csv_dir(target_dir)

    total_tables = 0
    for page_number in sorted(tables_by_page):
        for table_index, dataframe in enumerate(tables_by_page[page_number], start=1):
            filename = f"page_{page_number:03d}_table_{table_index:02d}.csv"
            dataframe.to_csv(target_dir / filename, index=False)
            total_tables += 1

    return total_tables


def process_pdf(slug: str, pdf_filename: str, url: str) -> Dict[str, object]:
    pdf_path = PDF_DIR / pdf_filename
    download_pdf(url, pdf_path)

    lattice_tables = extract_tables_for_mode(pdf_path, lattice=True, stream=False)
    extraction_mode = "lattice"
    tables_by_page = lattice_tables

    if not lattice_tables:
        tables_by_page = extract_tables_for_mode(pdf_path, lattice=False, stream=True)
        extraction_mode = "stream"

    table_count = write_tables(slug, tables_by_page)

    return {
        "slug": slug,
        "pdf_path": pdf_path,
        "csv_dir": CSV_DIR / slug,
        "table_count": table_count,
        "mode": extraction_mode,
        "failed": table_count == 0,
    }


def main() -> int:
    ensure_output_dirs()
    results = []

    for slug, pdf_filename, url in PDF_SOURCES:
        results.append(process_pdf(slug, pdf_filename, url))

    failed = [result for result in results if result["failed"]]

    print("Extraction summary")
    print(f"PDF output: {PDF_DIR}")
    print(f"CSV output: {CSV_DIR}")
    print()

    for result in results:
        status = "failed" if result["failed"] else "ok"
        print(
            f"{result['slug']}: {status} | downloaded | "
            f"mode={result['mode']} | tables={result['table_count']} | "
            f"pdf={result['pdf_path']} | csv_dir={result['csv_dir']}"
        )

    if failed:
        print()
        print("Failed sources:")
        for result in failed:
            print(f"- {result['slug']}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
