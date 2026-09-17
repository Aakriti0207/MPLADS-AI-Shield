"""
Normalized MPLADS project-sector classification.

The source dataset's work_category is retained unchanged for
traceability and ML/risk metadata.

This module provides a human-readable sector derived primarily
from the work description, with the source category used only
as a fallback.
"""

from __future__ import annotations

import re


PROJECT_SECTORS = [
    "Roads & Connectivity",
    "Education",
    "Healthcare",
    "Water & Sanitation",
    "Community & Public Buildings",
    "Electricity & Energy",
    "Sports & Recreation",
    "Agriculture & Irrigation",
    "Public Utilities",
    "Social Welfare",
    "Environment & Green Infrastructure",
    "Other Public Infrastructure",
]


def _text(value) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if not text or text.lower() in {"nan", "none", "null"}:
        return ""

    return text.casefold()


def _contains(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_project_sector(
    work_description=None,
    work_category=None,
) -> str:
    """
    Convert a raw MPLADS work into a meaningful project sector.

    Priority:
        1. Work description
        2. Raw work category
        3. Other Public Infrastructure

    The original work_category is never modified.
    """

    description = _text(work_description)
    category = _text(work_category)

    # ---------------------------------------------------------------
    # Roads & Connectivity
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "road",
            "roads",
            "link road",
            "link roads",
            "pathway",
            "pathways",
            "street",
            "highway",
            "culvert",
            "bridge",
            "flyover",
            "approach road",
            "drainage road",
        ),
    ):
        return "Roads & Connectivity"

    # ---------------------------------------------------------------
    # Education
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "school",
            "classroom",
            "college",
            "university",
            "educational",
            "education",
            "library",
            "laboratory",
            "lab ",
            "smart class",
            "computer lab",
            "school building",
            "anganwadi",
        ),
    ):
        return "Education"

    # ---------------------------------------------------------------
    # Healthcare
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "hospital",
            "health centre",
            "health center",
            "healthcare",
            "health care",
            "clinic",
            "dispensary",
            "phc",
            "primary health",
            "medical",
            "medicine",
            "diagnostic",
        ),
    ):
        return "Healthcare"

    # ---------------------------------------------------------------
    # Water & Sanitation
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "drinking water",
            "water supply",
            "water pipeline",
            "water pipe",
            "pipeline",
            "borewell",
            "bore well",
            "handpump",
            "hand pump",
            "water tank",
            "overhead tank",
            "sanitation",
            "sewer",
            "sewage",
            "toilet",
            "latrine",
            "drain",
            "drainage",
        ),
    ):
        return "Water & Sanitation"

    # ---------------------------------------------------------------
    # Electricity & Energy
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "electric",
            "electricity",
            "electrification",
            "transformer",
            "solar",
            "solar light",
            "solar lights",
            "street light",
            "street lights",
            "lighting",
            "high mast",
            "high-mast",
            "energy",
        ),
    ):
        return "Electricity & Energy"

    # ---------------------------------------------------------------
    # Sports & Recreation
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "playground",
            "play ground",
            "sports",
            "stadium",
            "gymnasium",
            "gym ",
            "football ground",
            "cricket ground",
            "sports complex",
            "recreation",
            "park",
        ),
    ):
        return "Sports & Recreation"

    # ---------------------------------------------------------------
    # Agriculture & Irrigation
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "irrigation",
            "agriculture",
            "agricultural",
            "farmer",
            "farming",
            "minor irrigation",
            "canal",
            "check dam",
            "watershed",
            "water harvesting",
            "farm",
            "agri ",
        ),
    ):
        return "Agriculture & Irrigation"

    # ---------------------------------------------------------------
    # Social Welfare
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "old age",
            "elderly",
            "senior citizen",
            "orphan",
            "orphanage",
            "disabled",
            "disability",
            "divyang",
            "welfare",
            "shelter home",
            "shelter",
            "women's",
            "women ",
            "child care",
            "children home",
        ),
    ):
        return "Social Welfare"

    # ---------------------------------------------------------------
    # Environment & Green Infrastructure
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "plantation",
            "tree plantation",
            "afforestation",
            "environment",
            "environmental",
            "green belt",
            "garden",
            "green infrastructure",
            "waste management",
            "solid waste",
            "compost",
        ),
    ):
        return "Environment & Green Infrastructure"

    # ---------------------------------------------------------------
    # Community & Public Buildings
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "community hall",
            "community centre",
            "community center",
            "public hall",
            "panchayat",
            "municipal building",
            "public building",
            "government building",
            "govt building",
            "office building",
            "bar association",
            "association building",
            "trust building",
            "society building",
            "construction of building",
            "building construction",
            "repair and renovation",
            "renovation",
        ),
    ):
        return "Community & Public Buildings"

    # ---------------------------------------------------------------
    # Public Utilities
    # ---------------------------------------------------------------
    if _contains(
        description,
        (
            "market",
            "bus stand",
            "bus shelter",
            "public toilet",
            "crematorium",
            "burial ground",
            "waiting shed",
            "public convenience",
            "parking",
            "public space",
            "public facility",
        ),
    ):
        return "Public Utilities"

    # ---------------------------------------------------------------
    # Fallback based on source category
    # ---------------------------------------------------------------

    if category in {
        "repair and renovation",
        "bar and associations",
        "trust and society",
    }:
        return "Community & Public Buildings"

    return "Other Public Infrastructure"