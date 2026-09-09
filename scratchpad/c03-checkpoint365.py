"""Keep the running validation state recoverable without carrying the whole diary."""
from pathlib import Path
from datetime import datetime, timezone
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-declared-memory365'
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    previous = (base / name).read_text(encoding='utf-8')
    (out / ('PREVIOUS_' + name)).write_text(previous, encoding='utf-8')
checkpoint = '''# C03 — checkpoint365 — EN_CURSO — 2026-09-08

Goal completo activo. Goal-c03/HEAD2bf3d4c; preservar WIP/main/evidencia. Sin agentes,
commit/push ni Full durante reparación. BAXY cerrado manualmente; producto364 y
diagnósticos anteriores cerrados. Encuesta1248/742 intacta, servidor101140 disponible.
16mensajes directos consolidados en INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md;
órdenes automáticas excluidas. AGENTS e identidad vigentes. No otro goal.

## Últimas mejoras integradas

340 confirmación exacta para enable y nuevo save;343/343b pregunta por dato faltante;
344 proyección privada observed/pendingAction;354 preserva operación al redactar;
356 corrige eco que vetaba saludo solicitado.357:6/7, saludo visible, cuentaWindows
errónea.359 quitar último recorte del selector solo regresó360:3/7, viejos pedidos
contaminaban acciónactual.361 roles nativos9/11→11/11.362 reemplaza JSON por
systempropio+historialuser/assistant(12mensajes/6000chars)+actualuserliteral.
363:7/7,0silencios; preguntas, activar/guardar/saludar, identidad personal frente
a Windows y recall verificado. RESULT/PINS363. No generalizar a otras rutas.
Python3621091pass0skip5,32s;Fast1,40sverde. App356225pass0skip15s. Dueñas memoria344
1913pass0skip5m19s. Registro2507 intacto;Qwen3.5 diagnóstico, no promoción. Native361
GPU3175,56MiB/RAM4599,84MiB aislado, sin voz/UI/mínimo. Ver PREVIOUS_CHECKPOINT para
historia exacta/rechazos. No repetir wrappers/annotations346/347/349/316/317.

## Generalización364 y reparación365

364:10controles sintéticos ES/EN, Jordan/Álvaro, cancelar.3/10 útiles,1silencio.
Primer turno da nombre y pide guardarlo en la misma frase; privado no lo enlaza
y promete recuerdo. T6similar ofrece nota privada. Nunca hubo save/enable, así
que preguntas sobre confirmar no alcanzaron la ramaMemoryTurnSession. Journal
status+2recallfallidos. T5What is my name? da18borradores I don't know your name
because the memory feature is disabled, vetadosmissing_failure: termina composition_failed.
T10No puedo decirte tu nombre porque la memoria está deshabilitada contradice
Álvaro recién declarado. T4/T9reconocenlosnombres yT8cancelaclarificación. RESULT/PINS364.

365 última fuente WIP: NaturalMemoryRequestParser.Classify enlaza declaración y
solicitud explícita del mismo nombre (antes/después, punto/coma/puntocoma/y/and),
reutilizaMissingNameSavePattern/DeclaredNameInputPattern/Savepersonalpersistent.
Guardas de negación/secretos/autorización van antes. DeclaredName admite espacios;
otra frontera de cláusula no entra como parte del nombre. No nombres fijos.
Tests en NaturalMemoryRequestParserTests y MemoryTurnSessionTests. Baseline5fail6pass
582ms; focalinicial1fail28pass detectó Lina y abre Steam absorbido; focal-fixed29pass
0skip666ms tras impedir esa absorción. Logs/PREREG astra-declared-memory365.

Dueñas .NET365 en curso, handle57441: MemoryAppFlowTests|MemoryTurnSessionTests|
NaturalMemoryRequestParserTests|MemoryOperationProtectionTests|MissionInputPipelineTests|
MindShellEndToEndTests. Recoger; no repetir. Después Fast (no lanzado365 aún) y
producto366 preparado: scratchpad/c03-product366.py, mismos10pedidos364/modelo/perfil
nuevo, sólo365 distinto. NO ejecutar producto antes de dueñas/Fast verdes.
No cambiar fuente mientras corre producto. Python sigue362sin cambios.

## Siguiente después del producto y resto íntegro

Preguntas durante confirmación: MemoryTurnSession:138–155 no manda pendingAction
en Invalid/cannot_withdraw_uncertain; PrivateOperationNarration ya lo construye.
Todavía sin editar. Separar ese defecto de T5/T10conmemoriadesactivada. El redactor
actual sólo recibe failed/memorydisabled/operationmemory.recall, no la declaración
humana. No relajar missing_failure para publicar una afirmación falsa. StartAsync
de MemoryTurnSession:240 sólo recibe operación/publicObjective, no pedido original;
Host.ContinuePublic llama TryExecuteWithMindAsync, una posible pieza de herencia
para contestar desde sesión, aún sin diseño/adopción. También queda prosa fija
en SendPreparedAsync cuando no llega challenge seguro para secreto: pendienteC03.

Otras ocho rutas/errores y fallos264, encuesta742requisitos(0validaciónindividual
registrada),100humanos frescos(0certificados/0congelados;204por auditar335), averías/
recuperación, escritorio real/voz física/ASR/recursos conjuntos, runtime/instalación,
continuidadC04–C09sin ejecutarlos, Fullfinalverde y publicaciónfuera de main.
No bloqueo externo, porcentaje ni fecha demostrados. C03 sigue íntegro EN_CURSO.
'''
(base / 'CHECKPOINT.md').write_text(checkpoint, encoding='utf-8')
handoff = '''# Handoff — C03 — 2026-09-08 — HEAD2bf3d4c / Goal-c03

Completar C03 íntegro según autoridad/identidad; no sólo memoria. Estado detallado:
CHECKPOINT.md manda. Preservar WIP/main/evidencia, sin agentes/commit/push/Full durante
reparación. BAXY manual cerrado; encuesta1248/742 intacta, servidor101140 disponible.

Última mejora integrada362: roles nativos del selector con historial saneado/acotado,
sin envoltorioJSON.363pasa7/7 memoria/nombre, journalverificado,0silencios. Modelo3.5
override, registro2507 intacto. No promoción. Native36111/11 no acredita UI/voz.

364generalización10sintéticosES/EN:3/10,1silencio. Declaración+guardar en una frase
no inicia memoria; nombre de sesión se pierde ante recall con memoria deshabilitada.
RESULT/PINS364 guardan todos los mensajes. No cambiar esa adjudicación por tests.

365WIP en NaturalMemoryRequestParser.cs: enlaza declaración y petición explícita
del mismo nombre, ambos órdenes; nombres compuestos, privacidad/negaciones intactas.
Tests nuevos en NaturalMemoryRequestParserTests/MemoryTurnSessionTests. Baseline5fail6pass;
focal-fixed29pass0skip666ms tras reparar absorción de y abre Steam como nombre.

SIGUIENTE: recoger handle57441 de dueñas .NET365 (6suites, comando enCHECKPOINT).
Fast365 aún NO lanzado. Si verdes, ejecutar preparado scratchpad/c03-product366.py:
mismos10controles364/Qwen3.5, sólo365diferente. Registrar handle, leercadarespuesta/journal.
No sourceedit mientras corre. ÚltimaPython3621091pass/Fast1,40s; noFull.

Después: preguntas durante confirmación sinpendingAction, y recall cuando memoria
está desactivada pero dato está en conversación.364T5rechaza18borradoresfalseunknown
por missing_failure; no relajar guarda.366dirá qué primeras ramas ya se alcanzan.
Otros fallos264/encuesta,100freshhuman(0certificados/204por auditar), averías/UI/voz/
recursos/runtime/instalación, contratosC04–C09, Fullfinal y publicación siguen abiertos.
Descartes y mediciones históricas están enlazados enCHECKPOINT y PREVIOUS_CHECKPOINT.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='365 source private-name binding WIP; focal29pass0skip666ms; .NET owners running57441, Fast365 not yet.364generalization3/10+1silence preserved.',
    continuation='Collect57441; then Fast365 and prepared product366 only if green. Full C03 active, no model promotion.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('365 checkpoint and compact handoff updated.')
