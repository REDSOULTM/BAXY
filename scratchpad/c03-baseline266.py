"""Run identical boundary tests against frozen source without swapping live files."""
from pathlib import Path
import importlib.util
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
import baxy_mind
path = root/'artifacts/comprobaciones/C03/astra-acknowledgement266/before/effect_intent.py'
spec = importlib.util.spec_from_file_location('baxy_mind.effect_intent', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
baxy_mind.effect_intent = module
spec.loader.exec_module(module)
import pytest
assert Path(module.__file__) == path
raise SystemExit(pytest.main(['tests/test_effect_intent.py', '-q', '--tb=short',
    '-k', 'affirmative_preface or authenticated_app_argument_uses_the_shared']))
