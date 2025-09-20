import os
import sys
import traceback

# Ensure project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.ml.model_loader import ModelLoader
from config import settings


def main() -> None:
    print("HF_TOKEN set:", bool(os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")))
    print("Cache:", os.getenv("HF_HOME") or os.getenv("TRANSFORMERS_CACHE"))
    ml = ModelLoader()
    print("Device:", ml.device)
    try:
        print("Loading gemma3_1b...")
        ok1 = ml.load_gemma3_1b()
        print("gemma3_1b:", ok1)
    except Exception:
        print("gemma3_1b exception:\n", traceback.format_exc())
    try:
        print("Loading gemma3_12b (quantized)...")
        ok2 = ml.load_gemma3_12b_quantized()
        print("gemma3_12b:", ok2)
    except Exception:
        print("gemma3_12b exception:\n", traceback.format_exc())
    print("Loaded:", ml.get_loaded_models())


if __name__ == "__main__":
    main()


