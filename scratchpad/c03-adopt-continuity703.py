"""Adopt the measured continuity correction without accepting the failed panel."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-continuity-source703'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

assert not (out / 'RESULT.json').exists()
record = read(out / 'VALIDATED.json')
assert all(sha(root / p) == expected for p, expected in record['sources'].items())
product = read(base / 'astra-status-batch704/RESULT.json')
assert product['counts'] == {'failed': 23, 'correct_observed_run': 50}
note = '''# Adopción703: las peticiones nuevas salen de una confirmación pendiente

La App ya no entrega automáticamente todo texto a la confirmación anterior. Reutiliza la decisión ordinaria del mensaje nuevo y la política de objetivo autocontenido que antes sólo atendía aclaraciones. Una petición privada tipada conserva su ruta privada. Si hay una decisión del modelo, se reutiliza al ejecutar: no se clasifica dos veces el mismo pedido.

MindPlanSession sólo retira una confirmación cuyo efecto no empezó ni requiere reconciliación. Primero resuelve la invocación en la cola durable y luego borra el plan persistido; la cancelación explícita comparte esa transición. Un fragmento conserva la confirmación original. Una nueva acción que también exige confirmación recibe nuevos MissionId eInvocationId. Si pudo haber un efecto, se conserva su identidad y evidencia. No se amplía la políticaSensitive/External ni se cambia el catálogo, el modelo, su muestreo o Python.

La validación inicial seleccionó192pruebas:188pasaron y4fixtures nuevas fueron rechazadas por construir token y fecha no canónicos. Se corrigieron sólo esos valores del test, con las huellas originales conservadas. El control final de11casos pasó, incluidos los4arreglados y7controles de sesión/reemplazo/binding;0skips. Las fuentes productivas son idénticas en ambas ejecuciones. Fast0,0advertencias/errores yRelease25,21s. No se presenta esto comoFull703: el Full de cierre continúa pendiente.

Producto704 mantiene los73textos, orden y criterios de702. Vuelve a aparecer la misma confirmación equivocada en el sexto turno; los39pedidos que antes quedaban atrapados ahora continúan de manera independiente.35llegan a su lectura y32finalizan correctamente. Resultado completo:50correctos/23fallos,32ganancias/0pérdidas frente702. La causalidad de continuidad se apoya en ese mismo preestado y en las pruebas de persistencia; no se atribuyen diferencias de valores Windows o de latencia global al parche.

La selección inicial de pestañas sigue siendo incorrecta y otros23resultados no cumplen. Esta adopción no aprueba el panel entero, no certifica la generalización de cada requisito y no cierraC03. No añade respuestas visibles fijas, otra capa de autorización ni reintentos del modelo. La encuesta permanece26cubiertos/716abiertos/0NA.

Pico del diagnóstico704:3499,5586MiBGPU y2444,0742MiBRAM,272,687s,sin infracciones. No hubo UI/voz simultáneas; no es una cifra certificada del producto completo. Siguiente: corregir selección/frescura y la primera transformación errónea de identidades de ventana; no repetir este panel sin una nueva corrección.
'''
(out / 'ADOPTION_NOTE.md').write_text(note, encoding='utf-8', newline='\n')
result = {**record, 'utc': datetime.now(timezone.utc).isoformat(), 'adopted': True,
          'product704_pending': False, 'product704': {'correct': 50, 'failed': 23, 'gains': 32, 'losses': 0},
          'whole_panel_accepted': False, 'private_hashes': {}, 'new_coverage': 0, 'goal_complete': False}
write(out / 'RESULT.json', result)
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
attributes = root / '.gitattributes'
existing = attributes.read_text(encoding='utf-8')
with attributes.open('a', encoding='utf-8', newline='\n') as stream:
    for line in ['/artifacts/comprobaciones/C03/astra-continuity-source703/** -text',
                 '/artifacts/comprobaciones/C03/STATUS_BATCH704_PLAN.json -text']:
        if line not in existing:
            stream.write(line+'\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n'+note)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), workStatus='continuity703_adopted_publication_pending',
             activeValidation=None,
             checkpoint='703adoptada de forma delimitada:188dueñaspass+4fixturesresueltas por11controlesfinales,Fast0.704mismos73:50correctos/23fallos,32ganancias/0pérdidas; confirmación deja de capturar39pedidos. Encuesta26/716/0.',
             continuation='Auditar índice y publicar703/704. Después primeras transformaciones de selección/frescura y rechazo de identidadesobservadas (Python+C#). No permitir Sensitive/External en bloque; no aplicar prototype695. Sin inferencia activa ni decisión pendiente del dueño.',
             previousGoalTurnClassification='progress',
             previousGoalTurnClassificationReason='703implementada/validada y704completaadjudicada:32respuestasrecuperadas,sin pérdidas,confirmaciónya no absorbe39pedidos. C03completo siguependiente.')
state['latestProductRun'] = {'name': 'product704', 'sessionId': 76313, 'exitCode': 0, 'turns': 73,
                             'manifestUnchanged': True, 'adjudication': 'completed:50correct,23failed; sealed',
                             'result': 'artifacts/comprobaciones/C03/astra-status-batch704/RESULT.json'}
write(base / 'RELEVO_ACTIVO.json', state)
print({'adopted703': True, 'product704_correct': 50, 'product704_failed': 23, 'goal_complete': False})
