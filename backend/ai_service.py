"""
ai_service.py - Legacy video processor integration.

Loads dresscode.pt via vision_service and exposes frame-level violation lists for
the older Video + Violation workflow. New compliance sessions use video_service
directly with the same YOLO weights.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import cv2

from services import vision_service

logger = logging.getLogger(__name__)


def load_model(model_path: str) -> bool:
    return vision_service.load_dresscode_model(model_path)


def detect_violations(frame) -> List[Dict[str, Any]]:
    if frame is None or not hasattr(frame, "shape") or frame.size == 0:
        return []
    return vision_service.legacy_frame_violations(frame)


def identify_student(face_crop) -> Optional[int]:
    """Legacy hook — identification is handled in vision_service / DB-backed pipeline."""
    return None


def extract_face_crop(frame, bbox: List[int]):
    x1, y1, x2, y2 = [int(v) for v in bbox]
    if hasattr(frame, "__getitem__"):
        return frame[y1:y2, x1:x2]
    return None


def process_video(
    video_path: str,
    evidence_dir: str,
    frames_interval: int = 30,
) -> List[Dict[str, Any]]:
    os.makedirs(evidence_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("Cannot open video: %s", video_path)
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    all_results: List[Dict[str, Any]] = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % max(1, frames_interval) == 0:
            violations = detect_violations(frame)
            for v in violations:
                safe_cls = str(v["class_name"]).replace(" ", "_")
                evidence_filename = f"frame_{frame_idx}_{safe_cls}_{int(time.time())}.jpg"
                evidence_path = os.path.join(evidence_dir, evidence_filename)
                x1, y1, x2, y2 = v["bbox"]
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                crop = frame[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else frame
                cv2.imwrite(evidence_path, crop)
                v["evidence_image_path"] = evidence_path
                face_crop = extract_face_crop(frame, v["bbox"])
                v["student_id"] = identify_student(face_crop)

            if violations:
                all_results.append(
                    {
                        "frame_number": frame_idx,
                        "timestamp_sec": round(frame_idx / fps, 2),
                        "violations": violations,
                    }
                )

        frame_idx += 1

    cap.release()
    logger.info("Processed %s frames, %s frames with detections.", frame_idx, len(all_results))
    return all_results
