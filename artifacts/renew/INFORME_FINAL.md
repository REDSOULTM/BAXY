# BAXY Renew: informe final (2026-10-17)

Producto final: commit `845d652ad` (rama `baxy-renew`, en hub). Qwen3.5-4B-Q4_K_M local, ≤4 GB de VRAM y de RAM.

## Qué hace

- Entiende órdenes habladas o escritas en español (y spanglish) y elige entre 172 herramientas tipadas: abrir y
  cerrar apps y ventanas, archivos y carpetas conocidas, navegador y pestañas, música (Spotify, YouTube), juegos
  (Steam, Epic), correo y calendario de Outlook, notas, tareas, alarmas, memoria, ajustes del PC, red, Bluetooth,
  búsquedas web, clima y más.
- El kernel pide el sí de la persona en lo arriesgado; cada efecto se verifica antes de decirlo hecho; el journal
  evita repetir una acción ya hecha.
- El latido mira el momento sin que nadie hable y casi siempre calla cuando debe.

## Qué no hace (límites honestos, medidos)

- Falla todavía en una parte de las tareas de varios pasos y de manejo de pantalla (e2e de práctica 19,67 de 30).
- A veces el modelo dice algo que no hizo o no leyó: el holdout v3 dio 7 falsedades confirmadas en 30 conversaciones.
  Están en el texto del modelo y la regla 1 prohíbe tapar eso con código.
- El instinto del latido actúa, propone o habla menos de lo que debería (70,8 % en el holdout; los silencios sí).
- La primera respuesta hablada tarda unos 4 s de mediana (meta 2,5 s).
- Con el prefijo de herramientas en 41-42k de los 49.152 tokens, el historial guarda unos 3 turnos; lo recortado se
  le dice al modelo.
- No hay instalador completo (aplazado por el dueño).

## Cifras

Holdout v3 (una vez, sobre `ff863b47f`, sellado):

| Meta | Resultado | Estado |
|---|---|---|
| Holdout ≥85 % | 83,0 % combinado (decisión 91,25 %, e2e 55 %, latido 8/12) | límite honesto |
| Falsedades 0 | 7 confirmadas a mano | límite honesto |
| Instinto ≥80 % | 70,8 %; 0 de riesgo solo; molestas 0,67 por 20 | límite honesto |
| Decisión p50 ≤1 s | 0,734 s | cumplida |
| Texto a voz p50 ≤2,5 s | 4149 ms a la respuesta | límite honesto |
| ≤4 GB VRAM y RAM | VRAM 3905-3938 MiB; RAM del producto ≤2,8 GB | cumplida |
| Ronda de auditoría limpia | 27 rondas 4+4 (19-45), ninguna limpia; todas sus A arregladas y probadas | límite honesto (decisión del dueño) |

Producto final `845d652ad`, bancos de desarrollo (no holdout), frente a la base de la decisión 20:

| Banco | Final | Base | Ruido |
|---|---|---|---|
| Decisión (268) | 229,67 | 231,67 | ±3: dentro |
| Escenas (39) | 30,5 | 32,5 | ±2: en el borde |
| E2E de práctica (30) | 19,67 | 19,33 | ±1: dentro |

Suites: Kernel 567, Contracts 69, Setup 477, Providers 2189.

## Lo pendiente

- 118 tareas B en `artifacts/renew/metas.json`, cada una con fecha, archivo:línea y escenario.
- El holdout no se volvió a correr tras los arreglos (decisión del dueño): las cifras del holdout son de `ff863b47f`.
- Aplazados por el dueño: instalador, interfaz, ajuste fino y modo conversación.
