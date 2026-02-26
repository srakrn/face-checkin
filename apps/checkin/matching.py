"""
Face embedding matching utilities.

Embeddings are stored as raw float32 bytes (numpy.ndarray.tobytes()).
Matching uses cosine similarity; a configurable threshold determines match/no-match.
"""

from __future__ import annotations

import numpy as np
from django.conf import settings

from apps.faces.models import Face


def _deserialise(embedding_bytes: bytes) -> np.ndarray:
    """Convert raw bytes back to a float32 numpy array."""
    return np.frombuffer(embedding_bytes, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity in [0, 1] between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_best_match(
    query_embedding: list[float],
    face_group_id: int,
    threshold: float | None = None,
) -> Face | None:
    """
    Compare *query_embedding* against all faces in *face_group_id*.

    Returns the best-matching :class:`~apps.faces.models.Face` if the
    similarity exceeds *threshold*, otherwise ``None``.
    """
    if threshold is None:
        threshold = getattr(settings, "FACE_MATCH_THRESHOLD", 0.6)

    query_vec = np.array(query_embedding, dtype=np.float32)

    faces = Face.objects.filter(
        face_group_id=face_group_id,
        embedding__isnull=False,
    )

    best_face: Face | None = None
    best_score: float = -1.0

    for face in faces:
        stored_vec = _deserialise(bytes(face.embedding))
        score = cosine_similarity(query_vec, stored_vec)
        if score > best_score:
            best_score = score
            best_face = face

    if best_score >= threshold:
        return best_face
    return None


def find_top_matches(
    query_embedding: list[float],
    face_group_id: int,
    top_n: int = 5,
) -> list[dict]:
    """
    Compare *query_embedding* against all faces in *face_group_id* and return
    the top *top_n* results sorted by descending cosine similarity.

    Each entry in the returned list is a dict::

        {
            "face":       Face instance,
            "similarity": float,   # cosine similarity in [-1, 1]
        }

    No threshold is applied — all faces are ranked and the top *top_n* are
    returned regardless of score.
    """
    query_vec = np.array(query_embedding, dtype=np.float32)

    faces = Face.objects.filter(
        face_group_id=face_group_id,
        embedding__isnull=False,
    )

    scored: list[tuple[float, Face]] = []
    for face in faces:
        stored_vec = _deserialise(bytes(face.embedding))
        score = cosine_similarity(query_vec, stored_vec)
        scored.append((score, face))

    scored.sort(key=lambda t: t[0], reverse=True)

    return [{"face": face, "similarity": score} for score, face in scored[:top_n]]
