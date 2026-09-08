"""Phase 6 duplicate and similar-work detection."""

from ml.duplicates.engine import (
    DUPLICATE_MATCH_COLUMNS,
    DUPLICATE_SUMMARY_COLUMNS,
    SIMILARITY_THRESHOLD,
    build_phase6_outputs,
    run_phase6_from_file,
    write_phase6_outputs,
)

__all__ = [
    "DUPLICATE_MATCH_COLUMNS",
    "DUPLICATE_SUMMARY_COLUMNS",
    "SIMILARITY_THRESHOLD",
    "build_phase6_outputs",
    "run_phase6_from_file",
    "write_phase6_outputs",
]
