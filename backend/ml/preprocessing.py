"""
Phase 1 — Preprocessing + Work ID normalization.

Scope (per the approved Phase 1 plan): load the 12 raw MPLADS CSVs
safely, normalize column names and string values, parse amounts and
dates robustly, and extract a canonical Work ID from whichever column
carries it. Nothing downstream of this (feature engineering, detectors,
risk scoring, fusion) is implemented here -- see ml/__init__.py.

Design rule enforced throughout: no branching on filename. Every
function here operates purely on a DataFrame's *normalized* column
names and cell values, so the same code path handles all 12 current
files and should handle a future 13th file without modification, as
long as its columns normalize to recognizable names (Work/WORK/Work ID,
*_date, *_amount, Sr. No.).

None of this reads, imports, or otherwise depends on the precomputed
project_risk_scores.csv or any of its columns (risk_score, risk_level,
etc.) -- confirmed no reference to that file anywhere below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from ml.config import (
    AMOUNT_COLUMN_MARKERS,
    DATE_COLUMN_MARKERS,
    DATE_FORMATS,
    FOOTER_ROW_MARKERS,
    MISSING_WORK_ID_PREFIXES,
    NULL_TOKENS,
    WORK_ID_PATTERN,
    canonical_work_id,
)


# =========================================================================
# 1. Loading
# =========================================================================

def load_csv(path: Path | str) -> pd.DataFrame:
    """Load a raw MPLADS CSV read-only, as strings, without touching the
    source file on disk.

    dtype=str keeps pandas from silently guessing types (e.g. turning a
    Work ID's numeric-looking segment into an int, or mangling a date) --
    all real typing is done explicitly and defensively below.
    encoding="utf-8-sig" strips the BOM every one of the 12 files starts
    with (confirmed: they all open with a literal `\\ufeff` before
    "Sr. No.").
    """
    path = Path(path)
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=True)


# =========================================================================
# 2. Column name normalization
# =========================================================================

_COLUMN_JUNK_RE = re.compile(r"[₹()]")
_COLUMN_WS_RE = re.compile(r"\s+")
_COLUMN_NONWORD_RE = re.compile(r"[^a-z0-9_]+")
_COLUMN_MULTI_UNDERSCORE_RE = re.compile(r"_+")


def normalize_column_name(name: str) -> str:
    """"RECOMMENDED AMOUNT   ( ₹ )" -> "recommended_amount"; "Work ID" ->
    "work_id"; "Sr. No." -> "sr_no". Deterministic and reversible enough
    to trace back to source (see normalize_columns()'s returned mapping)."""
    n = name.strip().lower()
    n = _COLUMN_JUNK_RE.sub(" ", n)
    n = n.replace(".", " ")
    n = _COLUMN_WS_RE.sub(" ", n).strip()
    n = n.replace(" ", "_")
    n = _COLUMN_NONWORD_RE.sub("_", n)
    n = _COLUMN_MULTI_UNDERSCORE_RE.sub("_", n).strip("_")
    return n


def normalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Return (df with normalized column names, {normalized: original}
    mapping) -- the mapping is what requirement #2 calls "preserve enough
    information for source mapping": later phases (canonical.py) can
    always look up which raw header a normalized column came from."""
    mapping: dict[str, str] = {}
    new_columns = []
    for col in df.columns:
        norm = normalize_column_name(col)
        mapping[norm] = col
        new_columns.append(norm)
    out = df.copy()
    out.columns = new_columns
    return out, mapping


# =========================================================================
# 3. Footer-row removal (universal "Grand Total" row, all 12 files)
# =========================================================================

def drop_footer_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop rows that are spreadsheet export footers, not project data.

    Matched by value on the normalized "sr_no" column (case-insensitive,
    stripped), not by row position -- confirmed present as the literal
    last row in all 12 raw files, always with Sr. No. == "Grand Total".
    If a given DataFrame has no "sr_no" column, this is a no-op.
    """
    if "sr_no" not in df.columns:
        return df, 0
    is_footer = df["sr_no"].fillna("").str.strip().str.lower().isin(FOOTER_ROW_MARKERS)
    dropped = int(is_footer.sum())
    return df.loc[~is_footer].copy(), dropped


# =========================================================================
# 4. String value normalization
# =========================================================================

def normalize_string(value: Optional[str]) -> Optional[str]:
    """Trim, collapse internal whitespace/tabs/newlines to single spaces,
    and map empty-after-strip or known null tokens to None. Case is
    preserved -- names (MP, state, agency) are display data; case-
    insensitive comparison is a job for the consumer (e.g. the API layer
    already does func.lower() for scope filtering), not for this layer to
    bake in destructively.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        # pandas represents a missing cell as float('nan') even in an
        # otherwise all-string column (e.g. after CSV load, before any
        # type-specific parsing runs) -- treat that the same as None
        # rather than letting a stray NaN float leak into downstream
        # string/regex logic.
        return None if pd.isna(value) else value
    collapsed = _COLUMN_WS_RE.sub(" ", value).strip()
    if collapsed.lower() in NULL_TOKENS:
        return None
    return collapsed


def normalize_string_series(s: pd.Series) -> pd.Series:
    return s.map(normalize_string)


def normalize_all_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Apply normalize_string_series to every column. Safe to run before
    the type-specific amount/date parsing below, since those parsers
    handle their own stripping too (defense in depth, not redundant --
    this pass is what makes Work ID extraction and general text columns
    clean, since those are never numeric/date-parsed)."""
    out = df.copy()
    for col in out.columns:
        out[col] = normalize_string_series(out[col])
    return out


# =========================================================================
# 5. Amount parsing
# =========================================================================

_AMOUNT_STRIP_RE = re.compile(r"[₹,\s]")


def parse_amount(value: Optional[str]) -> Optional[float]:
    """Parse a raw amount string into a float, or None if it can't be
    parsed. Strips currency symbols/commas defensively (ordinary data rows
    never have them, but the "Grand Total" footer row's Indian-comma-
    grouped total would, e.g. "17,11,29,25,064.87" -- relevant only if a
    footer row somehow reaches this function uncaught)."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    cleaned = _AMOUNT_STRIP_RE.sub("", str(value))
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_amount_series(s: pd.Series) -> tuple[pd.Series, int]:
    parsed = s.map(parse_amount)
    # A parse "failure" is a non-null source value that produced a null
    # result -- a genuinely empty/None source value is not a failure.
    failures = int(((s.notna()) & (parsed.isna())).sum())
    return parsed, failures


# =========================================================================
# 6. Date parsing
# =========================================================================

def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse a raw date string using the confirmed primary format first,
    falling back to the other configured formats before giving up."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text == "":
        return None
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(text, format=fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def parse_date_series(s: pd.Series) -> tuple[pd.Series, int]:
    parsed = s.map(parse_date)
    failures = int(((s.notna()) & (parsed.isna())).sum())
    return parsed, failures


# =========================================================================
# 7. Work ID extraction
# =========================================================================

def extract_work_id(value: Optional[str]) -> Optional[str]:
    """Search `value` for the WS/MP<n>/<YYYY-YYYY>/<n> pattern anywhere in
    the string (it's typically a prefix followed by "-<description>", but
    .search() rather than .match() costs nothing and is more robust) and
    rebuild it in canonical form. Returns None if no match."""
    if value is None:
        return None
    m = WORK_ID_PATTERN.search(value)
    if not m:
        return None
    mp_number, year_start, year_end, seq_number = m.groups()
    return canonical_work_id(mp_number, year_start, year_end, seq_number)


def _looks_like_missing_marker(value: Optional[str]) -> bool:
    """True for the confirmed real "no Work ID assigned yet" placeholder
    (a raw value starting with "NA-" or exactly "NA"), as opposed to a
    present-but-corrupted value."""
    if value is None:
        return True
    return value.strip().lower().startswith(MISSING_WORK_ID_PREFIXES)


WORK_ID_SOURCE_COLUMNS = ("work_id", "work")


def extract_work_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'work_id_canonical' and 'work_id_status' columns to df.

    Column choice is driven entirely by which normalized columns exist on
    this particular DataFrame -- 'work_id' (the Expenditure files'
    dedicated column) is preferred when present and extractable; 'work'
    (what both 'Work' and 'WORK' normalize to, in the Recommended/
    Sanctioned/Completed files) is the fallback. No filename check
    anywhere in this function.

    work_id_status is one of:
      "valid"   - canonical Work ID successfully extracted
      "missing" - source field was empty/null, or carried the confirmed
                  real "NA-<description>" not-yet-assigned marker
      "invalid" - source field had content but didn't match the pattern
                  and wasn't a recognized "missing" marker
    """
    source_col = next((c for c in WORK_ID_SOURCE_COLUMNS if c in df.columns), None)
    out = df.copy()
    if source_col is None:
        out["work_id_canonical"] = None
        out["work_id_status"] = "missing"
        return out

    raw = out[source_col]
    canonical = raw.map(extract_work_id)

    def status_for(raw_value, canonical_value):
        # pandas' Series.map() silently turns a function's `None` return
        # into float('nan') on this dtype, so `is not None` alone would
        # wrongly call every unmatched row "valid" -- pd.notna() is the
        # correct check here, not identity.
        if pd.notna(canonical_value):
            return "valid"
        if _looks_like_missing_marker(raw_value):
            return "missing"
        return "invalid"

    out["work_id_canonical"] = canonical
    out["work_id_status"] = [
        status_for(r, c) for r, c in zip(raw.tolist(), canonical.tolist())
    ]
    return out


# =========================================================================
# 8. Report
# =========================================================================

@dataclass
class PreprocessingReport:
    file_name: str
    rows_loaded: int
    footer_rows_dropped: int
    rows_after_footer_drop: int
    valid_work_ids: int
    missing_work_ids: int
    invalid_work_ids: int
    duplicate_work_ids: int
    date_columns_checked: list[str] = field(default_factory=list)
    date_parse_failures: dict[str, int] = field(default_factory=dict)
    numeric_columns_checked: list[str] = field(default_factory=list)
    numeric_parse_failures: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "rows": self.rows_loaded,
            "footer_rows_dropped": self.footer_rows_dropped,
            "rows_after_footer_drop": self.rows_after_footer_drop,
            "valid_work_ids": self.valid_work_ids,
            "missing_work_ids": self.missing_work_ids,
            "invalid_work_ids": self.invalid_work_ids,
            "duplicate_work_ids": self.duplicate_work_ids,
            "date_parse_failures": self.date_parse_failures,
            "numeric_parse_failures": self.numeric_parse_failures,
        }


# =========================================================================
# 9. Orchestration
# =========================================================================

def preprocess_file(path: Path | str) -> tuple[pd.DataFrame, PreprocessingReport]:
    """Run the full Phase 1 pipeline on one raw CSV and return the
    normalized, in-memory DataFrame plus a PreprocessingReport. The
    source file on disk is never written to."""
    path = Path(path)
    df = load_csv(path)
    rows_loaded = len(df)

    df, _column_mapping = normalize_columns(df)
    df, footer_dropped = drop_footer_rows(df)
    rows_after_footer_drop = len(df)

    df = normalize_all_strings(df)

    date_cols = [c for c in df.columns if any(m in c for m in DATE_COLUMN_MARKERS)]
    date_failures: dict[str, int] = {}
    for col in date_cols:
        parsed, failures = parse_date_series(df[col])
        df[col] = parsed
        date_failures[col] = failures

    amount_cols = [
        c for c in df.columns
        if any(m in c for m in AMOUNT_COLUMN_MARKERS) and c not in date_cols
    ]
    numeric_failures: dict[str, int] = {}
    for col in amount_cols:
        parsed, failures = parse_amount_series(df[col])
        df[col] = parsed
        numeric_failures[col] = failures

    df = extract_work_ids(df)

    status_counts = df["work_id_status"].value_counts()
    valid_ids = df.loc[df["work_id_status"] == "valid", "work_id_canonical"]
    duplicate_work_ids = int(valid_ids.duplicated(keep=False).sum())

    report = PreprocessingReport(
        file_name=path.name,
        rows_loaded=rows_loaded,
        footer_rows_dropped=footer_dropped,
        rows_after_footer_drop=rows_after_footer_drop,
        valid_work_ids=int(status_counts.get("valid", 0)),
        missing_work_ids=int(status_counts.get("missing", 0)),
        invalid_work_ids=int(status_counts.get("invalid", 0)),
        duplicate_work_ids=duplicate_work_ids,
        date_columns_checked=date_cols,
        date_parse_failures=date_failures,
        numeric_columns_checked=amount_cols,
        numeric_parse_failures=numeric_failures,
    )
    return df, report