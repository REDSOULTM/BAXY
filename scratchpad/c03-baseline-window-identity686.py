"""Run the expanded identity cohort against the published owner without replacing files."""
from pathlib import Path
import hashlib
import subprocess
import sys
import types

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
from baxy_mind import llm
import pytest

published = subprocess.check_output(['git', 'show', '68a27bdec8179404d2d9295a09c1f6f6db859ef4:src/baxy_mind/window_prose_facts.py'], cwd=root)
baseline = types.ModuleType('baxy_mind._baseline_window_identity686')
baseline.__package__ = 'baxy_mind'
exec(compile(published, 'published683/window_prose_facts.py', 'exec'), baseline.__dict__)
for name in ['window_fact_defect', 'window_focus_feedback', 'window_status_assertions']:
    setattr(llm, name, getattr(baseline, name))
print({'baseline_module_sha256': hashlib.sha256(published).hexdigest(), 'filesystem_source_modified': False}, flush=True)
raise SystemExit(pytest.main(['tests/test_c03_window_identity_answers.py', '-q']))
