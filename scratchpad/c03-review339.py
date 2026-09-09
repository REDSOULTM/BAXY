"""Adjudicate all six product339 terminals; keep C03 active."""
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib
import os

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-product339-private'
prereg = json.loads((out/'astra-memory-product339/PREREG.json').read_text(encoding='utf-8'))
events = [json.loads(s) for s in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals = [r for r in events if r.get('type') == 'terminal']
assert len(terminals) == 6
assert all(r['admissionStatus'] == 200 and not r['timedOut'] for r in terminals)
reasons = [
    'Útil: pide el nombre faltante; primera composición válida publicada, sin veto ni afirmación de guardado.',
    'Fallo: sigue tratando la reacción como incomprensión, sin recuperar el pedido.',
    'Parcial, no completo: causa memory_disabled verdadera; no saluda ni orienta activación/guardado.',
    'Fallo: convierte la referencia al nombre ya aportado en error de interpretación.',
    'Fallo: cuenta de Windows real pero referente equivocado respecto al nombre declarado.',
    'Fallo: pregunta si debe contestar ambas identidades, ya solicitadas.',
]
lines = ['# Producto339 — 1/6 útil, cero silencios', '',
    'Exit0, seis admisiones200 y terminales publicados sin timeout. Frente a337 '
    '(0/6, un silencio), fuente338 recupera la pregunta de nombre. No regresión '
    'de utilidad completa respecto a337; el conjunto sigue por debajo de334 (2/6). '
    'Sin aceptación de memoria integrada. Desarrollo; no reserva, UI gráfica ni voz física.', '']
for index, request, terminal, reason in zip([99,101,103,105,107,109], prereg['cases'], terminals, reasons, strict=True):
    lines.extend([f'## {index}', '', request, '', '> '+terminal['final'], '', reason, ''])
lines.extend(['## Causa comprobada y continuación', '',
    't1 publica su primer borrador; payload contiene kind y cause, sin can ajeno a '
    'la aclaración. La comparación conserva runtime y muestreo registrados y cambia '
    'sólo fuente338 frente a337. La historia posterior cambia con las respuestas: '
    'no atribuir cada diferencia posterior a una instrucción distinta del modelo.', '',
    'Conservar338 como reparación acotada comprobada. Pendiente: activación guiada '
    'de memoria por el canal privado existente, confirmación de la invocación exacta, '
    'guardado verificado, continuación pública y referencia al nombre declarado. '
    'La variante inglesa detectada durante338 tiene otro veto knowledge_question '
    'pendiente; no se afirma resuelta. C03 EN_CURSO, sin Full durante reparación.', ''])
(out/'astra-memory-product339/RESULT.md').write_text('\n'.join(lines),encoding='utf-8')
pins = {}
for path in [private/'capture/events.jsonl', private/'compose-audit.jsonl', private/'http-posts.jsonl']:
    with path.open('rb') as stream:
        pins[str(path)] = hashlib.file_digest(stream,'sha256').hexdigest()
(out/'astra-memory-product339/PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
current = '''# C03 — checkpoint339 — EN_CURSO — 2026-09-08

Última petición del dueño cumplida: consolidación de los16mensajes directos de
esta tarea, desde el inicio, en INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md y JSON
MENSAJES_DUENO_2026-09-08.json. Lectura paginada read_thread hasta hasMore=false.
Excluir como autoridad nuevos mensajes llegados de ChatGPT/otra tarea; hallazgos
sólo como evidencia contrastada. No reduce ni reinicia C03. Autoridad actualizada.
Herencia de tarea anterior separada en consolidación2026-09-06, no presentada
como mensajes directos adicionales. AGENTS/identidad vigentes. Sin delegación.

Producto3370/6completos,1silencio -> fuente338 -> producto3391/6útil,0silencio.
99publica pregunta de nombre a la primera;101incomprensión;103memory_disabled
sin saludo/guía;105errorinterpretación;107cuentaWindowsreferenteequivocado;
109repregunta. Los seis leídos/adjudicados, exit0, sin timeout, RESULT/PINS ambos.
338corrige sólo can/beyond conversacionales inyectados en situaciones tipadas;
validador/modelo/prompts intactos. Baseline14fail1pass; dueñas1023pass0skip5,24s;
Fastverde build3,77s0warnings/errors. Estado integrado de memoria NO aceptado.

336tiene1908pass0skip +1disabledseparado,Fast20,12s. Persistencia probada tras
nueva sesión SÓLOcon activación/confirmación explícitas en perfil temporal.
Journal337 acredita memory.savefailedmemory_disabled; no pérdida de dato enparser.
Default LocalMemoryStore.Enabled=false. No cambiarlo globalmente como atajo.

SIGUIENTE: diseño/implementación de activación guiada dentro de MemoryTurnSession
(no nuevo planificador), preservando solicitud explícita de guardar, canal
protegido, confirmación exacta de memory.enable, nueva invocación al reanudar un
save ya fallido, cancelación/reinicio/recuperación y continuación pública.
Todavía NO se implementó ni preregistró340. No hay procesos de pruebas activos.
Otro defecto pendiente: la variante «What can you do? Remember my name.» recibe
knowledge_question en llm.py:4418 aunque exista aclaración operativa. Los tests338
ingleses sólo verifican payload; NO afirmar soporte integrado de esa variante.

Lecturas listas: MemoryTurnSession.cs:230–260 ExecuteRoute,337–465 envío/continuación;
MemoryOperationProtection.cs:40–100 Prepare/OpenPrivateArguments vincula IDs/sesión;
MemoryAppFlowTests.cs:482–562 disabled y persistencia; PrivateOperationNarration.cs:27–50
confirmaciónmemory_enable. Reutilizar estas piezas; no repetir toda investigación.
Ideas de activación todavía sin adoptar: conservar petición privada cifrada pendiente
de enable; re-preparar save con nuevos IDs tras enable verificado; no reutilizar
confirmación para guardar secretos, ni retomar tras cancelación/nueva sesión sin
garantías. La continuación pública actual sólo corre tras éxito: revisar alcance.

BAXY cerrado para uso manual. Encuesta revisión1248 terminada,742 requisitos trazados
en SURVEY_REQUIREMENTS336.json; original intacto. Servidor101140 no cerrar ni reescribir.
Auditoría335:204 por revisar;0frescoscertificados,0reserva100congelada. Nuevos tests
cuentan como exposición de desarrollo. No Full hasta candidato de cierre completo.
Goal activo, ramaGoal-c03 HEAD2bf3d4c, conservar WIP/main, sin commit/push/agentes.
Pendiente: otrosfallos264/todas8rutas,100humanosfrescos,averías/recuperación,
UIreal/vozfísica/ASR/recursos,runtime/instalación,contratosC04–C09,Full/publicación.
Recursos260históricos3516,66MiBGPU4822,60MiBRAM: no mínimo ni conjuntovozcertificado.

'''
checkpoint = out/'CHECKPOINT.md'
checkpoint.write_text(current+'## Contexto anterior (histórico; este encabezado manda)\n\n'+checkpoint.read_text(encoding='utf-8'),encoding='utf-8')
(out/'HANDOFF.md').write_text(current,encoding='utf-8')
state_path = out/'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='339 complete:1/6 useful,0silence versus3370/6,1silence. 338 owners1023pass,Fastgreen3.77s. All16 direct owner messages consolidated; cross-task instructions excluded.',
    continuation='Implement guided memory activation/confirmed continuation using existing private session; separate English knowledge-question veto pending. No test runs active. BAXY closed. C03 active, no Full until closure candidate.')
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'useful':1,'total':6,'silence':0,'goal':'active','running_tests':0}))
