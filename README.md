# DressCode Monitor - AI-Based Dress Code Monitoring System

## Quick Start

### Prerequisites
- Python 3.10+ (3.14 supported)
- Node.js 18+
- PostgreSQL 14+

---

### 1 — Database Setup (PostgreSQL)

```sql
-- In psql or pgAdmin:
CREATE DATABASE dresscode_db;
```

Then update `backend/.env`:
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/dresscode_db
```

---

### 2 — Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python seed.py          # creates tables + demo accounts
venv\Scripts\uvicorn main:app --reload --port 8000
```

API docs → **http://localhost:8000/docs**

---

### 3 — Frontend

```bash
cd frontend
npm install
npm run dev
```

App → **http://localhost:5173**

---

## Demo Accounts

| Role    | Email                    | Password     |
|---------|--------------------------|--------------|
| Admin   | admin@dresscode.com      | admin123     |
| Student | arjun@dresscode.com      | student123   |
| Student | priya@dresscode.com      | student123   |
| Student | rohan@dresscode.com      | student123   |

---

## Project Structure

```
Dresscode project/
├── backend/
│   ├── main.py              ← FastAPI entry point
│   ├── database.py          ← SQLAlchemy engine + Settings
│   ├── models.py            ← ORM models (User, CreditScore, Violation, Video)
│   ├── schemas.py           ← Pydantic request/response schemas
│   ├── auth.py              ← JWT + bcrypt helpers + dependencies
│   ├── ai_service.py        ← ⭐ AI module (placeholder → YOLOv8)
│   ├── seed.py              ← Demo data seeder
│   ├── routes/
│   │   ├── auth_routes.py   ← POST /auth/login, /auth/register
│   │   ├── admin_routes.py  ← Admin API endpoints
│   │   └── student_routes.py← Student API endpoints
│   └── services/
│       └── video_service.py ← Background video processing task
└── frontend/
    └── src/
        ├── App.jsx           ← Router + ProtectedRoute
        ├── context/AuthContext.jsx
        ├── api/client.js     ← Axios + auth interceptor
        └── pages/
            ├── Login.jsx
            ├── AdminDashboard.jsx
            └── StudentDashboard.jsx
```

---

## Integrating YOLOv8 (Future Step)

All AI logic is isolated in **`backend/ai_service.py`**.  
No other file needs to change when you swap in the real model.

```python
# 1. Install:
pip install ultralytics

# 2. In ai_service.py — replace load_model():
from ultralytics import YOLO
_model = YOLO("models/best.pt")

# 3. In detect_violations() — replace placeholder block:
results = _model(frame)
for box in results[0].boxes:
    cls_name = _model.names[int(box.cls)]
    if cls_name in VIOLATION_CLASSES:
        detections.append({...})
```

Place your trained model at: `backend/models/best.pt`

---

## API Reference

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/login` | Public | Get JWT token |
| POST | `/api/v1/auth/register` | Public | Create user |
| GET | `/api/v1/admin/students` | Admin | List students + scores |
| POST | `/api/v1/admin/upload-video` | Admin | Upload + auto-process video |
| GET | `/api/v1/admin/videos` | Admin | List all videos |
| POST | `/api/v1/admin/process-video/{id}` | Admin | Re-trigger processing |
| GET | `/api/v1/admin/violations` | Admin | All violations (paginated) |
| GET | `/api/v1/admin/dashboard-stats` | Admin | Summary stats |
| GET | `/api/v1/student/me` | Student | Own profile |
| GET | `/api/v1/student/score` | Student | Current score |
| GET | `/api/v1/student/score-history` | Student | Score history (for graph) |
| GET | `/api/v1/student/violations` | Student | Own violations |
