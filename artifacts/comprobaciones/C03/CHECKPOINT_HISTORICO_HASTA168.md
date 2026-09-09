# Último: UI166 responde, audio167 falla;168 preparado

ASTRA-TRAMO-166_168.md manda. Fuente164191tests/Fast verdes. UI treshorasveraces ~1s, voiceon,3499,50MiBVRAM; grabación sin frases completas según ASR167. Sin procesos propios activos.168 registra eventos y errorTTS del fullsidecar con audio físico. No Full, wake no aprobado ni reserva aceptada.

# Último: fuente164 — precarga DSP antes del lector;165 siguiente

Fuente164191pass/0skips/19,14s; regresión fría antes fallaba10s.162preimport corrige voz4,438s.163ReadFile también bloquea: no cambiar protocolo. ASTRA-TRAMO-162_165.md manda.165 listo; no procesos propios activos antes del arranque. Sin Full/UI todavía.

# Actualización: 161 terminado; diagnóstico162 siguiente


161 terminado: voice.start agota 60 s; driver exit1 tras ~68 s. Stack repetido:
request_dispatch -> VoiceEngine._start (lock de voz retenido) -> LoopbackReference.start
-> scipy.signal -> scipy.linalg.blas -> carga nativa _fblas. TTS espera ese lock
en _on_tts_state. Cleanup del root exit0 NO prueba cierre cooperativo: stderr
registra request_dispatch_thread y voice_engine_shutdown timed_out; descendientes
propios recogidos. Sin procesos de esta prueba pendientes.
162 prepara una única diferencia experimental: importar scipy.signal en el hilo
principal antes de runpy/lector JSONL. Fuente147 sigue intacta. OpenBLAS documenta
un bloqueo de inicialización gfortran/pipes en Windows para Java; es hipótesis
análoga, todavía no demostración de la causa nativa de BAXY.
https://github.com/OpenMathLib/OpenBLAS#considerations-for-using-the-library-from-java

# C03 — CHECKPOINT — fuente147, falloUI158/sidecar161 en curso — EN_CURSO

Último: ASTRA-TRAMO-158_161.md. UI158 real falla: ES54s/EN116s, voiceoff,
reinicios/timeout de mente; sin salida audible durante300s capturados. Mezcla no
enviada. App35432 cerrada, sampler79424/captura65681exit0,3508,086MiBVRAM/5864,332MiBRAM;
volumen0/mutedtrue restaurado.159startwake nativo8,187s,160saludo+start8,312s ambosready.
**161 sidecarJSONL+LLM+catálogo vigente en curso, sesión16017**, timedfaulthandler
en LOCALAPPDATA/BAXY/C03-sidecar161-private/stacks161.log. Recoger resultado/árbol
antes de nueva prueba. No modificar fuente ni timeouts hasta localizar stack.
La sección siguiente147–157 es antecedente; no volver a UI sin diagnosticar158.

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
TRAMO143_157_PINS.json fija108ficheros públicos;32ficheros privados verificados.
Snapshot143 reconstruido sólo tras coincidir exactamente con hashesPREREG144;
snapshot147 preservado. No modificar informes/scripts fijados; abrir tramo nuevo.
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

## Evidencia hasta135 (anterior a la integración136)

Fuente119/124 vigente, sin cambios de producto en129–135.119 Piper completo:
311tests/0skips/10,36s y Fast60843exit0.124 eco a cada muestra en250ms/umbral0,55:
109tests/0skips/7,78s, Fast90073exit0. No repetir verdes ni Full durante reparación.
PRUEBAS_AEC129_134.md es el informe vigente; TRAMO129_135_PINS.json fija evidencia.

SpeexDSP1.2.1 oficial compilado MSVC14.44/O2/x64, DLL83456bytes sólo experimental
en D:/BAXYRuntime/experiments/voice/speexdsp129/build.129 denoise-off anulaba además
ganancia de eco;130 adopta defaults del ejemplo upstream. Sin cambiar umbrales,
132/133 sobre direct125, sin off-before de entrenamiento: original interrumpe8/8
alineaciones prefijadas a3,807–3,835s, AEC+guard0/8.131 conserva habla cercana
sintética sola; mezcla omite «aquí BAXY». No aceptación de fidelidad/voz humana.

134 físico experimental (wrappers explícitos, fuente intacta):31558/30068exit0,
speaking5,75s,0barge real; el detector original en sombra habría cancelado1vez sobre
los mismos265bloques. Captura36,41s, volumen0/muted=true restaurado. Procesamiento
completo en vivo media0,470ms/p9910,580ms por32ms.135 ASR61032exit0 recupera frase
completa y UTF-8 en micrófono y loopback (variantes invalid/isn't valid preservadas).
No App/server/Piper/captura/inferencia propios activos. Registro sin promoción.

Siguiente136: integrar AEC antes de VAD/energía/segmentación con un estado por
sesión de captura y cierre en finally. Sustituir NLMS de clips y retirar arrays
reference de _DecodeRequest/pre-roll; transportar indicador AEC aplicado al evento
recognized. Echo guard usa par crudo anterior (latencia512 del preprocesador).
Rutas: voice_aec.py:153–225; voice.py:373,2085–2601; tests/test_mind_voice_runtime.py
llamadas privadas decode y testNLMS; assets.manifest.json/resolvedor. Prototipo
scratchpad/speex_stream134.py y c03-voice134.py, no importarlos desde producto.
Probar limpieza/propiedad de estado nativo, sesiones y guard/AEC antes de físico/UI.

Manifest13b971b3… intacto; Qwen3.5 sólo override; assets119 todavía no promovidos.
App permite wake no calibrado por seam preexistente (MindRuntimeDiscovery.cs:188–208),
no aceptarlo. Reserva742/239, preview0–154; tres ingleses admitidos por «Son turnos
validos» ya registrado, no preguntar ni extender a742. Pendientes íntegros: reserva100,
voz/entrada física y UI final, runtime/regresión, continuidadC04–C09, Full final
entero y publicación fuera de main. Sin subagentes, commits/push ni cambios en main.

## Estado histórico anterior a119 (conservado; sustituido por el anterior)

Fuente112/UI108 sigue adoptada;114–118 son mediciones nativas sin edición de
producto. PRUEBAS_TTS114_118.md contiene decisiones, literales, hashes y límites.
Nuevo defecto localizado: el adaptador manual eSpeak pierde terminadores,
límites de oración, NFD y flags que sí conserva el frontend oficial Piper.
Native117 aísla punto final real: mismos3textos/voz inglesa/engine112; contenido
3/3 recuperado por Parakeet. No adoptar un parche de añadir puntos a todo.
Reference1187916exit0: Piper oficial Windows2023.11.14-2, misma voz española y
John inglesa, seis controles ES/EN con contenido recuperado. CLI por turno
0,844–1,218s, carga del modelo~0,6s. No aceptación de audio físico ni UI.
Contraste de backend/frontend completo, no atribuir todo118 sólo a puntuación.
C++ incluye PAD también trasBOS; referencia Python112 no: contrato distinto.

John medium114:63.531.379bytes, SHA789c6c875726e627ddee93d51d8727859abe9c091c3d141591f4b83c2072e988,
configen/familiaen_US, dataset LibriVox dominio público según ficha primaria.
D:/BAXYRuntime/experiments/voice/c03-john114. No otro modelo descargado.
Piper referencia en D:/BAXYRuntime/experiments/voice/piper-reference118/piper.
ZIPSHAf3c58906402b24f3a96d92145f58acba6d86c9b5db896d207f78dc80811efcea.
DLL eSpeak antigua no expone terminador; wheel piper-phonemize no ofreceWindows.
115/116: observador Nemotron existente, mismos WAVs, sin resíntesis.115 sin
flush truncaba;116 añade0,66s de silencio del ejemplo Sherpa y recupera UTF eight.
Eso limita la atribución al TTS de errores de Parakeet; no es prueba humana.

Siguiente implementación: sustituir el frontend manual por Piper completo
probado y retirar el motor sustituido; conservar propietario único de cola,
playback/cancelación. CLI por invocación es la referencia sencilla medida;
debe cancelar su hijo durante síntesis y comprobar coste integrado. Seleccionar
voz con evidencia del texto hablado, reutilizando request_reading, sin obedecer
instrucciones citadas en respuestas. No duplicar clasificador ni protocolo.
Revisar voice_output.py:342–487,624–714; callers measure_goal09_voice.py:186,
test_goal09_voice_engines.py:27/116 y ttsSha256 en voice.py:1685 para no informar
hash español cuando se usa voz inglesa. Asset/registro/modelos deben quedar
reproducibles con ambos idiomas antes de promoción. No cambio adoptado aún.

Fuente112 PAD:85pruebas voz pass/0skips,7,76s; Fast33691exit0,Release3,37s,
0avisos/errores. TRAMO110_113_PINS.json. No repetir verdes ni Full durante reparación.
Audio110: UI tres relojes fieles pero ASR físico no recuperado, última ventana
acortada. GPU3502,296875MiB/RAM6015,91796875MiB con wake1; arranque1,032s excluido.
Capturas privadas LOCALAPPDATA/BAXY/C03-audio110-private, volumen restaurado0/muted=true.
Ningún App/server/Piper/captura/inferencia activo; registro intacto y sin promoción.

UI108/109 error visible/restauración,169tests/Fast verdes; UI107 confirmación/
cancelación/cierre; UI104 progreso y ocho finales. No repetir paneles sin dato nuevo.
Reserva742/239, preview0–154; faltan155–238, selección/congelación100 humanos
antes de inferencia. Tres ingleses confirmados por dueño ya registrados; no
preguntar ni extendera742. Voz/audio físico+entrada, reserva100, promoción/regresión,
continuidadC04–C09, Full final entero y publicación validada fuera de main siguen
pendientes. C03 EN_CURSO íntegro; sin subagentes, commit/push ni cambios en main.

## Decisiones y pruebas que no se repiten

81 panel técnico10/10 útil: archivo/UTF8/causa/checksum/capacidades/hora+audio+CPU/nivel.
Fuente74 corrige veto de operation y fallo negado;77 agrupa sólo prefijo system
(Qwen3.5 daba HTTP400);78 limita vetos por rol;81 adapta gramática existente de
enumeración nominal, manteniendo orden y catálogo.2774pytest pass/0skips;Fast81 verde.
PRUEBAS_ENUMERACION81.md y reportes74/75_76/77/78_80 conservan evidencia.

83 búsqueda vacía2/4: se convertía entries[]/count0 verificados en step_data_missing.
84 conserva file_search_no_matches antes de grounding imposible;162integración pass,
Fast verde tras corregir formato. Producto84 sigue2/4 por veto de negación y cifrado
inventado.86 reconoce no se encontró/no encontré/no se pudo en el guard existente,
preservando ausencia de fallos;1151pytest pass y181integración pass,Fast verde.
Producto86 3/4; la causa inventada nace cuando fallback descarta el contexto.
89/91 nativos: contexto como dato recupera causa/latencia y conserva cálculo/checksum.
Control límites sigue metatexto sin catálogo: no es5/5 ni aceptación de capacidades.
PRUEBAS_RECUPERACION86_89_91.md fija esa distinción y la herencia panel-opus-4/5.

82 progreso nativo4/6 con acting/in progress: porqué afirma lectura nueva; hora/CPU
produce metatexto. App ComposeMilestoneAsync siempre da acting; se pierde understanding.
85 sólo phase=understanding insuficiente.87 state=understanding the person's request
mejora parcial pero sigue leyendo.88 sustituye instrucción: aún lecturas y actor invertido.
90 rol dedicado o solicitud JSON no resuelve. NO adoptar ni apilar vetos/prompts;
se cambia estrategia a perfil/capacidad en93. PRUEBAS_PROGRESO82/85/87/88_90.md.
Todos estos son borradores nativos, no publicación real, UI ni audio.

No reabrir sin dato nuevo: borrar historial rompe referencias68; clasificador69/70
5/10 descartado; frases/roles/descripción65–67 insuficientes. Hechos en historial73
8/10 pero file2/file3 siguen mal; no implementados. is_elliptical_followup no cubre
hazlo/close that. Registrar anomalías, no borrar evidencia ni repetir hasta obtener pase.

## Runtime, reserva y cierre pendiente

Registro: Qwen3-4B-Instruct-2507 Q4_K_M,b9980CUDA12.4,KVq8,ngl99,3x4096.
Manifest SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Core AOT de UI100 SHA9bc4b041ab4741a54a930dc7387498b9d263de9d1f3ed8ef45858dbf94bf6632.
App Release101. Qwen3.5-4B-Q4_K_M local sólo override, mismo backend/perfil salvo93.
Modelo D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf.
Python de pruebas C:/Users/usuario/AppData/Local/Programs/Python/Python312/python.exe;
py apunta a313 sin pytest. Python runtime en %LOCALAPPDATA%/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.

Tres textos ingleses admitidos por «Son turnos validos» ya registrado en
ADMISIBILIDAD_DUENO_2026-09-06.md; no preguntar de nuevo ni extender a742.
Reserva privada742,239candidatos no refutados;100 aún no seleccionados/congelados.
RESERVE_PROVENANCE_AUDIT45.json reutilizable. Spanglish español natural válido;
sin cuotas/traducciones. Cuatro ejemplos ACLARACION_DUENO_2026-09-06.md vigentes.

Falta cierre completo: ocho rutas útiles, cien turnos humanos frescos/literales
congelados antes de ejecutar y100/100 adjudicados, averías+recuperación aparte,
UI escritorio real con py main.py, voz/audio físico y techo conjunto4GB; conductor
no acredita UI/audio. Regresión y hashes antes de promover runtime; continuidad
C04–C09 hasta instalación; Full íntegro verde sólo al candidato final y publicación
validada fuera de main. No cerrar por panel técnico, silencio, skip ni traza solamente.

119 integrado: proveedor Piper completo en piper_tts.py sustituye frontend manual; cola/OutputStream dueño conservados, selección idioma/hash/frecuencia por texto. Assets de desarrollo copiados por hash; registro intacto.311tests pass/0skips/10,36s; Fast60843 ACTIVO tras retirar import muerto. ASTRA-TRAMO-119.md. Native120 preparado no ejecutado, sin App/modelos/captura activos. Recoger Fast y ejecutar native120 antes de aceptación física. Sin Full.

119 Fast60843exit0/Release2,96s; native12011445exit0,6contenidos ES/EN fieles y cancelación real94ms/hijo38440 recogido. Audio121 captura32330 ACTIVA, máximo300s/volumen0,30 restaura inicial; launcher-monitor21410 ACTIVO, py main.py. PREREG en astra-audio121. STOP_AUDIO/STOP_APP controlan únicamente esta corrida. No builds/modelos concurrentes.

121 concluido32330/21410exit0: tres finales UI fieles, GPU3513,41796875MiB/RAM5964,01953125MiB,257,75s; captura267,42s sin overflows, volumen0/muted=true restaurado. ASR85289exit0 no recupera contenido físico (t2loopback dice Yeah); ventanas completas13s. No aceptación acústica. Registro python_path confirma src actual. Diagnóstico122 ACTIVO: captura26286 con restore/300s y driver12205, VoiceEngine real off-before/wake/off-after, misma fraseEN, eventos barge_in guardados, sin App/LLM/efectos. No cambiar guards antes del resultado; STOP_AUDIO en finally.

122 terminó parcial12205exit1: off-before5,171s speaking,0barge; start wake rechazó wake_verifier_manifest_missing; captura26286exit0 restauró volumen. No relajar wake. App publica explícitamente manifiesto registrado con calibration.approved=false y BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED=1 (MindRuntimeDiscovery.cs:188–208), seam preexistente, no aceptación wake.123 ACTIVO: driver62079/captura97658; off-before/direct/off-after por rama barge-in compartida anterior a selección de modo; sin cambiar guards ni efectos. Recolectar resultado y restauración, luego documentar causa.

12362079/97658exit0: off-before5,234s/0barge, direct1,469s/1barge, off-after5,391s/0barge, misma frase/engine/Piper; volumen restaurado0/muted=true.124 corrige _looks_like_echo para evaluar cada muestra en misma ventana250ms y umbral0,55, sin cambiar reglas de interrupción. Prueba antes6fail/2pass retardos no múltiplos128; después109pass/0skips/7,78s, media0,328ms porframe en NumPy1.26.4. Fast90073 activo;125 preparado aún no arrancado. No App ni capturas activas.
