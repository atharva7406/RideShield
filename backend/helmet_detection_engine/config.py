"""
Helmet-detection inference config.

MODEL PROVENANCE — READ BEFORE CHANGING THRESHOLDS:
best.onnx is a YOLOv8n-cls (nano classifier) exported from a Colab
notebook (see HelmetDetection.ipynb / reference_colab_export.py in this
directory) that was run against its own placeholder dataset-generation
cell — which fills train/val folders with `np.random.randint(0,255,...)`
synthetic noise images, NOT real photos. The notebook was never pointed
at a real helmet/no-helmet photo dataset before export. Its own recorded
validation run scored 0.4753 confidence on its own noise image — i.e.
close to the 1/3 random baseline for a 3-class problem.

This means: the model is real, loads, and runs correctly end-to-end (the
ONNX graph, input/output shapes, and classification pipeline all work),
but its actual helmet/no-helmet judgment is NOT currently trustworthy —
it has not been trained on anything resembling a real selfie. It is
wired in as a complete, working pipeline specifically so it can be
retrained on a real dataset later WITHOUT changing any of the
integration code below this module — only best.onnx needs replacing.

Deployed anyway per explicit product decision: helmet-detection is a
mandatory gate before shift start, integrated as-is, no retraining
data available yet. See helmet_verification_service.py's docstring for
how the gate's fail-closed behavior is designed to limit the blast
radius of this known model-quality issue.
"""

from pathlib import Path

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "best.onnx"
MODEL_VERSION = "helmet-yolov8n-cls-v1-unvalidated"

# Alphabetical order — matches how Ultralytics' classification trainer
# assigns class indices from the training folder names (also confirmed
# against the notebook's own CLASSES list).
CLASS_NAMES = ["full_face_helmet", "half_face_helmet", "no_helmet"]
HELMET_CLASSES = {"full_face_helmet", "half_face_helmet"}

INPUT_SIZE = 224  # matches the ONNX graph's fixed [1,3,224,224] input

# Same default the notebook's own reference server used. Kept as the
# documented, tunable starting point — not validated against real data
# (see module docstring), so treat this as a placeholder, not a
# calibrated operating point.
CONFIDENCE_THRESHOLD = 0.70
