"""
Phase 1 configuration: paths, the canonical Work ID pattern, and the
constants preprocessing.py needs to parse the 12 raw MPLADS CSVs.

Nothing in this file is specific to any one filename. Adding a 13th
CSV, or a future source with slightly different header text, should
only ever require a change here (or in preprocessing.py's generic
logic) -- never a `if filename == "..."` branch anywhere in this
package.

Verified against the actual files in data/raw/ (12 files: LS/RS x
{Allocated Limit, Amount Consented for Calamity, Works Recommended,
Works Sanctioned, Works Completed, Expenditure}):

  - Every one of the 12 files ends with a spreadsheet-style
    "Grand Total" footer row in its `Sr. No.` column (confirmed on
    all 12, not just a subset). This is a universal export artifact,
    not project data, and is dropped by column *value*
    (`Sr. No. == "Grand Total"`), not by row position -- so it still
    works if a future export has a different row count.
  - Dates are consistently `DD-Mon-YYYY` (e.g. "21-Aug-2026") across
    every date column in every file. One format is primary; a couple
    of fallbacks are kept for robustness against a future source that
    isn't perfectly consistent, per the "must work for future MPLADS
    data" requirement.
  - Amount columns are plain numeric strings with no thousands
    separators in ordinary rows (e.g. "1484933", "154773472.11") --
    EXCEPT the "Grand Total" footer row, which uses Indian-style
    comma grouping (e.g. "17,11,29,25,064.87"). Since that row is
    dropped before amount parsing runs, comma-stripping in
    parse_amount() is a defensive fallback, not the primary path.
  - Work IDs appear two ways depending on the file: a dedicated
    `Work ID` column (Expenditure files only), or embedded as a
    prefix of a longer `Work`/`WORK` column shared with the
    description (Recommended/Sanctioned/Completed files), e.g.
    "WS/MP418/2024-2025/133409-Construction of roads...". Both
    "Work" and "WORK" normalize to the same column name after
    normalize_column_name() runs, so no per-file branching is needed
    to find it.
"""

from pathlib import Path
import re

# --- Paths --------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = BACKEND_ROOT / "data" / "raw"

# --- Universal footer-row filter -----------------------------------------
# Column value to match against the normalized "sr_no" column. Matching is
# done case-insensitively after stripping, so "Grand Total", "grand total ",
# etc. all match. This is a value check, not a positional ("drop last row")
# check, so it's safe even if a future export adds trailing blank rows.
FOOTER_ROW_MARKERS = {"grand total"}

# --- Work ID -------------------------------------------------------------
# Canonical form: WS/MP<number>/<YYYY-YYYY>/<number>
# The regex tolerates stray whitespace/tabs between tokens (confirmed
# dirty examples in the raw data, e.g. "WS/\t MP620/2024-2025/133166-...")
# and stops matching the moment the trailing sequence number ends -- it
# never consumes the "-<description>" text that follows in the
# Recommended/Sanctioned/Completed files' Work/WORK column.
WORK_ID_PATTERN = re.compile(
    r"WS\s*/\s*MP\s*(\d+)\s*/\s*(\d{4})\s*-\s*(\d{4})\s*/\s*(\d+)",
    re.IGNORECASE,
)

# Values that mean "no Work ID was ever assigned to this row" as opposed to
# "a Work ID field exists but is corrupted." Confirmed real in the raw
# Recommended files: rows for works recommended but not yet processed far
# enough to have a Work ID carry the literal description-column value
# "NA-<description>" instead of an ID.
MISSING_WORK_ID_PREFIXES = ("na-", "na")

# --- Null tokens ----------------------------------------------------------
# String values that represent "no value" beyond pandas' own NaN handling.
NULL_TOKENS = {"", "na", "n/a", "null", "none", "nan", "-", "nil"}

# --- Dates -----------------------------------------------------------------
# Primary format confirmed across every date column in every one of the 12
# files. Fallbacks are defensive only, for future sources that may not be
# perfectly consistent with the current export.
DATE_FORMATS = ["%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d/%m/%Y"]

# --- Column name matching (for choosing which parser to apply) ------------
# Substring markers used, post-normalize_column_name(), to decide whether a
# given column should be parsed as an amount or a date. Substring matching
# (not an exact name list) so a future column like "revised_sanction_amount"
# or "expected_completion_date" is still picked up without a code change.
AMOUNT_COLUMN_MARKERS = ("amount", "disbursed")
DATE_COLUMN_MARKERS = ("date",)


def canonical_work_id(mp_number: str, year_start: str, year_end: str, seq_number: str) -> str:
    """Rebuild the canonical WS/MP<n>/<YYYY-YYYY>/<n> string from regex groups.

    int() on mp_number/seq_number strips any leading zeros so the same
    project is never represented two different ways (e.g. "MP007" and
    "MP7" -- not observed in the current data, but cheap insurance).
    """
    return f"WS/MP{int(mp_number)}/{year_start}-{year_end}/{int(seq_number)}"