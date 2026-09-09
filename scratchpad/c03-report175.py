from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-webrtc174-private'
rows=json.loads((base/'astra-webrtc174/RESULTS.json').read_text(encoding='utf-8'))
asr=json.loads((private/'ASR.json').read_text(encoding='utf-8'))
obs=json.loads((private/'OBSERVE175.json').read_text(encoding='utf-8'))
text='''# C03 — contraste AEC3 y doble habla — tramos 173–175

La fuente172 corrige el contador de interrupciones, pero el ensayo físico173
sigue cortando dos de cuatro salidas. AEC3 por defecto mejora la eliminación de
eco174, pero falla el control de palabras cercanas mezcladas con eco174/175.
No se adopta ni se promueve. No hay nueva prueba de UI ni audio físico en174/175.

## Fuente172 y corrida física173

Pruebas dueñas:130 pass,0 skips,7,36s; Fast55364 exit0, Release2,73s,0 avisos/errores.
173: saludo1,344s y primera hora ES1,656s cortados por barge_in; hora EN2,750s
y última hora ES2,984s sin evento. Todos los errores TTS null. No se ha verificado
que las dos salidas sin evento contengan la frase completa. Dos eventos en dos
salidas: desaparece la emisión repetida observada en168, no baja la tasa2/4.
Capture84,25s,0overflows,threadsStopped=true,restoredExactly=true (0/muted=true).
Driver41212/captura20590 terminaron exit0. No procesos propios de esas corridas.

## Herencia, alternativa y configuración

SpeexDSP1.2.1,512muestras,16k,cola3200 y preprocesador por defecto, fuente172.
Se reutilizan señales149 nativas exactas y127/129/131 de mezcla sintética ya
consumidas.149 reproduce la salida Speex bit a bit.127/129 conservan alineación
aproximada de streamReadyUtc; no atribuir ese reloj a captura nativa exacta.

[pywebrtc-audio0.2.0](https://github.com/strands-labs/pywebrtc-audio), consultado
2026-09-07: wheel CPython312 Windows x64 de513.391bytes, SHA
0dabbdadd5d7fd7dcb88323266e5e14d46aaa136c58fa0573c4b0323b683c80b.
Descarga aislada en D:/BAXYRuntime/experiments/voice/webrtc174, sin instalación
en runtime. Fuente distribuida también conservada y verificada con PyPI.
MODIFICATIONS.md declara extracción ewan-xu/AEC3 y modificaciones; no identifica
un commit exacto de WebRTC. No describirla como idéntica al Chrome actual.

AEC3 16k mono, bloques continuos de160muestras, estado frío por caso;
stream_delay_ms=0 (estimador interno), HPF intrínseco, sin NS/AGC añadidos.
Sin rellenar de silencio cada bloque512. Se descarta sólo el resto final menor
a10ms en AEC3 y a32ms en Speex; no afecta la ventana hablada interior.
El análisisVAD usa umbral0,5/energía0,004/floor1,8 y contador consecutivo172.
Omite guard crudo: son candidatos máximos, no eventos reales de cancelación.

## Medición local

| Señal | Método | Bloques de habla | Candidatos sin guard | Mayor secuencia |
|---|---|---:|---:|---:|
'''
for r in rows:
    text+=f"| {r['case']} | {r['method']} | {r['speechFrames']} | {r['qualifiedFramesWithoutEchoGuard']} | {r['maxConsecutiveWithoutEchoGuard']} |\n"
text+='''
AEC3 media~0,075ms por10ms; Speex~0,135ms por32ms. Ambos CPU; no se mide aquí
VRAM/RAM de producto combinado. rssDelta incluye buffers/allocador y no equivale
a memoria aislada del algoritmo. Latencia observada del control cercano:127
muestras AEC3,511 Speex por correlación; no se ha integrado el adaptador512→160.

## Palabras preservadas y perdidas

Entrada cercana sintética heredada120: «¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?».
Parakeet registrado,CPU6/beam8,sin hints,misma ventana131 para cada método:

| Control | Método | Texto observado174 |
|---|---|---|
'''
for r in asr:
    text+=f"| {r['case']} | {r['method']} | {r['text'] or '(vacío)'} |\n"
text+='''
Observación175 del mismo PCM: Parakeet normalizado a pico0,8; Nemotron3.5 ya
instalado,CPU6/greedy/auto,silencio final0,66s heredado116, crudo y normalizado.
No cambia el cancelador ni se regenera señal. Resultados completos:

| Control | Método | Observador | Normalizado | Texto observado175 |
|---|---|---|---|---|
'''
for r in obs:
    text+=f"| {r['case']} | {r['method']} | {r['observer']} | {r['normalized']} | {r['text'] or '(vacío)'} |\n"
text+='''
El caso mezclado AEC3 pierde contenido ante ambos observadores. Normalizar no
recupera la frase íntegra. La ausencia de candidatos de eco no basta para adoptarlo.
Las variantes de nombre Baxi/Paxi no se confunden con omitir toda la frase.

## Decisión y siguiente contraste

176 observa salida lineal y final con la API nativa EchoControl::ProcessCapture
y GetMetrics. No cambia duración/umbrales de barge ni parámetros de supresión.
Primero exige comparar salida final de compilación local con wheel174 para
distinguir la diferencia de build del punto observado. No asumir pérdida en la
supresión residual sin ver salida intermedia.
Conservative_initial_phase no se cambia: aec_state.cc:91–101/283–312 prolonga
los tiempos iniciales, no demuestra recuperar voz cercana por su nombre.

Goal EN_CURSO.100 humanos sin congelar/ejecutar; ocho rutas finales, audio/ingreso,
averías/recuperación, promoción/regresión/continuidadC04–C09,Full/publicación
siguen pendientes. Fuente172 y manifiesto registrado intactos durante174/175.
'''
(base/'PRUEBAS_AEC173_175.md').write_text(text,encoding='utf-8')
note='''# Actualización175 — AEC3 elimina eco pero pierde palabras en mezcla

174 terminó exit0 (15557):15 mediciones; replaySpeex149 bitidéntico.
175 terminó exit0 (41409):18 observaciones locales sobre el mismo PCM.
AEC3 por defecto no se adopta: mezcla falla con ambos reconocedores y normalización.
PRUEBAS_AEC173_175.md contiene comparaciones y textos completos.
176 compilación diagnóstica en curso, sesión9568, log TEMP/c03-linear176-build.log.
Expone salida lineal y métricas; no cambia supresión ni producto. Recoger esa
sesión antes de iniciar otra; después verificar paridad final y observar etapas.
No App/modelo/captura activos; no Full. Resto de C03 íntegro.

'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name
    p.write_text(note+p.read_text(encoding='utf-8'),encoding='utf-8')
p=base/'RELEVO_ACTIVO.json'
d=json.loads(p.read_text(encoding='utf-8'))
d.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='174/175 terminados: AEC3 default suprime eco pero pierde palabras de doble habla; no adoptado.',continuation='Recoger build176 sesión9568; observar salida lineal/final y métricas con paridad de build antes de inferir causa. No fuente/runtime cambiados; resto C03 íntegro.')
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Report173–175 and checkpoint updated.')
