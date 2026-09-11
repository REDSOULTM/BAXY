"""Observe cold Core handshakes; capture a late startup before terminating it."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

import psutil

root = Path(__file__).resolve().parents[1]
public = root / 'artifacts/comprobaciones/C03/astra-core-startup-probe709'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-core-startup709-private'
temp = Path(os.environ['TEMP'])
core = root / 'tests/Baxy.Integration.Tests/bin/Release/net10.0-windows10.0.19041.0/baxy-core.exe'
stack = temp / 'c03-dotnet-diagnostics705/dotnet-stack.exe'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert core.is_file() and stack.is_file()
assert (temp / 'c03-window-vocabulary705-full4-exit.json').exists(), 'Wait for Full4 terminal state'
assert not any(p.info['name'] and p.info['name'].lower() in {'testhost.exe', 'baxy-core.exe', 'llama-server.exe'}
               for p in psutil.process_iter(['name'])), 'Do not overlap tests or inference'
public.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
record = {'utc': datetime.now(timezone.utc).isoformat(), 'maximum_trials': 50, 'handshake_limit_seconds': 10,
          'method': 'Cold Core process with a distinct private data root and no requests. Measure first stdout line before diagnostics. On timeout, preserve child-process samples and capture managed stacks; stop the series after the first failure. This is diagnosis, not an acceptance rerun or a relaxed startup SLA.',
          'core_files': {name: sha(core.parent / name) for name in ['baxy-core.exe', 'baxy-core.dll', 'Baxy.Providers.Windows.dll']},
          'stack_tool_version': '10.0.731102', 'stack_tool_sha256': sha(stack),
          'stack_tool_docs': 'https://learn.microsoft.com/en-us/dotnet/core/diagnostics/dotnet-stack',
          'full4_exit': json.loads((temp / 'c03-window-vocabulary705-full4-exit.json').read_text(encoding='utf-8-sig')),
          'model_inference': False, 'product_source_changed': False, 'coverage_added': 0}
write(public / 'PREREG.json', record)
results = []
for index in range(50):
    run = private / f'run-{index:02}'
    run.mkdir()
    env = dict(os.environ, BAXY_DATA_DIR=str(run / 'data'))
    first = []
    stderr_lines = []
    ready = threading.Event()
    began = time.monotonic()
    process = subprocess.Popen([str(core)], cwd=core.parent, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    samples = []

    def read_first():
        line = process.stdout.readline(1024 * 1024)
        first.append({'seconds': time.monotonic() - began, 'line': line.decode('utf-8', errors='replace')})
        ready.set()

    def read_errors():
        while line := process.stderr.readline(8192):
            if sum(map(len, stderr_lines)) < 65536:
                stderr_lines.append(line.decode('utf-8', errors='replace'))

    stdout_reader = threading.Thread(target=read_first, daemon=True)
    stderr_reader = threading.Thread(target=read_errors, daemon=True)
    stdout_reader.start()
    stderr_reader.start()
    try:
        while not ready.wait(0.25) and time.monotonic() - began < 10:
            try:
                owned = psutil.Process(process.pid)
                children = owned.children(recursive=True)
                samples.append({'seconds': time.monotonic() - began,
                                'free_ram_mib': psutil.virtual_memory().available / 2**20,
                                'core_cpu_seconds': sum(owned.cpu_times()[:2]),
                                'children': [{'pid': p.pid, 'name': p.name(), 'command': p.cmdline(),
                                              'cpu_seconds': sum(p.cpu_times()[:2])} for p in children]})
            except psutil.Error as error:
                samples.append({'seconds': time.monotonic() - began, 'sample_error': type(error).__name__})
        arrived_in_budget = bool(first) and first[0]['seconds'] <= 10
        valid_hello = False
        if arrived_in_budget:
            try:
                hello = json.loads(first[0]['line'])
                valid_hello = hello.get('type') == 'hello' and hello.get('pid') == process.pid
            except (ValueError, TypeError):
                pass
        row = {'index': index, 'pid': process.pid, 'seconds': first[0]['seconds'] if first else None,
               'arrived_within_10s': arrived_in_budget, 'valid_hello': valid_hello,
               'first_line_before_stack_capture': first.copy()}
        if not (arrived_in_budget and valid_hello) and process.poll() is None:
            with (run / 'managed-stack.txt').open('w', encoding='utf-8') as output:
                try:
                    result = subprocess.run([str(stack), 'report', '--process-id', str(process.pid)],
                                            stdout=output, stderr=subprocess.STDOUT, timeout=15,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                    row['stack_exit'] = result.returncode
                except subprocess.TimeoutExpired:
                    row['stack_timeout'] = True
            row['first_line_after_stack_capture'] = first.copy()
        write(run / 'samples.json', samples)
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        stdout_reader.join(timeout=1)
        stderr_reader.join(timeout=1)
        (run / 'stderr.log').write_text(''.join(stderr_lines), encoding='utf-8')
        write(run / 'first-line.json', first)
        process.stdout.close()
        process.stderr.close()
    row['exit_code_after_stdin_closed'] = process.returncode
    write(run / 'RESULT.json', row)
    public_row = {key: value for key, value in row.items() if not key.startswith('first_line_')}
    public_row['private_result_sha256'] = sha(run / 'RESULT.json')
    public_row['stderr_sha256'] = sha(run / 'stderr.log')
    results.append(public_row)
    write(public / 'PROGRESS.json', {'trials': results, 'coverage_added': 0})
    print(json.dumps(public_row), flush=True)
    if not (arrived_in_budget and valid_hello):
        break
write(public / 'RESULT.json', {'trials': results, 'source_files_unchanged': all(
    sha(core.parent / name) == value for name, value in record['core_files'].items()),
    'failed': sum(not r['arrived_within_10s'] or not r['valid_hello'] for r in results),
    'goal_complete': False, 'coverage_added': 0})
