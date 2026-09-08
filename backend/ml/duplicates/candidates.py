"""Exact grouping and bounded sparse nearest-neighbor candidate generation."""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

DEFAULT_CANDIDATE_LIMIT = 10
SIMILARITY_BATCH_SIZE = 256


def exact_pairs(frame: pd.DataFrame) -> list[tuple[str, str]]:
    """Generate canonical unordered pairs for equal usable descriptions."""
    pairs: list[tuple[str, str]] = []
    for _, group in frame.groupby("normalized_description", sort=True):
        identifiers = sorted(str(value) for value in group["work_id"])
        pairs.extend(combinations(identifiers, 2))
    return pairs


def similarity_candidates(
    frame: pd.DataFrame,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    batch_size: int = SIMILARITY_BATCH_SIZE,
) -> dict[tuple[str, str], float]:
    """Retrieve at most ``candidate_limit`` neighbors per usable project.

    TF-IDF is sparse and common terms are downweighted by inverse document
    frequency. Exact pairs are returned too and are removed by the engine when
    their normalized descriptions are handled as EXACT_MATCH.
    """
    if candidate_limit < 1:
        raise ValueError("candidate_limit must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if frame.empty:
        return {}
    texts = frame["normalized_description"].astype(str).tolist()
    vectorizer = TfidfVectorizer(dtype=np.float64, token_pattern=r"(?u)\b\w+\b")
    matrix = vectorizer.fit_transform(texts)
    if matrix.shape[0] < 2:
        return {}
    work_ids = frame["work_id"].astype(str).tolist()
    candidates: dict[tuple[str, str], float] = {}
    # TfidfVectorizer uses L2-normalized rows by default, so the sparse dot
    # product is cosine similarity. Batching bounds the sparse product's
    # intermediate size to roughly batch_size x number_of_documents.
    for start in range(0, matrix.shape[0], batch_size):
        stop = min(start + batch_size, matrix.shape[0])
        similarities = matrix[start:stop] @ matrix.T
        for local_index in range(stop - start):
            row_index = start + local_index
            row = similarities.getrow(local_index)
            neighbor_indices = row.indices
            neighbor_scores = row.data
            valid = neighbor_indices != row_index
            neighbor_indices = neighbor_indices[valid]
            neighbor_scores = neighbor_scores[valid]
            order = np.lexsort((neighbor_indices, -neighbor_scores))[:candidate_limit]
            selected = set(int(index) for index in neighbor_indices[order])
            selected.update({row_index})
            # NearestNeighbors previously filled its top-k result with
            # zero-similarity rows when a sparse row had fewer than k hits.
            # Preserve that deterministic contract without making zeros dense.
            if len(order) < candidate_limit:
                for neighbor_index in range(matrix.shape[0]):
                    if neighbor_index not in selected:
                        selected.add(neighbor_index)
                        order = np.append(order, -neighbor_index - 1)
                        if len(order) == candidate_limit:
                            break
            for position in order:
                if position < 0:
                    neighbor_index = -int(position) - 1
                    score = 0.0
                else:
                    neighbor_index = int(neighbor_indices[position])
                    score = float(neighbor_scores[position])
                pair = tuple(sorted((work_ids[row_index], work_ids[neighbor_index])))
                candidates[pair] = max(score, candidates.get(pair, -np.inf))
    return candidates
