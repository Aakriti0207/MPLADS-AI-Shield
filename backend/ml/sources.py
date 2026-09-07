"""
Phase 2 — Source adapter registry.

This is the ONE place in the codebase that knows the 12 actual raw
filenames and which house (LS/RS) each belongs to. Nothing outside this
file branches on filename -- everywhere else (ml.preprocessing,
ml.canonical) operates only on source_type and normalized column names.
Adding a future 13th file, or a differently-named export, means adding
one SourceFile entry here (and extending COLUMN_MAPPINGS if its headers
are worded differently) -- no other code changes.

Why house (LS/RS) can only come from here: none of the 12 files has an
explicit "House" column (verified). The only reliable signal for which
chamber a record belongs to is which file it was exported from, so it's
recorded as a fact ABOUT the source file, not inferred from row data.

Column mappings below were built from the actual verified headers of
all 12 files (not assumed):

  Recommended (LS & RS, identical headers):
    Sr. No., Work category, WORK, State, IDA,
    Hon'ble Members of Parliament, Constituency, Work description,
    Recommended date, RECOMMENDED AMOUNT ( ₹ ), Sanction Date

  Sanctioned (LS/RS headers DIFFER -- LS has Elected/Nominated,
  RS has Constituency instead):
    Sr. No., Work category, Work, State, IDA,
    Hon'ble Members of Parliament, [Elected/Nominated | Constituency],
    Work description, Recommended date, Sanction Date,
    Sanction Amount ( ₹ ), Work Status

  Completed (LS & RS, identical headers):
    Sr. No., Work Category, Work, State, IDA, Work Description,
    Hon'ble Members of Parliament, Elected/Nominated, Image,
    Completion Date, Amount Disbursed ( ₹ )

  Expenditure (LS/RS headers DIFFER -- LS has Constituency,
  RS has Elected/Nominated):
    Sr. No., State, Work, Work ID, IDA,
    Hon'ble Members of Parliament, [Constituency | Elected/Nominated],
    Expenditure Date, Vendor Name, Payment Status,
    Fund Disbursed Amount ( ₹ )

  Allocated Limit (LS/RS headers differ slightly -- LS's MP column is
  plural "Parliaments"; LS has no Elected/Nominated, RS has no
  Constituency):
    Sr. No., State, Hon'ble Members of Parliament[s],
    [Constituency | Elected/Nominated], Allocated AMOUNT ( ₹ )

  Calamity Consent (LS & RS, identical headers):
    Sr. No., Calamity Type, Calamity Name,
    Hon'ble Members of Parliament, Date of Consent,
    Consent Amount ( ₹ )

These LS-vs-RS column differences (Elected/Nominated vs Constituency)
are a genuine inconsistency in the source, not a mistake in this
registry -- see the Phase 2 report's "surprising findings" section.
COLUMN_MAPPINGS below is applied by column *existence* on each specific
file, never by house, so it's correct either way without a house-based
branch.
"""

from dataclasses import dataclass

from ml.config import RAW_DATA_DIR

RECOMMENDED = "recommended"
SANCTIONED = "sanctioned"
COMPLETED = "completed"
EXPENDITURE = "expenditure"
ALLOCATED_LIMIT = "allocated_limit"
CALAMITY_CONSENT = "calamity_consent"

LIFECYCLE_SOURCE_TYPES = (RECOMMENDED, SANCTIONED, COMPLETED, EXPENDITURE)
REFERENCE_SOURCE_TYPES = (ALLOCATED_LIMIT, CALAMITY_CONSENT)


@dataclass(frozen=True)
class SourceFile:
    filename: str
    source_type: str
    house: str  # "LS" or "RS" -- see module docstring for why this can only live here


SOURCE_REGISTRY: tuple[SourceFile, ...] = (
    SourceFile("LS_Works Recommended.csv", RECOMMENDED, "LS"),
    SourceFile("RS_Works_Recommended.csv", RECOMMENDED, "RS"),
    SourceFile("LS_Works_Sanctioned__1_.csv", SANCTIONED, "LS"),
    SourceFile("RS_Works_Sanctioned.csv", SANCTIONED, "RS"),
    SourceFile("LS_Works Completed (1).csv", COMPLETED, "LS"),
    SourceFile("RS_Works_Completed.csv", COMPLETED, "RS"),
    SourceFile(
        "LS_Expenditure on Completed and On-going Works as on Date.csv",
        EXPENDITURE, "LS",
    ),
    SourceFile(
        "RS_Expenditure_on_Completed_and_On-going_Works_as_on_Date.csv",
        EXPENDITURE, "RS",
    ),
    SourceFile("LS_Allocated_Limit_for_Honble_MPs.csv", ALLOCATED_LIMIT, "LS"),
    SourceFile("RS_Allocated_Limit_for_Honble_MPs__4_.csv", ALLOCATED_LIMIT, "RS"),
    SourceFile("LS_Amount_consented_for_Calamity.csv", CALAMITY_CONSENT, "LS"),
    SourceFile("RS_Amount_consented_for_Calamity__1_.csv", CALAMITY_CONSENT, "RS"),
)


def sources_of_type(source_type: str) -> list[SourceFile]:
    return [s for s in SOURCE_REGISTRY if s.source_type == source_type]


def resolve_path(source: SourceFile):
    return RAW_DATA_DIR / source.filename


# --- Column mapping: normalized source column -> canonical field ----------
# One mapping per source_type, covering the UNION of columns seen across
# both houses' files of that type. Applied by column *existence* on each
# specific file (see ml.canonical.load_and_adapt), so the LS/RS header
# differences documented above are handled correctly without a house check.
COLUMN_MAPPINGS: dict[str, dict[str, str]] = {
    RECOMMENDED: {
        "work_category": "work_category",
        "state": "state",
        "ida": "implementing_agency",
        "hon_ble_members_of_parliament": "mp",
        "hon_ble_members_of_parliaments": "mp",
        "constituency": "constituency",
        "work_description": "work_description",
        "recommended_date": "recommended_date",
        "recommended_amount": "recommended_amount",
        # Also present in the Sanctioned file -- reconciled, not
        # independently trusted. See RECONCILED_LIFECYCLE_FIELDS.
        "sanction_date": "sanction_date",
    },
    SANCTIONED: {
        "work_category": "work_category",
        "state": "state",
        "ida": "implementing_agency",
        "hon_ble_members_of_parliament": "mp",
        "hon_ble_members_of_parliaments": "mp",
        "elected_nominated": "elected_nominated",
        "constituency": "constituency",
        "work_description": "work_description",
        # Also present in the Recommended file -- reconciled.
        "recommended_date": "recommended_date",
        "sanction_date": "sanction_date",
        "sanction_amount": "sanction_amount",
        "work_status": "work_status",
    },
    COMPLETED: {
        "work_category": "work_category",
        "state": "state",
        "ida": "implementing_agency",
        "work_description": "work_description",
        "hon_ble_members_of_parliament": "mp",
        "hon_ble_members_of_parliaments": "mp",
        "elected_nominated": "elected_nominated",
        "image": "image",
        "completion_date": "completion_date",
        "amount_disbursed": "amount_disbursed",
    },
    EXPENDITURE: {
        "state": "state",
        "ida": "implementing_agency",
        "hon_ble_members_of_parliament": "mp",
        "hon_ble_members_of_parliaments": "mp",
        "constituency": "constituency",
        "elected_nominated": "elected_nominated",
        "expenditure_date": "expenditure_date",
        "vendor_name": "vendor_name",
        "payment_status": "payment_status",
        "fund_disbursed_amount": "fund_disbursed_amount",
    },
    ALLOCATED_LIMIT: {
        "state": "state",
        "hon_ble_members_of_parliament": "mp",
        "hon_ble_members_of_parliaments": "mp",
        "constituency": "constituency",
        "elected_nominated": "elected_nominated",
        "allocated_amount": "allocated_amount",
    },
    CALAMITY_CONSENT: {
        "calamity_type": "calamity_type",
        "calamity_name": "calamity_name",
        "hon_ble_members_of_parliament": "mp",
        "hon_ble_members_of_parliaments": "mp",
        "date_of_consent": "date_of_consent",
        "consent_amount": "consent_amount",
    },
}

# Identity/attribute fields that can legitimately appear in more than one
# lifecycle stage's file for the same project and therefore need conflict
# reconciliation (ml.canonical.reconcile_values), rather than a single
# direct column pull.
RECONCILED_LIFECYCLE_FIELDS = (
    "state",
    "mp",
    "constituency",
    "implementing_agency",
    "work_category",
    "work_description",
    "elected_nominated",
    "recommended_date",
    "sanction_date",
)

# Priority order for reconciling a field across stages when values
# disagree: earlier stages win. Documented reasoning: a Sanctioned-stage
# record is the formally verified administrative entry (review already
# happened before sanction); Completed-stage entries are typically
# re-keyed by execution staff off the sanctioned record; Recommended-stage
# is the earliest, least-verified entry; Expenditure-stage rows are keyed
# by disbursement/accounts staff working from vouchers, who may transcribe
# MP/state/IDA text slightly differently despite it being the same
# underlying project.
STAGE_PRIORITY = (SANCTIONED, COMPLETED, RECOMMENDED, EXPENDITURE)