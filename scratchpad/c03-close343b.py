"""Persist343b native result and an actionable handoff for private projection344."""
from pathlib import Path
from datetime import datetime, timezone
import os
import json
import hashlib

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-product343b-private'
prereg = json.loads((out/'astra-memory-product343b/PREREG.json').read_text(encoding='utf-8'))
events = [json.loads(l) for l in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals = [r for r in events if r.get('type') == 'terminal']
assert len(terminals) == 2 and all(r['kind']=='published_final' and not r['timedOut'] for r in terminals)
lines = ['# Producto343b — 2/2 controles útiles, cero silencios', '',
    'Dos controles sintéticos declarados: no aceptación fresca ni procedencia humana. '
    'Exit0, admisiones200, sin timeout. Mismos mensajes y runtime que343. '
    'La diferencia de esta comparación está en la publicación de la App, que '
    'ahora recibe el dato requerido del draft tipado. Sin cambios de modelo o muestreo.', '']
for request, terminal in zip(prereg['cases'],terminals,strict=True):
    lines.extend([request, '', '> '+terminal['final'], ''])
lines.extend(['La pregunta inglesa aceptada por Python llega ahora al final publicado '
    'sin repetirse hasta agotar la recuperación. Cancelar retira el dato pendiente. '
    'La grafía again del borrador no acredita una memoria previa; no se afirma '
    'guardado ni se ejecuta uno en esta prueba. No acredita UI gráfica ni voz física.', '',
    'App:217pass0skip16s y Fast19,43s; Python:1031pass0skip6,14s y Fast2,09s. '
    'No sumar esas suites como cobertura independiente. C03 sigue activo. '
    'Siguiente bloqueo: proyección de resultados y confirmaciones privadas344, '
    'demostrado por producto342; sus datos de memoria se pierden antes del modelo.'])
(out/'astra-memory-product343b/RESULT.md').write_text('\n'.join(lines),encoding='utf-8')
pins = {}
for path in [private/'capture/events.jsonl',private/'compose-audit.jsonl',private/'http-posts.jsonl']:
    with path.open('rb') as stream:
        pins[str(path)] = hashlib.file_digest(stream,'sha256').hexdigest()
(out/'astra-memory-product343b/PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
handoff = '''# C03 — checkpoint 343b — EN_CURSO — 2026-09-08

El turno fue PROGRESO: guardado con activación confirmada implementado y medido;
dos fronteras de aclaración corregidas. El goal completo continúa sin reducción.
Rama Goal-c03, HEAD 2bf3d4c. Preservar WIP, main y evidencia; sin commit/push/agentes.
BAXY cerrado para uso manual. Todos los procesos de pruebas de esta tanda terminaron.

## Qué está demostrado

- Fuente340: MemoryContinuation reemplaza PublicAfterMemory. Ante save normal
  de esta sesión fallido por memory_disabled, propone enable por el canal privado;
  sólo tras confirmación/verificación prepara un save con nuevos IDs. Cancelar
  descarta la continuación. Sin cambio de default, token reutilizado o secreto
  enviado al compositor. 1911 pass / 0 skips, 4m38s; Fast verde, build18,77s.
- Producto341: 1/6 completo, cero silencios. Producto342: 2/7 completos y una
  identidad parcial, cero silencios; contiene confirmación/recall sintéticos
  declarados. Journal342 acredita enable, nuevo save y recall completados.
  El motor devuelve name=emmanuel, pero la respuesta niega conocerlo.
- Fuente343: missingValue tipado se conserva en payload/prompt/validación Python.
  1031 pass / 0 skips, 6,14s; Fast2,09s. Producto343 aún silencia la pregunta:
  Python acepta el retry; la App lo veta como respuesta de conocimiento.
- Fuente343b alinea esa frontera de la App usando HasRequiredInput del draft.
  Baseline App4fail2pass; dueñas217pass0skip16s; Fast19,43s. Producto343b repite
  los dos controles sintéticos: 2/2 útiles, cero silencios. Pregunta publicada:
  «What’s your name again?». Cancelación publicada. No UI gráfica ni voz física.
  RESULT/PINS de341,342,343,343b escritos; no tests ni procesos activos.

## Siguiente acción: proyección privada344

Seguir PROYECCION_PRIVADA344_DISENO.md. TODAVÍA NO se editó344.
En342: C# emite records/shown/total, pero _compose_situation_payload los descarta;
enable/save llegan como prosa fija y su payload queda vacío; la confirmación no
incluye pendingAction y pregunta confirmar sin explicar qué se autoriza.

Owner: MemoryOperationResponseProjection.cs:106–218,225–267,444–482 y
PrivateOperationNarration.cs:27–60. Reutilizar observed/seen y pendingAction;
conservar schemas/redacción/export-replay y retirar la prosa sustituida.
MemoryAppFlowTests.cs:21–89 exige prosa fija y no JSON: reemplazar esa expectativa
caducada por hechos correctos y rechazo de JSON como salida visible, manteniendo
privacidad y tests de schema. Fixtures RecordsPayload/Record:1042–1087.
Repetir el recorrido342 y variantes con datos nuevos, leyendo cada mensaje.
No otro literal de nombre, segundo compositor ni parche a la frase final.

## Pendiente y preferencias

Identidad contextual105/107 y preguntas durante confirmación pendientes, además
del resto C03: todas8rutas,100humanos frescos, averías/recuperación, UI/voz física/
ASR/recursos, runtime/instalación, C04–C09, Full y publicación fuera de main.
No Full durante reparación. Encuesta final1248,742 requisitos intactos; servidor
101140 disponible. Auditoría335 deja204 por revisar, ninguno fresco certificado.
16 mensajes directos consolidados en INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md;
excluir instrucciones de la otra tarea. AGENTS e identidad siguen vigentes.
Recursos260 históricos3516,66MiB GPU/4822,60MiB RAM: no mínimo ni conjunto de voz.
Sin bloqueo externo. No dar memoria integrada ni C03 por terminados.

'''
checkpoint=out/'CHECKPOINT.md'
checkpoint.write_text(handoff+'## Estado anterior (histórico)\n\n'+checkpoint.read_text(encoding='utf-8'),encoding='utf-8')
(out/'HANDOFF.md').write_text(handoff,encoding='utf-8')
state_path=out/'RELEVO_ACTIVO.json'
state=json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='343b native complete2/2 synthetic controls,0silence; App217pass/Fast19.43s. 340 persistence proven;342 exposes dropped memory facts. All test processes finished.',
    continuation='Implement private structured result/confirmation projection344 per PROYECCION_PRIVADA344_DISENO.md; preserve schema/redaction, replace obsolete prose assertions. C03 active, no Full during repair.')
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('343b2/2; handoff344 recorded; no test process active; C03 active.')
