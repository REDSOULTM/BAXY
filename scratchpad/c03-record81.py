from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-files81-nominal'
paired = json.loads((out / 'paired.json').read_text(encoding='utf-8'))
assert len(paired) == 10 and all(t['terminal'] == 'published_final' for t in paired)
t9 = next(t for t in paired if t['turnId'] == 't9')
facts9 = next(r['payload'] for r in t9['compose'] if r['intent'] == 'status' and r.get('payload', {}).get('outcome') == 'completed')
assert [s['operation'] for s in facts9['completedStepsInOrder']] == ['system.time', 'audio.status', 'system.status']
lines = ['# C03 — enumeración nominal integrada81', '',
    '10/10 turnos útiles en este panel técnico, frente a9/10 en78 y5/10 en72. '
    'El resultado se adjudicó con hechos, final y eventos, no sólo por publicación. '
    '99,11s (incluye la espera inicial de50s),GPU3177,56MiB,RAM6381,38MiB,exit0; '
    'registro intacto. No benchmark de latencia. Qwen3.5 permanece override, sin promoción.', '',
    '81 hereda el normalizador existente de cláusulas; propaga el verbo a cada nominal '
    'y separa las comas sólo tras reconocer la enumeración completa. El turno9 pasa por '
    'system.time, audio.status y system.status en orden. Final03:58/volumen100/no silenciado/CPU33,125 '
    'coincide con los cuatro hechos. No se rebajó extra_claim. T6 sigue siendo conversación '
    'sin efecto nuevo; t10 pregunta por nivel sin ajustar audio.', '',
    'Se adopta la corrección local81. C03 sigue EN_CURSO: faltan otros recorridos, '
    'búsqueda vacía/progreso, reserva100 humana congelada, UI/voz/audio físico+4GB conjuntos, '
    'continuidadC04–C09, Full verde final y publicación. Este panel consumido/sintético '
    'no se añade a la reserva. La confirmación del dueño sólo cubre los tres textos admitidos.', '']
for turn in paired:
    labels = [e['label'] for e in turn['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')]
    lines += [f'## {turn["turnId"]} — útil', '', f'Entrada: {turn["request"]}', '',
              f'Final literal: {turn["final"]}', '',
              f'Labels de progreso publicados: {json.dumps(labels, ensure_ascii=False)}', '']
lines += ['## Hechos del turno9', '', '```json', json.dumps(facts9, ensure_ascii=False, indent=2), '```', '',
    '## Validación', '',
    'Python312 -m pytest tests/test_effect_intent.py tests/test_llm_transport.py '
    'tests/test_compose_contract.py tests/test_c03_request_preservation.py tests/test_turn_policy.py -q: '
    '2774pass/0skips/43,45s. Fast87199exit0,Release1,47s,0 avisos/errores. '
    'La fuente C# sigue78:169integración pass/0skips/30s en sus suites dueñas. '
    'No Full durante reparación. No procesos de llama-server activos tras cerrar46872.', '']
report = base / 'PRUEBAS_ENUMERACION81.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files = [report, out / 'PREREG.json', out / 'RESULT.json', out / 'paired.json', out / 'wire-35600.jsonl',
         root / 'src/baxy_mind/effect_intent.py', root / 'src/baxy_mind/llm.py',
         root / 'src/Baxy.App/UserMessagePolicy.cs', root / 'src/Baxy.App/MainWindowViewModel.cs']
for name in ('c03-nominal81-pytest.log', 'c03-nominal81-fast.log'):
    path = out / name
    path.write_bytes((Path(os.environ['TEMP']) / name).read_bytes())
    files.append(path)
(base / 'TRAMO81_PINS.json').write_text(json.dumps({'scope': 'Adopted local source repair81; model unpromoted; C03 remains open',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')

checkpoint = (base / 'CHECKPOINT.md').read_text(encoding='utf-8')
checkpoint = checkpoint.replace('roles78 y enumeración81', 'panel81 completo; otros recorridos pendientes')
checkpoint = checkpoint.replace(' + candidato81.', ' +81 adoptado localmente.')
checkpoint = checkpoint.replace('81 pendiente: adapta', '81 adoptado localmente: adapta')
checkpoint = checkpoint.replace('files81-nominal en ejecución46872; recoger RESULT, paired, avisos y operaciones.\nNo builds/pruebas paralelos. No fuente81 adoptada sin producto/regresión.',
    'files81-nominal terminó46872exit0:10/10 útiles,99,11s,GPU3177,56MiB,RAM6381,38MiB.\n'
    'T9 conserva03:58/volumen100/no silenciado/CPU33,125 en orden, con los tres\n'
    'resultados verificados. Registro intacto, Qwen3.5 sigue override sin promoción.\n'
    'No procesos/conductores/modelos propios activos. PRUEBAS_ENUMERACION81.md y\n'
    'TRAMO81_PINS.json fijan fuente/logs/hechos/finales. Panel técnico, no reserva100.\n'
    'Siguiente: comprobar búsqueda vacía y progreso con este candidato. Reusar\n'
    'scratchpad/c03-progress-inference64.py, aún no ejecutado; inspeccionar antes\n'
    'de adaptarlo al perfil actual. No leer nuevamente toda la investigación.')
(base / 'CHECKPOINT.md').write_text(checkpoint, encoding='utf-8')
handoff = (base / 'HANDOFF.md').read_text(encoding='utf-8')
handoff = handoff.replace('Fuente58+63+74+77+78; candidato81 en validación.', 'Fuente58+63+74+77+78+81, reparación local adoptada.')
handoff = handoff.replace('files81-nominal en ejecución46872: recoger RESULT/paired y adjudicar entero.\nNo builds/pruebas paralelos. No Full durante reparación.',
    'files81-nominal46872exit0:10/10 útil,99,11s,GPU3177,56MiB,RAM6381,38MiB,\n'
    'registro intacto. PRUEBAS_ENUMERACION81.md/TRAMO81_PINS.json fijan la fuente.\n'
    'Sin modelos/procesos propios activos. Siguiente: búsqueda vacía y progreso;\n'
    'reusar c03-progress-inference64.py (no ejecutado), adaptar tras inspección.\n'
    'No Full durante reparación. No promoción de modelo ni aceptación integral.')
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
relay = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Panel81 10/10 útil; otros recorridos pendientes; C03 completo EN_CURSO',
    continuation='Fuente81 adoptada localmente; modelo Qwen3.5 sólo override. Sin procesos activos. Comprobar búsqueda vacía/progreso antes de promoción/reserva100. No Full durante reparación.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
