from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-os-provider416'
out.mkdir(exist_ok=False)
for source, target in [('c03-os416-provider.log', 'provider.log'), ('c03-os416-integration.log', 'integration.log'), ('c03-os416-provider-compile-failure.log', 'compile-failure.log'), ('c03-os416-fast.log', 'fast-eol-failure.log')]:
    shutil.copyfile(Path(os.environ['TEMP']) / source, out / target)
paths = ['tests/Baxy.Integration.Tests/GpuSystemStatusHandlerTests.cs', 'tests/Baxy.Integration.Tests/SystemStatusHandlerTests.cs', 'tests/Baxy.Providers.Windows.Tests/SystemStatus/WindowsSystemStatusProviderTests.cs']
for name in paths:
    path = root / name
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))

# Repair the report's typographical join, not the saved measurement or prereg.
p = base / 'astra-os-caption415/RESULT.md'
p.write_text(p.read_text(encoding='utf-8').replace('«versión»+al', '«versión»\nal'), encoding='utf-8', newline='\n')
pin = p.parent / 'PINS.json'
pins = json.loads(pin.read_text())
pins[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
pin.write_text(json.dumps(pins, indent=2) + '\n', newline='\n')

script = '''$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Get-CimInstance -ClassName Win32_OperatingSystem -Property Caption,Version,ProductType |
    Select-Object Caption,Version,ProductType | ConvertTo-Json -Compress
'''
measurements = []
for _ in range(3):
    started = time.monotonic()
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, encoding='utf-8', timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr
    measurements.append({'utc': datetime.now(timezone.utc).isoformat(), 'seconds': round(time.monotonic()-started, 3), 'observed': json.loads(result.stdout)})
(out / 'CIM_OBSERVATION.json').write_text(json.dumps({'command': script, 'measurements': measurements}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

source = (root / 'scratchpad/c03-account-product411.py').read_text(encoding='utf-8')
source = source.replace('astra-account-product411', 'astra-os-product417').replace('C03-account-product411-private', 'C03-os-product417-private').replace('C03-account-profile411', 'C03-os-profile417').replace('c03-owner411-hook', 'c03-owner417-hook')
old = next(line for line in source.splitlines() if line.startswith('cases = '))
source = source.replace(old, old + " + ['¿Qué versión de Windows tengo?', 'How much RAM does this computer have?', '¿Qué procesador tiene este PC?']")
source = source.replace('source410', 'source416').replace('Six synthetic development turns', 'Nine synthetic development turns').replace('Four Windows-account requests, one OS version, one account concept.', 'Same six411 turns in their original order, followed by Spanish OS, English RAM and Spanish CPU controls. Only source416 OS provider/typed fact transport changed.').replace('Put English username first to observe actual cold-start limitation known in408;', 'Keep the original English username first;411 already passed it cold;').replace('OS version uses system.status;', 'OS version uses system.status and agrees with independent CIM observed caption; RAM/CPU remain correct;')
source = source.replace("'sources':{name:sha(root/name) for name in [", "'sources':{name:sha(root/name) for name in ['src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProbe.cs','src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProvider.cs','src/Baxy.Providers.Windows/SystemStatus/SystemStatusContracts.cs','src/Baxy.Core/Operations/SystemStatusHandler.cs','src/Baxy.Core/Operations/CoreOperationModels.cs',")
target = root / 'scratchpad/c03-os-product417.py'
assert not target.exists()
compile(source, str(target), 'exec')
target.write_text(source, encoding='utf-8', newline='\n')
hook = root / 'scratchpad/c03-owner417-hook'
hook.mkdir(exist_ok=False)
text = (root / 'scratchpad/c03-owner411-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-account-product411-private', 'C03-os-product417-private')
(hook / 'sitecustomize.py').write_text(text, encoding='utf-8', newline='\n')
print(json.dumps({'416':str(out), 'cim':measurements, '417':'prepared, not started'}))
