"""Run the declared direct-owner scope for candidate676."""
from pathlib import Path
import json
import sys
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'src')]
import pytest
record=json.loads((root/'artifacts/comprobaciones/C03/astra-focus-coverage-source676/PREREG.json').read_text(encoding='utf-8'))
raise SystemExit(pytest.main([*record['owner_tests'],'-q']))
