"""Join all73 diagnostic turns before independent adjudication and comparison."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "scratchpad/c03-review-status-batch694.py").read_text(encoding="utf-8")
exec(compile(source.replace("694", "729"), __file__, "exec"))
