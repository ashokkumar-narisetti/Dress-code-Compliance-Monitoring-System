"""
seed.py - Populate the database with demo data for local development.

Run once after creating the database:
    python seed.py

Creates:
  - 1 admin account    (admin@dresscode.com / admin123)
  - 3 student accounts (student1@dresscode.com / student123, etc.)
  - Initial credit scores for all students
  - A few sample violations
"""

from database import Base, engine, SessionLocal, settings
import models
from auth import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── Admin ──────────────────────────────────────────────────────────────────────
admin = models.User(
    name="Admin User",
    email="admin@dresscode.com",
    password_hash=hash_password("admin123"),
    role=models.RoleEnum.admin,
    gender="Male",
    department="Management",
)
db.add(admin)
db.commit()
db.refresh(admin)

# ── Students ───────────────────────────────────────────────────────────────────
students_data = [
    {"name": "Arjun Sharma",  "email": "arjun@dresscode.com",  "dept": "Computer Science", "gender": "Male"},
    {"name": "Priya Nair",    "email": "priya@dresscode.com",   "dept": "Electronics",      "gender": "Female"},
    {"name": "Rohan Mehta",   "email": "rohan@dresscode.com",   "dept": "Mechanical",       "gender": "Male"},
]

created_students = []
for i, s in enumerate(students_data):
    student = models.User(
        name=s["name"],
        email=s["email"],
        password_hash=hash_password("student123"),
        role=models.RoleEnum.student,
        gender=s["gender"],
        department=s["dept"],
    )
    db.add(student)
    db.flush()

    score_val = [100.0, 90.0, 85.0][i]
    credit = models.CreditScore(student_id=student.id, score=score_val)
    db.add(credit)
    db.flush()

    # Score history: started at 100, may have dipped
    history_points = [100.0, score_val]
    for sp in history_points:
        db.add(models.ScoreHistory(credit_score_id=credit.id, score=sp))

    created_students.append(student)

db.commit()

# ── Sample violations ──────────────────────────────────────────────────────────
violation_samples = [
    (created_students[0].id, "no_tie",        5.0),
    (created_students[1].id, "coloured_shoes", 5.0),
    (created_students[2].id, "untucked_shirt", 3.0),
    (created_students[2].id, "no_id_card",    5.0),
]

for sid, vtype, deduction in violation_samples:
    db.add(models.Violation(
        student_id=sid,
        violation_type=vtype,
        score_deducted=deduction,
    ))

db.commit()
db.close()

print("\n✅ Seed complete!")
print("  Admin:   admin@dresscode.com     / admin123")
print("  Student: arjun@dresscode.com     / student123")
print("  Student: priya@dresscode.com     / student123")
print("  Student: rohan@dresscode.com     / student123")
