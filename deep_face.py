"""
DeepFace analysis for mugshots. Uses CPU unless CUDA/cuDNN are installed and
TensorFlow can find them.

Why no GPU? TensorFlow uses CPU when it can't load CUDA (e.g. "Error loading CUDA
libraries"). Fixes: (1) Install NVIDIA drivers + CUDA toolkit + cuDNN (versions
must match your TensorFlow build). (2) If CUDA is in /usr/lib/cuda, symlink:
  sudo ln -s /usr/lib/cuda /usr/local/cuda
(3) Set LD_LIBRARY_PATH to include the CUDA lib dir. (4) Check:
  python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"

To avoid CUDA log spam when running on CPU only, set DEEPFACE_CPU_ONLY=1 before
running (e.g. DEEPFACE_CPU_ONLY=1 python deep_face.py).
"""
import os
import sys

# Suppress TensorFlow GPU/CUDA log spam (0=all, 1=no INFO, 2=no WARNING, 3=no ERROR)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_CPP_MIN_VLOG_LEVEL"] = "3"

if os.environ.get("DEEPFACE_CPU_ONLY", "").lower() in ("1", "true", "yes"):
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # hide GPUs before TF loads, avoids CUDA log spam

from deepface import DeepFace


def _f(x, decimals: int = 1):
    """Convert numpy scalar to float for display."""
    try:
        return round(float(x), decimals)
    except (TypeError, ValueError):
        return x


def pretty_print(result, image_name: str = "") -> None:
    """Print DeepFace analyze() result in human-readable form."""
    items = result if isinstance(result, list) else [result]
    for i, face in enumerate(items):
        preface = f"--- {image_name}" + (f" (face {i + 1})" if len(items) > 1 else "") + " ---"
        print(preface)
        print(f"  Age:           {face.get('age', '—')}")
        print(f"  Gender:        {face.get('dominant_gender', '—')} ({_f(face.get('gender', {}).get(face.get('dominant_gender'), 0))}%)")
        print(f"  Race:          {face.get('dominant_race', '—')} ({_f(face.get('race', {}).get(face.get('dominant_race'), 0))}%)")
        print(f"  Emotion:       {face.get('dominant_emotion', '—')} ({_f(face.get('emotion', {}).get(face.get('dominant_emotion'), 0))}%)")
        print(f"  Face conf.:    {_f(face.get('face_confidence', 0), 2)}")
        print()


def deep_face(image_path: str, actions=None):
    if actions is None:
        actions = ["age", "gender", "race", "emotion"]
    return DeepFace.analyze(img_path=image_path, actions=actions)


if __name__ == "__main__":
    sample_dir = "/home/richard/code/DHS_WOW_scraper/output/mugshots_sample"
    if not os.path.isdir(sample_dir):
        print(f"Directory not found: {sample_dir}", file=sys.stderr)
        sys.exit(1)

    for fname in sorted(os.listdir(sample_dir)):
        path = os.path.join(sample_dir, fname)
        if not os.path.isfile(path) or fname.startswith("."):
            continue
        try:
            result = deep_face(path)
            pretty_print(result, fname)
        except Exception as e:
            print(f"--- {fname} ---\n  Error: {e}\n")
