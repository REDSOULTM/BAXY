from datetime import datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import textwrap

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private_base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'astra-stored-product404b'
private = private_base / 'C03-stored-product404b-private'
def rows(path):
    return [json.loads(line) for line in path.open(encoding='utf-8-sig')]
events = rows(private / 'capture/events.jsonl')
activity = [r['event']['entry'] for r in events if r.get('event', {}).get('type') == 'activity'
            and r['event']['entry']['src'] in {'YOU', 'BAXY'}]
terminals = [r for r in events if r.get('type') == 'terminal']
turns = []
for event in activity:
    if event['src'] == 'YOU':
        turns.append({'request': event['msg'], 'answers': []})
    elif turns:
        turns[-1]['answers'].append({'text': event['msg'], 'route': event.get('route')})
assert len(turns) == len(terminals) == 6
verdicts = [
    ('útil', 'Causa memoria deshabilitada y confirmación de activación honestas.'),
    ('parcial', 'Activación/guardado reales, narración genérica.'),
    ('útil', 'LecturaJordan conserva el valorEN.'),
    ('fallo', 'Composición agotada, final ausente ante presentación normal; no sustituirlo por el terminal técnico.'),
    ('fallo', 'Esta vez sí pasa por resultado de lectura y diceMi nombreJordan; sujeto incorrecto.'),
    ('útil', '404 conserva conversación actual: respondeÁlvaro, noJordan persistido.'),
]
def primary(folder):
    return next(r['payload'] for r in rows(folder / 'http-posts.jsonl')
                if r.get('stage') == 'request' and len(r['payload'].get('tools', [])) == 28
                and r['payload']['messages'][-1].get('content') == 'Me llamo Álvaro.')
same_primary = primary(private) == primary(private_base / 'C03-stored-product402b-private')
report = ['#404b — nombre conversacional correcto; presentación y composición abiertas', '',
    'Seis sintéticos:3útiles,1parcial,2fallos. Una composition_failed, no timeout;6admissions200, exit0, manifiesto intacto. No UI/voz física/aceptación fresca.', '',
    'T6 mejoró deJordan persistido aÁlvaro del diálogo. T4 ahora agota composición en lugar de aclarar; T5, sin aclaración pendiente que lo desvíe, vuelve a leer memoria y atribuyeJordan aBAXY. No convertir estas diferencias en mejora general ni ocultar el final ausente.', '',
    f'Comparación del primer payload nativo28tools de Me llamoÁlvaro con402b: igualdad={same_primary}. La fuente404 sólo cambia el dispatch de consulta genérica; no atribuir variaciónT4 a un nuevo prompt ni borrar ninguna corrida.', '']
for i, (turn, terminal, verdict) in enumerate(zip(turns, terminals, verdicts), 1):
    turn.update(terminal=terminal, verdict=verdict[0], reason=verdict[1])
    report += [f'## {i}. {verdict[0]}', '', '**Entrada:** ' + turn['request'], '']
    for answer in turn['answers']:
        report += ['> ' + answer['text'].replace('\n', '\n> '), '', 'Ruta: ' + str(answer['route']), '']
    if not turn['answers']:
        report += ['Sin prosa final. Terminal: ' + terminal['kind'] + '.', '']
    report += [verdict[1], '']
assert not (out / 'RESULT.md').exists()
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
(out / 'replies.json').write_text(json.dumps(turns, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(out / 'comparison.json').write_text(json.dumps({'t4_primary_equals402b': same_primary}, indent=2) + '\n', encoding='utf-8')
paths = [out / n for n in ['PREREG.json', 'RESULT.md', 'replies.json', 'comparison.json', 'EXIT.json']]
paths += [private / n for n in ['capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl', 'http-posts.jsonl']]
paths += [private_base / 'C03-stored-profile404b/journal/missions.jsonl']
(out / 'PINS.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2) + '\n', encoding='utf-8')

previous = json.loads((root / 'scratchpad/c03-generic-mind403-cases.json').read_text(encoding='utf-8'))['cases']
cases = [copy.deepcopy(c) for c in previous if c['id'].startswith('account-')]
for identifier, request, expected in [
    ('username-en', 'What is my Windows username?', 'system.identity, not resource/OS status.'),
    ('username-es', 'Dime la cuenta actual de Windows.', 'system.identity, not resource/OS status.'),
    ('os-version', 'Which Windows version am I running?', 'system.status, OS version scope preserved.'),
    ('os-memory', 'Qué Windows tengo y cuánta RAM tiene esta máquina', 'system.status, OS and memory scope preserved.'),
    ('cpu', 'Dime el uso actual de la CPU.', 'system.status, CPU scope preserved.'),
    ('concept', '¿Qué es una cuenta de Windows?', 'Explain account concept; no PC operation.'),
    ('negative', 'Do not read my Windows account.', 'Respect prohibition, no operation or claimed reading.'),
]:
    cases.append({'id': identifier, 'request': request, 'history': [], 'expected': expected})
case_path = root / 'scratchpad/c03-account-scope405-cases.json'
assert not case_path.exists()
case_path.write_text(json.dumps({'cases': cases}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
source = (root / 'scratchpad/c03-generic-mind403.py').read_text(encoding='utf-8')
for a, b in [('astra-generic-mind403', 'astra-account-scope405'),
             ('C03-generic-mind403-private', 'C03-account-scope405-private'),
             ('c03-generic-mind403-cases.json', 'c03-account-scope405-cases.json'),
             ('catalog403', 'catalog405'), ('close403', 'close405')]:
    assert a in source
    source = source.replace(a, b)
fields = {
    'method': 'Nine fixed synthetic development cases, baseline versus one scope-abstention change in a diagnostic-only hook. Real full mind, same model/source397, history/catalog/prompt/sampler. Only _machine_status_is_the_whole_clause additionally abstains when the clause names account/user identity; let existing native selection decide, no forced system.identity. Two actual403 controls plus new usernames, OS version, OS+RAM, CPU, concept and prohibition. Sequential sidecars, no effect execution, source edit or promotion.',
    'reason': '403 trace proves explicit_effects selects system.status before the model for Windows account questions. _MACHINE_STATUS_SCOPES OS matches which/que...Windows while the whole-clause check excludes time/IP/network but not account identity. SystemStatusContracts lacks userName; SystemIdentityHandler owns it. Reuse the current native-tool/template research and existing whole-clause abstention design, not another descriptor/prompt variant387/391.',
    'criteria': 'Correct requested operation for all account and resource scopes; conceptual/prohibited requests make no PC reading. Every final decision and all HTTP drafts preserved. No gain counted by merely removing a string or by silence. If native selection still fails, do not hardcode a replacement or adopt on parser tests alone.',
}
lines = source.splitlines()
for index, line in enumerate(lines):
    for key, value in fields.items():
        if line.startswith('    ' + repr(key) + ':'):
            lines[index] = '    ' + repr(key) + ': ' + repr(value) + ','
source = '\n'.join(lines) + '\n'
hook_code = '''
from baxy_mind import effect_intent
if os.environ.get('BAXY_C03_SCOPE405') == 'identity-scope':
    prior_scope = effect_intent._machine_status_is_the_whole_clause
    def identity_scope(text):
        return prior_scope(text) and not effect_intent._has(
            text, r"\\b(?:cuentas?|usuarios?|accounts?|user(?:name)?s?|identidad|identity)\\b")
    effect_intent._machine_status_is_the_whole_clause = identity_scope
'''
needle = "(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')"
assert needle in source
source = source.replace(needle, 'hook_source += ' + repr(hook_code) + '\n' + needle)
start = source.index('client = JsonLineProcess')
end = source.index("assert sha(manifest) == prereg['manifest_sha256']", start)
block = source[start:end]
block = block.replace("out / 'PROCESS.json'", "out / f'PROCESS-{variant}.json'")
block = block.replace("'seconds': round(time.monotonic() - start, 3), 'reply': reply", "'variant': variant, 'seconds': round(time.monotonic() - start, 3), 'reply': reply")
block = block.replace("private / 'stderr-tail.json'", "private / f'stderr-tail-{variant}.json'")
source = source[:start] + "for variant in ['baseline', 'identity-scope']:\n    env['BAXY_C03_SCOPE405'] = variant\n" + textwrap.indent(block, '    ') + source[end:]
target = root / 'scratchpad/c03-account-scope405.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
print(json.dumps({'t4_primary_equals402b': same_primary, '405_cases': len(cases)}))
