"""Freeze a whole process-read category and reuse the existing product conductor."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-process-panel795-private'
TARGET = ROOT / 'scratchpad/c03-process-batch795.py'
assert not PRIVATE.exists() and not TARGET.exists()
requirements = PRIVATE.parent / 'C03-survey-requirements336-private/requirements.jsonl'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
scope = {'H0133': 'list', 'H0158': 'list', 'H0169': 'unspecified_rank', 'H0470': 'count',
         'H0669': 'unspecified_rank', 'H0678': 'count', 'H0364': 'cpu_rank',
         'H0650': 'memory_rank', 'H0675': 'app_memory'}
criteria = {
    'list': 'Fresh system.process.list observation. Name returned process instances faithfully; if only a subset is returned, identify that limit and observed count. Do not call a bounded/access-limited enumeration an exhaustive system list.',
    'count': 'Fresh process observation; report the observed process count, not the number of rows returned. Disclose any observed enumeration/access limit; do not fabricate an exact system-wide count from a subset.',
    'memory_rank': 'Fresh system.process.list sorted by memory with the requested top count when specified. Preserve process identities/PIDs and workingSetBytes with accurate units. Do not merge instances or call working set private/committed/app-total memory.',
    'cpu_rank': 'Current CPU ranking requires interval-based CPU measurements, not totalProcessorSeconds since start. Fresh data, requested top count, correct units and process membership. A truthful limitation is not completion of an available requested current-CPU read; retain the missing provider measurement as a blocker.',
    'unspecified_rank': 'Use a clearly declared metric backed by a fresh process reading, or ask one concise CPU-versus-memory clarification. A memory ranking may not be presented as current CPU; any claimed values require fresh observation.',
    'app_memory': 'Identify the requested largest memory-using app from fresh evidence sufficient for app membership and aggregation. A single process working set is not the total of a multi-process app; do not invent aggregation or reuse a prior turn.',
}
panel = []
with requirements.open(encoding='utf-8-sig') as stream:
    for line in stream:
        row = json.loads(line)
        if row.get('case_id') not in scope:
            continue
        assert row['expected_capability'] is True and row['human_attestation'] is True
        group = scope[row['case_id']]
        panel.append({'case_id': row['case_id'], 'text': row['literal'], 'group': group,
                      'criterion': criteria[group], 'origin': 'owner_confirmed_historical_development',
                      'verification_status_before': row['verification_status']})
assert len(panel) == 9
variants = {
    'list': [
        'Muéstrame los procesos que están en ejecución.',
        'Lista los procesos activos del equipo.',
        'Qué procesos están funcionando en este PC?',
        'Dime cuáles son los procesos que ves ahora.',
        'Lista cinco procesos que estén corriendo.',
        'Show the running processes on this PC.',
        'Which processes are running right now?',
        'List the processes by name.',
        'Mostrame los running processes.',
    ],
    'count': [
        'Cuántos procesos están en ejecución ahora?',
        'Dime el número de procesos que hay corriendo.',
        'Cuenta los procesos activos del PC.',
        'Quiero saber cuántos procesos pudiste observar.',
        'Qué cantidad de procesos está funcionando?',
        'How many processes are running on this PC?',
        'Count the running processes.',
        'What is the observed process count?',
        'Cuántos processes están running?',
        'Dime cuántos procesos hay, sin listarlos.',
    ],
    'memory_rank': [
        'Lista los tres procesos que más RAM usan.',
        'Qué proceso ocupa más memoria RAM?',
        'Muéstrame los cinco procesos con más uso de memoria.',
        'Ordena los procesos por consumo de memoria.',
        'Qué dos procesos tienen más memoria residente?',
        'Show the top three processes by memory usage.',
        'Which process uses the most RAM?',
        'List five processes with the largest working set.',
        'Mostrame el top 2 de processes por RAM.',
        'Dime qué procesos consumen más memoria, con sus valores.',
    ],
    'cpu_rank': [
        'Cuáles son los dos procesos que más CPU usan ahora?',
        'Muéstrame los tres procesos con más uso actual del procesador.',
        'Qué proceso está consumiendo más CPU en este momento?',
        'Lista cinco procesos por uso actual de CPU.',
        'Quiero ver los procesos que más procesador consumen ahora.',
        'Which processes are using the most CPU right now?',
        'Show the top three processes by current CPU usage.',
        'Which process is using the most CPU at the moment?',
        'List two processes by current CPU consumption.',
        'Dame el top 3 de processes por CPU actual.',
    ],
    'unspecified_rank': [
        'Qué procesos están gastando más recursos?',
        'Which processes are consuming the most resources?',
    ],
}
for group, texts in variants.items():
    for index, text in enumerate(texts, 1):
        panel.append({'case_id': f'process795-{group}-{index:02d}', 'text': text, 'group': group,
                      'criterion': criteria[group], 'origin': 'synthetic_development_variant'})
assert len(panel) == len({r['case_id'] for r in panel}) == 50
PRIVATE.mkdir()
panel_path = PRIVATE / 'panel.json'
panel_path.write_bytes((json.dumps(panel, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
plan = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': len(panel), 'human_requirements': list(scope),
        'groups': dict(Counter(r['group'] for r in panel)), 'panel_sha256': sha(panel_path),
        'requirements_sha256': sha(requirements), 'criteria': criteria,
        'coverage_rule': 'All complete answers judged against fresh typed observations and every relevant variant. No automatic coverage from terminal status, literal success, or a truthful limitation. Names and values vary with the real process snapshots; language, phrasing and requested ranks vary across the frozen panel.',
        'effect_scope': 'Only read process state, counts and resource rankings. No closing processes, opening apps, changing settings or writing user files. Dedicated private conductor profile; no UI/voice credit.',
        'known_blockers': '772 already demonstrated lifetime CPU seconds mislabelled as current usage and missing fresh app-memory reading. This panel also probes six additional human requests and41 variants as one category; it does not reopen model selection.',
        'source': 'Published793/65761a14;3134 owner passes,1 environmental STT skip,121 subtests andFast0. Registered Qwen manifest unchanged.'}
plan_path = BASE / 'PROCESS_CATEGORY795_PLAN.json'
assert not plan_path.exists()
plan_path.write_bytes((json.dumps(plan, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
s = (ROOT / 'scratchpad/c03-status-batch772.py').read_text(encoding='utf-8')
s = s.replace('772', '795').replace('STATUS_BATCH795', 'PROCESS_BATCH795').replace('C03-status-batch795-private', 'C03-process-batch795-private').replace('C03-status-profile795', 'C03-process-profile795')
s = s.replace('Frozen 73-case status regression', 'Frozen 50-case process-read category')
s = s.replace("panel_path = PRIVATE.parent / 'C03-status-batch729-private/panel.json'", "panel_path = PRIVATE.parent / 'C03-process-panel795-private/panel.json'")
s = s.replace("'artifacts/comprobaciones/C03/STATUS_BATCH689_PLAN.json'", "'artifacts/comprobaciones/C03/PROCESS_CATEGORY795_PLAN.json'")
s = s.replace('== 73', '== 50').replace("'registered_turns': 73", "'registered_turns': 50")
s = s.replace('pins771', 'pins793').replace('source771', 'source793').replace('INVENTORY_SCOPE771', 'INVENTORY_VETO793')
s = s.replace('Registered73 product regression after inventory scope and correction771 with dense764; original panel/criteria. Build prepared before sealing DLL; no model comparison.', 'Registered50 process-read category with published793; nine historical requests and41 variants. Build prepared before sealing DLL; model selection is closed.')
s = s.replace('Published771 owners/current pin integrity and Fast, dense764 owners/Fast retained. Full7 historical, no final acceptance.', 'Published793 owners/current pin integrity and Fast, dense764 unchanged. Full7 historical; not final acceptance.')
s = s.replace('73-case registered category runner694', 'Registered category runner772, original per-turn budget retained')
s = s.replace("'covered': 26, 'open': 716", "'covered': 28, 'open': 714")
compile(s, str(TARGET), 'exec')
TARGET.write_bytes(s.encode('utf-8'))
print(json.dumps({'cases': len(panel), 'groups': plan['groups'], 'driver': str(TARGET)}, ensure_ascii=False))
