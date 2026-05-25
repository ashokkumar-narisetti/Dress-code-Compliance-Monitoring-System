"""
main.py - FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app with metadata for Swagger docs
  - Configure CORS to allow the React dev server
  - Mount all route groups under /api/v1
  - Create DB tables on startup (dev convenience)
  - Load AI model at startup
  - Serve uploaded files as static assets
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import Base, engine, settings
import ai_service
from routes.auth_routes import router as auth_router
from routes.admin_routes import router as admin_router
from routes.student_routes import router as student_router
from routes.appeal_routes import student_appeal_router, admin_appeal_router
from routes.compliance_routes import admin_compliance_router, student_compliance_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Startup / Shutdown lifecycle ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create upload directories (always safe, no DB needed)
    for directory in [
        settings.UPLOAD_DIR,
        settings.VIDEO_DIR,
        settings.EVIDENCE_DIR,
        getattr(settings, "TEMP_FRAMES_DIR", "uploads/temp_frames"),
    ]:
        os.makedirs(directory, exist_ok=True)

    # Create tables — requires PostgreSQL to be running
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created / verified.")
    except Exception as e:
        logger.error(
            "\n\n"
            "  ╔══════════════════════════════════════════════════════════╗\n"
            "  ║  DATABASE CONNECTION FAILED                              ║\n"
            "  ║  PostgreSQL is not running or credentials are wrong.     ║\n"
            "  ║  1. Start PostgreSQL service                             ║\n"
            "  ║  2. Create database:  CREATE DATABASE dresscode_db;      ║\n"
            "  ║  3. Update .env with correct DATABASE_URL                ║\n"
            "  ║  4. Restart this server                                  ║\n"
            "  ╚══════════════════════════════════════════════════════════╝\n"
            f"  Error: {e}\n"
        )

    # Load AI model once at startup (always runs regardless of DB)
    ai_service.load_model(settings.MODEL_PATH)
    logger.info("AI service initialized.")

    yield  # Application is running

    logger.info("Application shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Dress Code Monitoring System",
    description=(
        "AI-Based Dress Code Monitoring and Compliance System. "
        "Integrates YOLOv8 object detection for dress code violation analysis."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files (evidence images, uploaded videos) ───────────────────────────
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth_router,          prefix="/api/v1")
app.include_router(admin_router,         prefix="/api/v1")
app.include_router(student_router,       prefix="/api/v1")
app.include_router(student_appeal_router, prefix="/api/v1")
app.include_router(admin_appeal_router,   prefix="/api/v1")
app.include_router(admin_compliance_router, prefix="/api/v1")
app.include_router(student_compliance_router, prefix="/api/v1")


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "service": "Dress Code Monitoring System"}


# ── Dev entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
