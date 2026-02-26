"""
Check-in API views.

POST /api/checkin/match/
    Body (multipart/form-data):
        session_id  — int
        embedding   — JSON array of floats (128-d face-api.js descriptor)
        face_image  — image file (raw face crop)

GET /api/sessions/<pk>/embeddings/
    Returns all embeddings for the session's face group (for client-side caching).
"""

import json

from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.sessions.models import Session

from .matching import find_best_match, find_top_matches
from .models import CheckIn


@csrf_exempt
@require_POST
def checkin_match(request):
    """
    Receive a face embedding + raw image, match against the session's face group,
    log the check-in, and return the result.
    """
    try:
        session_id = int(request.POST.get("session_id", ""))
    except (TypeError, ValueError):
        return JsonResponse({"error": "session_id is required and must be an integer."}, status=400)

    embedding_raw = request.POST.get("embedding", "")
    try:
        embedding = json.loads(embedding_raw)
        if not isinstance(embedding, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "embedding must be a JSON array of floats."}, status=400)

    face_image = request.FILES.get("face_image")
    if face_image is None:
        return JsonResponse({"error": "face_image is required."}, status=400)

    session = get_object_or_404(Session, pk=session_id)

    if session.state != Session.State.ACTIVE:
        return JsonResponse({"error": "Session is not active."}, status=409)

    # Auto-close check
    if session.should_auto_close:
        session.close()
        return JsonResponse({"error": "Session has been automatically closed."}, status=409)

    face_group_id = session.klass.face_group_id
    matched_face = find_best_match(embedding, face_group_id)

    # Compute top-5 matches (always, for display purposes)
    top_matches = find_top_matches(embedding, face_group_id, top_n=5)
    top_matches_data = [
        {
            "face_id": entry["face"].pk,
            "custom_id": entry["face"].custom_id,
            "name": entry["face"].name,
            "similarity": round(entry["similarity"], 4),
        }
        for entry in top_matches
    ]

    # Determine if this is a duplicate check-in within the session
    already_checked_in = False
    if matched_face is not None:
        already_checked_in = CheckIn.objects.filter(
            session=session,
            face=matched_face,
            matched=True,
        ).exists()

    # Always log the attempt
    checkin = CheckIn(
        session=session,
        face=matched_face,
        matched=matched_face is not None,
    )
    checkin.raw_face_image.save(
        f"checkin_{session_id}_{checkin.pk or 'new'}.jpg",
        face_image,
        save=False,
    )
    checkin.save()

    if matched_face is not None:
        return JsonResponse(
            {
                "matched": True,
                "already_checked_in": already_checked_in,
                "face": {
                    "id": matched_face.pk,
                    "custom_id": matched_face.custom_id,
                    "name": matched_face.name,
                },
                "checkin_id": checkin.pk,
                "top_matches": top_matches_data,
            }
        )
    else:
        return JsonResponse(
            {
                "matched": False,
                "already_checked_in": False,
                "checkin_id": checkin.pk,
                "top_matches": top_matches_data,
            }
        )


@require_GET
def session_embeddings(request, pk: int):
    """
    GET /api/sessions/<pk>/embeddings/
    Return all face embeddings for the session's face group.
    Useful for client-side caching / offline matching.
    """
    session = get_object_or_404(Session, pk=pk)
    faces = session.klass.face_group.faces.filter(embedding__isnull=False)

    import numpy as np

    data = []
    for face in faces:
        vec = list(
            map(float, __import__("numpy").frombuffer(bytes(face.embedding), dtype="float32"))
        )
        data.append(
            {
                "face_id": face.pk,
                "custom_id": face.custom_id,
                "name": face.name,
                "embedding": vec,
            }
        )

    return JsonResponse({"session_id": pk, "embeddings": data})
