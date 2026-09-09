from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-required-fact402'
for name in ['baseline', 'focal', 'owners', 'fast']:
    target = out / f'{name}.log'
    assert not target.exists()
    target.write_bytes((Path(os.environ['TEMP']) / f'c03-required-fact402-{name}.log').read_bytes())
report = '''#402 — dato leído conservado en composición y aceptación

UserMessagePolicy.CollectStructuredLiterals incluye el único valor corto (≤256
caracteres), no redactado, de una lectura memory.recall/list verificada y exitosa.
Reusa RequiredLiteralFacts y ModelMessageComposer.requiredFacts; no cambia prompt,
modelo, formato de la memoria, autorización ni parser. Los datos largos, múltiples,
vacíos o redactados siguen como observaciones, sin contrato de copiar todos.

401 midió3/8→5/8 útiles sin nuevas pérdidas; sujetoES/redacción siguen abiertos.
Las nuevas pruebas pasan por la proyección privada, transporte al compositor y
aceptación de prosa: una respuesta que omite el dato falla. Los secretos no salen.

- Baseline:4fail,5pass,0skip,779ms. Cada fallo incluye tres garantías ausentes;
  además la aserción inicial usaba Is.Empty para un retorno null aceptado. Se
  corrigió esa aserción a Is.Null; no altera las tres ausencias que reproducen el defecto.
- Focal:9pass,0skip,444ms.
- `dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
  --filter 'FullyQualifiedName~MemoryAppFlowTests|FullyQualifiedName~MemoryOperationProtectionTests|FullyQualifiedName~PlannerAppBoundaryTests'`:
  186pass,0skip,3m05s.
- `scripts/test_source_quality.ps1 -Mode Fast`: verde entero, build18,15s,
  0 advertencias/errores. No Full durante reparación.

Producto402b separado. No dar por resuelto C03 ni todas las consultas de memoria.
'''
(out / 'RESULT.md').write_text(report, encoding='utf-8')
paths = [out / name for name in ['PREREG.json', 'RESULT.md', 'baseline.log', 'focal.log', 'owners.log', 'fast.log']]
paths += [root / name for name in ['src/Baxy.App/UserMessagePolicy.cs', 'tests/Baxy.Integration.Tests/MemoryAppFlowTests.cs']]
(out / 'PINS.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2) + '\n', encoding='utf-8')

out = base / 'astra-stored-product402b'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-stored-product402b-private'
events = [json.loads(line) for line in (private / 'capture/events.jsonl').open(encoding='utf-8-sig')]
activity = [row['event']['entry'] for row in events if row.get('event', {}).get('type') == 'activity'
            and row['event']['entry']['src'] in {'YOU', 'BAXY'}]
terminals = [row for row in events if row.get('type') == 'terminal']
assert len(terminals) == 6
turns = []
for item in activity:
    if item['src'] == 'YOU':
        turns.append({'request': item['msg'], 'answers': []})
    elif turns:
        turns[-1]['answers'].append({'text': item['msg'], 'route': item.get('route')})
verdicts = [
    ('útil', 'Causa real memoria deshabilitada y confirmación de activación ligada a la solicitud.'),
    ('parcial', 'Activación y guardado verificados, narración genérica no identifica el nombre.'),
    ('útil', 'Lectura privada real devuelveJordan; respuesta conserva el nombre y el guardado previo.'),
    ('fallo', 'Aclaración innecesaria sobre el PC ante una declaración del nombre.'),
    ('útil en contenido; ruta pendiente', 'RespondeJordan, coincidente con la lectura verificadaT3. No hubo nueva lectura: la aclaraciónT4 toma precedencia y el turno atraviesa conversación. NO acredita reparación del compositor privado español.'),
    ('fallo', 'La ruta genérica leeJordan persistido en lugar de Álvaro del diálogo actual.'),
]
report = ['#402b — producto real con valor retenido', '',
    'Seis sintéticos en perfil nuevo;3 útiles en contenido,1parcial,2fallos. Exit0,6admissions200, sin timeout/final ausente; manifiesto intacto. No UI/voz física/aceptación fresca.', '',
    'La mejoraEN usa el contrato402. La respuestaES correcta deT5 circula como conversación después de la aclaración innecesariaT4; no prueba la composición de una nueva lectura privada. El journal conserva sólo dos recall, no tres. La precedencia de _pendingMindClarificationObjective sobre memory.Outcome está identificada en MainWindowViewModel:671. No atribuir todo el cambio a402 ni ocultar esta ruta.', '']
for number, (turn, terminal, verdict) in enumerate(zip(turns, terminals, verdicts), 1):
    turn.update(terminal=terminal, verdict=verdict[0], reason=verdict[1])
    report += [f'## {number}. {verdict[0]}', '', '**Entrada:** ' + turn['request'], '']
    for answer in turn['answers']:
        report += ['> ' + answer['text'].replace('\n', '\n> '), '', 'Ruta: ' + str(answer['route']), '']
    report += [verdict[1], '']
assert not (out / 'RESULT.md').exists()
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
(out / 'replies.json').write_text(json.dumps(turns, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
paths = [out / name for name in ['PREREG.json', 'RESULT.md', 'replies.json', 'EXIT.json']]
paths += [private / name for name in ['capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl', 'http-posts.jsonl']]
paths += [private.parent / 'C03-stored-profile402b/journal/missions.jsonl']
(out / 'PINS.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2) + '\n', encoding='utf-8')

history = []
for item in activity:
    history.append({'role': 'user' if item['src'] == 'YOU' else 'assistant', 'content': item['msg']})
    if item['src'] == 'YOU' and item['msg'] == '¿Cómo me llamo?':
        history = history[-12:]
        break
cases = [{'id': 'actual402b-t6', 'request': '¿Cómo me llamo?', 'history': history,
          'expected': 'Answer Alvaro from the current human declaration; no new PC read or persistence claim.'}]
import copy
for identifier, request in [('english-name', 'What is my name?'),
                            ('account-es', '¿Con qué cuenta de Windows se está ejecutando BAXY?'),
                            ('account-en', 'Which Windows account is running BAXY?')]:
    context = copy.deepcopy(history)
    context[-1]['content'] = request
    cases.append({'id': identifier, 'request': request, 'history': context,
                  'expected': 'Propose system.identity for explicit Windows account.' if 'account' in identifier else 'Answer Alvaro in English, no stored-name substitution.'})
context = copy.deepcopy(history)
for message in context:
    if message['role'] == 'user' and message['content'] == 'Me llamo Álvaro.':
        message['content'] = 'Me llamo Renata.'
cases.append({'id': 'new-name', 'request': '¿Cómo me llamo?', 'history': context,
              'expected': 'Answer Renata from the human declaration; no substitution with Jordan.'})
cases.append({'id': 'third-party', 'request': 'What is my name?',
              'history': [{'role': 'user', 'content': 'My name is Priya.'},
                          {'role': 'assistant', 'content': 'Hello, Priya.'},
                          {'role': 'user', 'content': 'My sister is named Casey.'}],
              'expected': 'Answer Priya, not sister Casey; no Windows read or persistence claim.'})
case_path = root / 'scratchpad/c03-generic-mind403-cases.json'
assert not case_path.exists()
case_path.write_text(json.dumps({'cases': cases}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
source = (root / 'scratchpad/c03-language-mind398.py').read_text(encoding='utf-8')
for a, b in [('astra-language-mind398','astra-generic-mind403'), ('C03-language-mind398-private','C03-generic-mind403-private'),
             ('c03-language-mind398-cases.json','c03-generic-mind403-cases.json'), ('catalog398','catalog403'), ('close398','close403')]:
    assert a in source
    source = source.replace(a, b)
source = source.replace("'method': 'Eight development controls through actual full mind source397, with source395 retry retention. Exact synthetic393bT4 request and native history, five declared synthetic language/identity variants, two unchanged385 operation boundaries. Observer hook records only; no classifier/response/history injection. No operations, private dispatch, App/UI/physical voice, fresh human acceptance or runtime promotion. Compare393bT4 English failure and report each result; do not count parser tests as behavior.'",
"'method': 'Six fixed development cases through actual full mind source397, with source395 retry retention. Exact402bT6 activity-derived last12 messages including current user request, plus EN, new name, two explicit Windows accounts and a third-party control. Compare actual private-parser402bT6 storedJordan against the existing mind with current dialogue. No new prompt/guard/role/answer injection, operation execution or product source change. This measures whether generic conversational recall can use current dialogue before deciding any App dispatch repair; not fresh acceptance, UI or voice.'")
source = source.replace("'reason': '393b native language flag was Spanish but the English draft escaped the guard because the Alvaro accent alone supplied Spanish evidence.397 distinguishes lexical Spanish evidence from a neutral accented name; functional naming clauses now use whole-word boundaries so white llamas remains English.395 keeps the dialogue if repair is needed. Preserve all other payload/guard/authority behavior.'",
"'reason': '402bT6 is intercepted by unconditional generic name memory.recall, discarding current human Alvaro in favor of storedJordan.398 with earlier history could answerAlvaro, but402b has different actual replies. Measure this route on the new exact history before changing the dispatch. Explicit stored queries and Windows reads must retain their own owners; no global name cache or reuse of rejected contextual resolver392.'")
target = root / 'scratchpad/c03-generic-mind403.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
