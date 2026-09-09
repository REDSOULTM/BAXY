from pathlib import Path
import hashlib
import json
import os
from datetime import datetime, timezone

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-sidecar173'
out.mkdir(exist_ok=False)
prereg=json.loads((base/'astra-sidecar168/PREREG.json').read_text(encoding='utf-8'))
prereg.update(method='Same physical fullsidecar168/catalog/model/observed App env and four consumed texts. Only product difference: source172 resets the interruption count on non-speech or non-speaking frames and emits at the third qualifying frame, not every subsequent frame. Same three-frame duration, VAD, energy, echo guard and Speex configuration. Same state-only observer as168; no169 snapshot/per-frame taps. Compare interruption events and actual complete output; do not call a pass proof of100-turn/wake acceptance.',sourceFiles={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in prereg['sourceFiles']})
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2,ensure_ascii=False),encoding='utf-8')
for name in ['c03-capture168.py','c03-sidecar168.py','c03-sidecar168-entry.py']:
    content=(root/'scratchpad'/name).read_text(encoding='utf-8').replace('168','173')
    content=content.replace('source164','source172')
    with (root/'scratchpad'/name.replace('168','173')).open('x',encoding='utf-8') as f:
        f.write(content)
snapshot=base/'astra-source172-snapshot'
snapshot.mkdir(exist_ok=False)
index=[]
for source in [root/'src/baxy_mind/voice.py',root/'tests/test_mind_voice_runtime.py',Path(os.environ['TEMP'])/'c03-source172-red.log',Path(os.environ['TEMP'])/'c03-source172-owner.log']:
    target=snapshot/source.name
    target.write_bytes(source.read_bytes())
    index.append({'source':str(source),'copy':str(target.relative_to(root)),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
(snapshot/'INDEX.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
report='''# C03 — contador de interrupción sostenida — fuente172

Defecto observado en código: si VAD no declara habla, el contador anterior no
se reinicia. Acumula candidatos separados por silencio o por salida detenida.
Además, >=3 emite nuevas cancelaciones en cada frame mientras el output aún
está cerrándose.168 mostró eventos separados por31ms dentro de un mismo corte.
Esto no prueba que el PRIMER corte169 fuera por acumulación; se conserva ese límite.

Prueba del capture_loop original: cinco secuencias, VAD/stream aislados;
4fallos/1pase/81deselected en1,42s. Capturaba [3,4,5,6] en vez de un solo [3]
y cancelaba al sumar tres frames no consecutivos. Incluye control positivo de
tres frames consecutivos que ya pasaba; no se cambia la duración exigida.

172 añade reinicio cuando no hay voz o no está hablando, y cambia >=3 por ==3.
No modifica modelo, DSP, duración3frames, umbrales, ventanas ni política wake.
Suites dueñas voz/captura/Speex/output/goal06:130pass,0skips,7,36s.
Fast55364 en curso al preparar este informe; recoger antes del ensayo173.

Herencia: biblioteca/gemma4-agent/documentacion/01_arquitectura/design/barge_in.md
exige actividad consecutiva, pero es DESIGN ONLY: no acredita una implementación
ni se adopta su duración propuesta de500ms. El código actual conserva96ms.
Contraste primario Speex consultado2026-09-07:
https://www.speex.org/docs/manual/speex-manual/node7.html
El manual advierte sobre adaptación, reloj y distorsión. mdf.c1.2.1:1124–1170
calcula adaptación mínima; no se midió todavía ese estado nativo en169.
No se atribuye el corte a adaptación sólo por esa lectura ni se modifica el filtro.

173 preparado: mismo fullsidecar168 y cuatro textos, mismo observador de estado
(sin taps porframe ni snapshot169), nueva fuente172. Registrar todos los cortes;
si siguen, no aumentar duración ni retocar correlación para aprobar la corrida.
'''
(base/'ASTRA-TRAMO-172.md').write_text(report,encoding='utf-8')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name
    intro='# Actualización172 — contador consecutivo reparado;173 preparado\n\n130pass/0skips/7,36s; antes4fail/1pass. Fast55364 en curso. ASTRA-TRAMO-172.md manda sobre el estado164 de abajo. Sin audio/modelos activos antes de173. No Full.\n\n'
    p.write_text(intro+p.read_text(encoding='utf-8'),encoding='utf-8')
p=base/'RELEVO_ACTIVO.json'
d=json.loads(p.read_text(encoding='utf-8'))
d.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='Fuente172 corrige acumulación no consecutiva y emisiones repetidas de barge.130pass/0skips7,36s; Fast55364 en curso.',continuation='Recoger Fast55364;173 preparado, mismo fullsidecar168/cuatrotextos/estadoonly. No taps169 ni cambiosDSP; mantener resto C03 íntegro.')
p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('173 preregistered; source172 and prior evidence preserved.')
