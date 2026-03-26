"""
train_yolo.py - Train a YOLOv8 classification model on the dress code dataset.

PREREQUISITES:
  pip install ultralytics

USAGE:
  cd "a:\\Dresscode project\\backend"
  venv\\Scripts\\pip install ultralytics
  venv\\Scripts\\python train\\prepare_dataset.py    # run first
  venv\\Scripts\\python train\\train_yolo.py

OUTPUT:
  backend/train/runs/classify/dresscode/weights/best.pt
  Copy this to:  backend/models/best.pt
  Then update ai_service.py (see instructions in that file).
"""

from pathlib import Path

# Guard: must have ultralytics installed
try:
    from ultralytics import YOLO
except ImportError:
    raise SystemExit(
        "\n  ❌  ultralytics not installed.\n"
        "  Run:  venv\\Scripts\\pip install ultralytics\n"
    )

# ── Config ─────────────────────────────────────────────────────────────────────
DATASET_DIR = Path(__file__).resolve().parent / "dataset"
MODELS_DIR  = Path(__file__).resolve().parent.parent / "models"
PROJECT_DIR = Path(__file__).resolve().parent / "runs"

# YOLOv8n-cls is the lightest classification model (~6 MB).
# Upgrade to yolov8s-cls or yolov8m-cls if you want higher accuracy.
BASE_MODEL  = "yolov8n-cls.pt"

EPOCHS      = 50     # increase to 100+ for better accuracy
IMG_SIZE    = 224    # standard for classification
BATCH       = 16
PATIENCE    = 10     # early stopping
WORKERS     = 2      # use 0 on Windows if multiprocessing errors occur


def train():
    if not DATASET_DIR.exists():
        raise FileNotFoundError(
            f"Dataset not found at {DATASET_DIR}.\n"
            "Please run:  python train/prepare_dataset.py  first."
        )

    print(f"  Dataset:    {DATASET_DIR}")
    print(f"  Base model: {BASE_MODEL}")
    print(f"  Epochs:     {EPOCHS}  |  Image size: {IMG_SIZE}  |  Batch: {BATCH}\n")

    model = YOLO(BASE_MODEL)

    results = model.train(
        data=str(DATASET_DIR),
        task="classify",
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH,
        patience=PATIENCE,
        workers=WORKERS,
        project=str(PROJECT_DIR),
        name="dresscode",
        exist_ok=True,
        verbose=True,
    )

    # Copy best weights to backend/models/
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    best_src = PROJECT_DIR / "dresscode" / "weights" / "best.pt"
    best_dst = MODELS_DIR / "best.pt"
    if best_src.exists():
        import shutil
        shutil.copy(best_src, best_dst)
        print(f"\n  ✅ Best model saved to: {best_dst}")
        print("  Next step: update ai_service.py to use this model (see integration comments).")
    else:
        print(f"\n  ⚠  Could not find weights at {best_src}. Check training output above.")

    return results


if __name__ == "__main__":
    print("Starting YOLOv8 classification training…\n")
    train()
