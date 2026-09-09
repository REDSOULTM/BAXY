from pathlib import Path
import datetime
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
checkpoint='''# C03 — CHECKPOINT — fuente147, evidencia157 — EN_CURSO

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, continuación de01a074f6-9e0e-7fb3-8282-a6b706198a7e.
Goal activo, Goal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
WIP/ajeno/evidencia preservados, sin commit/push/main/subagentes. Sin bloqueo externo.
Autoridad C03_ASTRA_AUTORIDAD.md/C03_RESPUESTA_VERAZ.md, identidad y AGENTS.
Historias anteriores CHECKPOINT_HISTORICO_HASTA67.md y CHECKPOINT_HISTORICO_HASTA91.md.

## Estado actual y siguiente acción

Fuente147:143 reemplaza MME/latest por WasapiCaptureStream con ADC/cola64,
LoopbackReference ring4s/sample_index/window_at, cursor anclado una vez/avance512.
No saltos/repeticiones para alimentar Speex. Overflow/cancelación explícitos.
PCM inyectado no afirma AEC del escritorio.147 crea stream dentro de __enter__ con
ExitStack/_com_apartment existente: COM antes de open/start, libera tras close.
145 main abre/worker falla;146 worker+COM3/3abre y lee. No cambiar DSP/umbrales.

Python runtime -m pytest tests/test_voice_capture_clock.py tests/test_speex_aec.py
tests/test_mind_voice_runtime.py tests/test_piper_tts.py tests/test_neural_speech_output.py
tests/test_goal06_voice.py tests/test_asset_resolution.py -q:148pass/0skips/11,29s.
Fast77674exit0, Release1,39s/0avisos/errores. Snapshot14714ficheros/logs con huellas.
No repetir verdes ni Full durante reparación. Todo source147 sin cambios posteriores.

PRUEBAS_CAPTURA143_157.md es informe vigente; ASTRA-TRAMO-143/147 documentan decisiones.
144 falla antes de hablar (COM);148 sí arranca pero se corta1,609s/1barge.157ASR
confirma que sólo quedó “The file…” en mic/loopback; no otra voz inteligible,
sin prueba de ausencia de interferencia. **Corte148 no resuelto causalmente.**
149tap retorna originales:5,282s/0barge.150historia continua bitidéntica entreframes,
lag global835samples/52,19ms;1518fases0–448step64 dan0barge y fase0cleanbitidéntico.
Es componente offline, no segmentación completa ni aceptación física.

152tresinicios+tap:0barge en3.153sólo copia única del PCM generado, sin tap por frame:
0barge en3.154seisfixtures ES/EN consumidos120, con tap:0barge en6. No seleccionar
estos pases para borrar148. Piper genera PCM variable:152duraciones4,403/4,600/4,252s
y hashesdistintos. No asumir que mismo texto sea misma señal ni atribuir cambios
sólo a instrumentación. AEC nuevo por captura; Silero del engine cargado se conserva.
156ASRCPU recupera contenidos físicos154: horas07:14/13/15 y negaciones de errores;
variantes Paxi/Baxi, re/read, in valid/invalid, una normalización omite quince.
Todos resultados crudos conservados. No transcripción perfecta/entrada humana aceptada.

Siguiente: avanzar a medición de producto/UI147 con entrada/salida físicas y recursos,
conservando evidencia exacta si reaparece corte. Empezar por scripts/capturasUI121
en scratchpad y PRUEBAS_CAPTURA143_157. No otro barrido de la misma frase ni umbrales.
148 queda abierto hasta mecanismo/estabilidad verificados; seisfixtures154 y PCM
generado152/153/154 disponibles para controles de señal idéntica si hacen falta.

Sin procesos propios App/server/Piper/captura/inferencia. Todas sesiones recogidas:
últimas154driver58440/captura25526exit0 y156ASR34732exit0. Cada captura144/148/149/
152/153/154 restauróexactamente0/muted=true,0overflows; ninguna fue UI.
Fuente147 mantiene136Speex por sesión antes deVAD/segmentación/streaming, guard
conparcrudoanterior porlatencia512. DLL staged D:/BAXYRuntime/assets/aec/speexdsp-1.2.1/
speexdsp.dll SHA bb683ab3c50f66f777f0d2eb570b57c0ef5c71cb7e45535f9625a3f2ab56d9f1.
Piper/John/AEC y Qwen3.5 sólo candidatos/override, runtime sin promoción.

Reserva742/239: **preview0–238 completo** tras155. RESERVA_PREVIEW155.md:194/177 y
207/185 duplicados redactados de misma ocurrencia;160/173/228/236 parecen truncados;
156/224 contexto ambiental pendiente. No inferir origen por estilo ni convertir
mensajes históricos en permiso para enviarlos. Sólo41/102/128 confirmados humanos
por «Son turnos validos»; no preguntar ni extender. Sin100seleccionados/congelados
ni inferencia. Siguiente reserva: contexto/procedencia/recuperaciónliteral antes de100.

App permite wake no calibrado por seam MindRuntimeDiscovery.cs:188–208, no aceptado.
Faltan ocho rutas/reserva100, UI y voz humana/doblehabla/continuidad, registro/regresión,
continuidadC04–C09, Full completo final y publicación propia fuera de main.

'''
old=(base/'CHECKPOINT.md').read_text(encoding='utf-8')
tail=old[old.index('## Evidencia hasta135'):]
(base/'CHECKPOINT.md').write_text(checkpoint+tail,encoding='utf-8')
handoff='''# Handoff C03 — fuente147/evidencia157 — 2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, Goal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Goal íntegro activo; CHECKPOINT manda.
Preservar WIP/ajeno/evidencia; sin commit/push/main/subagentes ni bloqueo externo.

147 integra captura WASAPI con ADC/cola64 y referencia continua ring4s/cursor512.
COM del dueño rodea open/start/close;145workerfallaba,146COM3/3abre. Speex136 sigue
únicoDSP antes deVAD/segmentación; no umbrales modificados.148tests/0skips/11,29s,
Fast77674exit0/Release1,39s. astra-source147-snapshot/INDEX.json14ficheros/logs.
PRUEBAS_CAPTURA143_157.md/ASTRA-TRAMO-147.md. No repetir verdes ni Full en reparación.

148físico falla1,609s/1barge y157ASR sólo“The file…”: **sigue abierto**.
149tap original5,282s/0barge;150referencia continua;1518fases/0barge,PCMfase0bitidéntico.
152tap3inicios/0barge;153sin taps porframe3/0;1546fixturesES/EN/0. No borrar148.
Piper varía señal/duración para idéntico texto (PCM152/153/154 privados con hashes).
No atribuir resultados sólo a instrumentación. Reinicios recreanAEC, noobjetoSilero.
156ASR recupera contenido físico154 con variantes conservadas (nombre/invalid/quince).
No entrada humana/UI aceptadas. Ningún proceso propio; capturas restauraron0/mutedtrue.

Siguiente: medición de producto/UI147, voz física y recursos, desde driversUI121
en scratchpad; si reaparece corte guardar señal exacta antes de cambiar mecanismo.
No otro barrido de misma frase buscando pase ni modificación de umbrales.148 abierto.

Reserva742/239: preview0–238 ya completo. RESERVA_PREVIEW155.md detecta duplicados
redactados y truncados/contexto pendientes. Sólo41/102/128 confirmados«Son turnos
validos»; no repetir pregunta ni extender. Resolver procedencia/literal, seleccionar
y congelar100 antes de inferencia; no selección/inferencia aún. Mensajes históricos
no autorizan envíos actuales. Mantener ocho rutas y mezcla natural sin traducciones.

Piper/John/AEC staged; Qwen3.5override; runtime no promovido. Wake App permite
manifestnoaprobado mediante MindRuntimeDiscovery.cs:188–208, noaceptación.
Faltan reserva100/ocho rutas, UI/vozhumana/doblehabla/sesión, registro/regresión,
continuidadC04–C09, Full final verde y publicartrabajopropio fuera de main.
RuntimePython LOCALAPPDATA/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe;
Fast resolvedornormal; UI sólo py main.py/ComputerUse. Sin procesos activos.
'''
(base/'HANDOFF.md').write_text(handoff,encoding='utf-8')
p=base/'RELEVO_ACTIVO.json'
state=json.loads(p.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Fuente147148tests/Fast verdes; evidencia143–157 y reserva239vista. C03 EN_CURSO;148corteabierto.',
    continuation='Sin procesos propios. Siguiente producto/UI147 con audio/recursos, preservar señal si falla; no otro barrido de frase. CHECKPOINT/PRUEBAS_CAPTURA143_157 mandan. No Full en reparación.')
p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Checkpoint/HANDOFF/relevo updated; full goal remains active.')
