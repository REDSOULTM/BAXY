"""Capture the exact failing lifecycle child only after its unchanged deadline."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-full5-sidecar716'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-full5-sidecar716-private'
assert not out.exists() and not private.exists()
out.mkdir()
private.mkdir()
test = root / 'tests/test_sidecar_lifecycle.py'
tree = ast.parse(test.read_text(encoding='utf-8'))
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == 'test_dispatch_crash_exits_while_redirected_stdin_remains_open')
assignment = next(node for node in function.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'script'
                          for target in node.targets))
script = ast.literal_eval(assignment.value)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
write = lambda path, value: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
spy = Path(os.environ['TEMP']) / 'c03-pyspy712/bin/py-spy.exe'
assert spy.is_file()
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'source_test_sha256': sha(test), 'child_script_sha256': hashlib.sha256(script.encode()).hexdigest(),
    'python': sys.executable, 'py_spy_sha256': sha(spy), 'deadline_seconds': 3.0,
    'method': 'Exact child script from failing test AST. Keep stdin open. Wait3s unchanged; only after a deadline failure capture a stack before disposing this owned child. A late exit remains a failed deadline. No locals, model inference or product source changes.',
})
environment = os.environ.copy()
environment['PYTHONPATH'] = str(root / 'src')
started = time.monotonic()
process = subprocess.Popen([sys.executable, '-c', script], stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
deadline_passed = False
stack_exit = None
try:
    process.wait(timeout=3.0)
    deadline_passed = True
except subprocess.TimeoutExpired:
    with (private / 'stack.txt').open('wb') as stream:
        stack = subprocess.run([str(spy), 'dump', '--pid', str(process.pid)],
                               stdout=stream, stderr=subprocess.STDOUT, timeout=15, check=False)
        stack_exit = stack.returncode
finally:
    late_code = process.poll()
    killed = late_code is None
    if killed:
        process.kill()
    process.wait(timeout=3.0)
    process.stdin.close()
    process.stdin = None
stdout, stderr = process.communicate(timeout=3.0)
(private / 'stdout.bin').write_bytes(stdout)
(private / 'stderr.bin').write_bytes(stderr)
result = {
    'utc': datetime.now(timezone.utc).isoformat(), 'pid': process.pid,
    'deadline_passed': deadline_passed, 'return_code': process.returncode,
    'late_code_before_disposal': late_code, 'killed_owned_child': killed,
    'elapsed_including_post_deadline_diagnostic': time.monotonic() - started,
    'stack_exit_code': stack_exit,
    'hello_seen': b'"type":"hello"' in stdout,
    'forced_dispatch_crash_seen': b'forced_dispatch_crash' in stderr,
    'buffered_busy_seen': b'_enter_buffered_busy' in stderr,
    'private_evidence': str(private), 'source_test_unchanged': sha(test),
    'coverage_added': 0, 'goal_complete': False,
}
assert result['source_test_unchanged'] == json.loads((out / 'PREREG.json').read_text())['source_test_sha256']
write(out / 'RESULT.json', result)
print(json.dumps(result, ensure_ascii=False))
if (private / 'stack.txt').exists():
    print((private / 'stack.txt').read_text(encoding='utf-8', errors='replace'))
