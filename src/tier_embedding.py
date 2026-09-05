"""Tier 2: local embedding plus kNN classification.

Loads all-MiniLM-L6-v2 once at import time, embeds the 90 labeled examples once,
and caches both in memory. classify() returns None when nothing clears the
similarity threshold, signaling the caller to escalate to Tier 3.
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from src.models import RootCause

SIMILARITY_THRESHOLD = 0.75
LABELED_EXAMPLES_PATH = Path(__file__).resolve().parent.parent / "data" / "labeled_examples.json"

_model: SentenceTransformer | None = None
_labeled_texts: list[str] = []
_labeled_causes: list[RootCause] = []
_labeled_embeddings: np.ndarray | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _load_labeled_examples() -> None:
    global _labeled_texts, _labeled_causes, _labeled_embeddings
    if _labeled_embeddings is not None:
        return
    examples = json.loads(LABELED_EXAMPLES_PATH.read_text(encoding="utf-8"))
    _labeled_texts = [e["text"] for e in examples]
    _labeled_causes = [RootCause(e["root_cause"]) for e in examples]
    _labeled_embeddings = _get_model().encode(_labeled_texts, normalize_embeddings=True)


def classify(error_message: str) -> RootCause | None:
    """Returns the closest RootCause if similarity clears the threshold, else None."""
    _load_labeled_examples()
    query_embedding = _get_model().encode([error_message], normalize_embeddings=True)[0]
    similarities = _labeled_embeddings @ query_embedding
    best_idx = int(np.argmax(similarities))
    if similarities[best_idx] > SIMILARITY_THRESHOLD:
        return _labeled_causes[best_idx]
    return None
