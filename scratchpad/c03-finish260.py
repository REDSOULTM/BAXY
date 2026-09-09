"""Seal the bounded desktop observation without promoting its candidate."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil
import numpy as np

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-ui260'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui260-private'
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

resources = read(out/'RESOURCES.json')
assert resources['reason']=='deadline_600s'
assert resources['volumeRestoredExactly'] and resources['cleanupExit']==0
assert resources['launcherExit']==0
owned = read(out/'PROCESSES_OBSERVED.json')
survivors = []
for row in owned:
    try:
        if psutil.Process(row['pid']).create_time()==row['created']:
            survivors.append(row['pid'])
    except psutil.NoSuchProcess:
        pass
assert not survivors, survivors
prereg = read(out/'PREREG.json')
changes = [name for name,digest in prereg['sourceFiles'].items() if sha(root/name)!=digest]
events = [json.loads(line) for line in (private/'voice-events.jsonl').read_text(encoding='utf-8').splitlines()]
counts = {kind:sum(e['event']==kind for e in events) for kind in sorted({e['event'] for e in events})}
aec = [e for e in events if e['event']=='aec_observation']
last = aec[-1]
generated = [e for e in events if e['event']=='piper_generated']
for event in generated:
    assert sha(Path(event['path']))==event['sha256']
    values = np.load(event['path'], allow_pickle=False)
    assert values.size==event['samples'] and np.isfinite(values).all()
speech_capture = [e for e in events if e['event']=='state' and e.get('speaking') and e.get('listening')]
summary = {'resources':resources, 'sourceChangesSinceLaunch':changes,
    'knownProcessesSurviving':survivors, 'eventCounts':counts,
    'lastAecObservation':last, 'speakingWhileListeningEvents':len(speech_capture),
    'observedDspMeanMs':last['dspTotalMs']/last['frames'],
    'registrationSha256':sha(Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'),
    'limitation':'Resource sampler measured process-tree dedicated GPU memory and RSS, not all system use. '
        'Human inputs were typed, not ASR decoding. AEC observations are cumulative every100 frames; '
        'forced process cleanup did not produce a graceful aec_closed event.'}
save(out/'SUMMARY.json',summary)
report = f'''# C03 — escritorio, voz y recursos conjuntos: tramo260

Arranque real `py main.py`, fuente257, lock60 instalado, Qwen3.5 con override.
Ejecución de600,51s, sesión72258 recogida exit0. Límite temporal alcanzado;
launcher0, cleanup0, procesos observados cerrados y volumen restaurado exactamente.
No promoción. La fuente del prereg cambió en: {changes}.

Picos atribuidos a BAXY: **{resources['gpuPeakMiB']:.2f}MiB de VRAM** y
**{resources['ramPeakMiB']:.2f}MiB de RAM residente**. VRAM menor que4096MiB.
No es el consumo de todo Windows ni una garantía de máximos para otras cargas.
Los comandos efectivos están en PROCESSES_OBSERVED.json.

El click derecho del agente en el micrófono de la ventana real produjo modo
directo y captura activa. La sospecha de bloqueo por el wake no se reprodujo:
no cambiar React para corregirla. Verificador wake ausente y cascada inválida
siguen declarados en ready; no se valida wake ni C08.

{len(speech_capture)} eventos de habla durante escucha; {last['frames']} bloques AEC
observados acumulados ({last['frames']*.032:.2f}s), micrófono y referencia no nulos.
{len(generated)} audios Piper verificados por hash y muestras. DSP medio observado
{summary['observedDspMeanMs']:.3f}ms y máximo{last['dspMaxMs']:.3f}ms: el máximo supera
un bloque32ms, no se afirma plazo duro. No hubo transcripciones humanas: las
entradas fueron texto, confirmado expresamente por el dueño en este chat.
Esto acredita convivencia de componentes y señales físicas, no exactitud ASR
ni inteligibilidad completa del altavoz mediante sólo el audio generado.

## Respuestas que bloquean C03

| Entrada literal observada del dueño | Salida visible | Evaluación |
|---|---|---|
| Hola como me puedes ayudar hoy? | Puedo ayudarte con cualquier pregunta, explicación o charla que necesites hoy. ¿Qué tienes en mente? | Respuesta general, no acredita explicar capacidades operativas. |
| Tengo en mente que abras steam | No puedo abrir Steam porque está fuera de mis capacidades en este equipo. | Fallo: petición normal no resuelta. Investigar alcance real y selección, no aceptar negativa como éxito. |
| No se que me hablas, tu si puedes hacer eso | No puedo hacer eso porque la interpretación de tu solicitud no fue válida. | Recuperación contractual honesta pero no útil ante corrección normal. |
| abre steam | ¿Quieres que abra Steam? | Aclaración innecesaria ante pedido explícito. |
| Si, abre steam | No puedo abrir Steam porque está fuera de mis capacidades en este equipo. | Sigue sin resolver la petición. |
| mhhhhh, porque no?, cuales son tus capacidades? | Soy BAXY, un asistente virtual que vive en este PC y puedo ayudarte con información, explicaciones y charla, pero no tengo la capacidad de ejecutar aplicaciones como Steam ni controlar el hardware directamente. | Negación general falsa de capacidades del catálogo. |

UI_OBSERVED.txt y UI_FINAL_OBSERVED.txt conservan accesibilidad; también se observó
la pregunta de Tortugas Ninja y el mensaje del dueño identificándose. No todos los
textos posteriores generados por Piper tienen captura visual independiente; no
confundir generación, composición y publicación. La frase posterior «Puedo abrir
y cerrar programas, mover ventanas, ajustar el audio y llevar tareas, además de
otras cosas» consta en Piper, sin acreditar por eso ejecución de ninguna operación.

Primera petición Steam (request11): shortlist28 sin app.open → game.launch bruto
→ domain_grounding lo convierte en unsupported → composición atribuye fuera de
catálogo. El siguiente turno(request16) tiene dos PlannerContractError y recuperación.
El problema empieza antes de prosa. La disponibilidad real de Steam y el rango de
app.open se comprobarán contra un hello nuevo en261, distinguiéndolo del original.

Prereg260 tenía tres controles planeados; no se enviaron porque el dueño estaba
probando la ventana. Sus mensajes son desarrollo humano, no reserva congelada.
Fuente sin editar en260; no tests ni Full repetidos. C03 íntegro EN_CURSO.
'''
(base/'PRUEBAS_UI260.md').write_text(report,encoding='utf-8')
public = [base/'PRUEBAS_UI260.md', *sorted(p for p in out.iterdir() if p.is_file()),
          root/'scratchpad/c03-launch260.py',root/'scratchpad/c03-inspect260.py',
          root/'scratchpad/c03-finish260.py',root/'scratchpad/c03-ui260-hook/sitecustomize.py']
private_files = [private/'voice-events.jsonl', *[Path(e['path']) for e in generated]]
save(base/'TRAMO260_PINS.json', {'public':[{'path':str(p.relative_to(root)), 'sha256':sha(p)} for p in public],
    'private':[{'privatePath':str(p), 'sha256':sha(p)} for p in private_files]})
note = '''# C03 — checkpoint260 — EN_CURSO

UI260 completada, exec72258 exit0 recogido. PRUEBAS_UI260.md y TRAMO260_PINS.json.
VRAM3516,66MiB / RAM4822,60MiB; interfaz/LLM/captura/AEC/Piper coexistieron.
Sin ASR humano, wake sin certificar; no promoción. Fuente257 intacta si SUMMARY
no registra cambios. Cero procesos260 supervivientes, volumen restaurado.

Dueño confirmó que los mensajes observados en UI eran suyos y por texto.
No son reserva. Fallos: Steam se niega, confirmación innecesaria y capacidades
negadas falsamente. Request11: app.open ausente de shortlist28, game.launch
elegido, domain_grounding→unsupported. Request16 falla contrato dos veces.
La sospecha de UI mic bloqueada no se confirmó; directo activo tras click derecho.

261 activo: scratchpad/c03-retrieval261.py, exec63898. Nuevo hello Core read-only,
E5/PlannerCatalog exactos y resolución de Steam para tres literales260. No relanzar.
Recoger handle y TEMP/c03-retrieval261.log; RESULT en astra-retrieval261.
Siguiente: distinguir ausencia de identidad de hueco retrieval y contagio del
historial; corregir causa con comparación medida, no filtros de frases.

Última validación fuente257:171 Python pass/0skips, Fast verde; no Full durante
reparación. Pendiente alcance íntegro: ocho rutas,100/100 humanos frescos aún sin
congelar, averías/recuperación, perfil/runtime/instalación, continuidad C04–C09,
Full final y publicación fuera main. Goal activo, no bloqueo externo.
'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    (base/name).write_text(note,encoding='utf-8')
relay = read(base/'RELEVO_ACTIVO.json')
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='260 completo: recursos conjuntos3516,66MiB GPU; fallos Steam/capacidades observados.',
    continuation='261 activo exec63898: identidad y retrieval. Reparar respuestas antes de reserva y promoción.')
save(base/'RELEVO_ACTIVO.json',relay)
print(json.dumps(summary,ensure_ascii=False))
