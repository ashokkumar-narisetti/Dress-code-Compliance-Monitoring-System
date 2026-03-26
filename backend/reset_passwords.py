"""
reset_passwords.py - Reset demo account passwords to fix bcrypt compatibility.
Run once:  venv\\Scripts\\python reset_passwords.py
"""
from database import SessionLocal
import models
from auth import hash_password

db = SessionLocal()

updates = [
    ("admin@dresscode.com",  "admin123"),
    ("arjun@dresscode.com",  "student123"),
    ("priya@dresscode.com",  "student123"),
    ("rohan@dresscode.com",  "student123"),
]

for email, pw in updates:
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        user.password_hash = hash_password(pw)
        print("  Updated:", email)
    else:
        print("  Not found:", email)

db.commit()
db.close()
print("Done — passwords reset.")
