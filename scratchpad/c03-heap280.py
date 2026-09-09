"""Preserve the authorized owner conversation via a private managed heap dump."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import psutil

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-heap280'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-owner264-heap280'
private.mkdir(exist_ok=False)
tool = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-diagnostics-tools/dotnet-dump.exe'
process = psutil.Process(84328)
assert process.name().casefold() == 'baxy.exe'
assert abs(process.create_time() - 1788820609.3516054) < .01
dump = private / 'owner264.dmp'
command = [str(tool), 'collect', '--process-id', '84328', '--type', 'Heap', '--output', str(dump)]
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'method': 'Official .NET diagnostic tool captures only Baxy.exe managed heap to private local storage. Owner authorized session review and PC control. No memory edits, UI input, restart, inference or effects. Recover MainWindowViewModel.Messages, not arbitrary process strings.',
    'process': {'pid': process.pid, 'createTime': process.create_time(), 'exe': process.exe()},
    'command': command, 'toolVersion': '10.0.731102', 'toolSha256': hashlib.sha256(tool.read_bytes()).hexdigest(),
    'primarySource': 'https://learn.microsoft.com/en-us/dotnet/core/diagnostics/dotnet-dump',
    'privateDirectory': str(private), 'completeTranscriptRecovered': False}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
with (private / 'collect.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
report = {'utc': datetime.now(timezone.utc).isoformat(), 'exitCode': result.returncode,
    'dumpExists': dump.is_file(), 'dumpBytes': dump.stat().st_size if dump.is_file() else 0,
    'ownerProcessStillRunning': process.is_running()}
if dump.is_file():
    with dump.open('rb') as handle:
        report['dumpSha256'] = hashlib.file_digest(handle, 'sha256').hexdigest()
(out / 'COLLECT.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report), flush=True)
raise SystemExit(result.returncode)
