# C03 — contraste neuronal DTLN-AEC —179–181

DTLN elimina los dos ecos del panel y conserva la frase cercana sola ante
Parakeet. La mezcla todavía presenta discrepancias/pérdidas entre observadores;
no se acredita fidelidad completa ni se adopta/promueve un motor nuevo.
No se cambiaron código de producto, umbrales, voz, LLM ni runtime registrado.

## Herencia y alternativa

Speex173 conserva2/4 cortes físicos. WebRTC174/178 elimina eco offline pero pierde
palabras cercanas: PRUEBAS_AEC173_175.md,PRUEBAS_AEC176.md,PRUEBAS_AEC177_178.md.
Inventario histórico buscado por DTLN/eco/AEC sin título específico nuevo;
PRUEBAS_ECO126_128.md ya descartó prolongar ventana/cambiar umbral de correlación.

[DTLN-AEC del autor](https://github.com/breizhn/DTLN-aec/tree/9d24e128b4f409db18227b8babb343016625921f),
revisión9d24e128b4f409db18227b8babb343016625921f, consultada2026-09-07. Código MIT,
licencia copiada. Se descarga primero128 (1,8M parámetros;7.273.612bytes); al
fallar mezcla a coste bajo,512 (10,4M;41.521.804bytes), el modelo presentado por
el autor al AEC Challenge. No se descarga256. Git blobs verificados y SHA256
de cada archivo/modelo en DOWNLOADS. No datos privados enviados fuera.

LiteRT2.2.0, wheel CPython312 Windows x6417.914.562bytes, SHA
86815ff3378ac9fa4bb5548bcede1be7d050bd59a8ebaf1c056b7aef69fedcee.
Extraída sólo en D:/BAXYRuntime/experiments/voice/dtln179/python, reutilizada180.
Interpreter CPU1/XNNPACK carga y asigna tensores; sin instalar TensorFlow ni
dependencias de2020 del autor. Runtime registrado no alterado.

## Método

Se ejecuta process_file extraído por AST del run_aec.py del autor, sin cambiar
su cálculo. Sólo sf.read/write son I/O en memoria; no se ejecuta su recorrido
de directorios, importTensorFlow ni cambio global de CUDA. Dos estados nuevos
por control, FFT/máscara/IFFT/overlap-add originales,512ventana/128salto.
Su padding/corte final se conserva; NO se ha demostrado equivalencia de un
adaptador en vivo512→128 ni latencia/finalización física.

Mismos cinco controles174, señales float32 por SHA en INPUTS, mismo detector
y criterios VAD0,5/energía0,004/floor1,8/consecutivos. Sin guard crudo: candidatos
máximos, no cancelación de producto. Guard no puede crear candidato si hay cero.
Los controles127/129 tienen alineación aproximada;149 son arrays ADC nativos.

Parakeet registradoCPU6/beam8,sin hints, mismo recorte131, PCM16 crudo y normalizado
a pico0,8.181 Nemotron3.5 ya instaladoCPU6/greedy/auto,mismo recorte,0,66s de
silencio final,crudo/normalizado. ASR es observación, no oyente humano infalible.

## Resultados179/180

| Modelo | Caso | Bloques habla | Candidatos | Mayor secuencia | ms por8ms | Parakeet crudo | Normalizado |
|---|---|---:|---:|---:|---:|---|---|
| 128 | native_echo149 | 0 | 0 | 0 | 0.290 | no ejecutado | no ejecutado |
| 128 | physical_echo | 0 | 0 | 0 | 0.252 | no ejecutado | no ejecutado |
| 128 | near_only | 86 | 44 | 8 | 0.286 | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? |
| 128 | physical_echo_plus_synthetic_near | 90 | 45 | 9 | 0.313 | Hola. ¿En qué te puedo hoy? | ¿En qué te puedo ayudar hoy? |
| 128 | cold_silence | 0 | 0 | 0 | 0.322 | no ejecutado | no ejecutado |
| 512 | native_echo149 | 0 | 0 | 0 | 2.806 | no ejecutado | no ejecutado |
| 512 | physical_echo | 0 | 0 | 0 | 2.881 | no ejecutado | no ejecutado |
| 512 | near_only | 86 | 44 | 8 | 2.760 | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? |
| 512 | physical_echo_plus_synthetic_near | 90 | 45 | 9 | 2.610 | Hola, aquí Patsy. ¿En qué te puedar hoy? | Hola, aquí Batsy. ¿En qué te puedar hoy? |
| 512 | cold_silence | 0 | 0 | 0 | 2.476 | no ejecutado | no ejecutado |

179 sesión51502 exit0;180 sesión29193 exit0. El coste medio no certifica p99
ni tiempo real con LLM/audio/UI. RSSdelta primer caso~15MB128 y~85MB512 incluye
buffers; no es consumo final combinado. No nueva medición VRAM de producto.

## Observador181

| Modelo | Caso | Normalizado | Nemotron |
|---|---|---|---|
| 128 | near_only | False | ¿En qué te pue |
| 128 | near_only | True | ¿En qué te puedo ayudar hoy? |
| 128 | physical_echo_plus_synthetic_near | False | PAXY.  ¿en qué se puedo ayudar hoy |
| 128 | physical_echo_plus_synthetic_near | True | Ola, a kibapsi, ¿en qué te puedo ayudar hoy |
| 512 | near_only | False | Vaxir.  ¿En qué te pue |
| 512 | near_only | True | ¿En qué te puedo ayudar hoy? |
| 512 | physical_echo_plus_synthetic_near | False | ¿En qué te pue |
| 512 | physical_echo_plus_synthetic_near | True | Ola! ATBAC, ¿en qué te puedo ayudar hoy? |

181 sesión71768 exit0. Nemotron crudo también pierde palabras del control cercano
solo que Parakeet recupera completo. Por ello no atribuir cada desacuerdo al AEC.
La normalización mejora observación, pero no sustituye éxito crudo del producto.
Se conserva que Parakeet de mezcla128 omite palabras y512 produce «puedar»;
no declarar esas lecturas frases fieles ni convertirlas en textos esperados.

## Decisión y siguiente acción

No nueva ganancia AEC3 ni colección de modelos. DTLN constituye un candidato
de desarrollo por rechazo de eco/coste, no sustitución aceptada. Antes de otra
prueba física, preparar un adaptador experimental continuo del cálculo del autor
y verificar paridad/latencia con179/180:128divide512 sin introducir padding por
llamada. Conservar el fallo de mezcla y contrastar el ciclo real de interrupción
(la voz propia se cancela al detectar habla, no sigue sonando todo el clip).
Ese contraste no borra el control de doble habla sostenida ni acredita humano.
No cambiar producción hasta tener mejora semántica y garantías conservadas.

C03 EN_CURSO: fuente172 vigente,130tests/Fast verdes;173 físico2/4 cortes.
Reserva100 sin congelar/ejecutar, ocho rutas finales, voz/ingreso/UI,averías,
promoción/regresión/continuidadC04–C09,Full y publicación siguen pendientes.
Sin procesos propios activos ni modificaciones de volumen durante174–181.
