from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-progress-activity87'
rows = [json.loads(s) for s in (out / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]
lines = ['# C03 — actividad de interpretación87', '',
    'Segunda comparación de datos sin cambiar instrucciones: sustituir state=in progress por '
    'state=understanding the person\'s request. T1 y t3 siguen afirmando lectura en curso; '
    't5 promete ajustar el volumen. T2/t4 describen interpretación con español poco natural; '
    't6 ya describe interpretación, sin atribuir nueva lectura. Mejora parcial, insuficiente '
    'para adoptar. No repetir variantes de etiqueta: cambiar hipótesis a la instrucción '
    'existente, que pide trabajar en la solicitud sin distinguir actividad actual de objetivo.', '',
    'exit0;7,94s;GPU3171,5625MiB;RAM3255,0625MiB;registro intacto. '
    'Fuente86 no se modifica por este prototipo. Qwen3.5 override sin promoción. '
    'No funciones, publicación/UI/audio/reserva humana.', '']
for row in rows:
    lines += [f'## {row["turn"]}', '', 'Entrada: ' + row['text'], '',
        row['response']['choices'][0]['message']['content'], '']
report = base / 'PRUEBAS_PROGRESO87.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files = [report, out / 'PREREG.json', out / 'RESULT.json', out / 'posts.jsonl']
(base / 'TRAMO87_PINS.json').write_text(json.dumps({'scope': 'Insufficient data-only prototype, not adopted',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')
for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    path = base / name
    path.write_text(path.read_text(encoding='utf-8') + '\n\n## Actualización86–87\n\n'
        '86 guard de negación adaptado:1151pytest pass/0skips/6,42s;181integración pass/0skips/15s.\n'
        'Fast1604exit0,Release15,73s,0 avisos/errores. files86-negation en ejecución73121;\n'
        'recoger RESULT/paired y fidelidad de causa. Sin builds/modelos paralelos.\n'
        '87 nativo cambia sólo state a interpretación de petición: mejora parcial, aún\n'
        'lectura inventada t1/t3 y promesa t5. PRUEBAS_PROGRESO87.md/TRAMO87_PINS.json.\n'
        '88 preparado, no ejecutado: sustituir instrucción existente por narración de\n'
        'actividad actual, con mismos datos87. Sin fuente de progreso adoptada. No Full.\n', encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(path.read_text(encoding='utf-8'))
relay.update(checkpoint='Fuente86 y Fast verdes; progreso87 insuficiente; C03 EN_CURSO',
    continuation='files86-negation activo73121; recoger resultado antes de ejecutar prototipo88. Sin builds/modelos paralelos, modelo override sin promoción.')
path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
