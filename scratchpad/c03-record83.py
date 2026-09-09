from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-files83-empty'
paired = json.loads((out / 'paired.json').read_text(encoding='utf-8'))
lines = ['# C03 — búsqueda vacía y recuperación83', '',
    '2/4 turnos útiles. La recuperación a lectura real y reloj funciona; la búsqueda vacía '
    'y la pregunta por su causa reciben un fallo genérico sobre datos del paso ausentes. '
    '65,08s,GPU3177,56MiB,RAM6897,59MiB,5417exit0,registro intacto. Fuente81 sin cambios, '
    'Qwen3.5 override sin promoción. No UI/audio/reserva humana.', '',
    'La fuente contiene búsqueda verificada con entries=[] y count=0. Los datos no faltan: '
    'son un resultado vacío. MindPlanSession:135 convierte GroundPlanStepAsync null en '
    'step_data_missing; ese fallo reemplaza el significado útil. TryGroundIdentityArguments '
    'sólo resuelve una identidad única y no distingue ausencia de coincidencias. No se '
    'ha editado ese flujo. La siguiente reparación debe conservar la causa de la búsqueda '
    'vacía, sin atribuir inexistencia global ni inventar una identidad.', '',
    'Además, el primer borrador español «No se pudo…» se veta como missing_failure, '
    'mientras C# ya reconoce no se pudo. Es otro desajuste gramatical del guard; no '
    'confundirlo con la causa primaria de la búsqueda vacía ni añadir un prompt.', '']
for turn in paired:
    useful = turn['turnId'] in {'t3', 't4'}
    labels = [e['label'] for e in turn['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')]
    lines += [f'## {turn["turnId"]} — {"útil" if useful else "no útil"}', '',
              f'Entrada: {turn["request"]}', '', f'Final literal: {turn["final"]}', '',
              f'Labels de progreso: {json.dumps(labels, ensure_ascii=False)}', '']
    seen = set()
    for row in turn['compose']:
        if row.get('draft') not in seen:
            seen.add(row.get('draft'))
            lines += [f'Borrador ({row.get("reason") or "sin veto Python"}): {row.get("draft")}', '',
                      '```json', json.dumps(row.get('payload'), ensure_ascii=False, indent=2), '```', '']
report = base / 'PRUEBAS_BUSQUEDA_VACIA83.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files = [report, out / 'PREREG.json', out / 'RESULT.json', out / 'paired.json', out / 'compose-audit.jsonl', out / 'turn-audit.jsonl']
(base / 'TRAMO83_PINS.json').write_text(json.dumps({'scope': 'Unsolved empty-search cause; recovery demonstrated; source81 unchanged',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')

path = base / 'CHECKPOINT.md'
checkpoint = path.read_text(encoding='utf-8')
checkpoint = checkpoint.replace('83 búsqueda vacía en ejecución5417: files83-empty, misma fuente81 y override.\nCuatro turnos técnicos: archivo ausente en sandbox, porqué, lectura real, reloj.\nRecoger RESULT/paired/causa antes de tocar provider. No builds/modelos paralelos.',
    '83 terminó5417exit0, files83-empty, misma fuente81 y override:2/4 útil.\n'
    'T1/t2 explican datos del paso ausentes aunque la búsqueda verificó entries=[]\n'
    'y count=0; t3 lectura real y t4 reloj recuperan.65,08s,GPU3177,56MiB,\n'
    'RAM6897,59MiB,registro intacto. PRUEBAS_BUSQUEDA_VACIA83.md/TRAMO83_PINS.json.\n'
    'Siguiente: MindPlanSession:135 convierte GroundPlanStepAsync null en\n'
    'step_data_missing; preservar resultado vacío verificado al resolver identidad,\n'
    'sin afirmar ausencia global ni inventar ID. TryGroundIdentityArguments en\n'
    'PlannerExecutionSupport.cs:548 sólo reconoce identidad única. No fuente nueva\n'
    'desde81. Primer borrador No se pudo también cae en missing_failure Python;\n'
    'C# lo reconoce. Mantener contraste entre gramática y causa, sin otro prompt.\n'
    'Sin procesos/modelos/conductores propios activos. No Full durante reparación.')
path.write_text(checkpoint, encoding='utf-8')
path = base / 'HANDOFF.md'
handoff = path.read_text(encoding='utf-8').replace('83 files83-empty en ejecución5417; recoger RESULT/paired y causalidad primero.\nSin builds/modelos paralelos. No ejecutar c03-progress-inference64.py sin adaptar.',
    '83 files83-empty5417exit0:2/4 útil; lectura/rerloj recuperan. La búsqueda\n'
    'verificó count0/entries[], pero MindPlanSession:135 genera step_data_missing.\n'
    'Siguiente: conservar ausencia de coincidencias en la resolución de identidad.\n'
    'PRUEBAS_BUSQUEDA_VACIA83.md. Sin procesos activos ni fuente nueva desde81.')
path.write_text(handoff, encoding='utf-8')
relay = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Panel81 10/10; progreso82 y búsqueda vacía83 pendientes; C03 EN_CURSO',
    continuation='Fuente81 sin cambios. Sin procesos activos. Reparar causa de búsqueda vacía en MindPlanSession/PlanObservationProjector; progreso pierde fase. Modelo sólo override, cierre integral pendiente.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
