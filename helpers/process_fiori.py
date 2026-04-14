import pandas as pd
from pathlib import Path
from typing import List, Dict, Any


def process_fiori_excel(file_path) -> List[Dict[str, Any]]:
    """
    Parse the SAP Fiori Apps Library Excel/CSV export into a list of app dicts.

    Expected columns (SAP List View download):
      fioriId, AppName, GTMAppDescription, RoleName, ProductCategory,
      ApplicationType, LineOfBusiness, ...

    Automatically detects whether the file is .xlsx or .csv.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Fiori dataset not found at {file_path}")

    # Load file — handle both xlsx and csv
    suffix = file_path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
    else:
        # Try common encodings for SAP exports
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(file_path, dtype=str, encoding=enc)
                break
            except UnicodeDecodeError:
                continue

    # Normalize column names — strip whitespace
    df.columns = df.columns.str.strip()

    # Print available columns on first run so user can verify
    print(f"      Columns in dataset: {list(df.columns)}")

    # Column name mapping — handles slight variations in SAP exports
    COL = {
        "app_id":        _find_col(df, ["fioriId", "App ID", "AppId", "FioriId"]),
        "title":         _find_col(df, ["AppName", "App Name", "Title", "Name"]),
        "description":   _find_col(df, ["GTMAppDescription", "Description", "ShortDescription", "Short Description"]),
        "business_role": _find_col(df, ["RoleName", "Business Role", "BusinessRole"]),
        "product":       _find_col(df, ["ProductCategory", "Product", "Product Category"]),
        "app_type":      _find_col(df, ["ApplicationType", "App Type", "AppType", "Application Type"]),
    }

    apps = []
    skipped_gui = 0

    for _, row in df.iterrows():
        description = _get(row, COL["description"])

        # Skip generic SAP GUI HTML wrappers — not useful for matching
        if "SAP GUI for HTML transaction" in description:
            skipped_gui += 1
            continue

        title = _get(row, COL["title"])
        if not title:
            continue  # skip blank rows

        apps.append({
            "app_id":        _get(row, COL["app_id"]),
            "title":         title,
            "description":   description,
            "business_role": _get(row, COL["business_role"]),
            "product":       _get(row, COL["product"]),
            "app_type":      _get(row, COL["app_type"]),
            "tags":          [],  # SAP export doesn't include tags — embeddings cover this
        })

    print(f"      Parsed {len(apps)} apps ({skipped_gui} SAP GUI rows skipped)")
    return apps


def _find_col(df: pd.DataFrame, candidates: list) -> str | None:
    """Return the first matching column name, or None."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _get(row, col: str | None) -> str:
    """Safely get a value from a row, returning '' if column is missing."""
    if col is None:
        return ""
    val = row.get(col, "")
    return str(val).strip() if pd.notna(val) else ""