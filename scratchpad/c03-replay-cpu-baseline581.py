"""Run the final CPU regression population against the saved pre581 owner in memory."""
from pathlib import Path
import importlib.util
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
import baxy_mind
import pytest

owner = root / 'src/baxy_mind/llm.py'
before = root / 'artifacts/comprobaciones/C03/astra-cpu-actor581/llm.py.before'
spec = importlib.util.spec_from_file_location('baxy_mind.llm', owner)
module = importlib.util.module_from_spec(spec)
sys.modules['baxy_mind.llm'] = module
baxy_mind.llm = module
# Preserve package-relative resource paths; execute the exact saved source,
# without overwriting the working tree or invoking a model.
exec(compile(before.read_bytes(), str(owner), 'exec'), module.__dict__)
raise SystemExit(pytest.main(['tests/test_c03_cpu_actor.py', '-q', '--tb=short']))
