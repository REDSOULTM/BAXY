# UI102 — fuente101, escritorio real, 2026-09-07

Ocho casos técnicos prerregistrados en `astra-ui102/PREREG.json`, los mismos
de UI100 y en el mismo orden. No reserva humana. Ocho finales observados útiles
y fieles; el progreso redactado sigue sin acreditarse en pantalla.

| Entrada literal | Respuesta visible literal | Captura en astra-ui102 |
|---|---|---|
| Dime la hora. | Son las 05:57. | 01-clock-visible.jpg |
| Lee el archivo "c03-ui100-ausente.txt" del sandbox. | No se encontró el archivo "c03-ui100-ausente.txt" en el sandbox. | 02-missing-visible.jpg |
| Why couldn't you read that file? | I couldn't read that file because it doesn't exist in the sandbox. | 03-why-missing-visible.jpg |
| Lee el contenido del archivo "c03-ui100-lectura.txt" del sandbox. | El archivo "c03-ui100-lectura.txt" contiene: "Lectura técnica C03: el color de control es turquesa." | 04-valid-visible.jpg |
| Read the file "c03-ui100-invalid-utf8.txt" in the sandbox. | The file read failed because the content contained invalid UTF-8 characters. | 05-invalid-visible.jpg |
| Why couldn't you read that file? | The file couldn't be read because it contained invalid UTF-8 characters. | 06-why-invalid-visible.jpg |
| Dime la hora, el audio y el uso de CPU. | La hora es 06:03. El volumen está en 0 y el audio está silenciado. El uso de CPU es del 64,58%. | 07-composite-visible.jpg |
| Pon el volumen. | ¿A qué nivel quieres que ponga el volumen? | 08-clarification-visible.jpg |

La bienvenida fue «¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?» (00-ready).
Las fixtures se verificaron antes de ejecutar. Los dos porqués preservan la
causa de su error anterior. El payload compuesto conserva reloj06:03,
muted=true, level=0 y CPU64,58333333333333; el final redondea correctamente.
Pedir volumen sin nivel produce aclaración, no un cambio inventado.

## Primera transformación incorrecta

Fuente101 compone temprano: request9 understanding en español y request26
preparing_steps en inglés, antes de sus finales. No basta el published del audit
Python para afirmar publicación UI. Cinco capturas consecutivas del caso5
(`05-invalid-progress-0` a `4`, 09:00:30.396–09:00:39.064UTC) muestran Thinking
y la petición aún dentro del input, sin el aviso redactado.

FieldCenter coloca bootStage.label únicamente en placeholder, mientras
handleSubmit mantiene draft hasta que el POST /turn termina. Un input con valor
oculta su placeholder. El bloqueo ahora es presentación, no otro prompt.

## Ejecución y límites

Entrada py main.py; launcher48202exit0; App16164, Sky201388. Qwen3.5 override,
wake0, sin promoción ni audio físico. CoreSHA256
8ffae49a6b074e937571feef652ad8c43ff8168f8ad4949364401b1f6e15223f.
Monitor4385exit0:787,91s, GPU3493,98828125MiB, RAM5737,51953125MiB,
atribución disponible. Arranque y tramo previo al monitor excluidos.
Tras guardar los ocho finales se detuvo el monitor mediante sentinel y se terminó
sólo el árbol App16164 con ruta del ejecutable verificada; no acredita cierre grácil.
No Full, no cien humanos, no cierre C03.
