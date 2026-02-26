"""
apps/faces/views.py

Face enrollment endpoint.

POST /faces/<pk>/enroll/
    Body (multipart/form-data):
        photo      — image file (JPEG / PNG)
        embedding  — JSON array of 128 float32 values produced by face-api.js

    Returns JSON:
        200  {"status": "ok", "face_id": <int>, "embedding_length": 128}
        400  {"error": "<reason>"}
        404  {"error": "Face not found"}

The embedding is extracted entirely in the browser by face-api.js
(FaceRecognitionNet).  The server receives it as a JSON array, converts it to
a numpy float32 array, and stores the raw bytes in Face.embedding.
"""

import json

import numpy as np
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .models import Face


@login_required
@require_POST
def enroll(request, pk: int) -> JsonResponse:
    """
    Accept a photo and a pre-computed face embedding, then persist both on the
    Face record identified by *pk*.

    The embedding is expected as a JSON-encoded array of 128 float values
    (produced by face-api.js ``FaceRecognitionNet``).
    """
    face = get_object_or_404(Face, pk=pk)

    # ── validate photo ────────────────────────────────────────────────────
    photo = request.FILES.get("photo")
    if not photo:
        return JsonResponse({"error": "No photo provided."}, status=400)

    # ── validate embedding ────────────────────────────────────────────────
    embedding_raw = request.POST.get("embedding")
    if not embedding_raw:
        return JsonResponse({"error": "No embedding provided."}, status=400)

    try:
        embedding_list = json.loads(embedding_raw)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "embedding must be a JSON array."}, status=400)

    if not isinstance(embedding_list, list) or len(embedding_list) != 128:
        return JsonResponse(
            {"error": f"embedding must be a 128-element array, got {len(embedding_list)}."},
            status=400,
        )

    try:
        embedding_array = np.array(embedding_list, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        return JsonResponse({"error": f"Invalid embedding values: {exc}"}, status=400)

    # ── persist ───────────────────────────────────────────────────────────
    face.photo = photo
    face.embedding = embedding_array.tobytes()
    face.save(update_fields=["photo", "embedding", "updated_at"])

    return JsonResponse(
        {
            "status": "ok",
            "face_id": face.pk,
            "embedding_length": len(embedding_array),
        }
    )
