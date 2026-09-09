# Actualización184 — contenido183 adjudicado;185 preparado

184 sesión91987 recogida exit0,16lecturas Parakeet CPU6beam8 sin pistas.
183 saludo completo en mic crudo;primera horaES truncada;EN completa en ambos
crudos;últimaES completa sólo loopback crudo(mic dice «Son las diez»).
Normalizar no mejora siempre. PREREG184 conserva ventanas y limitación de reloj:
UTC se estima con offset wall/monotonic actual; márgenes1s, no aceptación humana.
185 preparado: misma secuencia, DTLN128, snapshot sólo tras primer barge_in;
sin taps porframe ni cambios de producto/umbrales. Recoger señales exactas antes
de variar algoritmo.182/183/184 todavía pendientes de pins conjuntos.
Turno anterior: progreso por recoger183 y registrar evento/cierre; no cierreC03.

# Actualización183 — ejecución recogida; contenido pendiente

Driver42628 y captura27245 recogidos: ambos exit0. CLEANUP.json:58,312s.
AUDIO_RESULT.json:81,05s, operator_finished, cero overflows en ambos streams,
threadsStopped true y restauración exacta a volumen0/mutedtrue.
messages.jsonl registra un barge_in en88780,953, durante primera hora ES;
cuatro salidas ensayadas.173 registró dos eventos en cuatro salidas. No afirmar
mejora robusta ni contenido íntegro: ASR de183 y fidelidad de mezcla pendientes.
Siguiente: adjudicar audio183 con señales conservadas; no repetir captura.
Usuario pide explicación completa de avance y pendientes; goal sigue activo.

# Actualización182 — adaptador continuo verificado;183 preparado

182 sesión47659exit0: seis comparaciones PCM idénticas a179/180;384muestras de
retardo/alineación verificada, propiedad de hilo/cierre/entrada inválida pasan.
128 p99≤4,11ms por32ms;512 p99≤22,22ms. Sin fuente/runtime cambiados.
183 preparado: mismo fullsidecar173/cuatro salidas, binding experimental DTLN128
y observador sóloestado, sin taps porframe. Comparar falsas interrupciones y
contenido físico. No aceptación de entrada humana ni del fallo de mezcla179.
Turno anterior clasificado progreso: comparaciones174–181 cambiaron estrategia.

# Handoff C03 —181 —2026-09-07 — EN_CURSO

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, continuación01a074f6-9e0e-7fb3-8282-a6b706198a7e.
Goal activo completo; Goal-c03,HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
Sin commit/push/main/subagentes. Conservar WIP y evidencia privada/pública.

## Estado y decisión

Fuente172 vigente (contador barge consecutivo/una emisión);130pass0skips7,36s,
Fast55364exit0,Release2,73s0avisos/errores.173 físico aún2/4cortes.164 precarga
SciPy antes lectorJSONL corrigió bloqueo; UI166 tres horas veraces~1s y3499,5MiB
VRAM, pero audio no aceptado. No nuevo Full ni promoción durante174–181.

AEC3 aislado174: eco149/1270VAD pero mezcla pierde palabras.176 exporta lineal,
finalbitidéntico174; residual pierde más, lineal tampoco conserva todo/dejaeco.
177: near empieza35msantes de sonido de referencia (speaking no era sonido).
178 ganancia0,1 inspirada en fieldtrialupstream no recupera palabras: NO adoptar
ni barrer ganancias. PRUEBAS_AEC173_175.md/176.md/177_178.md y pins.

179 DTLN128 y180 DTLN512, fuente del autor9d24e128b4f409db18227b8babb343016625921f,
LiteRT2.2.0 CPU1/XNNPACK aislado; algoritmo process_file sin cambio, sóloI/O.
Ambos0VAD en2ecos/silencio; Parakeet recupera near-only, mezcla sigue discrepante.
128~0,3ms/8ms;512~2,5–2,9ms/8ms.181Nemotron recupera más normalizado pero también
falla near-only crudo; no observador infalible. PRUEBAS_DTLN179_181.md tiene todos
los textos/criterios. Ninguno promovido ni aceptado como sustitución de Speex.

## Procesos, evidencia y entorno

Todos recogidos: build1769568/eval83450,build17818707fallóincludes/retry84605pass,
eval17855442,17951502,18029193,18171768 terminaron. Ningún proceso propio activo.
TRAMO172_176_PINS.json43públicos40privados verificado; TRAMO177_181_PINS.json nuevo.
No editar informes/scripts fijados. CHECKPOINT/HANDOFF_HISTORICO_HASTA176 conserva
historia y rutas de texto/UI/reserva. Datos no se enviaron fuera; no audiofísico174–181.
Runtime: C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
`py` es313 sinpytest; sólo py main.py para UI. Manifiesto registrado13b971b3… intacto.
DTLN179: D:/BAXYRuntime/experiments/voice/dtln179 (128,LiteRT,run_aec.py/LICENSE).
DTLN180: D:/BAXYRuntime/experiments/voice/dtln180 (512, mismo runtime179).
WebRTC176/178: D:/BAXYRuntime/experiments/voice/webrtc176 y webrtc178.

## Siguiente acción

Abrir run_aec.py179:57–140 y c03-evaluate179.py; adaptar experimentalmente el
streaming512→128 y verificar continuidad/paridad/latencia con señales179/180.
No padding por llamada. Luego contrastar interrupción cerrando salida real,
conservando fallo de mezcla sostenida; no declarar aceptación humana por síntesis.
No repetir UI, modelos o filtros sin una hipótesis distinta y criterio mantenido.

## Cierre restante íntegro

Audio/entrada humana/wake (App permite manifiesto no aprobado), ocho rutas finales,
100humanos frescos congelados y100/100 (742pool/239revisados;100NOcongelados),
averías/recuperación,UI/runtime/4GB, promoción/regresión/continuidadC04–C09,Full
entero y publicación fuera main. Tres ingleses ya confirmados: «Son turnos validos»;
no preguntar de nuevo. C03_ASTRA_AUTORIDAD.md y C03_RESPUESTA_VERAZ.md mandan.
