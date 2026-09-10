# Peticiones de estado: tema, orden y evidencia

BAXY conservaba el nombre del recurso, pero podía perder la petición que lo acompañaba. «Respecto a CPU, comprueba qué modelo tengo» tropezaba con la preposición española `a`, la cabecera `comprueba` y la separación del tópico. «About my RAM, tell me how much memory is free» además se confundía con una explicación de cómo hacer algo. Estos son defectos de interpretación del producto, independientes del modelo que proponga la lectura.

La reparación comparte una lectura acotada del tópico entre los validadores existentes. Conserva el texto y el orden para la evidencia, reutiliza los alcances del catálogo y unifica las cabeceras de observación. La excepción de cantidades actuales mantiene los límites de conocimiento, pasado, otro dispositivo, citas, negación y ausencia de herramientas. No añade operaciones, respuestas fijas ni excepciones para un modelo.

La prueba de orden encontró un segundo defecto: «Comprueba qué modelo está instalado en mi GPU» seleccionaba `system.status`, pero su evidencia se recortaba a «gpu.», perdiendo identidad frente a uso. La lectura ahora conserva la petición completa para su extractor de alcance.

Comparación reproducible con el commit `65282f2cdd6824bbe9095ab4ed54950a4938013b`, sobre los mismos 70 controles de desarrollo de747:

| Comprobación | Fuente anterior | Fuente corregida |
|---|---:|---:|
| Dominio correcto | 23/70 | 70/70 |
| Selección o abstención correcta | 20/70 | 70/70 |
| Argumentos conservados desde petición y evidencia | No medido en esta comparación | 50/50 positivos |

Son llamadas puras, sin inferencia ni efectos. Los controles sintéticos no son reserva humana ni acreditan cobertura de la encuesta. Las entradas, resultados y huellas están en `RESULT.json`; el ejecutable es `scratchpad/c03-fronted-status750.py`.

Se añadieron86 pruebas de variantes ES/EN/mezcla, tópico, orden, cortesía, cantidades, alcances compuestos, evidencia y límites. La primera corrida conjunta dio2669pass/1fail por la pérdida de identidad GPU; se conserva en `owners-initial.log`. Tras reparar su causa, las dueñas dieron **2687pass/0fail/1skip ambiental en61,99s**. El skip corresponde a entradas privadas ausentes de una campaña STT y no se cuenta como pass. La ejecución aislada del fallo reparado dio1pass/85deselected antes de repetir todas las dueñas.

`scripts/test_source_quality.ps1 -Mode Fast` terminó con exit0: estática y compilación Release verdes,24,90s de build,0advertencias/0errores. Comandos exactos y huellas en `VALIDATION.json`. No se repite Full por este cambio sólo Python según el objetivo vigente; Full7 valida la base748 y el Full del candidato final sigue siendo requisito de cierre.

Las declaraciones STT actuales pasan al árbol407 `e6416b4290298d023c4cb600fd3e748393295de8c1cb1588c7f71c859df97f37`; los sellos históricos permanecen intactos. La fuente se adopta en el commit que contiene `ADOPTION.json`.

C03 continúa activo: encuesta26cubiertos/716abiertos/0NA, sin nueva cobertura por estas pruebas. No se ha cambiado ni promovido modelo, medido RAM/VRAM conjunta ni acreditado UI/voz. Siguiente bloqueo: interpretación y argumentos del inventario global de ventanas, con prosa que respete paginación y totales desconocidos.
