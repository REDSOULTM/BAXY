"""Seal the actual desktop regression, including its failures and recovery."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-ui263'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui263-private'
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

resources=read(out/'RESOURCES.json')
assert resources['volumeRestoredExactly'] and resources['cleanupExit']==0 and resources['launcherExit']==0
assert resources['reason']=='deadline_600s'
for process in read(out/'PROCESSES_OBSERVED.json'):
    try:
        assert psutil.Process(process['pid']).create_time()!=process['created']
    except psutil.NoSuchProcess:
        pass
source=read(base/'astra-source263-snapshot/FILES.json')
assert all(sha(root/name)==digest for name,digest in source.items())
compose=[json.loads(line) for line in (out/'compose-audit.jsonl').read_text(encoding='utf-8').splitlines()]
verified=[row for row in compose if row.get('trace') in {'t1','t5'} and row.get('published')
          and row.get('payload',{}).get('seen',{}).get('appId')=='Steam']
assert len(verified)==2
for row in verified:
    facts=json.loads(row['situation'])
    assert facts['verified'] and facts['succeeded'] and facts['observed']['alreadyRunning']
error_ui=(out/'UI_CAPABILITIES_TERMINAL.txt').read_text(encoding='utf-8')
recovery_ui=(out/'UI_RECOVERY_SETTLED.txt').read_text(encoding='utf-8')
assert 'Response error' in error_ui and 'agent state: error' in error_ui
assert 'Steam ya está abierto.' in recovery_ui and 'agent state: idle' in recovery_ui
assert 'Response error' not in recovery_ui
events=[json.loads(line) for line in (private/'voice-events.jsonl').read_text(encoding='utf-8').splitlines()]
generated=[row for row in events if row['event']=='piper_generated']
for row in generated:
    assert sha(Path(row['path']))==row['sha256']
posts=[json.loads(line) for line in (private/'http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
save(out/'SUMMARY.json',{'resources':resources,'sourceFilesUnchanged':len(source),
    'verifiedSteamResults':len(verified),'piperGenerated':len(generated),
    'httpObservations':len(posts),'acousticCaptureActivated':False,
    'closeButton':'Hides window by MainWindow.OnClosing; deadline closed the owned tree.',
    'allFiveControlsPassed':False,'knownProcessesSurviving':[]})
report='''# C03 — regresión en escritorio tras recuperar Steam:263

Fuente262,37archivos congelados en astra-source263-snapshot, sin cambios durante
la corrida. Qwen3.5 sigue override. Entrada real py main.py; cinco controles
introducidos por el agente mediante Computer Use, reutilizando literales que el
dueño había escrito en260. Ningún mensaje sintético inyectado por el hook. No reserva.
El orden cambia respecto260; esto es regresión de causa, no comparación pareada
de todas las respuestas de aquella secuencia.

| Caso | Respuesta final visible | Resultado |
|---|---|---|
| abre steam | Steam ya está abierto. | Correcto: app.open, Core succeeded/verified, alreadyRunning=true, ventana132992. |
| Tengo en mente que abras steam | Ya he abierto Steam. | No aceptado: no hubo nueva operación/lectura; el compositor reutilizó previousResponse. |
| Si, abre steam | No puedo abrir Steam porque está fuera de mis capacidades en este equipo. | Fallo: negativa falsa. |
| mhhhhh, porque no?, cuales son tus capacidades? | Sin prosa final; alerta Response error y estado error. | Fallo normal espontáneo; entrada permanece disponible. |
| abre steam (después del error) | Steam ya está abierto. | Recuperación comprobada: nueva app.open verificada, alerta desaparece y estado idle. |

La reparación262 sí llega al producto: el primer y último control resuelven y
verifican Steam sin pedir confirmación. Ya estaba abierto: no se presenta como
un lanzamiento nuevo. La ventana real y los hechos del Core se contrastaron.

La frase larga todavía tiene shortlist28 sin app.open. Dos selecciones nativas
(HTTP id5 con28tools e id7 con4) contestan «Steam ya está abierto.» sin toolcalls;
la mente genera después «No puedo abrir Steam directamente, pero puedo ayudarte
a encontrar enlaces o guiar los pasos para hacerlo tú mismo.» El compositor
publica «Ya he abierto Steam.» desde previousResponse=«Steam ya está abierto.».
No hubo Core app.open para t2; el historial no acredita una verificación actual.

«Si, abre steam» entra en explicit_conversation/unsupported(request15); el
chequeo adicional HTTP id11 ve sólo cuatro operaciones game.install y responde
sin toolcalls. `_catalog_unavailable_turn_decision` sigue siendo un owner a
inspeccionar: su patrón game_request abarca open/abre y puede cerrar antes del
selector normal cuando la extracción de identidad no coincide.

Capacidades(request19): selección nativa id18 devuelve una lista larga y
finish_reason=length. Enumera capacidades de su shortlist incompleta, niega
abrir aplicaciones y termina truncada. Segundo intento id22: TimeoutError.
Recuperación turn_runtime_failure; varios borradores de error son rechazados
por extra_claim. Se observa estado error, sin final público. El siguiente turno
normal sí funciona. No se relajan límites ni validadores para convertirlo en pass.

HTTP lógico completo y respuestas se conservan privados en
C03-ui263-private/http-posts.jsonl. El hook observa LlmRuntime._post y eventos
de voz; no modifica parámetros, resultados ni criterios. UI_STEAM_SETTLED,
UI_LONG,UI_FOLLOWUP,UI_CAPABILITIES_TERMINAL y UI_RECOVERY_SETTLED guardan
las vistas estables. Algunas vistas inmediatas anteriores conservan caché UIA
antigua mientras la imagen ya había cambiado; no usarlas solas para adjudicar.
set_value falló sin escribir; se usó el teclado sobre el campo visible.

Recursos:3504,71MiB GPU y5624,86MiB RAM residente,600,41s; atribución disponible.
No captura acústica activada en263: no sustituye la medición conjunta260.
El botón cerrar ocultó la ventana por la presencia en bandeja; el monitor cerró
su árbol al límite600s. Exec80211 exit0 recogido, launcher0,cleanup0,
volumen restaurado exactamente y ningún proceso observado sobreviviente.

No fuente editada en263 ni pruebas repetidas. Fuente262 conserva39tests dueños
sin skips y Fast verde. C03 íntegro EN_CURSO: falta reparar los tres recorridos
anteriores antes de aceptación fresca, promoción, Full y publicación.
'''
(base/'PRUEBAS_UI263.md').write_text(report,encoding='utf-8')
public=[base/'PRUEBAS_UI263.md',*sorted(path for path in out.iterdir() if path.is_file())]
public += [root/'scratchpad'/name for name in ['c03-prepare263.py','c03-launch263.py',
    'c03-ui263-hook/sitecustomize.py','c03-inspect263.py','c03-read263.py','c03-finish263.py']]
public += [base/'astra-source263-snapshot/FILES.json']
private_files=[private/'voice-events.jsonl',private/'http-posts.jsonl',*[Path(row['path']) for row in generated]]
save(base/'TRAMO263_PINS.json',{'public':[{'path':str(path.relative_to(root)),'sha256':sha(path)} for path in public],
    'private':[{'privatePath':str(path),'sha256':sha(path)} for path in private_files]})
state='''# C03 — checkpoint263 — EN_CURSO

Goal-c03; main preservada. Último cambio262: catálogo Windows filtra alias con
destino .exe local comprobado ausente sólo frente a una identidad existente,
sin alternativas desconocidas.39tests/0skips y Fast verde Release22,27s.
Hello292→293 nombres: sólo añade Steam,169operaciones sin cambios.
CATALOGO_STEAM261_262.md,antes en astra-app-catalog262/before.

UI263 confirma «abre steam»→app.open verificada→«Steam ya está abierto.»;
se repite tras error con nueva verificación y UI idle. PRUEBAS_UI263.md,
TRAMO263_PINS.json; fuente37archivos congelada astra-source263-snapshot intacta.

Tres bloqueos concretos: (1) «Tengo en mente que abras steam» shortlist28 sin
app.open; dos selecciones nativas sin toolcalls, prosa mente niega, compositor
reutiliza previousResponse y publica «Ya he abierto Steam.» sin nueva operación.
(2) «Si, abre steam» explicit_conversation unsupported; revisar
__main__._catalog_unavailable_turn_decision y extracción de identidad antes de
añadir un patrón. (3) capacidades tras negativa: nativo id18 length con lista
incompleta/negación falsa; id22 TimeoutError, recuperación/extra_claim agota
prosa; UI Response error con entrada activa. «abre steam» después recupera.
HTTP exacto lógico en %LOCALAPPDATA%/BAXY/C03-ui263-private/http-posts.jsonl.

Recursos263:3504,71MiB GPU/5624,86MiB RAM,600,41s; sin captura activada.
260 sí observó UI/LLM/captura/AEC/Piper conjuntamente:3516,66MiB GPU/4822,60MiB
RAM; no ASR humano. Usuario confirmó que sus mensajes260 eran texto humano.
Wake aún sin certificar. No promoción; registro intacto, Qwen3.5 override.

Ningún proceso propio activo.80211 cerrado exit0; botón cerrar oculta ventana,
deadline600 cerró árbol; volumen restaurado. Fuente263 sin editar ni nuevos tests.
Siguiente264: aislar las tres transformaciones anteriores con HTTP263 y helpers
actuales, misma población/contexto, una diferencia cada vez. Heredar investigación
de formato/modelo y casos67; no repetir Full ni añadir filtros de frases.

Pendiente entero: ocho rutas útiles,100/100humanos frescos aún sin congelar
(742 únicos/239 revisados; tres ingleses históricos admitidos), averías,
UI/voz/ASR/recursos finales,perfil/runtime/instalación,continuidad C04–C09,
Full y publicación fuera main. C03 activo sin bloqueo externo.
'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    (base/name).write_text(state,encoding='utf-8')
relay=read(base/'RELEVO_ACTIVO.json')
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='263 completado: Steam simple verificado y recuperación; tres fallos de contexto/selección/prosa. Sin procesos.',
    continuation='264 aislar retrieval/identidad/composición con HTTP263; alcance íntegro pendiente, no Full durante reparación.')
save(base/'RELEVO_ACTIVO.json',relay)
print(json.dumps({'publicPins':len(public),'privatePins':len(private_files),'checkpoint':263,'allFiveControlsPassed':False}))
