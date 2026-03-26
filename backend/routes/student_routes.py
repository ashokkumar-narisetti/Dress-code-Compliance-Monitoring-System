"""
student_routes.py - Endpoints accessible only by authenticated students.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models, schemas
from auth import require_student

router = APIRouter(prefix="/student", tags=["Student"])


@router.get("/me", response_model=schemas.UserResponse)
def get_my_profile(
    current_user: models.User = Depends(require_student),
):
    """Return the logged-in student's profile."""
    return current_user


@router.get("/score")
def get_my_score(
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Return the student's current credit score."""
    credit = (
        db.query(models.CreditScore)
        .filter(models.CreditScore.student_id == current_user.id)
        .first()
    )
    if not credit:
        raise HTTPException(status_code=404, detail="Credit score record not found")
    return {"student_id": current_user.id, "score": credit.score}


@router.get("/score-history", response_model=List[schemas.ScoreHistoryPoint])
def get_score_history(
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Return the full score history for the student dashboard graph."""
    credit = (
        db.query(models.CreditScore)
        .filter(models.CreditScore.student_id == current_user.id)
        .first()
    )
    if not credit:
        return []
    history = (
        db.query(models.ScoreHistory)
        .filter(models.ScoreHistory.credit_score_id == credit.id)
        .order_by(models.ScoreHistory.recorded_at.asc())
        .all()
    )
    return history


@router.get("/violations", response_model=List[schemas.ViolationResponse])
def get_my_violations(
    current_user: models.User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Return all violations recorded for this student."""
    violations = (
        db.query(models.Violation)
        .filter(models.Violation.student_id == current_user.id)
        .order_by(models.Violation.timestamp.desc())
        .all()
    )
    return violations
