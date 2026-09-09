# C03 — normalización nativa215–217 — causa numérica demostrada

La observación215 reproduce los cuatro resultados214 sin modificar el resultado:
tres vacíos y un control positivo. Se observa una copia aislada de la extensión;
no se instala ni modifica el runtime de BAXY. Fuente207 y baxy.1 siguen vigentes.

## Primera transformación anómala

Los tensores de características que salen de GetFrames, antes del encoder,
contienen los siguientes valores. No hay NaN/Inf en características, encoder ni
joiner. El decodificador elige exclusivamente blank en los tres fallos.

| Ventana214 | Máximo características215 | Desviación215 | Máximo con arreglo216 | Desviación216 |
|---|---:|---:|---:|---:|
| h0 RAW+Speex | 24348,164 | 77,864 | 27,610 | 1,000 |
| h1 voz sola+Speex | 2391,720 | 6,257 | 33,740 | 1,000 |
| h1 RAW+Speex | 24335,289 | 87,581 | 24,537 | 1,000 |
| h1 voz sola sin filtro | 15,086 | 1,000 | 14,966 | 1,000 |

NemoNormalizePerFeature en sherpa1.13.4 calcula varianza en float32 mediante
E[x²]−E[x]² y recorta negativos a cero. Para columnas casi constantes, la resta
pierde precisión. El inverso de sqrt(var)+1e−5 amplifica desviaciones pequeñas.
El tensor anómalo precede al encoder; no lo introduce el corrector de BAXY ni
la selección del decodificador. El audio humano sigue presente en la entrada.

La PR oficial3857, ya fusionada, corrige exactamente esa función calculando la
media de (x−media)². Conserva la semántica de varianza poblacional y epsilon.
Se aplica su parche original math.cc/math-test.cc sobre la misma compilación
observada215. No se ajusta ganancia, modelo, duración ni umbral para obtener texto.

Procedencia fijada: head a0ba8800cf8580782a9cc9566659ff61f729d76d;
merge0967a08db705d8eec9cf5cef962c8ec57c16e4a8,2026-08-11T03:15:33Z.
Metadata y parche originales guardados en astra-normalize216.

Un ejecutable nativo pequeño llama a la misma función con los dos casos de la PR:
columna casi constante y columna constante. Antes, máximo7510,853; después31,458.
La columna constante da0 en ambos. Los dos controles después del arreglo cumplen
sus límites matemáticos. Se compiló/ejecutó este ejecutable; NO se afirma haber
ejecutado toda la suite GTest math-test.cc (tests CMake siguen desactivados).

## Resultado acústico/ASR: mejora y límites

216 devuelve texto en las tres ventanas antes vacías, y conserva literalmente el
control positivo. No equivale a tres transcripciones perfectas:

- h0 RAW+Speex añade «Hola, aquí Basi.» antes de la frase humana, conserva «del
  clima» y «pueda» frente a «de clima» y «puede». Sigue pasando eco al ASR.
- h1 voz sola+Speex devuelve «…que no todos pudier al funeral…»: pierde palabras.
- h1 RAW+Speex recupera «…que no todos pudieron acceder al funeral en la Plaza
  de San Pedro.».

217 ejecuta los47 controles203/205 y las16 ventanas213, todos con greedy y beam:
126 lecturas, no126 pases semánticos. Comprueba selección efectiva en todas,
dos rechazos de configuración/contexto y un batch mixto. Todos esos controles de
contrato pasan. Hay13 cambios greedy entre63 entradas y16 cambios beam entre las47
que tenían baseline beam. Para las16 recientes no había baseline beam213.

Cambios relevantes que impiden declarar regresión de calidad verde:

- Índice3/case3segment0: greedy pasa de la frase humana a «Hola, aquí Baxi.».
  Ese caso es mezcla sin AEC198/201, pero se conserva como regresión observada.
- Índice11/case8segment0 pierde «acceder», además de un error previo.
- Índice56/h2near_speex cambia «25 to 30 years» por «25 to 3 years», con ambos
  decodificadores nuevos. Es una regresión numérica del contenido reconocido.
- Índice50/h0RAW+Speex recupera humano con eco inicial en greedy; beam conserva
  la frase sin ese prefijo. No se selecciona decoder por conocer el texto deseado.
- Índices52–54 recuperan texto antes vacío o palabras perdidas en españoles.
- El silencio puro sigue vacío en greedy. Beam cambia «Thank you.» por «Gracias.»;
  sigue siendo una alucinación y no justifica volver a beam como ruta principal.
- Beam aún pierde «the slow communication channels» en case15segment0. No se
  puede retirar la selección greedy207 afirmando que3857 arregla todo beam.

Todos los literales antes/después están en COMPARACION_LITERAL217.md y RESULTS.json.
No se relaja ningún criterio de C03 ni se da por aceptada una lectura por no estar vacía.

## Decisión y continuidad

La corrección matemática3857 tiene causa y efecto demostrados, y debe formar parte
de la próxima candidata reproducible. Todavía no está instalada ni aceptada como
solución completa de ASR. Integrarla exige compilar sin observación215, empaquetar
una versión local nueva (baxy.2), conservar licencias/procedencia y actualizar
receta/patch/lock/pruebas. No instalar el bundle216 de observación.

Conservar la regresión217 como evidencia abierta; la candidata integrada no podrá
llamarse voz resuelta mientras siga pasando eco o alterando el contenido humano.
Después de la integración y controles correspondientes, retomar RAW/Speex como
candidata acústica212 y sus pruebas físicas con el reconocedor numéricamente válido.
No barrer ganancias ni volver a pruebas de eco usando el normalizador defectuoso.

El primer preparador215 falló antes de editar fuente externa por un marcador que
no coincidía con CRLF; se conserva FAILURE.json y script original. El reintento
normalizó sólo el texto en memoria y restauró los bytes originales al terminar.
Builders215(45736)/216(92403) y regresión217(94064) recogidos exit0; runs215/216
terminaron directamente. Fuentes externas restauradas exactamente; instalado207
intacto. No procesos propios activos, no capturas/volumen nuevos, no Fast/Full nuevos.

Sigue pendiente C03 completo: activación/voz, ocho rutas,100humanos frescos aún sin
congelar/ejecutar/adjudicar, averías y recuperación, UI/audio físico final, recursos
conjuntos, runtime e instalación, continuidadC04–C09, Full y publicación fuera main.

## Fuentes primarias

- [PR3857 de sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/pull/3857): función corregida, reproducción y controles oficiales.
- [Normalización de NeMo](https://github.com/NVIDIA-NeMo/Speech/blob/main/nemo/collections/asr/parts/preprocessing/features.py): calcula desviaciones centradas; su denominador incluye corrección de sesgo.216 conserva el denominador original de sherpa, tal como la PR3857; no se mezclan ambas implementaciones.
- Fuente local v1.13.4: csrc/offline-stream.cc recoge características y llama a
  NemoNormalizePerFeature; csrc/math.cc contiene la resta inestable; el observador
  conserva tensores reales y decisiones en la carpeta privada215/216.
