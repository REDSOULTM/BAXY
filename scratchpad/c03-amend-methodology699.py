"""Supersede the model verdict while preserving the original sealed evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
old = base / 'K2_HORIZON_LATENCY697'
out = base / 'K2_HORIZON_NATIVE699'
out.mkdir(exist_ok=False)
now = datetime.now(timezone.utc).isoformat()
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
note = ('Decisión K2/Qwen provisional por aclaración metodológica del dueño. '
        'Las 860 respuestas previas usaron instrucciones de BAXY mediante API nativa, '
        'con muestreo y esfuerzo específicos del modelo; no son una referencia independiente. '
        'Primero comparar modelos con plantilla oficial sin instrucciones de BAXY; '
        'después añadir capas con tareas emparejadas para localizar regresiones. '
        '693/694 siguen pausados. Runtime intacto; encuesta 26 cubiertos/716 abiertos/0 NA; C03 activo.')
amendment = '''# Rectificación de método: comparación de modelos antes de BAXY

La elección anterior queda **provisional**. El dueño señaló que las instrucciones de BAXY pueden favorecer a Qwen. Las pruebas 696–698 llamaron directamente a los servidores, pero transportaron políticas, historias y datos preparados para BAXY. No acreditan todavía una comparación de calidad independiente del producto.

Se conservan los 860 resultados: sirven para diagnosticar esa combinación concreta de modelo, backend e instrucciones. El muestreo sí se ajustó por familia: Qwen documentado T0.7/p0.8/k20; K2 pequeño T0.6 y grande T1/p0.95, con esfuerzo high/medium/low explícito. No todos recibieron los defaults Qwen. La API recibió streaming; no ejecutó kernel, providers ni efectos.

La continuación es: 50 tareas nuevas y completas por modelo, sólo mensajes user/assistant y plantilla oficial, con criterios fijados antes de inferencia. Después, las mismas tareas bajo instrucciones adicionales para aislar su efecto; finalmente integración real. Las tareas nuevas son controles sintéticos, no turnos humanos ni cobertura de la encuesta. Comparar porcentajes de baterías diferentes no demuestra una regresión causada por BAXY.

«Original» se interpreta conforme a la aclaración del dueño: sin ecosistema BAXY ni ajuste de pesos. Se declara por separado cada cuantización y backend. K2 pequeño dispone de BF16; los modelos grandes usan cuantización para el techo local de memoria. El perfil de referencia de calidad conserva el esfuerzo y margen de salida oficiales; los perfiles prácticos reducidos se rotulan aparte.

Los ficheros anteriores a esta aclaración y sus hashes se preservan aquí. Los sellos nuevos registran explícitamente la modificación de estado/conclusión; no cambian las respuestas ni sus adjudicaciones. No se ha promovido K2, aceptado Qwen ni cerrado C03.
'''
(out/'METODO.md').write_text(amendment, encoding='utf-8')
names = ['REPORTE_FINAL.md', 'MODEL_DECISION698.json', 'SUMMARY698.json', 'PLAN.md', 'PINS698.json']
before = {}
for name in names:
    p = old/name
    before[name] = sha(p)
    (out/('PRE_ACLARACION_'+name)).write_bytes(p.read_bytes())
decision = json.loads((old/'MODEL_DECISION698.json').read_text(encoding='utf-8'))
decision.update(decision='provisional_pending_independent_and_paired_comparison',
    report_lead=note,
    next='Independent official-template baseline, then paired prompt layers before resuming Qwen repairs.',
    supersedes_previous_verdict_at=now,
    interpretation='Prior results are BAXY-prompt-conditioned diagnostics, not intrinsic model ranking.')
write(old/'MODEL_DECISION698.json', decision)
summary = json.loads((old/'SUMMARY698.json').read_text(encoding='utf-8'))
summary['decision'] = decision
write(old/'SUMMARY698.json', summary)
for name in ['REPORTE_FINAL.md', 'PLAN.md']:
    p = old/name
    original = p.read_text(encoding='utf-8')
    p.write_text('> **Rectificación posterior del dueño (699): la elección de modelo queda provisional.** '
        'Este documento conserva el informe histórico de pruebas condicionadas por instrucciones de BAXY. '
        'Su recomendación de retomar Qwen queda suspendida hasta aislar el modelo original. '
        'Véase [método vigente](../K2_HORIZON_NATIVE699/METODO.md).\n\n'+original, encoding='utf-8')
pins = json.loads((old/'PINS698.json').read_text(encoding='utf-8'))
for name in names[:-1]:
    p = old/name
    pins['files'][p.relative_to(root).as_posix()] = {'bytes': p.stat().st_size, 'sha256': sha(p)}
pins['methodology_amendment'] = {'utc':now, 'previous_pins_sha256':before['PINS698.json'],
    'previous_pins_preserved':'../K2_HORIZON_NATIVE699/PRE_ACLARACION_PINS698.json',
    'reason':'Owner requires original-model baseline before model choice; measurements unchanged.'}
write(old/'PINS698.json', pins)
write(out/'AMENDMENT_RECEIPT.json', {'utc':now, 'before':before,
    'after':{name:sha(old/name) for name in names}, 'measurements_changed':False})
p = base/'RELEVO_ACTIVO.json'
state = json.loads(p.read_text(encoding='utf-8-sig'))
state.update(confirmedAtUtc=now, checkpoint=note, continuation=note,
    ownerPriority='Independent original-model baseline and paired BAXY layers before model selection.',
    workStatus='independent_model_comparison_699', k2Report='artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699/METODO.md')
state['k2Comparison'].update(investigationCompleted=False, decision=decision['decision'],
    methodologyAmendment='artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699/AMENDMENT_RECEIPT.json')
write(p, state)
with (base/'CHECKPOINT.md').open('a', encoding='utf-8') as f:
    f.write('\n\n## Aclaración del dueño: referencia independiente 699 — '+now+'\n\n'+note+'\n')
p = base/'HANDOFF.md'
text = p.read_text(encoding='utf-8')
text = text.replace('# Handoff — C03 — investigación K2 cerrada, goal activo', '# Handoff — C03 — comparación independiente K2 prioritaria')
text = text.replace('Decisión: conservar runtime Qwen registrado.', 'Decisión anterior PROVISIONAL; debe revisarse tras referencia independiente. Runtime productivo todavía Qwen.')
text = text.replace('No reabrir otra cuadrícula K2 sin hipótesis/dato nuevo.', 'Hipótesis nueva del dueño: las instrucciones BAXY sesgan la comparación; medir modelos originales y añadir capas por separado.')
text = text.replace('## Siguiente acción\nAdjudicar', '## Siguiente acción\nPrioridad 699: '+note+'\n\nDespués de resolver la elección de modelo, adjudicar')
p.write_text(text, encoding='utf-8')
print(json.dumps({'amended':True, 'decision':decision['decision'], 'coverage':state['surveyVerificationCounts']}))
