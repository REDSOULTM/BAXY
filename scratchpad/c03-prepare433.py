from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-private-product432-private'
out = base / 'astra-private-product432'
assert not (out / 'RESULT.md').exists()
cases = json.loads((out / 'PREREG.json').read_text(encoding='utf-8'))['cases']
events = [json.loads(line) for line in (private / 'capture/events.jsonl').open(encoding='utf-8-sig')]
terminals = [r for r in events if r.get('type') == 'terminal']
assert len(terminals) == 8
useful = [True, True, True, True, False, False, False, True]
notes = [
    'Confirma habilitación exacta; previamente explica fallo por memoria deshabilitada. No guardar sin esa confirmación.',
    'Habilita y guarda el nombre autorizado; no basta esta frase para acreditar journal.',
    'Pregunta por la aplicación, sin inventar destino.',
    'Recupera Jordan de memoria privada pese a aclaración pública pendiente.',
    'Pregunta qué necesita del PC en vez de responder a una presentación.',
    'Pide permiso genérico en vez del nombre de aplicación; hereda aclaración T5.',
    'El dato Jordan es correcto, pero «Mi nombre» atribuye el nombre a BAXY.',
    'Nombre de la conversación Álvaro, distinto del persistido Jordan.',
]
records = [{'turn': i+1, 'request': request, 'terminal': terminal,
    'useful_terminal': ok, 'reason': note}
    for i, (request, terminal, ok, note) in enumerate(zip(cases, terminals, useful, notes, strict=True))]
(out / 'ADJUDICATION.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
report = '''# 432 — aplicación aclarada en T3; recorrido 5/8 útil, aún incompleto

Fuente431, mismo desarrollo426 y nuevo perfil privado aislado. Ocho admisiones200
y ocho terminales publicados;5/8 útiles frente a4/8 en426. Sin composition_failed.
T3 llega a la aclaración existente por aplicación. T5 ahora pregunta por el PC,
todavía incorrectamente; T6 arrastra esa aclaración y pregunta permiso sin destino.
No se declara resuelta toda la secuencia de apertura. T7 conserva el error de sujeto.

49,344s; RAM2377,1484375MiB (2,32GiB), GPU3177,5625MiB (3,10GiB); sin violaciones,
exit0 y manifiesto intacto. Perfil425 de memoria sigue vigente; no reducción nueva
de pesos/contexto/precisión. No certifica mínimo global, UI ni audio físico conjunto.
Se conservaron todos los eventos, no sólo los terminales, en la captura privada.

'''
for row in records:
    report += f"- T{row['turn']} | {row['request']}\n  {row['terminal'].get('final')}\n  {'Útil' if row['useful_terminal'] else 'Fallo'}: {row['reason']}\n\n"
(out / 'RESULT.md').write_text(report, encoding='utf-8', newline='\n')
paths = [out / n for n in ['PREREG.json', 'PROCESS.json', 'EXIT.json', 'resources.json', 'ADJUDICATION.json', 'RESULT.md']]
paths += [private / n for n in ['http-posts.jsonl', 'effective-server-command.json', 'memory-samples.json', 'capture/events.jsonl', 'turn-audit.jsonl']]
(out / 'PINS.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2) + '\n', newline='\n')

next_out = base / 'astra-name-conversation433'
next_out.mkdir(exist_ok=False)
prereg = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'Extend the existing standalone social-act reader with a whole self-introduction grammar inherited from NaturalMemoryRequestParser.DeclaredNameInputPattern, rather than sending a closed declarative social turn to PC-operation retrieval. Reuse conversation composition already4/4 in429. No stored name cache, fixed reply, new classifier or kernel effect.',
    'boundary': 'First-person declarative name only, Unicode letters/apostrophe/hyphen/space with bounded length. Entire input must match. Decline added action heads using existing effect_intent._COVERAGE_ACTION_HEAD and question words using request_reading._INTERROGATIVE. Name remains raw user text passed to composer, never authorization or assistant identity. Pending clarification remains with ordinary interpretation. Third-person/saving/negation/quoted/hypothetical/PC queries stay outside this shortcut.',
    'evidence': '426/427 native self-introduction selects Windows;430 wire alias fails;427 global guard9/13 rejected.429 proper conversation event4/4 vs428 task status2/4.432 T5 still goes to irrelevant PC clarification and contaminates T6. C# AskToSave cannot directly close because its name pattern alone accepts arbitrary trailing letter sequences; do not add that shortcut.',
    'validation': 'Positive and negative standalone/pending regressions before source; owner turn_policy/request_reading and related composition suites, Fast. Then same8turn product432 replay with one source change. No fresh acceptance, no Full during repair.',
    'sources_before': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['src/baxy_mind/__main__.py', 'src/baxy_mind/request_reading.py', 'src/baxy_mind/effect_intent.py', 'src/baxy_mind/llm.py', 'tests/test_turn_policy.py']},
}
(next_out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path=base/name
    text=path.read_text(encoding='utf-8')
    text=text.replace('431 validado; producto432 preparado', '431 validado;432 producto5/8;433 preparado')
    text=text.replace('`runtimePython -X utf8 scratchpad/c03-private-product432.py`; mismo426 con\nfuente431. No fuente durante corrida; recoger terminales/payloads/recursos.',
        '433: gramática completa de presentación personal en lector social existente;\n'
        'declinar órdenes/preguntas añadidas con vocabulario compartido, sin nuevos\n'
        'clasificadores ni efecto. PREREG433. Primero regresiones baseline.\n'
        '432:8 publicados,5 útiles; T3 pregunta aplicación. T5 aclaración PC errónea\n'
        'contamina T6;T7 sujeto erróneo. RAM2377,15MiB/GPU3177,56MiB49,344s, sin corte.')
    path.write_text(text, encoding='utf-8', newline='\n')
relay_path = base / 'RELEVO_ACTIVO.json'
relay=json.loads(relay_path.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='432 completed:5/8 useful, T3 fixed; T5 irrelevant clarification contaminates T6; T7 wrong speaker. Source431 current.',
    continuation='433 preregistered: whole self-introduction in existing social reader, shared boundary vocabulary; regression baseline before edit, owners/Fast then product. Full C03 active.')
relay_path.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('432 recorded;433 prepared')
