from pathlib import Path
import datetime
import json

base = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03'
for name in ['CHECKPOINT', 'HANDOFF']:
    with (base / f'{name}_HISTORICO_HASTA107.md').open('x', encoding='utf-8', newline='\n') as f:
        f.write((base / f'{name}.md').read_text(encoding='utf-8-sig'))
current = '''## Estado actual y siguiente acción

Fuente108 implementada: HasCompositionError notifica y se proyecta como state
error también en bootstrap; cola pendiente proyecta thinking sin bloquear
entrada. React usa el reducer existente, grafo Error y región alert persistente
Response error (etiquetas de estado, no prosa). Se retira duplicación del código
interno como actividad; evento diagnóstico con causa/ruta conservado.
ASTRA-TRAMO-108.md y ADR-0008/ORIGIN: herencia, W3C ARIA19, diseño y huellas.
Sello38archivos99FF9838C07CE32F25F329AACF830F62D8DD70C5931E26C2EC483B710B2CA657.
pnpm build exit0;169pruebas .NET pass/0skips/6s,94729exit0; Fast77667exit0,
Release19,29s,0avisos/errores. No repetir verdes sin nuevo cambio/fallo.

UI107 terminado: recuperación real del mismo App4888/server19948 tras106,17s
suspendido. Cuatro finales de confirmación/cancelación/cierre fieles: fixture
31896 conservada al cancelar, ausente al confirmar antes de limpiar nada.
PRUEBAS_UI107.md: siete literales/capturas. Monitor22512exit0,781,48s,
GPU3497,52734375MiB,RAM5847,5MiB. Árbol App4888 terminado. No procesos UI107.
El fallo total mostró SYSTEM composition_failed e Idle: causa de fuente108.

UI109 prerregistrada, tres primeros relojes de UI107, mismo override Qwen3.5/wake0.
Launcher4252 en curso: py main.py con trazas/astra-ui109. Esperar fin antes de
observar App; obtener PID/ruta y ventana Sky nuevos. Monitor c03-ui109-resources.py
preparado, NO arrancado. c03-suspend-ui109.py preparado, NO ejecutado; pausa sólo
server descendiente verificado y reanuda por RESUME_SERVER o watchdog300s.
No builds/modelos paralelos ni Full. Verificar Thinking pendiente, Error/Response
error con controles disponibles, luego recuperación sin reinicio tras reanudar.
Después detener monitor y terminar únicamente árbol propio con ruta verificada.

103/UI104: progreso visible ES/EN y ocho finales fieles; reportes102/104 vigentes.
106:3averías/3recuperaciones por conductor mismoPID, no UI/audio. No repetir.
Preview105 vistos0–154/239 candidatos, no selección/congelación ni inferencia.
Tres textos ingleses admitidos por dueño ya registrados; no preguntar ni extender
a742. Reserva100, voz/audio físico,4GB combinado, promoción/regresión runtime,
continuidadC04–C09,Full final verde y publicación fuera de main siguen pendientes.

'''
checkpoint = base / 'CHECKPOINT.md'
text = checkpoint.read_text(encoding='utf-8-sig')
start, end = text.index('## Estado actual'), text.index('## Decisiones y pruebas')
text = text[:start] + current + text[end:]
# The archived checkpoint retains all interim process notes; avoid stale active tails.
tail = text.find('\n106 finalizado:')
if tail >= 0:
    text = text[:tail] + '\n'
checkpoint.write_text(text, encoding='utf-8', newline='\n')
handoff = '''# Handoff C03 — fuente108/UI109 — 2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, Goal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Goal activo e íntegro;
CHECKPOINT manda. Sin commit/push/main ni subagentes, preservar WIP y evidencia.

''' + current + '''
Python312 para pytest; resolvedor predeterminado para calidad; py main.py GUI.
UI sólo Computer Use sky/node_repl, ya inicializado; baxyWindow266900 está muerto.
saveBaxyEvidence existe pero uiEvidenceBase aún apunta aUI107: actualizar antes
de guardar UI109. Inspeccionar capturas/oclusiones, no automatizar Codex.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8', newline='\n')
relay_path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(relay_path.read_text(encoding='utf-8-sig'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Fuente108 error tipado/presentación;169tests/Fast verdes; C03 EN_CURSO',
    continuation='UI109 launcher4252 en curso; monitor y suspensión aún no ejecutados. CHECKPOINT. No Full ni modelos/builds paralelos.')
relay_path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
print('Current checkpoint and handoff108 saved; historical107 notes preserved.')
