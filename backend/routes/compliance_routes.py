"""
compliance_routes.py - Extended compliance workflow APIs.

These routes implement:
- student management with face photo embeddings
- video session processing + review workflow
- alert generation and score deduction
- student alert/appeal flow with proof upload
- analytics and policy management
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import cv2
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

import models
import schemas
from auth import require_admin, require_student
from database import get_db, settings
from services.face_service import register_face_embedding
from services.scoring_service import (
    apply_score_change,
    ensure_default_policies,
    total_deduction_for_violations,
)
from services.video_service import process_video_session_task

admin_compliance_router = APIRouter(prefix="/admin", tags=["Compliance - Admin"])
student_compliance_router = APIRouter(prefix="/student", tags=["Compliance - Student"])

ALLOWED_VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_VIDEO_BYTES = 500 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _parse_violations(raw: str) -> List[str]:
    try:
        data = json.loads(raw or "[]")
        return [str(x) for x in data]
    except Exception:
        return []


def _build_detection_response(d: models.Detection) -> schemas.DetectionResponse:
    return schemas.DetectionResponse(
        id=d.id,
        session_id=d.session_id,
        student_id=d.student_id,
        frame_path=d.frame_path,
        violations=_parse_violations(d.violations_json),
        confidence=float(d.confidence or 0.0),
        compliance_status=d.compliance_status.value if hasattr(d.compliance_status, "value") else str(d.compliance_status),
        review_status=d.review_status.value if hasattr(d.review_status, "value") else str(d.review_status),
        admin_verified=d.admin_verified,
        reviewed_by=d.reviewed_by,
        reviewed_at=d.reviewed_at,
        created_at=d.created_at,
    )


def _save_uploaded_file(upload: UploadFile, folder: str, max_bytes: int, allowed_exts: set[str]) -> str:
    os.makedirs(folder, exist_ok=True)
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    unique = f"{uuid.uuid4().hex}{ext}"
    target = os.path.join(folder, unique)
    total = 0
    with open(target, "wb") as out:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                out.close()
                os.remove(target)
                raise HTTPException(status_code=400, detail="File exceeds size limit")
            out.write(chunk)
    upload.file.close()
    return target.replace("\\", "/")


def _build_alert_message(violations: List[str], session_id: int) -> str:
    if not violations:
        return f"Dress code alert from session #{session_id}"
    joined = ", ".join(violations)
    return f"Dress code violations detected ({joined}) in session #{session_id}"


@admin_compliance_router.post("/students/register", response_model=schemas.UserResponse, status_code=201)
def register_student(
    payload: schemas.StudentRegisterRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    from auth import hash_password

    student = models.User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=models.RoleEnum.student,
        gender=payload.gender,
        department=payload.department,
    )
    db.add(student)
    db.flush()

    db.add(models.CreditScore(student_id=student.id, score=100.0))
    db.flush()

    db.add(
        models.StudentProfile(
            student_id=student.id,
            roll_no=payload.roll_no,
            year=payload.year,
        )
    )
    db.commit()
    db.refresh(student)
    return student


@admin_compliance_router.post("/students/{student_id}/face-photos", response_model=List[schemas.FacePhotoResponse])
def upload_student_face_photos(
    student_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    student = db.query(models.User).filter(models.User.id == student_id, models.User.role == models.RoleEnum.student).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if not files:
        raise HTTPException(status_code=400, detail="At least one photo is required")

    saved_records: List[models.FaceEmbedding] = []
    photos_dir = os.path.join(settings.UPLOAD_DIR, "faces", str(student_id))

    for file in files:
        path = _save_uploaded_file(file, photos_dir, MAX_IMAGE_BYTES, ALLOWED_IMAGE_EXTS)
        image = cv2.imread(path)
        if image is None:
            os.remove(path)
            raise HTTPException(status_code=400, detail="Failed to read uploaded image")
        if not register_face_embedding(db, student_id, path, image):
            os.remove(path)
            raise HTTPException(
                status_code=400,
                detail="Could not compute a face embedding (use a clear frontal face photo; on Python 3.14+ the server uses a CNN fallback if DeepFace is unavailable)",
            )

    db.commit()
    records = (
        db.query(models.FaceEmbedding)
        .filter(models.FaceEmbedding.student_id == student_id)
        .order_by(models.FaceEmbedding.created_at.desc())
        .all()
    )
    return records


@admin_compliance_router.get("/students/detail", response_model=List[schemas.StudentDetailResponse])
def list_students_detail(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    students = db.query(models.User).filter(models.User.role == models.RoleEnum.student).all()
    rows: List[schemas.StudentDetailResponse] = []
    for s in students:
        profile = (
            db.query(models.StudentProfile)
            .filter(models.StudentProfile.student_id == s.id)
            .first()
        )
        score = (
            db.query(models.CreditScore)
            .filter(models.CreditScore.student_id == s.id)
            .first()
        )
        photos_count = (
            db.query(models.FaceEmbedding)
            .filter(models.FaceEmbedding.student_id == s.id)
            .count()
        )
        rows.append(
            schemas.StudentDetailResponse(
                id=s.id,
                name=s.name,
                email=s.email,
                gender=s.gender,
                department=s.department,
                score=float(score.score if score else 100.0),
                roll_no=profile.roll_no if profile else None,
                year=profile.year if profile else None,
                face_photos=photos_count,
            )
        )
    return rows


@admin_compliance_router.post("/video-sessions/upload", response_model=schemas.VideoSessionResponse, status_code=201)
def upload_video_session(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    video_dir = os.path.join(settings.UPLOAD_DIR, "videos")
    saved_path = _save_uploaded_file(file, video_dir, MAX_VIDEO_BYTES, ALLOWED_VIDEO_EXTS)

    session = models.VideoSession(
        uploaded_by=current_admin.id,
        video_path=saved_path,
        original_filename=file.filename,
        status=models.ProcessingStatusEnum.pending,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    background_tasks.add_task(process_video_session_task, session.id)
    return session


@admin_compliance_router.get("/video-sessions", response_model=List[schemas.VideoSessionResponse])
def list_video_sessions(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    sessions = db.query(models.VideoSession).order_by(models.VideoSession.created_at.desc()).all()
    return sessions


@admin_compliance_router.get("/video-sessions/{session_id}/results", response_model=schemas.SessionResultsResponse)
def get_video_session_results(
    session_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    session = db.query(models.VideoSession).filter(models.VideoSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Video session not found")

    detections = (
        db.query(models.Detection)
        .filter(models.Detection.session_id == session_id)
        .order_by(models.Detection.created_at.desc())
        .all()
    )
    compliant = []
    non_compliant = []
    unidentified = []
    pending_review = 0
    for d in detections:
        dto = _build_detection_response(d)
        if dto.review_status == models.DetectionReviewStatusEnum.pending.value:
            pending_review += 1
        if dto.compliance_status == models.ComplianceStatusEnum.compliant.value:
            compliant.append(dto)
        elif dto.compliance_status == models.ComplianceStatusEnum.non_compliant.value:
            non_compliant.append(dto)
        else:
            unidentified.append(dto)

    return schemas.SessionResultsResponse(
        session=session,
        compliant=compliant,
        non_compliant=non_compliant,
        unidentified=unidentified,
        pending_review=pending_review,
    )


@admin_compliance_router.post("/detections/{detection_id}/review", response_model=schemas.DetectionResponse)
def review_detection(
    detection_id: int,
    body: schemas.DetectionReviewRequest,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    detection = db.query(models.Detection).filter(models.Detection.id == detection_id).first()
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    if detection.compliance_status != models.ComplianceStatusEnum.non_compliant:
        raise HTTPException(status_code=400, detail="Only non-compliant detections require review")

    action = body.action.strip().lower()
    if action not in {"confirm", "dismiss"}:
        raise HTTPException(status_code=400, detail="action must be confirm or dismiss")

    detection.review_status = (
        models.DetectionReviewStatusEnum.confirmed
        if action == "confirm"
        else models.DetectionReviewStatusEnum.dismissed
    )
    detection.admin_verified = action == "confirm"
    detection.reviewed_by = current_admin.id
    detection.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(detection)
    return _build_detection_response(detection)


@admin_compliance_router.post("/alerts/send", response_model=List[schemas.AlertResponse])
def send_alerts(
    body: schemas.SendAlertsRequest,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    ensure_default_policies(db)

    alerts_out: List[schemas.AlertResponse] = []
    for detection_id in body.detection_ids:
        detection = db.query(models.Detection).filter(models.Detection.id == detection_id).first()
        if not detection:
            continue
        if detection.student_id is None:
            continue
        if detection.review_status != models.DetectionReviewStatusEnum.confirmed:
            continue
        if detection.compliance_status != models.ComplianceStatusEnum.non_compliant:
            continue
        existing = db.query(models.Alert).filter(models.Alert.detection_id == detection_id).first()
        if existing:
            continue

        reasons = _parse_violations(detection.violations_json)
        deduction = total_deduction_for_violations(db, reasons)
        message = _build_alert_message(reasons, detection.session_id)

        alert = models.Alert(
            student_id=detection.student_id,
            detection_id=detection.id,
            message=message,
            score_deducted=deduction,
            sent_at=datetime.now(timezone.utc),
            status=models.AlertStatusEnum.pending,
        )
        db.add(alert)
        db.flush()

        apply_score_change(
            db=db,
            student_id=detection.student_id,
            amount=-deduction,
            reason=f"Confirmed violation: {', '.join(reasons) if reasons else 'Dress code violation'}",
            actor_user_id=current_admin.id,
            alert_id=alert.id,
        )

        # Keep legacy violation table populated for backward-compatible screens.
        legacy_violation_type = reasons[0] if reasons else "Dress code violation"
        db.add(
            models.Violation(
                student_id=detection.student_id,
                violation_type=legacy_violation_type.replace(" ", "_").lower(),
                evidence_image_path=detection.frame_path,
                score_deducted=deduction,
                video_id=None,
            )
        )

        alerts_out.append(
            schemas.AlertResponse(
                id=alert.id,
                student_id=alert.student_id,
                detection_id=alert.detection_id,
                message=alert.message,
                score_deducted=alert.score_deducted,
                sent_at=alert.sent_at,
                status=alert.status.value,
                is_read=alert.is_read,
                frame_path=detection.frame_path,
                violations=reasons,
            )
        )

    db.commit()
    return alerts_out


@admin_compliance_router.get("/alerts", response_model=List[schemas.AlertResponse])
def list_alerts(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    query = db.query(models.Alert).order_by(models.Alert.sent_at.desc())
    if status:
        query = query.filter(models.Alert.status == status)
    rows = query.all()
    out = []
    for a in rows:
        det = db.query(models.Detection).filter(models.Detection.id == a.detection_id).first()
        out.append(
            schemas.AlertResponse(
                id=a.id,
                student_id=a.student_id,
                detection_id=a.detection_id,
                message=a.message,
                score_deducted=a.score_deducted,
                sent_at=a.sent_at,
                status=a.status.value if hasattr(a.status, "value") else str(a.status),
                is_read=a.is_read,
                frame_path=det.frame_path if det else None,
                violations=_parse_violations(det.violations_json) if det else [],
            )
        )
    return out


@admin_compliance_router.get("/score-policies", response_model=List[schemas.ViolationPolicyResponse])
def get_score_policies(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    ensure_default_policies(db)
    return db.query(models.ViolationPolicy).order_by(models.ViolationPolicy.violation_type.asc()).all()


@admin_compliance_router.put("/score-policies", response_model=schemas.ViolationPolicyResponse)
def upsert_score_policy(
    body: schemas.ViolationPolicyUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    row = (
        db.query(models.ViolationPolicy)
        .filter(models.ViolationPolicy.violation_type == body.violation_type)
        .first()
    )
    if not row:
        row = models.ViolationPolicy(
            violation_type=body.violation_type,
            deduction_points=body.deduction_points,
            active=body.active,
        )
        db.add(row)
    else:
        row.deduction_points = body.deduction_points
        row.active = body.active
    db.commit()
    db.refresh(row)
    return row


@admin_compliance_router.get("/appeals-v2", response_model=List[schemas.AlertAppealCreateResponse])
def list_alert_appeals(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    query = db.query(models.AlertAppeal).order_by(models.AlertAppeal.created_at.desc())
    if status:
        query = query.filter(models.AlertAppeal.status == status)
    return query.all()


@admin_compliance_router.post("/appeals-v2/{appeal_id}/decide", response_model=schemas.AlertAppealCreateResponse)
def decide_alert_appeal(
    appeal_id: int,
    body: schemas.AlertAppealDecisionRequest,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    appeal = db.query(models.AlertAppeal).filter(models.AlertAppeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    if appeal.status != models.AppealStatusEnum.pending:
        raise HTTPException(status_code=409, detail="Appeal already decided")
    if body.status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be approved or rejected")

    alert = db.query(models.Alert).filter(models.Alert.id == appeal.alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Linked alert not found")

    appeal.status = models.AppealStatusEnum(body.status)
    appeal.review_note = body.review_note
    appeal.reviewed_by = current_admin.id
    appeal.reviewed_at = datetime.now(timezone.utc)

    if body.status == "approved":
        apply_score_change(
            db=db,
            student_id=appeal.student_id,
            amount=float(alert.score_deducted),
            reason=f"Appeal approved for alert #{alert.id}",
            actor_user_id=current_admin.id,
            alert_id=alert.id,
        )
    alert.status = models.AlertStatusEnum.resolved
    db.commit()
    db.refresh(appeal)
    return appeal


@admin_compliance_router.get("/analytics/compliance", response_model=schemas.AdminAnalyticsResponse)
def admin_analytics(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    total_students = db.query(models.User).filter(models.User.role == models.RoleEnum.student).count()
    total_sessions = db.query(models.VideoSession).count()
    total_detections = db.query(models.Detection).count()
    compliant_detections = db.query(models.Detection).filter(
        models.Detection.compliance_status == models.ComplianceStatusEnum.compliant
    ).count()
    non_compliant_detections = db.query(models.Detection).filter(
        models.Detection.compliance_status == models.ComplianceStatusEnum.non_compliant
    ).count()

    compliance_rate = round(
        (compliant_detections / total_detections) * 100.0,
        2,
    ) if total_detections else 0.0

    violations_by_type = {}
    for d in db.query(models.Detection).filter(
        models.Detection.compliance_status == models.ComplianceStatusEnum.non_compliant
    ).all():
        for reason in _parse_violations(d.violations_json):
            violations_by_type[reason] = violations_by_type.get(reason, 0) + 1

    return schemas.AdminAnalyticsResponse(
        total_students=total_students,
        total_sessions=total_sessions,
        total_detections=total_detections,
        compliant_detections=compliant_detections,
        non_compliant_detections=non_compliant_detections,
        compliance_rate=compliance_rate,
        violations_by_type=violations_by_type,
    )


@student_compliance_router.get("/dashboard-v2", response_model=schemas.StudentDashboardResponse)
def student_dashboard_v2(
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    score_row = (
        db.query(models.CreditScore)
        .filter(models.CreditScore.student_id == current_user.id)
        .first()
    )
    unread = db.query(models.Alert).filter(
        models.Alert.student_id == current_user.id,
        models.Alert.is_read.is_(False),
    ).count()
    pending_alerts = db.query(models.Alert).filter(
        models.Alert.student_id == current_user.id,
        models.Alert.status.in_([models.AlertStatusEnum.pending, models.AlertStatusEnum.appealed]),
    ).count()
    pending_appeals = db.query(models.AlertAppeal).filter(
        models.AlertAppeal.student_id == current_user.id,
        models.AlertAppeal.status == models.AppealStatusEnum.pending,
    ).count()
    return schemas.StudentDashboardResponse(
        student_id=current_user.id,
        score=float(score_row.score if score_row else 100.0),
        unread_alerts=unread,
        pending_alerts=pending_alerts,
        pending_appeals=pending_appeals,
    )


@student_compliance_router.get("/alerts", response_model=List[schemas.AlertResponse])
def student_alerts(
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.Alert)
        .filter(models.Alert.student_id == current_user.id)
        .order_by(models.Alert.sent_at.desc())
        .all()
    )
    out = []
    for a in rows:
        det = db.query(models.Detection).filter(models.Detection.id == a.detection_id).first()
        out.append(
            schemas.AlertResponse(
                id=a.id,
                student_id=a.student_id,
                detection_id=a.detection_id,
                message=a.message,
                score_deducted=a.score_deducted,
                sent_at=a.sent_at,
                status=a.status.value if hasattr(a.status, "value") else str(a.status),
                is_read=a.is_read,
                frame_path=det.frame_path if det else None,
                violations=_parse_violations(det.violations_json) if det else [],
            )
        )
    return out


@student_compliance_router.post("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id, models.Alert.student_id == current_user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    db.commit()
    return {"status": "ok"}


@student_compliance_router.post("/alerts/{alert_id}/appeal", response_model=schemas.AlertAppealCreateResponse)
def submit_alert_appeal(
    alert_id: int,
    justification: str = Form(...),
    proof: UploadFile | None = File(None),
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id, models.Alert.student_id == current_user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    existing = db.query(models.AlertAppeal).filter(models.AlertAppeal.alert_id == alert_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="An appeal already exists for this alert")

    proof_path = None
    if proof is not None:
        proof_dir = os.path.join(settings.UPLOAD_DIR, "appeals", str(current_user.id))
        proof_path = _save_uploaded_file(proof, proof_dir, MAX_IMAGE_BYTES, ALLOWED_IMAGE_EXTS)

    appeal = models.AlertAppeal(
        alert_id=alert_id,
        student_id=current_user.id,
        justification=justification.strip(),
        proof_path=proof_path,
        status=models.AppealStatusEnum.pending,
    )
    db.add(appeal)
    alert.status = models.AlertStatusEnum.appealed
    db.commit()
    db.refresh(appeal)
    return appeal


@student_compliance_router.get("/appeals-v2", response_model=List[schemas.AlertAppealCreateResponse])
def student_appeals_v2(
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.AlertAppeal)
        .filter(models.AlertAppeal.student_id == current_user.id)
        .order_by(models.AlertAppeal.created_at.desc())
        .all()
    )


@student_compliance_router.get("/profile/photos", response_model=List[schemas.FacePhotoResponse])
def student_face_photos(
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.FaceEmbedding)
        .filter(models.FaceEmbedding.student_id == current_user.id)
        .order_by(models.FaceEmbedding.created_at.desc())
        .all()
    )


@student_compliance_router.get("/compliance-history", response_model=List[schemas.ScoreLogResponse])
def student_compliance_history(
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.CreditScoreLog)
        .filter(models.CreditScoreLog.student_id == current_user.id)
        .order_by(models.CreditScoreLog.timestamp.desc())
        .all()
    )
