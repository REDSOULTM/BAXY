"""Repeat716 with the virtualenv launcher's actual interpreter identified."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-diagnose-full5-sidecar716.py').read_text(encoding='utf-8')
source = source.replace('716', '717').replace('import sys\n', 'import sys\nimport psutil\n')
source = source.replace('stack_exit = None\n', 'stack_exit = None\nobserved_processes = []\nowned_descendants = []\n')
source = source.replace(
    "except subprocess.TimeoutExpired:\n    with (private / 'stack.txt').open('wb') as stream:",
    """except subprocess.TimeoutExpired:
    parent = psutil.Process(process.pid)
    owned_descendants = [(child.pid, child.create_time()) for child in parent.children(recursive=True)]
    for pid, created in [(parent.pid, parent.create_time()), *owned_descendants]:
        try:
            child = psutil.Process(pid)
            if child.create_time() != created:
                continue
            observed_processes.append({'pid': pid, 'parent': child.ppid(), 'name': child.name(),
                                       'rss': child.memory_info().rss, 'exe': child.exe()})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    write(private / 'processes.json', observed_processes)
    target_pid = max(observed_processes, key=lambda item: item['rss'])['pid'] if observed_processes else process.pid
    with (private / 'stack.txt').open('wb') as stream:""",
)
source = source.replace("'--pid', str(process.pid)", "'--pid', str(target_pid)")
source = source.replace(
    '    if killed:\n        process.kill()',
    """    if killed:
        for pid, created in owned_descendants:
            try:
                child = psutil.Process(pid)
                if child.create_time() == created:
                    child.kill()
                    child.wait(timeout=3.0)
            except psutil.NoSuchProcess:
                pass
        if process.poll() is None:
            process.kill()""",
)
source = source.replace("'stack_exit_code': stack_exit,", "'stack_exit_code': stack_exit, 'observed_processes': observed_processes,")
assert 'target_pid' in source and 'owned_descendants' in source
exec(compile(source, __file__, 'exec'))
