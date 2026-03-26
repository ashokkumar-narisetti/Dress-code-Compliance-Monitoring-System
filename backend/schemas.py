"""
schemas.py - Pydantic models for request validation and response serialization.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────────

class RoleEnum(str, Enum):
    admin = "admin"
    student = "student"


class ProcessingStatusEnum(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# ── Auth ───────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    name: str


# ── User ───────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.student
    gender: Optional[str] = None
    department: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    gender: Optional[str]
    department: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Credit Score ───────────────────────────────────────────────────────────────

class CreditScoreResponse(BaseModel):
    score: float
    updated_at: datetime

    class Config:
        from_attributes = True


class ScoreHistoryPoint(BaseModel):
    score: float
    recorded_at: datetime

    class Config:
        from_attributes = True


# ── Violations ─────────────────────────────────────────────────────────────────

class ViolationResponse(BaseModel):
    id: int
    student_id: int
    violation_type: str
    timestamp: datetime
    evidence_image_path: Optional[str]
    score_deducted: float
    video_id: Optional[int]

    class Config:
        from_attributes = True


# ── Videos ─────────────────────────────────────────────────────────────────────

class VideoResponse(BaseModel):
    id: int
    uploaded_by: int
    video_path: str
    original_filename: Optional[str]
    upload_timestamp: datetime
    processing_status: str

    class Config:
        from_attributes = True


# ── Admin dashboard aggregates ─────────────────────────────────────────────────

class StudentWithScore(BaseModel):
    id: int
    name: str
    email: str
    gender: Optional[str]
    department: Optional[str]
    score: float

    class Config:
        from_attributes = True


# ── Appeals ────────────────────────────────────────────────────────────────────

class AppealCreate(BaseModel):
    violation_id: int
    reason: str


class AppealDecide(BaseModel):
    status: str          # "approved" or "rejected"
    admin_note: Optional[str] = None


class AppealResponse(BaseModel):
    id: int
    violation_id: int
    student_id: int
    reason: str
    status: str
    admin_note: Optional[str]
    created_at: datetime
    decided_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Manual Violation (admin) ───────────────────────────────────────────────────

class ManualViolationCreate(BaseModel):
    student_id: int
    violation_type: str
    score_deducted: float = 5.0
    note: Optional[str] = None


class StudentRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = "student123"
    roll_no: Optional[str] = None
    department: Optional[str] = None
    year: Optional[str] = None
    gender: Optional[str] = None


class StudentProfileResponse(BaseModel):
    student_id: int
    roll_no: Optional[str]
    year: Optional[str]

    class Config:
        from_attributes = True


class StudentDetailResponse(BaseModel):
    id: int
    name: str
    email: str
    gender: Optional[str]
    department: Optional[str]
    score: float
    roll_no: Optional[str] = None
    year: Optional[str] = None
    face_photos: int = 0


class FacePhotoResponse(BaseModel):
    id: int
    photo_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class VideoSessionResponse(BaseModel):
    id: int
    uploaded_by: int
    video_path: str
    original_filename: Optional[str]
    status: str
    processed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class DetectionResponse(BaseModel):
    id: int
    session_id: int
    student_id: Optional[int]
    frame_path: Optional[str]
    violations: List[str]
    confidence: float
    compliance_status: str
    review_status: str
    admin_verified: Optional[bool]
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    created_at: datetime


class DetectionReviewRequest(BaseModel):
    action: str  # confirm | dismiss


class SessionResultsResponse(BaseModel):
    session: VideoSessionResponse
    compliant: List[DetectionResponse]
    non_compliant: List[DetectionResponse]
    unidentified: List[DetectionResponse]
    pending_review: int


class ViolationPolicyUpdate(BaseModel):
    violation_type: str
    deduction_points: float
    active: bool = True


class ViolationPolicyResponse(BaseModel):
    id: int
    violation_type: str
    deduction_points: float
    active: bool

    class Config:
        from_attributes = True


class SendAlertsRequest(BaseModel):
    detection_ids: List[int]


class AlertResponse(BaseModel):
    id: int
    student_id: int
    detection_id: int
    message: str
    score_deducted: float
    sent_at: datetime
    status: str
    is_read: bool
    frame_path: Optional[str] = None
    violations: List[str] = []


class StudentDashboardResponse(BaseModel):
    student_id: int
    score: float
    unread_alerts: int
    pending_alerts: int
    pending_appeals: int


class AlertAppealCreateResponse(BaseModel):
    id: int
    alert_id: int
    student_id: int
    justification: str
    proof_path: Optional[str]
    status: str
    review_note: Optional[str]
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertAppealDecisionRequest(BaseModel):
    status: str  # approved | rejected
    review_note: Optional[str] = None


class ScoreLogResponse(BaseModel):
    id: int
    student_id: int
    change_amount: float
    reason: str
    actor_user_id: Optional[int]
    alert_id: Optional[int]
    timestamp: datetime

    class Config:
        from_attributes = True


class AdminAnalyticsResponse(BaseModel):
    total_students: int
    total_sessions: int
    total_detections: int
    compliant_detections: int
    non_compliant_detections: int
    compliance_rate: float
    violations_by_type: Dict[str, int]
