"""
auth_routes.py - Authentication endpoints.

POST /auth/login   → returns JWT token
POST /auth/register → creates a new user (admin use only in production)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models, schemas, auth as auth_utils

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user and return a JWT access token."""
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not auth_utils.verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = auth_utils.create_access_token({"sub": str(user.id), "role": user.role.value})
    return schemas.TokenResponse(
        access_token=token,
        role=user.role.value,
        user_id=user.id,
        name=user.name,
    )


@router.post("/register", response_model=schemas.UserResponse, status_code=201)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    In production, restrict this endpoint to admins only.
    """
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        name=payload.name,
        email=payload.email,
        password_hash=auth_utils.hash_password(payload.password),
        role=payload.role,
        gender=payload.gender,
        department=payload.department,
    )
    db.add(user)
    db.flush()  # get user.id before commit

    # Create initial credit score for students
    if user.role == models.RoleEnum.student:
        score = models.CreditScore(student_id=user.id, score=100.0)
        db.add(score)
        db.flush()
        # Add initial history point
        history = models.ScoreHistory(credit_score_id=score.id, score=100.0)
        db.add(history)

    db.commit()
    db.refresh(user)
    return user
