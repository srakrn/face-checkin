"""
Unit tests for apps/checkin/matching.py

Covers:
- cosine_similarity: exact match, orthogonal vectors, zero-norm edge case
- find_best_match: exact match, no match (below threshold), empty face group,
  zero-norm vector edge case
"""

import numpy as np
import pytest

from apps.checkin.matching import cosine_similarity, find_best_match
from apps.faces.models import Face, FaceGroup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding(vec: list[float]) -> bytes:
    """Serialise a float list to raw float32 bytes (same as production code)."""
    return np.array(vec, dtype=np.float32).tobytes()


def _unit_vec(dim: int, index: int) -> list[float]:
    """Return a unit vector of length *dim* with a 1.0 at *index*."""
    v = [0.0] * dim
    v[index] = 1.0
    return v


# ---------------------------------------------------------------------------
# cosine_similarity — pure function tests (no DB)
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors_return_one(self):
        a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_opposite_vectors_return_minus_one(self):
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_orthogonal_vectors_return_zero(self):
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_zero_norm_a_returns_zero(self):
        a = np.array([0.0, 0.0], dtype=np.float32)
        b = np.array([1.0, 0.0], dtype=np.float32)
        assert cosine_similarity(a, b) == 0.0

    def test_zero_norm_b_returns_zero(self):
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 0.0], dtype=np.float32)
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero_norm_returns_zero(self):
        a = np.array([0.0, 0.0], dtype=np.float32)
        assert cosine_similarity(a, a) == 0.0

    def test_scaled_vectors_return_one(self):
        """Cosine similarity is scale-invariant."""
        a = np.array([2.0, 0.0], dtype=np.float32)
        b = np.array([5.0, 0.0], dtype=np.float32)
        assert cosine_similarity(a, b) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# find_best_match — DB-backed tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFindBestMatch:
    """Tests for find_best_match() against a real (test) database."""

    def _create_face_group(self, name: str = "Test Group") -> FaceGroup:
        return FaceGroup.objects.create(name=name)

    def _create_face(
        self,
        face_group: FaceGroup,
        name: str,
        embedding_vec: list[float],
    ) -> Face:
        return Face.objects.create(
            face_group=face_group,
            custom_id=name,
            name=name,
            embedding=_make_embedding(embedding_vec),
        )

    # --- exact match ---

    def test_exact_match_returns_correct_face(self):
        fg = self._create_face_group()
        vec = _unit_vec(128, 0)
        face = self._create_face(fg, "Alice", vec)

        result = find_best_match(vec, fg.pk, threshold=0.5)

        assert result is not None
        assert result.pk == face.pk

    def test_best_match_selected_among_multiple_faces(self):
        fg = self._create_face_group()
        # face_a is aligned with query; face_b is orthogonal
        face_a = self._create_face(fg, "Alice", _unit_vec(128, 0))
        _face_b = self._create_face(fg, "Bob", _unit_vec(128, 1))

        query = _unit_vec(128, 0)
        result = find_best_match(query, fg.pk, threshold=0.5)

        assert result is not None
        assert result.pk == face_a.pk

    # --- no match (below threshold) ---

    def test_no_match_when_similarity_below_threshold(self):
        fg = self._create_face_group()
        # Store a vector along axis 1; query along axis 0 → similarity = 0
        self._create_face(fg, "Alice", _unit_vec(128, 1))

        query = _unit_vec(128, 0)
        result = find_best_match(query, fg.pk, threshold=0.5)

        assert result is None

    def test_threshold_boundary_exact_match(self):
        """A similarity exactly equal to the threshold should match."""
        fg = self._create_face_group()
        # Two equal unit vectors → similarity = 1.0; threshold = 1.0 should still match
        vec = _unit_vec(128, 0)
        face = self._create_face(fg, "Alice", vec)

        result = find_best_match(vec, fg.pk, threshold=1.0)

        assert result is not None
        assert result.pk == face.pk

    # --- empty face group ---

    def test_empty_face_group_returns_none(self):
        fg = self._create_face_group()
        query = _unit_vec(128, 0)

        result = find_best_match(query, fg.pk, threshold=0.5)

        assert result is None

    def test_face_group_with_no_embeddings_returns_none(self):
        """Faces without embeddings should be ignored."""
        fg = self._create_face_group()
        # Create a face with no embedding
        Face.objects.create(face_group=fg, name="NoEmbed", embedding=None)

        query = _unit_vec(128, 0)
        result = find_best_match(query, fg.pk, threshold=0.5)

        assert result is None

    # --- zero-norm vector edge case ---

    def test_zero_norm_query_returns_none(self):
        """A zero-norm query vector should never match (similarity = 0.0)."""
        fg = self._create_face_group()
        self._create_face(fg, "Alice", _unit_vec(128, 0))

        zero_query = [0.0] * 128
        result = find_best_match(zero_query, fg.pk, threshold=0.5)

        assert result is None

    def test_zero_norm_stored_embedding_returns_none(self):
        """A stored zero-norm embedding should never match."""
        fg = self._create_face_group()
        self._create_face(fg, "ZeroFace", [0.0] * 128)

        query = _unit_vec(128, 0)
        result = find_best_match(query, fg.pk, threshold=0.5)

        assert result is None

    # --- uses settings threshold when none provided ---

    def test_uses_settings_threshold_when_not_specified(self, settings):
        settings.FACE_MATCH_THRESHOLD = 0.99
        fg = self._create_face_group()
        # Orthogonal vectors → similarity = 0.0, well below 0.99
        self._create_face(fg, "Alice", _unit_vec(128, 1))

        query = _unit_vec(128, 0)
        result = find_best_match(query, fg.pk)  # no explicit threshold

        assert result is None
