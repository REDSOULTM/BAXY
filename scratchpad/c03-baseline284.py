"""Price final owner controls against the frozen prior fact guard in memory."""
from pathlib import Path
import ast
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import llm
import pytest
source = root / 'artifacts/comprobaciones/C03/astra-account284/before/llm.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_payload_fact_defect')
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), vars(llm))
raise SystemExit(pytest.main(['tests/test_compose_contract.py', '-k', 'observed_account or composed_identity', '-q', '--tb=short']))
