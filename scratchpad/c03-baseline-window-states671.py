"""Run the final new cohort with the published factual owner in an isolated process."""
from pathlib import Path
import hashlib
import subprocess
import sys
import types

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
from baxy_mind import llm
import pytest

published = subprocess.check_output(['git','show','4d491328925890d68a922c12349ca75647f15010:src/baxy_mind/window_prose_facts.py'], cwd=root)
assert b'_window_focus_defect' not in published
baseline = types.ModuleType('baxy_mind._baseline_window_states671')
baseline.__package__ = 'baxy_mind'
exec(compile(published, 'published660/window_prose_facts.py', 'exec'), baseline.__dict__)
llm.window_fact_defect = baseline.window_fact_defect
print({'baseline_module_sha256':hashlib.sha256(published).hexdigest(), 'filesystem_source_modified':False}, flush=True)
raise SystemExit(pytest.main(['tests/test_c03_window_state_facts.py','-q']))
