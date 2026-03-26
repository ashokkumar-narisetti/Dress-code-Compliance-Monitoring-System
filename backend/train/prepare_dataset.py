"""
prepare_dataset.py - Prepares the dress code image dataset for YOLOv8 training.

INPUT:
  dresscode/ImproperDresscode/  - images of dress code violations
  dresscode/ProperDresscode/    - images of proper dress code

OUTPUT (YOLO classification format):
  backend/train/dataset/
    train/
      improper/   <- 80% of improper images
      proper/     <- 80% of proper images
    val/
      improper/   <- 20% of improper images
      proper/     <- 20% of proper images

USAGE:
  cd "a:\\Dresscode project\\backend"
  venv\\Scripts\\python train\\prepare_dataset.py
"""

import os
import shutil
import random
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).resolve().parent.parent.parent  # "Dresscode project/"
IMPROPER_SRC  = PROJECT_ROOT / "dresscode" / "ImproperDresscode"
PROPER_SRC    = PROJECT_ROOT / "dresscode" / "ProperDresscode"
DATASET_OUT   = Path(__file__).resolve().parent / "dataset"
TRAIN_SPLIT   = 0.80   # 80% train, 20% val
SEED          = 42

CLASSES = {
    "improper": IMPROPER_SRC,
    "proper":   PROPER_SRC,
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def collect_images(src_dir: Path) -> list:
    return [p for p in src_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS]


def prepare():
    random.seed(SEED)

    # Clean and recreate output
    if DATASET_OUT.exists():
        shutil.rmtree(DATASET_OUT)

    splits = ["train", "val"]
    for split in splits:
        for cls in CLASSES:
            (DATASET_OUT / split / cls).mkdir(parents=True, exist_ok=True)

    total_train, total_val = 0, 0

    for cls_name, src_dir in CLASSES.items():
        if not src_dir.exists():
            print(f"  [WARN] Source folder not found: {src_dir}")
            continue

        images = collect_images(src_dir)
        if not images:
            print(f"  [WARN] No images found in: {src_dir}")
            continue

        random.shuffle(images)
        split_idx  = int(len(images) * TRAIN_SPLIT)
        train_imgs = images[:split_idx]
        val_imgs   = images[split_idx:]

        for img in train_imgs:
            shutil.copy(img, DATASET_OUT / "train" / cls_name / img.name)
        for img in val_imgs:
            shutil.copy(img, DATASET_OUT / "val" / cls_name / img.name)

        print(f"  {cls_name:12s}  train={len(train_imgs):4d}  val={len(val_imgs):4d}")
        total_train += len(train_imgs)
        total_val   += len(val_imgs)

    print(f"\n  ✅ Dataset ready at: {DATASET_OUT}")
    print(f"     Total: {total_train} train  /  {total_val} val")
    print(f"\n  Next step: run  python train/train_yolo.py")


if __name__ == "__main__":
    print("Preparing YOLOv8 classification dataset…\n")
    prepare()
