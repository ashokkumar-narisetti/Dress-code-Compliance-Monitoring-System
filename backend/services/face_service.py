"""
face_service.py - Face embeddings and matching.

1) DeepFace + ArcFace when importable (TensorFlow available; typical on Python 3.11–3.12).
2) Torchvision ResNet18 feature vector (ImageNet backbone, identity head removed) — always available
   where torch/torchvision are installed (e.g. Python 3.14). Real CNN features, not random mocks.

Cosine distance threshold 0.40 (lower = more similar) on L2-normalized embeddings.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from sqlalchemy.orm import Session

import models

logger = logging.getLogger(__name__)

_deepface = None
_torch_backbone = None
_face_cascade = None

COSINE_DISTANCE_THRESHOLD = 0.40


def _get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return _face_cascade


def _get_torch_backbone():
    """ResNet18 up to global pool → 512-D embedding (eval mode, no gradients)."""
    global _torch_backbone
    if _torch_backbone is not None:
        return _torch_backbone
    import torch
    import torch.nn as nn
    import torchvision.models as tvm

    weights = tvm.ResNet18_Weights.IMAGENET1K_V1
    m = tvm.resnet18(weights=weights)
    m.fc = nn.Identity()
    m.eval()
    _torch_backbone = m
    logger.info("Torch ResNet18 backbone loaded for face embeddings (DeepFace unavailable).")
    return _torch_backbone


def _lazy_load_deepface():
    global _deepface
    if _deepface is not None:
        return _deepface
    try:
        from deepface import DeepFace

        _deepface = DeepFace
        logger.info("DeepFace import OK (ArcFace will load on first use).")
    except Exception as exc:
        logger.info("DeepFace not used (%s); using OpenCV SFace.", exc)
        _deepface = False
    return _deepface


def _to_unit(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    a = _to_unit(vec1.astype(np.float32).flatten())
    b = _to_unit(vec2.astype(np.float32).flatten())
    return float(np.dot(a, b))


def cosine_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
    return 1.0 - cosine_similarity(vec1, vec2)


def _deepface_embedding(face_bgr: np.ndarray) -> Optional[np.ndarray]:
    deepface = _lazy_load_deepface()
    if not deepface or deepface is False:
        return None
    try:
        reps = deepface.represent(
            img_path=face_bgr,
            model_name="ArcFace",
            detector_backend="opencv",
            enforce_detection=False,
        )
        if reps and isinstance(reps, list):
            emb = np.array(reps[0]["embedding"], dtype=np.float32)
            return _to_unit(emb)
    except Exception as exc:
        logger.debug("DeepFace.represent failed: %s", exc)
    tmp_path: Optional[str] = None
    try:
        tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp_path = tmp_file.name
        tmp_file.write(cv2.imencode(".jpg", face_bgr)[1].tobytes())
        tmp_file.close()
        reps = deepface.represent(
            img_path=tmp_path,
            model_name="ArcFace",
            detector_backend="opencv",
            enforce_detection=False,
        )
        if reps and isinstance(reps, list):
            emb = np.array(reps[0]["embedding"], dtype=np.float32)
            return _to_unit(emb)
    except Exception as exc2:
        logger.debug("DeepFace temp-file represent failed: %s", exc2)
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
    return None


def _torch_resnet_embedding(face_bgr: np.ndarray) -> Optional[np.ndarray]:
    """512-D ResNet18 image embedding (ImageNet). Haar crop when possible."""
    if face_bgr is None or face_bgr.size == 0:
        return None
    import torch
    from torchvision import transforms

    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    rects = _get_face_cascade().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(32, 32))
    if len(rects) == 0:
        crop = face_bgr
    else:
        x, y, w, h = max(rects, key=lambda r: r[2] * r[3])
        crop = face_bgr[y : y + h, x : x + w]
    if crop.size == 0:
        return None

    rgb = cv2.cvtColor(cv2.resize(crop, (224, 224)), cv2.COLOR_BGR2RGB)
    t = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0
    t = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])(t).unsqueeze(0)
    model = _get_torch_backbone()
    with torch.no_grad():
        out = model(t)
    vec = out.squeeze().cpu().numpy().astype(np.float32)
    return _to_unit(vec)


def extract_embedding(face_bgr: np.ndarray) -> Optional[np.ndarray]:
    if face_bgr is None or face_bgr.size == 0:
        return None
    emb = _deepface_embedding(face_bgr)
    if emb is not None:
        return emb
    return _torch_resnet_embedding(face_bgr)


def serialize_embedding(embedding: np.ndarray) -> str:
    return json.dumps([float(x) for x in embedding.flatten().tolist()])


def parse_embedding(raw: str) -> Optional[np.ndarray]:
    try:
        data = json.loads(raw)
        return np.array(data, dtype=np.float32)
    except Exception:
        return None


@dataclass
class FaceMatch:
    student_id: Optional[int]
    similarity: float


def match_student_embedding(
    db: Session,
    embedding: np.ndarray,
    max_cosine_distance: float = COSINE_DISTANCE_THRESHOLD,
) -> FaceMatch:
    best_id: Optional[int] = None
    best_similarity = -1.0
    best_distance = float("inf")

    for record in db.query(models.FaceEmbedding).all():
        db_vec = parse_embedding(record.embedding_vector)
        if db_vec is None:
            continue
        dist = cosine_distance(embedding, db_vec)
        sim = cosine_similarity(embedding, db_vec)
        if dist < best_distance:
            best_distance = dist
            best_similarity = sim
            best_id = record.student_id

    if best_id is not None and best_distance <= max_cosine_distance:
        return FaceMatch(student_id=best_id, similarity=best_similarity)
    return FaceMatch(student_id=None, similarity=max(best_similarity, 0.0))


def register_face_embedding(
    db: Session,
    student_id: int,
    photo_path: str,
    face_bgr: np.ndarray,
) -> bool:
    embedding = extract_embedding(face_bgr)
    if embedding is None:
        return False

    db.add(
        models.FaceEmbedding(
            student_id=student_id,
            embedding_vector=serialize_embedding(embedding),
            photo_path=photo_path,
        )
    )
    return True
