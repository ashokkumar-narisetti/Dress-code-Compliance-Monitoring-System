"""
appeal_routes.py - Endpoints for the student appeal system.

Student routes (prefix /student):
  POST /student/appeals        - submit an appeal for a violation
  GET  /student/appeals        - list own appeals

Admin routes (prefix /admin):
  GET  /admin/appeals          - list all appeals (filterable by status)
  POST /admin/appeals/{id}/decide - approve or reject an appeal
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import require_student, require_admin

student_appeal_router = APIRouter(prefix="/student", tags=["Appeals - Student"])
admin_appeal_router   = APIRouter(prefix="/admin",   tags=["Appeals - Admin"])


# ── Student: submit appeal ─────────────────────────────────────────────────────

@student_appeal_router.post("/appeals", response_model=schemas.AppealResponse, status_code=201)
def submit_appeal(
    body: schemas.AppealCreate,
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Student submits an appeal for one of their violations."""
    # Verify the violation belongs to this student
    violation = (
        db.query(models.Violation)
        .filter(
            models.Violation.id == body.violation_id,
            models.Violation.student_id == current_user.id,
        )
        .first()
    )
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found or does not belong to you")

    # Only one appeal per violation
    existing = (
        db.query(models.Appeal)
        .filter(models.Appeal.violation_id == body.violation_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="An appeal already exists for this violation")

    appeal = models.Appeal(
        violation_id=body.violation_id,
        student_id=current_user.id,
        reason=body.reason,
    )
    db.add(appeal)
    db.commit()
    db.refresh(appeal)
    return appeal


@student_appeal_router.get("/appeals", response_model=List[schemas.AppealResponse])
def list_my_appeals(
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Return all appeals submitted by the logged-in student."""
    return (
        db.query(models.Appeal)
        .filter(models.Appeal.student_id == current_user.id)
        .order_by(models.Appeal.created_at.desc())
        .all()
    )


# ── Admin: manage appeals ─────────────────────────────────────────────────────

@admin_appeal_router.get("/appeals", response_model=List[schemas.AppealResponse])
def list_all_appeals(
    status: Optional[str] = Query(None, description="Filter by status: pending|approved|rejected"),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Return all appeals, optionally filtered by status."""
    query = db.query(models.Appeal).order_by(models.Appeal.created_at.desc())
    if status:
        query = query.filter(models.Appeal.status == status)
    return query.all()


@admin_appeal_router.post("/appeals/{appeal_id}/decide", response_model=schemas.AppealResponse)
def decide_appeal(
    appeal_id: int,
    body: schemas.AppealDecide,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """
    Admin approves or rejects an appeal.
    On approval, the deducted points are restored to the student's credit score
    and a new ScoreHistory record is written.
    """
    if body.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")

    appeal = db.query(models.Appeal).filter(models.Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    if appeal.status != "pending":
        raise HTTPException(status_code=409, detail="Appeal has already been decided")

    appeal.status     = body.status
    appeal.admin_note = body.admin_note
    appeal.decided_at = datetime.now(timezone.utc)

    if body.status == "approved":
        # Restore the deducted points
        credit = (
            db.query(models.CreditScore)
            .filter(models.CreditScore.student_id == appeal.student_id)
            .first()
        )
        if credit:
            violation = db.query(models.Violation).filter(
                models.Violation.id == appeal.violation_id
            ).first()
            restored = violation.score_deducted if violation else 0
            credit.score = min(100.0, credit.score + restored)

            # Log to history
            history_point = models.ScoreHistory(
                credit_score_id=credit.id,
                score=credit.score,
            )
            db.add(history_point)

    db.commit()
    db.refresh(appeal)
    return appeal
