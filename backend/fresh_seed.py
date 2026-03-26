"""
fresh_seed.py - Create demo accounts fresh in Supabase.
Skips already-existing records safely.

Run:  venv\\Scripts\\python fresh_seed.py
"""

from database import Base, engine, SessionLocal
import models
from auth import hash_password

# Create all tables (safe / idempotent)
Base.metadata.create_all(bind=engine)
db = SessionLocal()


def get_or_create_user(email, name, password, role, gender, department):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        # Update password hash to current bcrypt version
        user.password_hash = hash_password(password)
        print("  Updated password:", email)
    else:
        user = models.User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=role,
            gender=gender,
            department=department,
        )
        db.add(user)
        db.flush()
        print("  Created:", email)
    return user


# ── Admin ──────────────────────────────────────────────────────────────────────
admin = get_or_create_user(
    "admin@dresscode.com", "Admin User", "admin123",
    models.RoleEnum.admin, "Male", "Management"
)
db.commit()
db.refresh(admin)

# ── Students ───────────────────────────────────────────────────────────────────
students_data = [
    {"name": "Arjun Sharma",  "email": "arjun@dresscode.com",  "dept": "Computer Science", "gender": "Male",   "score": 90.0},
    {"name": "Priya Nair",    "email": "priya@dresscode.com",  "dept": "Electronics",      "gender": "Female", "score": 85.0},
    {"name": "Rohan Mehta",   "email": "rohan@dresscode.com",  "dept": "Mechanical",       "gender": "Male",   "score": 75.0},
]

for s in students_data:
    student = get_or_create_user(
        s["email"], s["name"], "student123",
        models.RoleEnum.student, s["gender"], s["dept"]
    )
    db.flush()

    # Credit score
    credit = db.query(models.CreditScore).filter(models.CreditScore.student_id == student.id).first()
    if not credit:
        credit = models.CreditScore(student_id=student.id, score=s["score"])
        db.add(credit)
        db.flush()
        # History
        db.add(models.ScoreHistory(credit_score_id=credit.id, score=100.0))
        db.add(models.ScoreHistory(credit_score_id=credit.id, score=s["score"]))

    # Violations
    if not db.query(models.Violation).filter(models.Violation.student_id == student.id).first():
        if s["email"] == "arjun@dresscode.com":
            v = models.Violation(student_id=student.id, violation_type="no_tie",        score_deducted=5.0)
            db.add(v)
        elif s["email"] == "priya@dresscode.com":
            v = models.Violation(student_id=student.id, violation_type="coloured_shoes", score_deducted=5.0)
            db.add(v)
        elif s["email"] == "rohan@dresscode.com":
            v1 = models.Violation(student_id=student.id, violation_type="untucked_shirt", score_deducted=3.0)
            v2 = models.Violation(student_id=student.id, violation_type="no_id_card",     score_deducted=5.0)
            db.add(v1); db.add(v2)

db.commit()
db.close()

print()
print("Seed complete!")
print("  admin@dresscode.com  / admin123")
print("  arjun@dresscode.com  / student123")
print("  priya@dresscode.com  / student123")
print("  rohan@dresscode.com  / student123")
