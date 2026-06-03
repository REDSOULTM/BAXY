"""Read-only: screenshot del estado actual (portal UNIEJ logueado) para ver qué hay."""
import sys
from pathlib import Path
sys.path.insert(0, ".")
from PIL import ImageGrab
OUT = Path("scripts/_diag/_live"); OUT.mkdir(parents=True, exist_ok=True)
ImageGrab.grab().convert("RGB").save(str((OUT / "now.png").resolve()))
print("[peek] scripts/_diag/_live/now.png")
