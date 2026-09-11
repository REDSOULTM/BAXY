"""Seal the process repair candidate before its integrated Full gate."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/PROCESS_REPAIR796'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-process-source796-private'
assert not out.exists() and not private.exists()
out.mkdir()
private.mkdir()
paths = [
    'src/Baxy.App/OperationResponseProjection.cs',
    'src/Baxy.Core/Operations/CoreOperationModels.cs',
    'src/Baxy.Core/Operations/ProcessListHandler.cs',
    'src/Baxy.Kernel/Operations/OperationVisibleFacts.cs',
    'src/Baxy.Providers.Windows/SystemStatus/ProcessStatusContracts.cs',
    'src/Baxy.Providers.Windows/SystemStatus/WindowsProcessStatusProvider.cs',
    'src/baxy_mind/__main__.py', 'src/baxy_mind/effect_intent.py',
    'src/baxy_mind/llm.py', 'src/baxy_mind/measurement_prose_projection.py',
    'tests/Baxy.Integration.Tests/ProcessListHandlerTests.cs',
    'tests/Baxy.Providers.Windows.Tests/SystemStatus/WindowsProcessStatusProviderTests.cs',
    'tests/test_effect_intent.py', 'tests/test_c03_process_inventory.py',
]
pins = {}
for name in paths:
    raw = (root / name).read_bytes()
    pins[name] = hashlib.sha256(raw).hexdigest()
    target = private / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
(out / 'SOURCE_PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
(out / 'SOURCE_PATCH.diff').write_bytes(subprocess.check_output(['git', 'diff', '--binary', '--', *paths], cwd=root))
temp = Path(os.environ['TEMP'])
for old, new in [('c03-process796-fast.log', 'fast.log'),
                 ('c03-process796-owners2-py.log', 'owners-python.log'),
                 ('c03-process796-owners-net.log', 'owners-dotnet-before-app-limit.log'),
                 ('c03-process796-owners-py.log', 'owners-python-first.log')]:
    (out / new).write_bytes((temp / old).read_bytes())
state = {'utc': datetime.now(timezone.utc).isoformat(), 'candidate': 796, 'adopted': False,
         'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
         'private_snapshot': str(private), 'source_paths': len(paths),
         'changes': ['Current per-process CPU interval instead of lifetime rank; physical logical-core denominator.',
                     'Preserve process identities and complete bounded50 rows through Kernel and App.',
                     'Existing read-intent gate and argument parser understand ES/EN/mixed count/rank; closed cardinal/metric values preserved.',
                     'Project process count independently of returned rows; explicit current CPU and decimal resident MB.'],
         'validation': {'provider': '6 passed, 0 skips',
                        'integration_before_app_limit': '33 passed, 0 skips; final shared projection tested by upcoming Full',
                        'python_owners': '3248 passed in89.31s,0skips',
                        'fast': 'exit0;Release0warnings0errors22.87s', 'Full': 'pending'},
         'test_contract_update': 'The existing negative Qué proceso me come tanta RAM moves to positive request coverage because system.process.list now handles it. Biological/knowledge/past/tool-denial controls remain.',
         'survey': {'covered': 28, 'open': 714, 'not_applicable': 0}}
(out / 'CANDIDATE.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
base = out.parent
checkpoint = '796 candidato sellado14fuentes;3248Pythonpass0skip/89,31s,Fast0/Release22,87s. Provider6pass;33integración anteriores al último límiteApp. Full pendiente por cambiosC#+Python; sin adoptar.795 baseline4/50,28/714/0. SelecciónQwencerrada.'
p = base / 'CHECKPOINT.md'
p.write_text(checkpoint + '\n\n' + p.read_text(encoding='utf-8-sig'), encoding='utf-8')
p = base / 'RELEVO_ACTIVO.json'
relevo = json.loads(p.read_text(encoding='utf-8-sig'))
relevo.update(checkpoint=checkpoint, workStatus='process796_full_pending', activeValidation=None)
p.write_text(json.dumps(relevo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(state, ensure_ascii=False))
