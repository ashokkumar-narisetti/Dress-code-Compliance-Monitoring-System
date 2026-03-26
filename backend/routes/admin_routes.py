"""
admin_routes.py - Endpoints accessible only by authenticated admins.

Covers:
  - Student management
  - Video upload and processing
  - Violations overview
"""

import os
import shutil
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from sqlalchemy.orm import Session

from database import get_db, settings
import models, schemas
from auth import require_admin
from services.video_service import process_video_task

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Students ───────────────────────────────────────────────────────────────────

@router.get("/students", response_model=List[schemas.StudentWithScore])
def list_students(
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Return all students with their current credit scores. Supports department filter."""
    query = db.query(models.User).filter(models.User.role == models.RoleEnum.student)
    if department:
        query = query.filter(models.User.department == department)
    students = query.all()

    result = []
    for s in students:
        credit = s.credit_score
        result.append(
            schemas.StudentWithScore(
                id=s.id,
                name=s.name,
                email=s.email,
                gender=s.gender,
                department=s.department,
                score=credit.score if credit else 100.0,
            )
        )
    return result


# ── Videos ─────────────────────────────────────────────────────────────────────

@router.post("/upload-video", response_model=schemas.VideoResponse, status_code=201)
def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    """
    Accept a video file upload, save to disk, create a DB record,
    and automatically start background processing.
    """
    os.makedirs(settings.VIDEO_DIR, exist_ok=True)
    dest = os.path.join(settings.VIDEO_DIR, f"{current_admin.id}_{file.filename}")

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    video = models.Video(
        uploaded_by=current_admin.id,
        video_path=dest,
        original_filename=file.filename,
        processing_status=models.ProcessingStatusEnum.pending,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # Kick off background processing immediately after upload
    background_tasks.add_task(process_video_task, video.id)
    return video


@router.get("/videos", response_model=List[schemas.VideoResponse])
def list_videos(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Return all uploaded videos and their processing statuses."""
    return db.query(models.Video).order_by(models.Video.upload_timestamp.desc()).all()


@router.post("/process-video/{video_id}")
def trigger_processing(
    video_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Manually trigger (or re-trigger) AI processing for a video."""
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    background_tasks.add_task(process_video_task, video_id)
    return {"message": f"Processing started for video {video_id}"}


# ── Violations ─────────────────────────────────────────────────────────────────

@router.get("/violations", response_model=List[schemas.ViolationResponse])
def list_violations(
    student_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Return all violations, optionally filtered by student_id. Paginated."""
    query = db.query(models.Violation).order_by(models.Violation.timestamp.desc())
    if student_id:
        query = query.filter(models.Violation.student_id == student_id)
    return query.offset(skip).limit(limit).all()


@router.get("/dashboard-stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Return summary statistics for the admin dashboard cards."""
    total_students = db.query(models.User).filter(models.User.role == models.RoleEnum.student).count()
    total_violations = db.query(models.Violation).count()
    total_videos = db.query(models.Video).count()
    processing = db.query(models.Video).filter(
        models.Video.processing_status == models.ProcessingStatusEnum.processing
    ).count()
    pending_appeals = db.query(models.Appeal).filter(
        models.Appeal.status == models.AppealStatusEnum.pending
    ).count()

    avg_score_row = db.query(
        models.CreditScore
    ).all()
    avg_score = (
        round(sum(c.score for c in avg_score_row) / len(avg_score_row), 1)
        if avg_score_row else 100.0
    )

    return {
        "total_students": total_students,
        "total_violations": total_violations,
        "total_videos": total_videos,
        "videos_processing": processing,
        "average_credit_score": avg_score,
        "pending_appeals": pending_appeals,
    }


# ── Manual Violation ───────────────────────────────────────────────────────────

@router.post("/violations/manual", response_model=schemas.ViolationResponse, status_code=201)
def create_manual_violation(
    body: schemas.ManualViolationCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Admin manually logs a dress-code violation for a student."""
    student = db.query(models.User).filter(
        models.User.id == body.student_id,
        models.User.role == models.RoleEnum.student,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    violation = models.Violation(
        student_id=body.student_id,
        violation_type=body.violation_type,
        score_deducted=body.score_deducted,
    )
    db.add(violation)

    # Deduct from credit score
    credit = (
        db.query(models.CreditScore)
        .filter(models.CreditScore.student_id == body.student_id)
        .first()
    )
    if credit:
        credit.score = max(0.0, credit.score - body.score_deducted)
        history_point = models.ScoreHistory(
            credit_score_id=credit.id,
            score=credit.score,
        )
        db.add(history_point)

    db.commit()
    db.refresh(violation)
    return violation
