"""
scoring_service.py - Credit score updates and audit logging.
"""

from __future__ import annotations

from typing import Iterable, List

from sqlalchemy.orm import Session

import models


DEFAULT_POLICY_POINTS = {
    "Shirt not tucked": 5.0,
    " shoes detected": 5.0,
    "Dress code non-compliance detected": 5.0,
    "dress_code_violation": 5.0,
}


def ensure_default_policies(db: Session) -> None:
    for violation_type, points in DEFAULT_POLICY_POINTS.items():
        exists = (
            db.query(models.ViolationPolicy)
            .filter(models.ViolationPolicy.violation_type == violation_type)
            .first()
        )
        if not exists:
            db.add(
                models.ViolationPolicy(
                    violation_type=violation_type,
                    deduction_points=points,
                    active=True,
                )
            )
    db.commit()


def get_policy_points(db: Session, violation_type: str) -> float:
    row = (
        db.query(models.ViolationPolicy)
        .filter(
            models.ViolationPolicy.violation_type == violation_type,
            models.ViolationPolicy.active.is_(True),
        )
        .first()
    )
    if row:
        return float(row.deduction_points)
    return float(DEFAULT_POLICY_POINTS.get(violation_type, 5.0))


def total_deduction_for_violations(db: Session, violations: Iterable[str]) -> float:
    return float(sum(get_policy_points(db, v) for v in violations))


def _get_or_create_credit_score(db: Session, student_id: int) -> models.CreditScore:
    score = (
        db.query(models.CreditScore)
        .filter(models.CreditScore.student_id == student_id)
        .first()
    )
    if score:
        return score
    score = models.CreditScore(student_id=student_id, score=100.0)
    db.add(score)
    db.flush()
    db.add(models.ScoreHistory(credit_score_id=score.id, score=score.score))
    return score


def apply_score_change(
    db: Session,
    student_id: int,
    amount: float,
    reason: str,
    actor_user_id: int | None = None,
    alert_id: int | None = None,
) -> float:
    """
    Positive amount restores points. Negative amount deducts points.
    Returns the new score.
    """
    score = _get_or_create_credit_score(db, student_id)
    new_score = max(0.0, min(100.0, score.score + amount))
    score.score = new_score

    db.add(models.ScoreHistory(credit_score_id=score.id, score=new_score))
    db.add(
        models.CreditScoreLog(
            student_id=student_id,
            change_amount=amount,
            reason=reason,
            actor_user_id=actor_user_id,
            alert_id=alert_id,
        )
    )
    db.flush()
    return new_score
