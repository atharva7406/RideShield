"""
ONNX inference for the helmet classifier. Deliberately does NOT depend on
torch/ultralytics — the exported best.onnx only needs onnxruntime + numpy
+ Pillow to run, keeping this module's footprint as light as
ml_incident_engine/predict.py and behaviour_risk_engine/predict.py.

Preprocessing mirrors Ultralytics' own classification pipeline for this
export: direct resize to 224x224 (no letterbox — classification heads use
a plain resize, unlike detection heads), RGB, /255 normalize, HWC->CHW,
batch dim added. Confirmed against the ONNX graph's actual input/output
signature (images: [1,3,224,224] float32 -> output0: [1,3] float32,
already softmax-normalized — verified by a smoke-test run summing the
output to 1.0) rather than assumed.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import numpy as np
import onnxruntime as ort
from PIL import Image

from . import config as cfg

_session_cache: dict[str, ort.InferenceSession] = {}


def load_session(model_path: Optional[Path] = None) -> ort.InferenceSession:
    model_path = model_path or cfg.MODEL_PATH
    key = str(model_path)
    if key not in _session_cache:
        _session_cache[key] = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
    return _session_cache[key]


def preprocess_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Raises ValueError for anything that isn't a decodable image —
    callers must not let a malformed upload reach the ONNX runtime."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Could not decode image: {e}")

    img = img.resize((cfg.INPUT_SIZE, cfg.INPUT_SIZE), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0  # HWC, [0,1]
    arr = arr.transpose(2, 0, 1)  # CHW
    return np.expand_dims(arr, axis=0)  # NCHW


def predict_from_image_bytes(image_bytes: bytes, session: Optional[ort.InferenceSession] = None) -> dict:
    """Returns {predicted_class, confidence, helmet_worn, class_probabilities,
    model_version}. Never applies business-logic fallback itself (e.g. what
    happens on a corrupt image or missing model) — that's
    app/services/helmet_verification_service.py's job, same separation as
    every other *_engine/predict.py module in this codebase."""
    session = session or load_session()
    input_tensor = preprocess_image_bytes(image_bytes)
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_tensor})
    probs = outputs[0][0]

    top_idx = int(np.argmax(probs))
    predicted_class = cfg.CLASS_NAMES[top_idx]
    confidence = float(probs[top_idx])

    helmet_worn = (predicted_class in cfg.HELMET_CLASSES) and (confidence >= cfg.CONFIDENCE_THRESHOLD)

    return {
        "predicted_class": predicted_class,
        "confidence": round(confidence, 4),
        "helmet_worn": helmet_worn,
        "class_probabilities": {
            name: round(float(p), 4) for name, p in zip(cfg.CLASS_NAMES, probs)
        },
        "model_version": cfg.MODEL_VERSION,
    }
