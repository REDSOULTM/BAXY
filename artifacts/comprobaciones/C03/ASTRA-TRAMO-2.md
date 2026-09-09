# C03 — hechos, contexto y límite del modelo, 2026-09-06

EN_CURSO. Base `2bf3d4c`, rama `Goal-c03`. No aceptación fresca ni promoción.

## Reparación y contraste

La prueba nueva reprodujo 7 fallos / 15 pass antes de editar Python: la
equivalencia de reloj admitía AM/PM incorrecto y un reloj contradictorio añadido;
el seguimiento conservaba router en el prompt pero su contrato léxico lo vetaba;
«Explain encryption» se leía como español al faltar el verbo en el owner de idioma.

Ahora el reloj se compara con utc + desplazamiento reales conservando la mitad
del día; el tema resuelto del seguimiento participa en la exención léxica, sin
eximir planner/tool ajenos; explain y explica son evidencia lingüística en el
owner existente. No hay plantillas de respuesta nuevas. C# conserva los contratos
equivalentes y permite el vocabulario del usuario anterior sin cambiar la intención.

MindPlanSession entrega a MissionNarration el fallo del paso serializado en
reason. Python lo descartaba por comenzar con JSON. La misma proyección de hechos
ahora conserva causa, polaridad y número de paso como datos para el generador;
JSON malformado no se publica ni se transforma en éxito. La recursión se acota.

Validación: 215 pass de test_c03_request_preservation, test_request_reading y
test_goal06_voice; 21 pass C# de C03FactPreservation/RequestReadingConformance;
75 pass previos de coordinación/progreso. 17 pass / 1 skip ambiental de los
evaluadores STT y V8. No se afirma aceptación nueva de voz con esos tests.

`scripts/test_source_quality.ps1` termina `source_quality_gate_passed: mode=Fast`,
build Release con 0 errores y 0 advertencias. Log `scratchpad/c03-source-quality-tramo2.log`.
Full final pendiente. La huella V8 actualizada conserva el corpus y veredicto
históricos: los programas actuales ya cambiaron en C03. Árbol de programas STT
esperado: `e1ade3c832bad97b37adbc19e76c2a1dc6a304920f1f41d7e18c55681dfa8784`.
llm.py: `e275ccd261ddd362552a735cb300921c943c281e45557d4ba2185ab2b9cf99c2`.

## Herencia de modelo: resultado negativo

El Ministral 3 3B Q4_K_M histórico existe y coincide con SHA256
`9ed150d4367e68df0ac8e1540f6ddc65b42d0ee26378329d1ecbca60f93fc5f8`.
La evaluación de julio lo había descartado por latencia/VRAM antes de evaluar
semántica. El nuevo techo de 4 GB permitió esta comparación acotada de contenido.
Se usó temperature 0.05 y top_p 0.95, coherente con la recomendación de
[Mistral](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF#recommended-settings).

`astra-native-ministral` y `astra-native-ministral-q8`: 12 preguntas de desarrollo,
dos brazos (compositor existente y prompt directo), sin cambiar el registro.
El primer diagnóstico se reanudó sólo para las dos llamadas pendientes tras un
fallo de codificación de stdout; los resultados previos están conservados y el
reinicio está documentado. No es una prueba de recuperación de producto.

Resultado: no promover. Con q4, doce por ocho recibe 124/24; con q8, 24/80;
diecisiete más veintiséis empeora de 43 a 173 con q8. Persiste gramática deficiente,
spanglish no respetado e imprecisiones sobre routers y privacidad de proxies.
Ni el prompt directo ni q8 son una reparación general. Picos atribuidos al proceso
de diagnóstico: q4 2593.56 MiB y q8 2905.56 MiB; no certifican toda la app y voz.

La comparación integrada Granite `astra-facts` terminó: 11/16 útiles/fieles,
16 publicados. Su ADJUDICACION.md conserva cada veredicto, nunca aceptación fresca.
La evidencia de los otros diagnósticos astra-native-* sigue siendo desarrollo.

## Continuación: instrucciones y autoridad de la pregunta

Se retiró el recorte greeting_clip que publicaba «Hola,.» al recibir un saludo
natural con pregunta social. El prompt común permite conocimiento general en
conversación y conserva la obligación de hechos verificados para PC/acciones.
Se retiraron frases prescritas y el inicio exacto del resumen de misión; se
conservan las comprobaciones de pasos, acciones, polaridad y hechos. SYSTEM_PROMPT
no cambió. Spanglish pide mezcla explícita sin duplicar traducciones.

Dueños de esta modificación: 363 pass y 101 subtests; los tres casos nuevos de
saludo/resumen fallaban antes. `astra-prose` publicó 15/16, con 9/16 útiles/fieles:
la reparación del prompt no demuestra una mejora global. Su t14 «¿y para qué
sirve?» propuso wifi.connect; una misión pendiente contaminó t15/t16.

La causa estaba en el veto existente de efectos sobre preguntas: omitía los
seguimientos elípticos, why y cuánto. Se reutiliza el lector de elipsis; lecturas
y acciones pedidas conservan su tratamiento. Cinco regresiones fallan antes y
pasan después; suite de política completa 834 pass. `astra-question-authority`
recorre router → utilidad → 12×8 → Lima: 4 publicados, 3 plenamente correctos,
una falta gramatical. Todos sus estados posteriores están disponibles, sin misión
ni composición pendiente/error; el turno matemático recuperó un rechazo léxico
interno y publicó 96. No sustituye R07 ni la aceptación nueva.

Qwen3-8B heredado con carga parcial fue medido antes del prompt común nuevo:
10/12 útiles en compositor; ver `astra-native-qwen8-q8/LECTURA.md`. No promovido.
Los 12 diagnósticos también revelan una instrucción pendiente de corregir:
«What is fourteen times six?» recibe «Explain the concept», y un borrador acaba
definiendo la multiplicación sin dar 84. Corregir esa sustitución de la pregunta
no requiere crear un calculador ni otro veto de prosa.

Full segundo interrumpido: sesión 62287, `scratchpad/c03-full-tramo2.log`;
estática/build y .NET sin fallos; Python cancelado durante el 73 %. No es verde.
Las siguientes huellas corresponden al candidato de ese Full, previo al tramo 3:
`1b6d453937435dff769884c1545a1d6b4b79b93b91bb219d042511cf571f1d68`,
__main__.py `f71b2c934088618ff2cb98b14b09b561fbbf0400b809c1c7ac7e5b66b2f38fba`,
árbol STT `524b2d5bd39229529942ae34354d6fe275b9d6d7d06fa18929f4f13383be5d10`.
Los pins actuales no cambian el corpus/veredicto histórico ni certifican voz nueva.
