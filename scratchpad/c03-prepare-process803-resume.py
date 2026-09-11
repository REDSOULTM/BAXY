"""Prepare, without running, the remaining41 sealed process cases after RAM abort."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "scratchpad/c03-process-batch803-resume.py"
assert not target.exists()
source = (root / "scratchpad/c03-process-batch803.py").read_text(encoding="utf-8")
source = source.replace("PROCESS_BATCH803'", "PROCESS_BATCH803_RESUME'")
source = source.replace("C03-process-batch803-private'", "C03-process-batch803-resume-private'")
source = source.replace("C03-process-profile803'", "C03-process-profile803-resume'")
anchor = "assert len(panel) == 50 and len({c['case_id'] for c in panel}) == 50\n"
assert source.count(anchor) == 1
source = source.replace(anchor, anchor + """previous = ROOT / 'artifacts/comprobaciones/C03/PROCESS_BATCH803'
previous_private = PRIVATE.parent / 'C03-process-batch803-private'
previous_exit = read(previous / 'EXIT.json')
assert previous_exit['exit_code'] == 1
assert all(previous_exit[key] for key in ('manifest_unchanged', 'sources_unchanged',
    'source802_unchanged', 'source764_unchanged', 'runner_unchanged', 'app_dll_unchanged'))
assert read(previous / 'RESOURCES.json')['violations'] == ['system_free_ram_bound']
previous_review = read(previous_private / 'live-review.json')
assert len(previous_review) == 9
assert [case['case_id'] for case in previous_review] == [case['case_id'] for case in panel[:9]]
assert len(read(previous_private / 'root-adjudication.json')) == 9
panel = panel[9:]
assert len(panel) == 41
""")
start = source.index("# Use the launcher build path before sealing.")
end = source.index("paths = subprocess.check_output(", start)
source = source[:start] + """# Same DLL/source as the first segment; no new build or idle server.
preparation_stdout = (previous_private / 'build-preparation.log').read_bytes()
shutdown_stdout = (previous_private / 'build-servers-shutdown.log').read_bytes()
""" + source[end:]
source = source.replace("app_sha = sha(app)", "app_sha = sha(app)\nassert app_sha == read(previous / 'PREREG.json')['app_dll_sha256']")
source = source.replace("write_bytes(preparation.stdout)", "write_bytes(preparation_stdout)")
source = source.replace("write_bytes(shutdown.stdout)", "write_bytes(shutdown_stdout)")
source = source.replace("(PRIVATE / 'panel.json').write_bytes(panel_path.read_bytes())", "write(PRIVATE / 'panel.json', panel)")
source = source.replace("'method': 'Registered50 process-read category with sealed candidate802; nine historical requests and41 variants. Build prepared before sealing DLL; model selection is closed.'",
    "'method': 'Remaining41 of sealed50 after RAM interruption803. First9 finals and interrupted next attempt preserved. Same candidate802 and DLL; new isolated profile, so not50 continuous turns. No model comparison.'")
source = source.replace("'registered_turns': 50", "'registered_turns': 41")
source = source.replace("'profile': 'Fresh isolated private conductor profile, wake disabled.'",
    "'profile': 'New isolated profile after RAM abort. Cases10-50 in original order; first9 and interrupted attempt remain separately recorded. Wake disabled.'")
compile(source, str(target), "exec")
target.write_bytes(source.encode("utf-8"))
review = (root / "scratchpad/c03-review-process803.py").read_text(encoding="utf-8")
review = review.replace("C03-process-batch803-private'", "C03-process-batch803-resume-private'")
review = review.replace("PROCESS_BATCH803'", "PROCESS_BATCH803_RESUME'")
review = review.replace("assert len(panel) == 50", "assert len(panel) == 41")
review_target = root / "scratchpad/c03-review-process803-resume.py"
assert not review_target.exists()
compile(review, str(review_target), "exec")
review_target.write_bytes(review.encode("utf-8"))
print("Prepared remaining41, no launch; first9 and original panel preserved.")
