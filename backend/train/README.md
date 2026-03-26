# YOLOv8 Training Guide

## Quick Start

```powershell
# 1. Activate venv & install ultralytics (one-time)
cd "a:\Dresscode project\backend"
venv\Scripts\pip install ultralytics

# 2. Prepare dataset (splits images into train/val)
venv\Scripts\python train\prepare_dataset.py

# 3. Train the model
venv\Scripts\python train\train_yolo.py
```

That's it. When training completes, `best.pt` is automatically copied to `backend/models/best.pt`.

---

## What the Scripts Do

| Script | Purpose |
|--------|---------|
| `prepare_dataset.py` | Reads `dresscode/ImproperDresscode/` (122 images) and `dresscode/ProperDresscode/` (79 images), splits 80/20 train/val, writes YOLO classification folder structure |
| `train_yolo.py` | Trains `yolov8n-cls` for 50 epochs (with early stopping), copies `best.pt` to `backend/models/` |

---

## Dataset Structure (after prepare)

```
backend/train/dataset/
  train/
    improper/     ← ~98 images
    proper/       ← ~63 images
  val/
    improper/     ← ~24 images
    proper/       ← ~16 images
```

---

## Integrating the Trained Model

After training, open `backend/ai_service.py` and replace the placeholder block:

```python
# Step 1 — change load_model():
from ultralytics import YOLO
_model = YOLO(model_path)      # model_path = "backend/models/best.pt"

# Step 2 — change detect_violations():
results = _model(frame)
predicted_class = _model.names[results[0].probs.top1]
if predicted_class == "improper":
    detections.append({
        "class_name": "improper_dresscode",
        "confidence": float(results[0].probs.top1conf),
        "bbox": [0, 0, frame.shape[1], frame.shape[0]],   # whole frame
        "score_deduction": 5.0,
    })
return detections
```

No other file needs to change.

---

## Tips for Better Accuracy

- **More data → better model.** Collect 500+ images per class if possible.
- **Longer training:** Change `EPOCHS = 100` in `train_yolo.py`.
- **Larger model:** Change `BASE_MODEL = "yolov8s-cls.pt"` for higher accuracy at the cost of speed.
- **Windows multiprocessing issue:** If training crashes, set `WORKERS = 0` in `train_yolo.py`.
