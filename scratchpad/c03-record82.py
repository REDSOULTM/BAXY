from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-progress-baseline82'
rows = [json.loads(s) for s in (out / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]
verdicts = [
    'Compatible con lectura en curso; no infiere problema del nombre.',
    'Compatible con lectura en curso; no infiere corrupción del nombre.',
    'Compatible con lectura en curso; no infiere disco lleno del nombre.',
    'No útil: metatexto genérico sobre datos de la situación, sin nombrar lo que se comprueba.',
    'Compatible con ajuste en curso, sin afirmar que ya terminó; esta prueba NO ejecutó audio.',
    'Incorrecto: la petición pregunta por la causa; el aviso afirma estar leyendo otra vez.',
]
lines = ['# C03 — primer borrador de progreso82', '',
    'Fuente81, Qwen3.5 en override. Se capturó el primer paquete real del compositor y se '
    'ejecutó sin guardas/reintentos adicionales. No se ejecutó la variante de instrucción '
    'preparada en64; no se añade un prompt. No funciones, UI, audio ni reserva humana.', '',
    'Cuatro de seis borradores compatibles con el estado supuesto de trabajo en curso. '
    'T4 es metatexto vago y t6 afirma lectura nueva ante porqué. Los tres nombres sugestivos '
    'no provocan inferencias de corrupción/disco lleno en este modelo y perfil. No afirmar '
    'que progreso completo está resuelto: falta la publicación y el momento real.', '',
    '7,92s,GPU3171,56MiB,RAM3206,45MiB,registro intacto. El script terminó exit0.', '',
    'La inspección posterior localiza pérdida de fase: MainWindowViewModel.ComposeMilestoneAsync '
    'siempre usa TurnVisibleFacts.Status("acting"); el compositor lo reduce a state="in progress". '
    'StatusDescription sí distingue understanding al iniciar/decidir y el ejecutor de planes '
    'cambia su estado después. No se ha editado ese flujo. Antes de añadir instrucciones, '
    'contrastar transportar fase verdadera y evitar publicar un aviso de una fase ya vencida.', '']
for row, verdict in zip(rows, verdicts, strict=True):
    choice = row['response']['choices'][0]
    lines += [f'## {row["turn"]}', '', f'Entrada: {row["text"]}', '',
              f'Borrador literal: {choice["message"].get("content")}', '',
              f'Fin: {choice["finish_reason"]}. {verdict}', '']
report = base / 'PRUEBAS_PROGRESO82.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files = [report, out / 'PREREG.json', out / 'RESULT.json', out / 'posts.jsonl', root / 'scratchpad/c03-progress-baseline82.py']
(base / 'TRAMO82_PINS.json').write_text(json.dumps({'scope': 'Native first-draft progress diagnostic, not publication acceptance',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')
checkpoint = (base / 'CHECKPOINT.md').read_text(encoding='utf-8')
needle = 'No leer nuevamente toda la investigación.'
replacement = '''No leer nuevamente toda la investigación.

82 progreso nativo terminóexit0:4/6 borradores compatibles, no UI/publicación.
T4 metatexto vago y t6 afirma leer de nuevo ante porqué.7,92s,GPU3171,56MiB,
RAM3206,45MiB,registro intacto. PRUEBAS_PROGRESO82.md/TRAMO82_PINS.json.
No se ejecutó la variante de instrucción64, ni se cambió fuente después de81.
ComposeMilestoneAsync (MainWindowViewModel:291) siempre da causa acting;
_compose_situation_payload:3227 reduce a in progress. La fase understanding
existe en StatusDescription pero no llega al compositor. Investigar transporte
de fase verdadera y descarte de avisos obsoletos, sin clasificador por frases.
83 búsqueda vacía en ejecución5417: files83-empty, misma fuente81 y override.
Cuatro turnos técnicos: archivo ausente en sandbox, porqué, lectura real, reloj.
Recoger RESULT/paired/causa antes de tocar provider. No builds/modelos paralelos.'''
assert needle in checkpoint
(base / 'CHECKPOINT.md').write_text(checkpoint.replace(needle, replacement), encoding='utf-8')
handoff = (base / 'HANDOFF.md').read_text(encoding='utf-8')
handoff += '''
82 progreso nativo4/6; t6 porqué vuelve a lectura, t4 metatexto. Sin fuente nueva.
PRUEBAS_PROGRESO82.md: el hito pierde la fase, siempre acting/in progress.
83 files83-empty en ejecución5417; recoger RESULT/paired y causalidad primero.
Sin builds/modelos paralelos. No ejecutar c03-progress-inference64.py sin adaptar.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
relay = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Panel81 10/10; progreso82 pendiente; búsqueda vacía83 en ejecución5417; C03 EN_CURSO',
    continuation='Fuente81 sin cambios. Recoger83; progreso pierde fase en ComposeMilestoneAsync. Modelo sólo override; reserva100/cierre integral pendientes.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
