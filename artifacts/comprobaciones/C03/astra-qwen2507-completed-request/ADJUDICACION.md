# Desarrollo: objetivo original en el resumen, 21 turnos

Sesión 79989 terminó con exitCode 0; 44,05 s, GPU 3497,56 MiB, RAM 4853,48 MiB.
Registro intacto; Qwen4B con override de diagnóstico, no promoción. 21/21 finales
publicados, sin agotamientos. **No es 21/21 correcto ni aceptación de C03.**
Se repite el panel cancel-outcome, cambiando t17/t19 a título explícito de la
ventana vacía propia. No son turnos frescos ni una población representativa nueva.

| Turno | Evaluación individual |
|---|---|
| t1 | Correcto: hora observada 11:52, expresada oralmente. |
| t2 | Fiel: 11:52, volumen 100 y muted=false. Repite información sobre audio; naturalidad mejorable. |
| t3 | Correcto, inglés, 11:52. |
| t4 | Fiel, inglés, hora/volumen/mute correctos. «The local clock is» es poco natural. |
| t5 | Hora fiel y mezcla mínima. «amigos» plural innecesario ante una sola persona; naturalidad pendiente. |
| t6 | **Fallo de hechos e idioma**: dice audio desactivado con muted=false, level=100; además responde sólo en español a entrada mixta. |
| t7 | Saludo pertinente; añade dos preguntas donde bastaría una apertura breve. |
| t8 | Explicación básica de cifrado útil, analogía extensa y sólo una palabra inglesa: mezcla/naturalidad pendientes. |
| t9 | Explica recuperación mediante copia correctamente; «backup» aislado no acredita por sí solo spanglish natural. |
| t10 | Analogía sencilla del pegamento, caída explicada; mezcla casi enteramente española y explicación conceptual superficial. |
| t11 | Respeta la negación: no promete abrir Paint. |
| t12 | Correcto: Lima; nombre propio neutral, no exige traducción. |
| t13 | Dos oraciones, inglés; mecanismo básico correcto. «eats sunlight» está señalado como analogía, no como alimentación literal. |
| t14 | Correcto: menor densidad por mayor volumen. «más ligero» se entiende a igual volumen por la explicación previa. |
| t15 | **Fallo de idioma y calidad**: sólo español pese a Reply in Spanglish; definición de archivo circular, contraste con carpeta parcialmente útil. |
| t16 | Correcto: tasks=[] y count=0, responde lista vacía en inglés. |
| t17 | Confirmación del título exacto y opciones correctas. |
| t18 | Cancelación fiel; repetitiva y narra detección interna innecesaria. No se cerró al cancelar. |
| t19 | Repite resolución y solicita nueva confirmación del mismo título. |
| t20 | Cierre fiel, windowClosed=true. Ya no narra resolución/maximización; conserva coletilla «El proceso se completó correctamente». |
| t21 | Correcto: nueva hora observada 11:53, inglés. |

El payload de t20 contiene completedRequest con la petición original, las lecturas
ordenadas y el cierre verificado. El resumen mejora respecto de quoted-title t4,
que contaba «fue resuelta y confirmada como maximizada». Una captura no prueba
causalidad estadística ni naturalidad general. Se conserva el transporte del
objetivo por fidelidad del contrato, sin otra iteración de frases del prompt.

Fixture propia C03TitleFixture PID 8708; ausencia comprobada después del conductor.
No se realizó limpieza externa. Evidencia detallada: paired.json, PREREG.json,
RESULT.json, compose-audit.jsonl y events.jsonl de esta carpeta.

Siguiente bloqueo concreto: composición del audio contradice hechos presentes.
Examinar el contrato de hechos existente y su herencia antes de añadir reglas;
no basta rechazar una frase y sustituirla por prosa fija. Spanglish sigue abierto.
