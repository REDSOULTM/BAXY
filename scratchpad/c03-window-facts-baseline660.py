"""Run the final contract tests with the previously published compositor bytes."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import types

root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root / 'src'))
import baxy_mind
import pytest

source = subprocess.check_output(['git','show','b8a7399b1b1d39c701941ef24bc67f86db8f2fcf:src/baxy_mind/llm.py'],cwd=root)
path = Path(os.environ['TEMP']) / 'c03-llm-before660.py'
path.write_bytes(source)
module = types.ModuleType('baxy_mind.llm')
module.__file__ = str(path)
module.__package__ = 'baxy_mind'
sys.modules['baxy_mind.llm'] = module
baxy_mind.llm = module
exec(compile(source,str(path),'exec'),module.__dict__)
print(json.dumps({'baseline_commit':'b8a7399b1b1d39c701941ef24bc67f86db8f2fcf',
                  'git_source_sha256':hashlib.sha256(source).hexdigest(),
                  'current_worktree_modified':False,'model_calls':False}))
raise SystemExit(pytest.main(['tests/test_c03_window_facts.py','-q']))
