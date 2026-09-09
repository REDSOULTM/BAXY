"""Record product393b and retry394–396 results without changing raw evidence."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private_base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def rows(path):
    return [json.loads(line) for line in path.open(encoding='utf-8-sig') if line.strip()]

def quote(text):
    return '\n'.join('> ' + line for line in text.splitlines())

def pin(out, paths):
    (out / 'PINS.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths}, indent=2) + '\n', encoding='utf-8')

out = base / 'astra-stored-product393b'
private = private_base / 'C03-stored-product393b-private'
prereg = read(out / 'PREREG.json')
events = rows(private / 'capture/events.jsonl')
terminals = [r for r in events if r.get('type') == 'terminal']
audit = rows(private / 'compose-audit.jsonl')
assert len(terminals) == len(prereg['cases']) == 6
verdicts = [
    ('útil', 'Explica el guardado fallido por memoria deshabilitada y ofrece confirmar la activación. No atribuye persistencia al nombre.'),
    ('parcial', 'Activación y guardado sí se completaron, pero la prosa es genérica: dice que guardó la memoria, sin identificar el nombre guardado.'),
    ('fallo', 'Niega recuerdos aunque la lectura completada devuelve un registro name=Jordan. Primera respuesta del compositor ya incorrecta.'),
    ('fallo', 'Responde en inglés a la declaración española. Reconoce Álvaro; no hay un nuevo guardado. La tilde del nombre aporta dos puntos de español y hace que la guardia de idioma no rechace la frase inglesa.'),
    ('fallo', 'El valor Jordan leído es correcto, pero BAXY se lo atribuye a sí mismo: “Mi nombre”. El dato guardado es del usuario.'),
    ('fallo', 'El parser genérico lee la persistencia y responde Jordan aunque la declaración conversacional más reciente es Álvaro. Es el alcance aún no reparado por393.'),
]
replies = []
report = ['# Producto393b — lectura reparada, composición aún incorrecta', '',
    'Seis turnos sintéticos en un perfil separado. Exit0, seis admissions200, cero timeouts; manifest intacto. Un turno útil, uno parcial y cuatro fallos. No UI real, voz física ni aceptación fresca.', '',
    'El journal confirma memory.enable completed, memory.save completed y tres memory.recall completed tras el save inicial failed por memoria deshabilitada. La posterior declaración de Álvaro no guardó ni sobrescribió el nombre. La lectura privada está bien encaminada; su respuesta no lo está.', '']
for index, (request, terminal, verdict) in enumerate(zip(prereg['cases'], terminals, verdicts), 1):
    drafts = [r['draft'] for r in audit if r.get('published') and r.get('trace') == f't{index}']
    if terminal.get('final') and terminal['final'] not in drafts:
        drafts.append(terminal['final'])
    replies.append({'request': request, 'answers': drafts, 'terminal': terminal, 'verdict': verdict[0], 'reason': verdict[1]})
    report += [f'## {index}. {verdict[0]}', '', '**Entrada:** ' + request, '',
               'Respuestas registradas como publicadas por compositor y terminal del conductor:', '']
    for draft in drafts:
        report += [quote(draft), '']
    report += [verdict[1], '']
report += ['La observación de transporte de los posts5 y10 contiene literalmente shown=1, total=1, records=[{label:name,value:Jordan}], outcome=completed, operation=memory.recall. Sus respuestas brutas ya son la negación de recuerdos y “Mi nombre es Jordan”. No fue pérdida del resultado en el provider ni invención del valor por el parser.', '',
           'Fuente393 queda conservada por la reparación de la lectura, con su validación independiente; no se declara resuelta la conducta completa por pasar esas pruebas.', '']
assert not (out / 'RESULT.md').exists()
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
(out / 'replies.json').write_text(json.dumps(replies, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
pin(out, [out / n for n in ['PREREG.json', 'RESULT.md', 'replies.json', 'EXIT.json']] +
    [private / n for n in ['capture/events.jsonl', 'http-posts.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl']] +
    [private_base / 'C03-stored-profile393b/journal/missions.jsonl'])

for number, folder, private_folder in [
    (394, 'astra-retry-history394', 'C03-retry-history394-private'),
    (396, 'astra-retry-real396', 'C03-retry-real396-private'),
]:
    out = base / folder
    prereg = read(out / 'PREREG.json')
    actual_rows = rows(out / 'replies.jsonl')
    report = [f'# {number} — reparación con historial conservado', '',
        ('Baseline 2/5 útiles; retención 4/5 útiles y un parcial. Todos atravesaron una vez bounded_chat_answer. Ninguna llamada ejecutada.' if number == 394 else
         'Fuente395 real, sin hook que modifique historial: 5/5 útiles en esta corrida de averías. Todos atravesaron una vez bounded_chat_answer; ninguna llamada ejecutada.'), '',
        'Se inyecta explícitamente un primer borrador en idioma opuesto para activar la guardia existente. No son turnos normales ni aceptación fresca. El contexto y las preguntas se heredan del panel sintético385. Modelo, configuración y manifest sin promoción.', '',
        'La comparación programática de los cinco payloads396 con los de la variante394 dio igualdad en los cinco. Álvaro cambió de “Tu nombre es Álvaro. Lo recordé porque me lo dijiste en tu último mensaje, aunque la memoria privada esté desactivada.” (394: parcial por cronología falsa) a “Te llamas Álvaro.” (396). No atribuir esa variación de inferencia a una diferencia de payload ni borrar el fallo previo; una corrida buena no acredita estabilidad ni cierre.', '']
    for case in prereg['cases']:
        report += ['## ' + case['id'], '', '**Entrada:** ' + case['request'], '', 'Contexto literal:', '']
        for msg in case['history']:
            report += ['**' + msg['role'] + '**', quote(msg['content']), '']
        for row in actual_rows:
            if row['id'] != case['id']:
                continue
            report += ['**' + row['variant'] + '**', 'Borrador inyectado:', quote(row['injected_draft']),
                       '', 'Respuesta final:', quote(row.get('answer', row.get('detail', ''))), '',
                       f"Reintentos: {row['retries']}; {row['seconds']} s.", '']
    assert not (out / 'RESULT.md').exists()
    (out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
    pin(out, [out / n for n in ['PREREG.json', 'RESULT.md', 'replies.jsonl']] +
        [private_base / private_folder / 'posts.jsonl'])

out = base / 'astra-retry-source395'
report = '''# 395 — reintento con su mismo historial

LlmRuntime.chat ahora conserva presentation_history en el reintento
bounded_chat_answer: mantiene roles, hechos y correcciones, respeta la exclusión
de temas anteriores y no duplica el pedido actual. No cambia prompt, schema,
sampler, límites, guardias ni autoridad. El pin de programa actual de V8 se
actualiza por esta edición; sus seis artefactos, aritmética y veredicto no cambian.

- Focal antes de fuente: 2 failed, 1 passed, 964 deselected, 1,80s.
- Focal después de fuente: 3 passed, 0 skips, 964 deselected, 0,67s.
- `python -m pytest tests/test_turn_policy.py tests/test_compose_contract.py
  tests/test_llm_transport.py tests/test_request_reading.py
  tests/test_price_v8_veto_damage_by_cause.py -q`: 1343 passed, 0 skips, 6,00s.
- `scripts/test_source_quality.ps1`: Fast verde entero; build Release 1,52s,
  cero advertencias y errores. No Full durante reparación.

394 demuestra 2/5→4/5 más un parcial en averías sintéticas;396 confirma la
implementación real y sus payloads, con 5/5 en esa corrida. La variación de
Álvaro con payload idéntico se conserva explícita en ambos RESULT.md.
No se declara resuelto el compositor de memoria, el idioma del caso393bT4,
la ruta genérica de nombres ni el goal completo.
'''
assert not (out / 'RESULT.md').exists()
(out / 'RESULT.md').write_text(report, encoding='utf-8')
pin(out, [out / n for n in ['PREREG.md', 'RESULT.md', 'baseline.log', 'focal.log', 'owners.log', 'fast.log']] +
    [root / n for n in ['src/baxy_mind/llm.py', 'tests/test_turn_policy.py', 'tests/test_price_v8_veto_damage_by_cause.py']])

archive = base / 'CHECKPOINT_393_ANTES_397.md'
assert not archive.exists()
archive.write_bytes((base / 'CHECKPOINT.md').read_bytes())
checkpoint = '''# C03 — checkpoint396 — EN_CURSO

Goal completo activo, Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia; sin
agentes, commit/push ni Full durante reparación. BAXY manual cerrado.
16 mensajes directos y 742 registros rev1248 consolidados; automáticos excluidos.
Encuesta original/servidor101140 intactos. Todos los modelos/productos/tests de
389–396 cerrados; últimos handles62347,83555,15876,94185 cerraron exit0.

Última .NET393: preguntas explícitas de nombre guardado ES/EN cruzan la ruta
privada memory.recall exact/name. Focal20pass0skip1m08 (baseline10fail10pass1m26);
seis dueñas1996pass0skip2m59; Fast verde, build17,97s cero warnings/errors.
Última Python395: chat conserva presentation_history en bounded_chat_answer,
sin restaurar contexto excluido por un tema nuevo ni duplicar el pedido.
Focal3pass0skip0,67s (baseline2fail1pass1,80s); cinco dueñas1343pass0skip6,00s;
Fast verde, build1,52s cero warnings/errors. Pins actuales V8 actualizados por
395; seis artefactos/veredicto históricos intactos. No Full.

Producto393b seis sintéticos:1 útil,1 parcial,4 fallos. Se guardó Jordan en
perfil aislado; después declarar Álvaro no persistió. Journal: enable/save/3recall
completed, save inicial failed. T3 se leyó Jordan pero el compositor negó
recuerdos; T5 dijo “Mi nombre es Jordan”; T6 genérico leyó persistenciaJordan
en vez del contextoÁlvaro. T4 conversacional reconoció Álvaro en inglés.
Posts5/10 tienen la observación correcta; primer borrador ya erróneo.
No llamar a 1996tests una solución de esta composición. RESULT/PINS393b completos.

394 averías con primer borrador en idioma opuesto: retener historial2/5→4/5
estrictos+parcialÁlvaro por inventar “en tu último mensaje”.395 lo implementa.
396 implementación real sin hook:5/5 en esa corrida. Los cinco payloads son
idénticos a394variante, pero Álvaro ahora “Te llamas Álvaro”; variación de
inferencia no explicada por payload, no borrar parcial anterior ni certificar
estabilidad. RESULT/PINS394/395/396 escritos.

389RAM libre stop antes de respuesta;3909B no-mmap cabe aislado(2,85GiB GPU,
3,89GiB RAM) pero2/4identidad, sin mejora/no promoción.391promptselector5/8→4/8
rechazado.392resolvedorcontextual5/10 rechazado: terceros→usuario, guardado
inventado. No repetir esa estrategia, variantes346/347/349/316/317 ni ampliar
el catálogo público a memory.* (376fracasó, la ruta privada permanece sellada).

Siguiente: corregir la guardia de idioma demostrada en393bT4, sin editar nombres
ni prompts. llm._reply_uses_opposite_language3915 sólo rechaza si wanted==0.
“I understand you're Álvaro. I've noted your name.” evidencia(es2,en6) pasa por
la tilde del nombre. read_request(_policy_guard_text(text)) tiene es0,en4;
Sirve separar evidencia léxica de la tilde, manteniendo el bonus cuando hay
palabras españolas (Sí). “Te llamas Jordan” aún evidencia0,0; “Me llamo Jordan”
hereda idioma si falta tilde. Posible reutilización de frases funcionales en
request_reading._ES_PHRASES; todavía NO implementado ni script397 preparado.
Después: composición de memoria393b y consultas genéricas/humanidad siguen
abiertas. UserMessagePolicy.RequiredStructuredLiterals2531 sólo conserva
reason/title, no los records. No imponer nombre ni sujeto mediante prosa fija.

C03 restante íntegro: ocho rutas y fallos264/base742 (0 validados finales);
100 humanos frescos literales con procedencia/contexto congelados(0 certificados);
averías aparte; UI real; voz física/ASR/wake/recursos conjuntos<=4GB; runtime,
instalación y contratosC04–C09 sin ejecutar otros goals; Full final verde y
publicación fuera de main. Sin bloqueo externo/cierre/porcentaje o plazo inventado.
Historial: CHECKPOINT_393_ANTES_397.md y RESULT/PINS por tramo.
'''
(base / 'CHECKPOINT.md').write_text(checkpoint, encoding='utf-8')
(base / 'HANDOFF.md').write_text(checkpoint, encoding='utf-8')
active = read(base / 'RELEVO_ACTIVO.json')
active.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='396 closed. NET393 validated1996/Fast17.97; Python395 validated1343/Fast1.52.393b product1useful1partial4fails;394 retry2/5->4/5+partial;396 actual5/5 with identical payloads and recorded inference variation. No models active.',
    continuation='Next language guard393bT4: an accented name masks an English answer. Stored-result composition and generic conversation/persistence routing remain open. Full C03 active; no Full or promotion.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(active, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Records393b/394/395/396 pinned; checkpoint396 current; no source edited.')
