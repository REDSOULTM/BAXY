from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private411 = local / 'C03-account-product411-private'
out411 = base / 'astra-account-product411'
def rows(path):
    return [json.loads(s) for s in path.open(encoding='utf-8-sig')]
events = rows(private411 / 'capture/events.jsonl')
activity = [r['event']['entry'] for r in events if r.get('event', {}).get('type') == 'activity' and r['event']['entry']['src'] in {'YOU', 'BAXY'}]
terminals = [r for r in events if r.get('type') == 'terminal']
turns = []
history = []
for entry in activity:
    if entry['src'] == 'YOU':
        turns.append({'request': entry['msg'], 'history': copy.deepcopy(history[-12:]), 'answers': []})
    elif turns:
        turns[-1]['answers'].append({'text': entry['msg'], 'route': entry.get('route')})
    history.append({'role': 'user' if entry['src'] == 'YOU' else 'assistant', 'content': entry['msg']})
assert len(turns) == len(terminals) == 6
journal = [r['payload'] for r in rows(local / 'C03-account-profile411/journal/missions.jsonl')]
identities = [r['response']['result'] for r in journal if r['operation'] == 'system.identity' and (r.get('response') or {}).get('verified')]
assert len(identities) == 3
real_names = {value for row in identities for value in row.values() if isinstance(value, str) and value}
def sanitized(text):
    for value in sorted(real_names, key=len, reverse=True):
        text = text.replace(value, '[WINDOWS_IDENTITY]')
    return text
reasons = ['Lectura real fría EN correcta; la preocupación408 no se reprodujo en este producto.',
    'Cuenta efectiva del proceso leída y narrada correctamente en español.',
    'Aclaración innecesaria: el usuario ya pidió la lectura. La primaria recita la cuenta previa; el selector posterior sí propone identity, pero observation_not_recital lo convierte en pregunta.',
    'Nueva lectura de la cuenta actual y narración correcta.',
    'Windows10 es incorrecto como nombre del producto: CIM observa Windows11 Home Single Language. El proveedor sólo entrega NT10.0/build26200 y la composición lo interpreta como nombre comercial.',
    'Concepto útil, sin lectura nueva.']
report = ['# 411 — producto real:4/6 útiles; aclaración y versión comercial pendientes', '',
    'Seis sintéticos,6admissions200,6finales,sin timeout/silencio,exit0,manifiesto intacto. Tres identity y una status verificadas. BAXY cerrado al terminar; sólo encuesta y nodos MSBuild inactivos permanecen.', '',
    'T1 usernameEN funciona aun con audit lexical y closed_refusal_withdrawn. No atribuirle el fallo frío previsto desde408 ni editar descriptor por un fallo que aquí no ocurrió. T3 también lexical, identity primero en28candidatos: no hay pérdida de herramienta. El nativo recita una cuenta ya vista; una segunda selección identifica la lectura pedida, pero __main__6288–6318 siempre pregunta antes de ella. T5 confunde la versiónNT10.0 con Windows10; consulta CIM independiente confirmó Microsoft Windows11 Home Single Language, versión10.0.26200. Resultado privado/journal conservan valores originales.', '',
    'No UI/voz física/aceptación fresca. Identificadores Windows se ocultan sólo en esta copia legible; no se alteran registros privados. Fuente410 sin cambios posteriores.', '']
for i, (turn, terminal, reason) in enumerate(zip(turns, terminals, reasons, strict=True), 1):
    report += [f"## {i} — {'fallo' if i in {3,5} else 'útil'}", '', turn['request'], '']
    for answer in turn['answers']:
        report += ['> ' + sanitized(answer['text']).replace('\n', '\n> '), '', 'Ruta: ' + str(answer['route']), '']
    report += [reason, '']
(out411 / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
(private411 / 'adjudicated-turns.json').write_text(json.dumps(turns, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(out411 / 'OS_OBSERVATION.json').write_text(json.dumps({'command': 'Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber', 'caption': 'Microsoft Windows 11 Home Single Language', 'version': '10.0.26200', 'buildNumber': '26200', 'observedUtc': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n', encoding='utf-8')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = [out411 / n for n in ['PREREG.json', 'RESULT.md', 'EXIT.json', 'OS_OBSERVATION.json']]
paths += [private411 / n for n in ['capture/events.jsonl', 'http-posts.jsonl', 'turn-audit.jsonl', 'compose-audit.jsonl', 'adjudicated-turns.json']]
paths += [local / 'C03-account-profile411/journal/missions.jsonl']
(out411 / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', encoding='utf-8')

case_dir = local / 'C03-read-recovery412-cases-private'
case_dir.mkdir(exist_ok=False)
actual = turns[2]
cases = [{'id': 'actual411-t3', 'request': actual['request'], 'history': actual['history'], 'expected': 'Perform the explicitly requested system.identity read; do not ask whether to perform it or present historical prose as a new observation.'}]
cases += json.loads((root / 'scratchpad/c03-descriptor-mind409-cases.json').read_text(encoding='utf-8'))['cases']
case_path = case_dir / 'cases.json'
case_path.write_text(json.dumps({'cases': cases}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

source = (root / 'scratchpad/c03-descriptor-mind409.py').read_text(encoding='utf-8')
for a, b in [('astra-descriptor-mind409', 'astra-read-recovery412'), ('C03-descriptor-mind409-private', 'C03-read-recovery412-private'), ('catalog409', 'catalog412'), ('close409', 'close412')]:
    source = source.replace(a, b)
source = source.replace("cases_path = root / 'scratchpad/c03-descriptor-mind409-cases.json'", "cases_path = Path(" + repr(str(case_path)) + ")")
lines = []
for line in source.splitlines():
    if line.startswith("hook_source += '") and 'effect_intent' in line:
        continue
    if line.startswith('replacement = '):
        continue
    if line.startswith("prereg = {'new_description': replacement, 'utc':"):
        line = line.replace("'new_description': replacement, ", '')
    if line.strip() == "env['BAXY_C03_SCOPE405'] = 'identity-scope'":
        line = "    env['BAXY_C03_EARLY_READ412'] = variant"
    if line.strip() == "if variant == 'descriptor':" or "next(c for c in current_capabilities if c['name'] == 'system.identity')['description'] = replacement" in line:
        continue
    lines.append(line)
source = '\n'.join(lines) + '\n'
source = source.replace("for variant in ['baseline', 'descriptor']:", "for variant in ['baseline', 'early-read']:")
source = source.replace("(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')", "hook_source += (root / 'scratchpad/c03-early-read412-hook.py').read_text(encoding='utf-8')\n(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')")
source = source.replace("'cases': cases,", "'case_ids': [c['id'] for c in cases], 'private_case_file': str(cases_path),")
fields = {
    'method': 'Fourteen fixed development cases: actual411T3 with exact last12role history plus13controls409. Source410 and current authenticated catalog, same model/template/sampler, two sequential warm sidecars. Diagnostic-only variant runs a second existing native decision over the first4 offered candidates when the primary is knowledge/social without effects, and retains it only if all proposed operations have authenticated read_only risk. The normal information/domain/compound/action/grounding/confirmation guards still run. No injected answers, fixed identity operation, effect execution, source change or promotion. Original late fallback remains in this diagnostic; successful adoption must move the existing repair rather than add duplicate passes.',
    'reason': '411T3 native primary recites account from prior prose; actual existing later AUTO picks identity. observation_not_recital unconditionally asks permission for that already requested read. Test whether preserving a native read proposal before ordinary guards avoids the extra clarification. The earlier rejected expansion for unsupported turns is excluded; only knowledge/social with catalog candidates. Native tool mechanics/one-sided veto research already documented.',
    'criteria': 'Actual repeat-account read becomes identity; all four account controls and three resource controls remain correct; concept/prohibition and four names remain useful no-effect. No write operation is promoted by the diagnostic. Compare drafts/final/stages, latency and native-call count. This is full mind without effects, not acceptance or UI.'}
lines = []
for line in source.splitlines():
    key = next((key for key in fields if line.startswith('    '+repr(key)+':')), None)
    lines.append('    '+repr(key)+': '+repr(fields[key])+',' if key else line)
source = '\n'.join(lines) + '\n'
needle = "        evidence_status = client.request({'id': 'evidence407-initial'"
position = source.index(needle)
cold_probe = '''        cold_case = cases[0]
        started_cold = time.monotonic()
        cold_reply = client.request({'id': cold_case['id'] + '-cold', 'type': 'turn.decide', 'text': cold_case['request'], 'history': cold_case['history'], 'pendingClarification': False, 'uiLanguage': 'es'}, 60)
        cold_result = {'id': cold_case['id'], 'phase': 'cold', 'variant': variant, 'seconds': round(time.monotonic() - started_cold, 3), 'reply': cold_reply}
        with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(cold_result, ensure_ascii=False) + '\\n')
        print(json.dumps(cold_result, ensure_ascii=True), flush=True)
'''
source = source[:position] + cold_probe + source[position:]
source = source.replace("'variant': variant, 'seconds': round(time.monotonic() - start, 3)", "'phase': 'warm', 'variant': variant, 'seconds': round(time.monotonic() - start, 3)")
source = source.replace('two sequential warm sidecars.', 'two sequential sidecars: actual411T3 first immediately after catalog.ready, then the14cases after semantic readiness (15requests per arm). Audit must confirm lexical mode for the initial target before attributing its comparison to the real411 boundary.')
target = root / 'scratchpad/c03-read-recovery412.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
print(json.dumps({'411_useful': 4, '411_failures': 2, '412_cases': len(cases), 'prepared': True}))
