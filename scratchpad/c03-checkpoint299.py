from pathlib import Path
import json
from datetime import datetime, timezone

base = Path(__file__).resolve().parents[1]/'artifacts/comprobaciones/C03'
text = (base/'CHECKPOINT.md').read_text(encoding='utf-8')
text = text.replace('checkpoint296', 'checkpoint299')
text = text.replace('Fuente adoptada284 sin cambios posteriores.', 'Fuente298 adopta comparación por pregunta, no respuesta entera; fuente299 cambia AskToSave a continuación semántica, en validación.')
text = text.replace('1012 pass, 0 skips, 5,20s;', '1022 pass,0 skips,5,65s para las tres suites Python298;')
text = text.replace('ruff y Fast287 integrado VERDE (build4,45s,0warn/error). No Full de reparación.', 'Último Fast VERDE287; Fast298 pasó estática pero falló por Core95028 abierto. Logs intactos. Resolver mediante parada verificada293 ya hecha; nueva compilación integrada pendiente. No Full de reparación.')
start = text.index('UI293 ABI real ABI actual abierta,')
end = text.index('Sesión humana264 íntegra:', start)
text = text[:start]+'''UI293 DETENIDA para compilar; snapshot privado C03-ui293-snapshot298 preserva los
seis logs. /slots libre y sólo IDs6/10del agente verificados antes de parar árbol.
App97436/backend71708 ya no son activos. Cuestionario101140 sigue abierto.
REABRIR BAXY tras prueba integrada299/Fast; no dejarlo cerrado al entregar.
Prueba .NET299 activa al escribir: exec session79628, owners-corrected.log.
''' + text[end:]
text += '''
297 prueba exacta de predicados identifica visible_reply_restates_the_request como
causa única.298 corrige alcance de pregunta y mejora ambos saludos y Lima (tres
replays + tres inferencias iguales con payload idéntico296). SALUDO_Y_PREGUNTAS297_298.md.
299 AskToSave deja seguir el texto completo por la ruta existente; explícita memoria
sigue sólo por parser. Simple memory.* rechazado en TryExecuteMindOperationAsync,
planes memory.* rechazados en MissionPlanValidator. No fiarse sólo de encryption.
Nuevos tests:3conversaciones+propuesta memory.save adversarial. Baseline corregido
4fail/0pass18s demuestra interceptación. Error inicial de tests: journal exclusivo;
ahora compara longitud append-only. Primera suite1845pass4fail por helperoutbox
inexistente (no hubo efecto); corregida para exigir ausencia. Suite actual en marcha.
Próximo: terminar owners/Fast, producto nativo mismo saludo sin reclamar UI/audio,
reabrir instancia del dueño sin timer. Identidad-role y París siguen fallando.
'''
for filename in ('CHECKPOINT.md','HANDOFF.md'):
    (base/filename).write_text(text,encoding='utf-8')
path=base/'RELEVO_ACTIVO.json'
record=json.loads(path.read_text(encoding='utf-8'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='299: source298 native greeting repair verified; source299 AskToSave continuation under owner validation.',continuation='Finish299 owner suites and integrated Fast, verify full native route, reopen BAXY; UI293 stopped with snapshot298. Whole goal active.')
record['userOwnedInstance'].update(status='stopped_for_build298',processRevalidated=False,instruction='UI293 preserved and stopped; reopen after integrated validation. Questionnaire remains alive.')
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
