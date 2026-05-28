"""
vision_service.py - YOLO (dresscode.pt) inference for person crops and frames.

Uses Ultralytics YOLO. Supports detection checkpoints (boxes + class names) and
classification checkpoints trained as proper/improper (see train/train_yolo.py).
OpenCV HOG is used only to propose person boxes when the model yields no person-sized boxes.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from sqlalchemy.orm import Session

import models
from .compliance_service import evaluate_dress_code_from_classes, normalize_gender
from .face_service import extract_embedding, match_student_embedding

logger = logging.getLogger(__name__)

# Trained dresscode.pt class ids (see startup log model.names)
_DRESSCODE_GENDER_LABEL_PREFIXES = ("boy_", "girl_")

_yolo = None
_model_path_loaded: str = ""

_person_hog = None


def _dresscode_label_rules(
    label: str,
) -> Optional[Tuple[bool, List[str], Optional[bool], Optional[bool]]]:
    """
    Map trained detection class names to (compliant, violations, shirt_tucked, shoes_present).
    """
    key = label.strip().lower().replace(" ", "_")
    if key == "boy_valid":
        return True, [], True, True
    if key == "girl_valid":
        return True, [], None, True
    if key == "boy_no_shoes":
        return False, ["No shoes detected"], None, False
    if key == "boy_no_inshirt":
        return False, ["Shirt not tucked"], False, None
    if key == "boy_full_violation":
        return False, ["Shirt not tucked", "No shoes detected"], False, False
    if key == "girl_violation":
        return False, ["Dress code violation"], None, False
    return None


def _is_dresscode_style_frame(r) -> bool:
    if r is None or r.boxes is None or len(r.boxes) == 0:
        return False
    for i in range(len(r.boxes)):
        nm = str(_yolo.names[int(r.boxes.cls[i])]).lower()
        if nm.startswith(_DRESSCODE_GENDER_LABEL_PREFIXES):
            return True
    return False


def predict_best_box_label(bgr: np.ndarray) -> Tuple[Optional[str], float]:
    """Highest-confidence box class name on this BGR image."""
    r = _predict(bgr)
    if r is None or r.boxes is None or len(r.boxes) == 0:
        return None, 0.0
    best_c = -1.0
    best_name: Optional[str] = None
    for i in range(len(r.boxes)):
        cf = float(r.boxes.conf[i])
        if cf > best_c:
            best_c = cf
            best_name = str(_yolo.names[int(r.boxes.cls[i])])
    return best_name, best_c


def detect_person_instances(
    frame_bgr: np.ndarray,
) -> List[Dict]:
    """
    Each entry: {bbox (x1,y1,x2,y2), class_name, confidence}.
    For dresscode.pt, every box is one student ROI. If YOLO finds nothing, falls back to HOG with class_name=None.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return []

    r = _predict(frame_bgr)
    h, w = frame_bgr.shape[:2]
    out: List[Dict] = []

    if r and r.boxes is not None and len(r.boxes) > 0:
        dresscode_style = _is_dresscode_style_frame(r)
        names = _yolo.names
        frame_area = float(h * w)

        for i in range(len(r.boxes)):
            cid = int(r.boxes.cls[i])
            nm = str(names[cid])
            cf = float(r.boxes.conf[i])
            x1, y1, x2, y2 = map(int, r.boxes.xyxy[i].tolist())
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            area = float((x2 - x1) * (y2 - y1))
            nml = nm.lower()

            if dresscode_style:
                out.append({"bbox": (x1, y1, x2, y2), "class_name": nm, "confidence": cf})
                continue

            if (
                "person" in nml
                or nml in {"student", "man", "woman", "human", "people", "pedestrian"}
                or area >= 0.06 * frame_area
            ):
                out.append({"bbox": (x1, y1, x2, y2), "class_name": nm, "confidence": cf})

        if out:
            return out

    for bb in _hog_person_boxes(frame_bgr):
        out.append({"bbox": bb, "class_name": None, "confidence": 0.0})
    return out


def _get_person_hog():
    global _person_hog
    if _person_hog is not None:
        return _person_hog
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    _person_hog = hog
    return _person_hog


def load_dresscode_model(model_path: str) -> bool:
    """Load YOLO weights once; logs model.names for class mapping."""
    global _yolo, _model_path_loaded
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        logger.error("ultralytics is required to load dresscode.pt: %s", exc)
        _yolo = None
        return False

    if not model_path or not os.path.isfile(model_path):
        logger.error("Model path missing or not a file: %s", model_path)
        _yolo = None
        return False

    _yolo = YOLO(model_path)
    _model_path_loaded = model_path
    names = getattr(_yolo, "names", None)
    logger.info(
        "Dress code YOLO loaded: path=%s names=%s",
        model_path,
        dict(names) if isinstance(names, dict) else names,
    )
    return True


def get_yolo():
    return _yolo


def _predict(bgr: np.ndarray):
    global _yolo
    if _yolo is None:
        from database import settings
        load_dresscode_model(settings.MODEL_PATH)
    if _yolo is None or bgr is None or bgr.size == 0:
        return None
    return _yolo(bgr, verbose=False)[0]


def _hog_person_boxes(frame_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
    hog = _get_person_hog()
    rects, _weights = hog.detectMultiScale(
        frame_bgr,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.05,
    )
    h, w = frame_bgr.shape[:2]
    bboxes: List[Tuple[int, int, int, int]] = []
    for (x, y, rw, rh) in rects:
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(w, int(x + rw))
        y2 = min(h, int(y + rh))
        if (x2 - x1) < 40 or (y2 - y1) < 120:
            continue
        bboxes.append((x1, y1, x2, y2))
    return bboxes


def detect_people(frame_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Bboxes only — see detect_person_instances for YOLO class + confidence per ROI."""
    return [tuple(inst["bbox"]) for inst in detect_person_instances(frame_bgr)]


def crop_bbox(frame_bgr: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    return frame_bgr[y1:y2, x1:x2]


def extract_face_crop(person_crop_bgr: np.ndarray) -> Optional[np.ndarray]:
    """Face region for DeepFace: upper 30% of the person crop (per pipeline spec)."""
    if person_crop_bgr is None or person_crop_bgr.size == 0:
        return None
    h, w = person_crop_bgr.shape[:2]
    if h < 16 or w < 16:
        return None
    top_h = max(8, int(h * 0.3))
    region = person_crop_bgr[0:top_h, :]
    return region if region.size > 0 else None


def _compliance_from_result(r, gender: str) -> Tuple[bool, List[str], float, Optional[bool], Optional[bool]]:
    """Parse a single ultralytics Results object for one BGR crop."""
    if r is None:
        return False, ["Vision model not loaded"], 0.0, None, None

    if r.boxes is not None and len(r.boxes):
        name_list: List[str] = []
        conf_vals: List[float] = []
        for b in r.boxes:
            name_list.append(str(_yolo.names[int(b.cls)]))
            conf_vals.append(float(b.conf))
        ok, viol, tuck, shoes = evaluate_dress_code_from_classes(gender, name_list)
        conf = sum(conf_vals) / len(conf_vals) if conf_vals else 0.5
        return ok, viol, conf, tuck, shoes

    if r.probs is not None:
        top_i = int(r.probs.top1)
        raw_names = r.names
        if isinstance(raw_names, dict):
            top_name = raw_names[top_i]
        else:
            top_name = raw_names[top_i]
        conf = float(r.probs.top1conf)
        tn = str(top_name).lower()
        if any(x in tn for x in ("improper", "violation", "non_compliant", "noncompliant")):
            return False, ["Dress code non-compliance detected"], conf, None, None
        if any(x in tn for x in ("proper", "compliant")):
            return True, [], conf, None, None
        logger.debug("Unknown classification label: %s", top_name)
        return True, [], conf * 0.5, None, None

    return False, ["No model output for this crop"], 0.0, None, None


def _resolve_gender(db: Session, student_id: Optional[int], inferred: str = "unknown") -> str:
    if student_id is None:
        return inferred
    user = db.query(models.User).filter(models.User.id == student_id).first()
    if not user:
        return inferred
    return normalize_gender(user.gender) or inferred


def analyze_person_crop(
    db: Session,
    person_crop_bgr: np.ndarray,
    fallback_gender: Optional[str] = None,
    require_identity_for_dress_check: bool = True,
    frame_level_hint: Optional[Tuple[str, float]] = None,
) -> Dict:
    """
    Face match (DeepFace on upper 30% crop), then YOLO on the person crop (and optional full-frame hint).
    If require_identity_for_dress_check and no face match, returns unidentified payload (no dress scoring).
    """
    if person_crop_bgr is None or person_crop_bgr.size == 0:
        return {
            "student_id": None,
            "is_compliant": False,
            "violations": ["Invalid crop"],
            "confidence": 0.0,
            "shirt_tucked": None,
            "shoes_present": None,
            "gender": "unknown",
            "identity_confidence": 0.0,
            "unidentified": True,
        }

    face_region = extract_face_crop(person_crop_bgr)
    matched_student_id = None
    identity_confidence = 0.0
    if face_region is not None:
        emb = extract_embedding(face_region)
        if emb is not None:
            match = match_student_embedding(db, emb)
            matched_student_id = match.student_id
            identity_confidence = match.similarity

    gender = normalize_gender(fallback_gender) if fallback_gender else "unknown"
    if matched_student_id is not None:
        gender = _resolve_gender(db, matched_student_id, gender)

    if require_identity_for_dress_check and matched_student_id is None:
        return {
            "student_id": None,
            "is_compliant": True,
            "violations": [],
            "confidence": round(identity_confidence, 3),
            "shirt_tucked": None,
            "shoes_present": None,
            "gender": gender,
            "identity_confidence": round(identity_confidence, 3),
            "unidentified": True,
        }

    lbl, yconf = predict_best_box_label(person_crop_bgr)
    if lbl is None and frame_level_hint is not None:
        lbl, yconf = frame_level_hint[0], float(frame_level_hint[1])

    dc = _dresscode_label_rules(lbl) if lbl else None
    if dc is not None:
        is_compliant, reasons, shirt_tucked, shoes_present = dc
    else:
        r = _predict(person_crop_bgr)
        is_compliant, reasons, yolo_conf, shirt_tucked, shoes_present = _compliance_from_result(r, gender)
        yconf = yolo_conf

    confidence = round((yconf + identity_confidence) / 2.0, 3) if matched_student_id else round(yconf, 3)

    return {
        "student_id": matched_student_id,
        "is_compliant": is_compliant,
        "violations": reasons,
        "confidence": confidence,
        "shirt_tucked": shirt_tucked,
        "shoes_present": shoes_present,
        "gender": gender,
        "identity_confidence": round(identity_confidence, 3),
        "unidentified": False,
    }


def legacy_frame_violations(frame_bgr: np.ndarray) -> List[Dict]:
    """
    Shape-compatible with ai_service.detect_violations: list of dicts with
    class_name, confidence, bbox, score_deduction (deduction filled by caller).
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return []

    r = _predict(frame_bgr)
    out: List[Dict] = []
    h, w = frame_bgr.shape[:2]

    if r is None:
        return out

    if r.boxes is not None and len(r.boxes):
        for i in range(len(r.boxes)):
            cid = int(r.boxes.cls[i])
            name = str(_yolo.names[cid])
            nl = name.lower()
            if nl in ("boy_valid", "girl_valid"):
                continue
            conf = float(r.boxes.conf[i])
            x1, y1, x2, y2 = map(int, r.boxes.xyxy[i].tolist())
            out.append(
                {
                    "class_name": name.replace(" ", "_").lower(),
                    "confidence": round(conf, 4),
                    "bbox": [max(0, x1), max(0, y1), min(w, x2), min(h, y2)],
                    "score_deduction": 5.0,
                }
            )
        return out

    if r.probs is not None:
        top_i = int(r.probs.top1)
        raw_names = r.names
        if isinstance(raw_names, dict):
            top_name = raw_names[top_i]
        else:
            top_name = raw_names[top_i]
        conf = float(r.probs.top1conf)
        tn = str(top_name).lower()
        if any(x in tn for x in ("improper", "violation", "non_compliant", "noncompliant")):
            out.append(
                {
                    "class_name": "dress_code_violation",
                    "confidence": round(conf, 4),
                    "bbox": [0, 0, w, h],
                    "score_deduction": 5.0,
                }
            )
    return out
