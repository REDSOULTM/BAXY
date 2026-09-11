"""Two paired full-HEAD snapshot probes; change only Git checkout workers."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
output = root / "artifacts/comprobaciones/C03/astra-packaging-workers720"
output.mkdir(exist_ok=False)
source = (root / "scratchpad/c03-packaging-phases718.py").read_text(encoding="utf-8")
source = source.replace('instrumented.write_text(helper, encoding="utf-8")', 'instrumented.write_text(segment, encoding="utf-8")')
source = source.replace('command.replace(old_import, f". \'{instrumented}\'\\n',
                        'command.replace(old_import, old_import + f"\\n. \'{instrumented}\'\\n')
source = source.replace('import time\n', 'import time\nimport threading\nimport psutil\n')
source = source.replace('deadline_passed = False\n', '''deadline_passed = False
peak_rss = 0
max_children = 0
stop_observer = threading.Event()
def observe(pid):
    global peak_rss, max_children
    while not stop_observer.wait(0.2):
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            rss = parent.memory_info().rss
            for child in children:
                try:
                    rss += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            peak_rss = max(peak_rss, rss)
            max_children = max(max_children, len(children))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return
''')
source = source.replace('    try:\n        code = process.wait(timeout=45)', '''    observer = threading.Thread(target=observe, args=(process.pid,), daemon=True)
    observer.start()
    try:
        code = process.wait(timeout=45)''')
source = source.replace('elapsed = time.monotonic() - started\n', '''stop_observer.set()
observer.join(timeout=2)
elapsed = time.monotonic() - started
''')
source = source.replace('"phases": phase_lines, "snapshot_absent"', '"phases": phase_lines, "peak_rss_mib": peak_rss / 1048576, "max_children": max_children, "snapshot_absent"')
profiles = [("pair1-original", None), ("pair1-workers2", 2),
            ("pair2-workers2", 2), ("pair2-original", None)]
(output / "PLAN.json").write_text(json.dumps({
    "profiles_in_order": profiles, "same_commit_and_full_worktree": True,
    "same_original_45_second_deadline": True,
    "difference": "per-command checkout.workers=2 only; no global Git configuration",
    "resource_observer": "same 0.2-second RSS observer in both profiles",
    "source": "https://git-scm.com/docs/git-checkout#Documentation/git-checkout.txt-checkoutworkers",
    "rationale": "Two installed drives are NVMe SSDs; official docs describe possible SSD gains, to be measured",
    "source_adopted": False, "coverage_added": 0,
}, indent=2) + "\n", encoding="utf-8")
for tag, workers in profiles:
    candidate = source.replace('astra-packaging-phases718"', f'astra-packaging-workers720/{tag}"')
    candidate = candidate.replace('BAXY/C03-packaging-phases718-private"', f'BAXY/C03-packaging-workers720-{tag}-private"')
    if workers:
        marker = 'helper = helper[:start] + segment + helper[end:]'
        replacement = '''segment = segment.replace(
    "& git -C $repositoryFull worktree add --detach",
    "& git -c checkout.workers=2 -C $repositoryFull worktree add --detach")
helper = helper[:start] + segment + helper[end:]'''
        assert candidate.count(marker) == 1
        candidate = candidate.replace(marker, replacement)
    exec(compile(candidate, __file__, "exec"), {"__file__": __file__})
    print("Completed " + tag, flush=True)
