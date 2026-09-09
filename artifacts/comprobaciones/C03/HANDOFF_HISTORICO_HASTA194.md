# Actualización194 — tres casos de interfaz comprobados; C03 EN_CURSO

UI real iniciada por py main.py con fuente192 y Qwen3.5 de prueba. Eventos
diagnósticos externos: acuse wake, aclaración por transcripción dudosa y llegada
de petición nueva mientras se redacta un acuse. Los dos primeros visibles; el
acuse obsoleto no se publica. La nueva hora «Son las 13:05.» coincide con Core
utc 2026-09-07T16:05:01.2546992+00:00 y offset -180. UI-supersede.txt conserva
cinco entradas, sin el segundo acuse. La marca published del audit del compositor
no equivale por sí sola a publicación en UI: el descarte posterior es correcto.
Evidencia exacta: astra-ui194/{UI-wake.txt,UI-uncertain.txt,UI-supersede.txt,
compose-audit.jsonl,shell-trace.jsonl,RESOURCES.json}. No aceptación acústica,
entrada humana ni reserva: comandos inyectados y wake sin calibración aprobada.
Monitor51134 recogido exit0; fin operator_finished mediante STOP_APP propio,
cleanupExit0, launcherExit0. 540,41s, GPU3480,15234375MiB, RAM5326,40625MiB.
No cambio de AEC ni promoción. Pendiente fijar el tramo194 por hashes y continuar
el fallo acústico183; sigue pendiente el cierre completo descrito abajo.
El usuario solicita balance de todo el chat y trabajo restante; responder con
avances demostrados y criterios abiertos, sin porcentaje o plazo inventados.

# Actualización193 — fuente192 validada localmente; C03 EN_CURSO

191 completo16lecturas: Nemotron recupera inglés187 completo en loopback; la
lectura Parakeet189 incompleta no acredita corte.183 y mezcla129 siguen abiertos.
Fuente192 retira dos TTS fijos, conserva eventos, App/cola existente compone
hechos y descarta avisos obsoletos. Sin AEC/umbrales/modelo/runtime nuevos.
Python113pass0skips6,94s; .NET final16pass0skips946ms; Fast32127exit0,
Release17,10s0avisos/errores. Dos nuevosTestCase193 compilados/pasados despuésFast.
193 nativo Qwen3.5: «Estoy listo para ayudarte con lo que necesites.»0,547s;
«¿Podrías repetir lo que dijiste?»0,344s. Política C# acepta ambas. GPU3171,56MiB.
No publicación UI/audio acreditada por193. PRUEBAS_FEEDBACK191_193.md e
TRAMO191_193_PINS.json + astra-source192-snapshot fijan fuente/tests/logs.
182_190pins íntegros. Todos procesos recogidos/terminados, ninguno propio activo.
Siguiente: comprobar App/cola con fuente192; continuar audio183 sin reinterpretar
191 como arreglo. No repetir187 para la lectura inglesa ni scripts de fuente172.
Este turno fue progreso: corrección192 + evidencia191/193. Goal íntegro activo.

# Actualización191–192 — fuente nueva; Fast en curso

191 sesión51364 recogida exit0: Nemotron recupera «It is ten fifty six» en
loopback187 crudo y normalizado. No imputar omisión de Parakeet a un corte.
Fuente192: retira dos TTS fijos de VoiceEngine; App convierte wake/ASR dudoso
en hechos para la cola de composición existente. Sin bloquear UI; avisos
caducan al llegar un turno nuevo y acuse wake al terminar escucha.
Llm proyecta ambas causas observadas; no operación inferida. AEC sigue Speex.
Rojo192:2fallos. Python113pass0skips6,94s; .NET14pass0skips808ms (sesión5176).
Se corrigieron import pytest y una referencia del renombrado en reintentos.
Fast192 iniciado, log TEMP/c03-feedback192-fast.log; recoger antes de modelo.
Pendiente contraste con LLM real de los dos hechos; no aceptación UI/voz.
No ejecutar scripts antiguos que exigen hashes172. C03 íntegro sigue activo.

# CHECKPOINT C03 —190 — EN_CURSO —2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, continúa01a074f6-9e0e-7fb3-8282-a6b706198a7e.
Goal íntegro activo, Goal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
Sin commit/push/main/subagentes. Preservar WIP y evidencia privada/pública.

## Producto y evidencia

Fuente172 vigente: contador de barge consecutivo/una emisión;130pass0skips7,36s
y Fast/Release verdes.164 precarga SciPy antes de JSONL corrigió bloqueo nativo.
UI166 tres horas veraces ~1s,3499,5MiBVRAM; no audio aceptado ni Full actual.
Qwen3.5/Piper/Speex/DTLN siguen candidatos; manifiesto registrado13b971b3… intacto.

182 adaptación DTLN128/512 continua: seis paridades PCM y guard alineado384samples.
183 una interrupción de4;184 confirma primera horaES cortada.185 cero eventos,
snapshot post-barge ausente;186 recupera cada contenido en alguna lectura.
187 cero eventos, captura exacta1249bloques/39,968s y cuatro originales Piper.
188 reproduce PCM128 Y VAD1249/1249 idénticos;128/512 ceroVAD en ese eco.
512 p99 19,38ms/max32,42ms por32ms;128 p99 2,69ms. No coste combinado final.
189 inglés sólo «It is ten» pese a no evento.190 lo mismo en ORIGINAL Piper;
no atribuir esa omisión de ASR a corte/AEC. No demuestra pérdida de Piper.
ASR/ganancia tienen variantes; correlación fuente/loopback0,48–0,70 no certifica
onda íntegra. PRUEBAS_DTLN182_184.md y PRUEBAS_VOZ185_190.md conservan todas lecturas.
DTLN mezcla129/179–181 aún discrepante; AEC3 default/ganancia0,1 ya descartados
por pérdida de palabras. No repetir ganancias/desplazamientos/modelos sin causa.

## Procesos y ficheros

Todos recogidos exit0:18342628/27245,18491987,18596589/13341,18630401,
18752688/89539,18821835,1892240;190 comando terminóexit0 directamente.
Capturas183/185/187: cerooverflows, hilosparados y restauración exacta0/mutedtrue.
TRAMO182_190_PINS.json fija informes/scripts/inputs;177_181 verificado intacto.
No editar ficheros fijados. CHECKPOINT/HANDOFF_HISTORICO_HASTA184 conserva anteriores.
Privado: LOCALAPPDATA/BAXY/C03-sidecar187-private/{generated187.json,npz;
tap187.json,npz;microphone.wav;loopback.wav;tts-state.jsonl}. Índice público187.
Originales22050Hz, cuatro textos del PREREG187; no regenerar para comparación.
Observaciones189: astra-observe189/{PREREG,RESULTS}. Comparación190:
astra-compare190/{PREREG,RESULTS}; se ajustó ganancia/retardo global solamente.
Python: C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
DTLN128/512 y LiteRT aislados D:/BAXYRuntime/experiments/voice/dtln179 y dtln180.

## Siguiente acción y alcance

Observador independiente ya instalado(Nemotron) sobre originales187 y sus mismas
ventanas189, para separar pronunciación de fallo de Parakeet; no nueva captura.
Usar helper previo181/.66s flush, raw+normalizado sin texto esperado. Conservar
fallos183 y mezcla129; no promoverDTLN por dos negativos físicos sin eventos.
Herencia humana hallada sólo por título/reporte: baseline_real_voice.txt y
REPORTE_NOCHE_STT_PARAKEET_2026_05_23.md en biblioteca/gemma4-agent/documentacion/
03_voz_stt/research. Declaran84RED/180terceros y remiten stt_real_voice_eval.py;
audios NO localizados ni procedencia verificada. No contar como reserva100.

Pendientes íntegros: audio/entrada humana/wake aprobado, ocho rutas finales,
100humanos frescos congelados y100/100(742pool/239revisados;100NOcongelados),
averías/recuperación,UI/runtime/4GB,promoción/regresión/instalación/continuidadC04–C09,
Full entero y publicación fuera main. Tres ingleses ya admitidos por dueño,
no repetir pregunta. C03_ASTRA_AUTORIDAD.md y C03_RESPUESTA_VERAZ.md mandan.
Este turno: progreso por183–190 evidencia nueva; no cierre ni bloqueo externo.
