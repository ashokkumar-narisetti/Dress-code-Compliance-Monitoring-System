"""
models.py - SQLAlchemy ORM models defining the database schema.

Tables:
  - User: stores admin and student accounts
  - CreditScore: tracks each student's current score
  - Violation: individual dress code infractions
  - Video: uploaded clips and their processing status
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from database import Base


class RoleEnum(str, enum.Enum):
    admin = "admin"
    student = "student"


class ProcessingStatusEnum(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class User(Base):
    """
    Represents both admin and student accounts.
    face_embedding is reserved for future face-recognition integration.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.student)
    gender = Column(String(10), nullable=True)
    department = Column(String(100), nullable=True)
    # Placeholder for future face-recognition vector (JSON-encoded list)
    face_embedding = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    credit_score = relationship("CreditScore", back_populates="student", uselist=False)
    violations = relationship("Violation", back_populates="student")
    uploaded_videos = relationship("Video", back_populates="uploaded_by_user")
    student_profile = relationship("StudentProfile", back_populates="student", uselist=False)
    face_embeddings = relationship("FaceEmbedding", back_populates="student")
    uploaded_sessions = relationship("VideoSession", back_populates="uploaded_by_user")
    detections = relationship(
        "Detection",
        back_populates="student",
        foreign_keys="Detection.student_id",
    )
    alerts = relationship("Alert", back_populates="student")


class CreditScore(Base):
    """
    Tracks the current credit score for each student.
    Score starts at 100 and is decremented on each violation.
    """
    __tablename__ = "credit_scores"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    score = Column(Float, default=100.0, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    student = relationship("User", back_populates="credit_score")
    history = relationship("ScoreHistory", back_populates="credit_score")


class ScoreHistory(Base):
    """
    Tracks historical score changes so the student dashboard graph can render a timeline.
    A record is appended each time the score changes.
    """
    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True, index=True)
    credit_score_id = Column(Integer, ForeignKey("credit_scores.id"), nullable=False)
    score = Column(Float, nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    credit_score = relationship("CreditScore", back_populates="history")


class Violation(Base):
    """
    An individual dress-code infraction detected by the AI service.
    evidence_image_path points to a saved frame crop stored on disk.
    """
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    violation_type = Column(String(100), nullable=False)    # e.g. "no_tie", "coloured_shoes"
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    evidence_image_path = Column(String(512), nullable=True)
    score_deducted = Column(Float, default=5.0)

    # Link back to the video that sourced this violation
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=True)

    student = relationship("User", back_populates="violations")
    video = relationship("Video", back_populates="violations")


class Video(Base):
    """
    A video clip uploaded by an admin.
    processing_status drives the async processing pipeline.
    """
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_path = Column(String(512), nullable=False)
    original_filename = Column(String(255), nullable=True)
    upload_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    processing_status = Column(
        Enum(ProcessingStatusEnum),
        default=ProcessingStatusEnum.pending,
        nullable=False
    )

    uploaded_by_user = relationship("User", back_populates="uploaded_videos")
    violations = relationship("Violation", back_populates="video")


class AppealStatusEnum(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class Appeal(Base):
    """
    A student's appeal against a specific dress-code violation.
    Admins review appeals and can approve (restoring points) or reject them.
    """
    __tablename__ = "appeals"

    id           = Column(Integer, primary_key=True, index=True)
    violation_id = Column(Integer, ForeignKey("violations.id"), nullable=False, unique=True)
    student_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason       = Column(Text, nullable=False)
    status       = Column(Enum(AppealStatusEnum), default=AppealStatusEnum.pending, nullable=False)
    admin_note   = Column(Text, nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    decided_at   = Column(DateTime(timezone=True), nullable=True)

    violation = relationship("Violation", backref="appeal")
    student   = relationship("User", foreign_keys=[student_id])


class ComplianceStatusEnum(str, enum.Enum):
    compliant = "compliant"
    non_compliant = "non_compliant"
    unidentified = "unidentified"


class DetectionReviewStatusEnum(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    dismissed = "dismissed"


class AlertStatusEnum(str, enum.Enum):
    pending = "pending"
    appealed = "appealed"
    resolved = "resolved"


class StudentProfile(Base):
    """
    Extra student metadata kept separate from users so this can be added
    without altering existing user records in deployed databases.
    """
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    roll_no = Column(String(50), unique=True, nullable=True, index=True)
    year = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    student = relationship("User", back_populates="student_profile")


class FaceEmbedding(Base):
    """
    Stores one embedding vector per uploaded face photo.
    Embeddings are JSON-serialized arrays and never exposed by API responses.
    """
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    embedding_vector = Column(Text, nullable=False)
    photo_path = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("User", back_populates="face_embeddings")


class VideoSession(Base):
    """
    Canonical processing unit for one uploaded surveillance clip.
    """
    __tablename__ = "video_sessions"

    id = Column(Integer, primary_key=True, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_path = Column(String(512), nullable=False)
    original_filename = Column(String(255), nullable=True)
    status = Column(Enum(ProcessingStatusEnum), default=ProcessingStatusEnum.pending, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    uploaded_by_user = relationship("User", back_populates="uploaded_sessions")
    detections = relationship("Detection", back_populates="session")


class Detection(Base):
    """
    Consolidated compliance result per student per processed video session.
    """
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("video_sessions.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    frame_path = Column(String(512), nullable=True)
    violations_json = Column(Text, nullable=False, default="[]")
    confidence = Column(Float, nullable=False, default=0.0)
    compliance_status = Column(
        Enum(ComplianceStatusEnum),
        nullable=False,
        default=ComplianceStatusEnum.unidentified,
    )
    review_status = Column(
        Enum(DetectionReviewStatusEnum),
        nullable=False,
        default=DetectionReviewStatusEnum.pending,
    )
    admin_verified = Column(Boolean, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("VideoSession", back_populates="detections")
    student = relationship("User", back_populates="detections", foreign_keys=[student_id])


class ViolationPolicy(Base):
    """
    Configurable score deduction per violation reason.
    """
    __tablename__ = "violation_policies"

    id = Column(Integer, primary_key=True, index=True)
    violation_type = Column(String(100), unique=True, nullable=False, index=True)
    deduction_points = Column(Float, nullable=False, default=5.0)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class Alert(Base):
    """
    Student notification generated only from admin-confirmed non-compliance.
    """
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    detection_id = Column(Integer, ForeignKey("detections.id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    score_deducted = Column(Float, nullable=False, default=0.0)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Enum(AlertStatusEnum), nullable=False, default=AlertStatusEnum.pending)
    is_read = Column(Boolean, nullable=False, default=False)

    student = relationship("User", back_populates="alerts")
    detection = relationship("Detection")
    appeal = relationship("AlertAppeal", back_populates="alert", uselist=False)


class AlertAppeal(Base):
    """
    One appeal per alert. If approved, points are restored and logged.
    """
    __tablename__ = "alert_appeals"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, unique=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    justification = Column(Text, nullable=False)
    proof_path = Column(String(512), nullable=True)
    status = Column(Enum(AppealStatusEnum), default=AppealStatusEnum.pending, nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    alert = relationship("Alert", back_populates="appeal")
    student = relationship("User", foreign_keys=[student_id])


class CreditScoreLog(Base):
    """
    Fully auditable score ledger with reasons and actor identity.
    """
    __tablename__ = "credit_score_log"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    change_amount = Column(Float, nullable=False)
    reason = Column(String(255), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
