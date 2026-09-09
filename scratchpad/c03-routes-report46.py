"""Render manually adjudicated regression46 evidence; no automatic quality judge."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
source = base / 'astra-routes-regression46'
rows = json.loads((source / 'paired.json').read_text(encoding='utf-8'))
lines = [
    '# C03 — regresión técnica de rutas, tramo46', '',
    'Fuente45; runtime registrado Qwen3-4B-Instruct-2507 Q4_K_M sin cambios. '
    '33 entradas técnicas consumidas, no reserva humana. Averías y recuperaciones separadas. '
    '31/33 respuestas normales útiles; fallan t23 y t24. No aprobación de C03.', '',
    'RESULT: exit0, 106,14s, GPU3499,56MiB, RAM5927,09MiB, registro intacto. '
    'La ventana vacía propia se cerró por el producto tras confirmar; no hubo limpieza forzada. '
    'El conductor desactiva wake: no acredita UI ni audio físico.', '',
    'Rutas con prosa: welcome1, conversation8, clarification3, confirmation2, '
    'result18, mission-summary4 (incluidas recuperaciones). Ninguna etiqueta de progreso. '
    'Los tres composition_failed son averías del compositor con estado recuperable; '
    'no equivalen a tres respuestas redactadas de la ruta error.', '',
    'Juicio humano del agente sobre entradas, respuestas y hechos de paired.json. '
    'La rúbrica del dueño admite respuestas españolas a mezcla y marcas inglesas. '
    'No se penaliza una definición simple por preferencia de estilo.', '',
]
for index, row in enumerate(rows, 1):
    if index == 23:
        verdict = 'FALLO: pidió ajustar sin nivel; se eligió audio.status y no se solicitó el dato faltante.'
    elif index == 24:
        verdict = 'FALLO: la continuación se refería al volumen; pregunta por tarea/tiempo sin apoyo en el contexto.'
    elif index in (34, 36, 38):
        verdict = 'AVERÍA APARTE: composition_failed; no se publicó una frase de éxito. Recuperación en el turno siguiente.'
    elif index in (35, 37, 39):
        verdict = 'RECUPERACIÓN APARTE: devuelve la hora observada en la misma sesión tras restaurar composición.'
    elif index == 18:
        verdict = 'ÚTIL/FIEL: cancela el cierre; window.resolve observó la ventana maximizada. No hay cierre en este turno.'
    elif index == 25:
        verdict = 'ÚTIL/FIEL a la consulta actual: nivel observado100; el ajuste fallido anterior no había cambiado el dispositivo.'
    else:
        verdict = 'ÚTIL/FIEL: responde a la petición con conocimiento estable o resultado observado; confirmaciones y aclaraciones mantienen el objeto.'
    lines.extend([f'## t{index}', '', f'Entrada: {row["request"]}', '',
                  f'Respuesta: {row["final"] or "[sin prosa BAXY publicada]"}', '', verdict, ''])
lines.extend([
    '## Causa localizada y límites', '',
    't23, request79: raw_attempt nativo ya propone audio.status. El lector literal '
    'no identifica ni efecto completo ni aclaración. El resto de capas conserva '
    'la selección equivocada. t24, request83: propuesta nativa audio.volume; '
    'domain_grounding retira la autoridad porque el antecedente incompleto no '
    'fue conservado. La composición recibe sólo ambiguous_request y redacta '
    'tarea/tiempo. No se culpa al provider ni se cambia el modelo por inferencia.', '',
    'Comparación nativa astra-incomplete-volume46: 16 llamadas sin ejecutar funciones, '
    'ocho controles con historial público reconstruido y los mismos ocho sin él. '
    'El original se reproduce con historial; sin él mejora la familia de ajuste '
    'pero volumen de ventas se confunde con audio. No promover retirada de historial. '
    '17,86s, GPU3495,56MiB, registro intacto. posts.jsonl conserva payload y respuesta '
    'real de esas llamadas; no se afirma captura exacta del cable del panel original.', '',
    'Herencia y contraste: INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md, '
    'ASTRA-TRAMO-43.md, y aclaración incompleta de volumen relativo en effect_intent. '
    'Se amplía ese owner para nivel absoluto faltante; no otro prompt ni clasificador. '
    'La generación visible sigue a cargo del modelo. Falta medir producto corregido.', '',
])
(base / 'PRUEBAS_RUTAS_C03_TRAMO46.md').write_text('\n'.join(lines), encoding='utf-8')

# Same normal panel and prior context; omit faults already measured on this runtime.
target = base / 'astra-routes-volume46'
target.mkdir(exist_ok=True)
assert not (target / 'PREREG.json').exists()
commands = (base / 'astra-routes-regression46.turns.jsonl').read_text(encoding='utf-8').splitlines()
commands = commands[:next(i for i, line in enumerate(commands) if json.loads(line)['cmd'] == 'inject')]
target.with_suffix('.turns.jsonl').write_text('\n'.join(commands) + '\n', encoding='utf-8')
driver = (root / 'scratchpad/c03-routes-regression46.py').read_text(encoding='utf-8')
driver = driver.replace('routes-regression46', 'routes-volume46')
driver = driver.replace('then separate reject/timeout/exhaust injections each followed by restore and a normal request in the SAME process/profile/session.', 'No fault injections in this follow-up: same33 normal inputs and order after only the incomplete-level source repair; previous fault/recovery evidence retained separately.')
(root / 'scratchpad/c03-routes-volume46.py').write_text(driver, encoding='utf-8')
print('Wrote literal report and prepared same33 corrected-source regression.')
