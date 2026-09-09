from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
source410 = base / 'astra-account-catalog410'
log = source410 / 'turn-policy.log'
assert not log.exists()
log.write_bytes((Path(os.environ['TEMP']) / 'c03-account-catalog410-turn-policy.log').read_bytes())
with (source410 / 'RESULT.md').open('a', encoding='utf-8') as stream:
    stream.write('\nValidación adicional del consumidor de turnos: `pytest tests/test_turn_policy.py -q`:967passed,0skips,4,68s. Sin nueva edición de fuente.\n')
pins = json.loads((source410 / 'PINS.json').read_text(encoding='utf-8'))
for path in [log, source410 / 'RESULT.md']:
    pins[str(path)] = sha(path)
(source410 / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')

out413 = base / 'astra-read-recovery413'
with (out413 / 'RESULT.md').open('a', encoding='utf-8') as stream:
    stream.write('''
## Segunda selección nativa inspeccionada

Con los mismos mensajes, el top4 frío es identity/status/folder.open/notification.diagnose
y devuelve identity. El top4 caliente es identity/notification.cancel.at/
notification.cancel.latest/notification.diagnose y recita el resultado anterior.
El hook actual filtra risk read_only después de la propuesta, pero ofrece efectos
de escritura en la propia revisión de lectura.414 compara únicamente filtrar el
catálogo por riesgo read_only antes de tomar cuatro candidatos. No nueva descripción,
prompt, nombre de operación fijado ni cambio de modelo. La primaria28tools se conserva.
''')
pins = json.loads((out413 / 'PINS.json').read_text(encoding='utf-8'))
for path in [out413 / 'RESULT.md', local / 'C03-read-recovery413-private/actual-target-native-sequence.json']:
    pins[str(path)] = sha(path)
(out413 / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')

source = (root / 'scratchpad/c03-read-recovery413.py').read_text(encoding='utf-8')
for a, b in [('astra-read-recovery413', 'astra-read-candidates414'), ('C03-read-recovery413-private', 'C03-read-candidates414-private'), ('catalog413', 'catalog414'), ('close413', 'close414'), ('c03-early-read413-hook.py', 'c03-read-candidates414-hook.py')]:
    source = source.replace(a, b)
source = source.replace("for variant in ['baseline', 'early-read']:", "for variant in ['early-read', 'read-only-candidates']:")
source = source.replace("    client = JsonLineProcess", "    trace_path = private / 'http-posts.jsonl'\n    trace_offset = trace_path.stat().st_size if trace_path.exists() else 0\n    client = JsonLineProcess")
begin = source.index("        cold_primary = next(")
end = source.index("        exact = cold_primary == reference", begin)
source = source[:begin] + '''        with trace_path.open(encoding='utf-8-sig') as cold_trace:
            cold_trace.seek(trace_offset)
            cold_primary = next(row['payload'] for line in cold_trace
                                if (row := json.loads(line)).get('stage') == 'request'
                                and len(row['payload'].get('tools', [])) == 28
                                and row['payload']['messages'][-1].get('content') == cold_case['request'])
''' + source[end:]
fields = {
    'method': 'Same14development cases413, including exact411native history/welcome; target cold then14warm per arm. Two sequential sidecars, same source410/catalog/model/template/sampler. Both use diagnostic early-read hook; ONLY new arm filters candidates to authenticated read_only risk BEFORE selecting the first4 for the secondary native request. Primary28tools remains identical. Both still retain only read proposals and run normal downstream guards. No effects, injected answers, operation hardcoding, source edits or promotion. Check each arms own first primary from its trace byte offset against411 before continuing.',
    'reason': '413 improved cold target but warm secondAUTO still recited. actual-target-native-sequence proves cold top4 identity/status/folder.open/notification.diagnose selects identity, while warm identity/cancel.at/cancel.latest/diagnose recites. The observation-recovery review should not offer writing operations. Test typed-risk candidate filtering instead of another identical pass, prompt, seed or catalog descriptor.',
    'criteria': 'Compared with413early-read14/15, repair warm target without losing cold target or13controls. All proposed recovery effects read_only, all normal guards retained; count native calls and latency. No source adoption based only on availability or nonempty prose. The original late fallback remains only for this diagnostic and must be retired/reused if implementation follows.'}
lines = []
for line in source.splitlines():
    key = next((key for key in fields if line.startswith('    '+repr(key)+':')), None)
    lines.append('    '+repr(key)+': '+repr(fields[key])+',' if key else line)
source = '\n'.join(lines) + '\n'
target = root / 'scratchpad/c03-read-candidates414.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
hook_source = (root / 'scratchpad/c03-early-read413-hook.py').read_text(encoding='utf-8')
hook_source = hook_source.replace('C03-read-recovery413-private', 'C03-read-candidates414-private')
hook_source = hook_source.replace("== 'early-read':", "in {'early-read', 'read-only-candidates'}:")
hook_source = hook_source.replace("            second = _prior_decide412(self, text, candidates[:4], history=history, evidence=evidence)", "            read_candidates = [c for c in candidates if c['name'] in _reads412] if os.environ.get('BAXY_C03_EARLY_READ412') == 'read-only-candidates' else candidates\n            if not read_candidates:\n                return primary\n            second = _prior_decide412(self, text, read_candidates[:4], history=history, evidence=evidence)")
(root / 'scratchpad/c03-read-candidates414-hook.py').write_text(hook_source, encoding='utf-8')
print('414 prepared; no source change;410 extra owner967passed')
