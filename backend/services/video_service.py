"""
video_service.py - Video processing orchestration.

This file keeps the legacy processor for backward compatibility and adds the
new compliance session pipeline used by admin verification + alerts workflow.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

import cv2
from sqlalchemy.orm import Session

import ai_service
import models
from database import SessionLocal, settings
from .compliance_service import majority_vote_frame_results
from .vision_service import analyze_person_crop, crop_bbox, detect_person_instances

logger = logging.getLogger(__name__)


def _safe_name(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text)[:64]


def _save_evidence_image(
    session_id: int,
    frame_number: int,
    person_index: int,
    person_crop,
) -> str:
    os.makedirs(settings.EVIDENCE_DIR, exist_ok=True)
    filename = f"session_{session_id}_frame_{frame_number}_p{person_index}_{int(time.time()*1000)}.jpg"
    out_path = os.path.join(settings.EVIDENCE_DIR, filename)
    cv2.imwrite(out_path, person_crop)
    return out_path.replace("\\", "/")


def _status_for_result(is_compliant: bool) -> models.ComplianceStatusEnum:
    return (
        models.ComplianceStatusEnum.compliant
        if is_compliant
        else models.ComplianceStatusEnum.non_compliant
    )


def process_video_session_task(session_id: int) -> None:
    """
    New workflow processor:
    - Samples frames
    - Detects persons
    - Tries face identification
    - Runs dress-code checks
    - Aggregates by student using majority vote
    - Stores Detection records for admin review
    """
    # ── Ensure YOLO model is loaded (guard against hot-reload clearing module state) ──
    from services.vision_service import get_yolo, load_dresscode_model
    if get_yolo() is None:
        logger.warning("YOLO model not loaded at task start — reloading from settings.MODEL_PATH")
        ok = load_dresscode_model(settings.MODEL_PATH)
        if not ok:
            logger.error("Failed to load YOLO model from %s — detections will be empty.", settings.MODEL_PATH)
        else:
            logger.info("YOLO model reloaded successfully for session %s", session_id)

    db = SessionLocal()
    try:
        session = db.query(models.VideoSession).filter(models.VideoSession.id == session_id).first()
        if not session:
            logger.error("VideoSession %s not found.", session_id)
            return

        session.status = models.ProcessingStatusEnum.processing
        db.commit()

        cap = cv2.VideoCapture(session.video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Unable to open video: {session.video_path}")

        # Clear existing detections when re-processing.
        db.query(models.Detection).filter(models.Detection.session_id == session_id).delete()
        db.commit()

        observations_by_student: Dict[int, List[Dict]] = defaultdict(list)
        unidentified_observations: List[Dict] = []  # dress-check skipped entirely
        unknown_person_observations: List[Dict] = []  # dress-checked but no face match

        frame_idx = 0
        sample_every = max(1, int(settings.FRAMES_INTERVAL))
        temp_dir = os.path.join(settings.TEMP_FRAMES_DIR, f"session_{session_id}")
        os.makedirs(temp_dir, exist_ok=True)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_every != 0:
                frame_idx += 1
                continue

            cv2.imwrite(
                os.path.join(temp_dir, f"frame_{frame_idx}.jpg"),
                frame,
            )

            instances = detect_person_instances(frame)
            if not instances:
                h, w = frame.shape[:2]
                instances = [{"bbox": (0, 0, w, h), "class_name": None, "confidence": 0.0}]

            for person_index, inst in enumerate(instances):
                bbox = inst["bbox"]
                person_crop = crop_bbox(frame, bbox)
                hint = (
                    (inst["class_name"], float(inst["confidence"]))
                    if inst.get("class_name")
                    else None
                )
                analysis = analyze_person_crop(db, person_crop, frame_level_hint=hint, require_identity_for_dress_check=False)
                frame_path = _save_evidence_image(session_id, frame_idx, person_index, person_crop)
                record = {
                    "is_compliant": analysis["is_compliant"],
                    "violations": analysis["violations"],
                    "confidence": analysis["confidence"],
                    "frame_path": frame_path,
                }

                if analysis.get("unidentified"):
                    # Dress-code check was skipped entirely (identity required); auto-dismiss.
                    unidentified_observations.append(
                        {
                            "is_compliant": False,
                            "violations": ["Unidentified person"],
                            "confidence": float(analysis.get("confidence", 0.0)),
                            "frame_path": frame_path,
                        }
                    )
                elif analysis["student_id"] is not None:
                    # Dress-code check ran AND student identified — add to per-student queue.
                    observations_by_student[analysis["student_id"]].append(record)
                else:
                    # Dress-code check ran but no face match — save for pending review.
                    unknown_person_observations.append(record)

            frame_idx += 1

        cap.release()

        for student_id, observations in observations_by_student.items():
            aggregated = majority_vote_frame_results(observations)
            compliance_status = _status_for_result(aggregated["is_compliant"])
            review_status = (
                models.DetectionReviewStatusEnum.confirmed
                if aggregated["is_compliant"]
                else models.DetectionReviewStatusEnum.pending
            )
            admin_verified = True if aggregated["is_compliant"] else None

            db.add(
                models.Detection(
                    session_id=session_id,
                    student_id=student_id,
                    frame_path=aggregated["frame_path"],
                    violations_json=json.dumps(aggregated["violations"]),
                    confidence=aggregated["confidence"],
                    compliance_status=compliance_status,
                    review_status=review_status,
                    admin_verified=admin_verified,
                )
            )

        # Unknown persons: dress-checked but no face match — save as pending non-compliant
        # (or compliant) so admin can see violations in the Review tab.
        for obs in unknown_person_observations:
            compliance_status = _status_for_result(obs["is_compliant"])
            review_status = (
                models.DetectionReviewStatusEnum.confirmed
                if obs["is_compliant"]
                else models.DetectionReviewStatusEnum.pending
            )
            db.add(
                models.Detection(
                    session_id=session_id,
                    student_id=None,
                    frame_path=obs["frame_path"],
                    violations_json=json.dumps(obs.get("violations", [])),
                    confidence=obs["confidence"],
                    compliance_status=compliance_status,
                    review_status=review_status,
                    admin_verified=True if obs["is_compliant"] else None,
                )
            )

        # Truly unidentified (dress-check skipped) — auto-dismiss.
        for obs in unidentified_observations:
            db.add(
                models.Detection(
                    session_id=session_id,
                    student_id=None,
                    frame_path=obs["frame_path"],
                    violations_json=json.dumps(obs.get("violations", ["Unidentified person"])),
                    confidence=obs["confidence"],
                    compliance_status=models.ComplianceStatusEnum.unidentified,
                    review_status=models.DetectionReviewStatusEnum.dismissed,
                    admin_verified=False,
                )
            )

        session.status = models.ProcessingStatusEnum.completed
        session.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "VideoSession %s completed: %s identified students, %s unknown-person observations, %s truly-unidentified.",
            session_id,
            len(observations_by_student),
            len(unknown_person_observations),
            len(unidentified_observations),
        )
    except Exception as exc:
        logger.exception("Error processing VideoSession %s: %s", session_id, exc)
        session = db.query(models.VideoSession).filter(models.VideoSession.id == session_id).first()
        if session:
            session.status = models.ProcessingStatusEnum.failed
            session.processed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def process_video_task(video_id: int, db: Session | None = None) -> None:
    """
    Legacy processor retained for backward compatibility with existing routes.
    """
    owns_session = db is None
    if db is None:
        db = SessionLocal()

    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        logger.error("Video %s not found.", video_id)
        if owns_session:
            db.close()
        return

    video.processing_status = models.ProcessingStatusEnum.processing
    db.commit()

    try:
        results = ai_service.process_video(
            video_path=video.video_path,
            evidence_dir=settings.EVIDENCE_DIR,
            frames_interval=settings.FRAMES_INTERVAL,
        )

        for frame_result in results:
            for detection in frame_result["violations"]:
                assigned_student_id = detection.get("student_id")
                if assigned_student_id is None:
                    continue

                violation = models.Violation(
                    student_id=assigned_student_id,
                    violation_type=detection["class_name"],
                    evidence_image_path=detection.get("evidence_image_path"),
                    score_deducted=detection["score_deduction"],
                    video_id=video_id,
                )
                db.add(violation)

        db.commit()
        video.processing_status = models.ProcessingStatusEnum.completed
        db.commit()
    except Exception as exc:
        logger.exception("Error processing legacy video %s: %s", video_id, exc)
        video.processing_status = models.ProcessingStatusEnum.failed
        db.commit()
    finally:
        if owns_session:
            db.close()
