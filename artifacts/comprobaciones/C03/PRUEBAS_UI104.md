# UI104 — progreso visible y ocho finales, 2026-09-07

Fuente103 frente a UI102/fuente101. Mismos ocho casos y fixtures, orden y modelo
local, fijados antes en [PREREG](astra-ui104/PREREG.json). Se observaron ocho
finales técnicos útiles/fieles y avisos de progreso en español e inglés antes de
sus finales. No reserva humana ni aceptación acústica.

## Progreso observado

En el caso2, sin borrar la petición del input, aparece «Estoy revisando tu
solicitud para ver qué necesitas.» a09:19:45.237UTC y sigue a09:19:46.435UTC.
[Captura](astra-ui104/02-missing-progress-1.jpg). El primer cuadro, a09:19:44.458,
todavía no lo muestra: aparición observada en menos de0,8s desde ese cuadro,
sin atribuir ese intervalo exactamente al clic. El aviso se retira al cambiar
de fase; el final llega a06:19:51local sin arrastrarlo.

Caso5: «I'm currently reviewing your request to understand the details before
proceeding.» visible a09:21:58.552 y09:22:00.383UTC.
[Revisión](astra-ui104/05-invalid-progress-1.jpg).
A09:22:06.264UTC se lee completo, en dos líneas: «I'm currently organizing the
steps needed to address your request. The results aren't ready yet.»
[Preparación](astra-ui104/05-invalid-progress-4.jpg).
Ambos describen la fase actual, sin anticipar lecturas ni resultados.
El final de error a06:22:10local retira el aviso y conserva la causa.

Antes: cinco cuadros del mismo caso en UI102 contenían sólo Thinking y draft.
Después: el lector React existente presenta la etiqueta recibida encima del
input, con salto de línea y sin ocultarla tras draft. El área vacía no ocupa
altura de texto en reposo. `role=status` conserva un nodo anterior al cambio de
contenido; no se hizo una prueba física de Narrator/NVDA.

## Entradas y respuestas literales

| Entrada | Respuesta visible | Captura |
|---|---|---|
| Dime la hora. | Son las 06:19. | [01](astra-ui104/01-clock-visible.jpg) |
| Lee el archivo "c03-ui100-ausente.txt" del sandbox. | No se encontró el archivo "c03-ui100-ausente.txt" en el sandbox. | [02](astra-ui104/02-missing-visible.jpg) |
| Why couldn't you read that file? | I couldn't read the file because it wasn't found in the sandbox. | [03](astra-ui104/03-why-missing-visible.jpg) |
| Lee el contenido del archivo "c03-ui100-lectura.txt" del sandbox. | He leído el archivo "c03-ui100-lectura.txt" y su contenido es: "Lectura técnica C03: el color de control es turquesa." | [04](astra-ui104/04-valid-visible.jpg) |
| Read the file "c03-ui100-invalid-utf8.txt" in the sandbox. | The file read failed because the content is invalid UTF-8. | [05](astra-ui104/05-invalid-visible.jpg) |
| Why couldn't you read that file? | I couldn't read the file because its content is invalid UTF-8. | [06](astra-ui104/06-why-invalid-visible.jpg) |
| Dime la hora, el audio y el uso de CPU. | La hora es 06:23. El volumen está en 0 y el audio está silenciado. El uso de CPU es del 27,78%. | [07](astra-ui104/07-composite-visible.jpg) |
| Pon el volumen. | ¿A qué nivel quieres que ponga el volumen? | [08](astra-ui104/08-clarification-visible.jpg) |

Bienvenida: «¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?» ([00](astra-ui104/00-ready.jpg)).
Los porqués conservan la causa de la lectura inmediatamente anterior. La fixture
válida coincide literalmente. El resumen compuesto conserva el orden y las tres
lecturas verificadas: reloj06:23, volumen0/muted=true, CPU27,77777777777778%,
redondeado a27,78%. La aclaración no inventa un nivel ni un cambio de audio.

## Validación y recursos

`pnpm build` exit0, TypeScript/Vite;97pruebas dueñas de shell, progreso y entrada
pass/0skips,12s. Fast73364exit0, Release18,95s,0avisos/errores. Detalle de comandos,
sello y dos fallos de entorno/formato corregidos en ASTRA-TRAMO-103.md.

`py main.py`, launcher72826exit0, App35420, Sky11538408; Qwen3.5 override,
wake0. CoreSHA256176FE1BF667F1A80B5792603A73E417429D88824F40869693FAA86C513BBC6DE.
[Monitor](astra-ui104/RESOURCES.json)21463exit0:388,12s,
GPU3519,48046875MiB, RAM5946,796875MiB, atribución disponible. Incluye App y
descendientes desde el inicio del monitor; excluye build y arranque anterior.
Registro de runtime conservado; no promoción. Audio silenciado a0: no aceptación
de altavoz. Tras guardar la última captura se detuvo el monitor y se terminó
sólo el árbol App35420 con ruta verificada; no prueba de cierre grácil.

Auditorías [composición](astra-ui104/compose-audit.jsonl),
[raw](astra-ui104/raw-replies.jsonl) y [shell](astra-ui104/shell-trace.jsonl).
Cada imagen tiene metadatos JSON contiguos. No se cambió código durante la
corrida, no hubo otro modelo/build simultáneo, no Full ni cierre de C03.
