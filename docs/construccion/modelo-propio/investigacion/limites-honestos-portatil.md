# Límites honestos de BAXY Renew (borrador del notebook para `metas.json`)

Cada límite dice qué falla, cómo se midió y qué se probó sin éxito. Las cifras vienen de `PROGRESO.md` (líder),
`PROGRESO-nb.md` y las corridas de `<evaluacion>\renew_v1\runs` (PC) y `<evaluacion>\renew_v1\runs` (notebook). Al final
va el bloque listo para `metas.json`.

## 1. «Sube el volumen a N» se entiende como «súbelo N»

- **Qué pasa.** Con «sube/baja el volumen a (o hasta) N», el 4B elige `audio.volume.adjust` y calcula la diferencia en
  vez de fijar el nivel N. Casos: e2e práctica E028 («sube a 40» → +40) y decisión P257.
- **Medido.** Un juego propio de 10 frases, que no se copiaron de los bancos:
  - con las descripciones actuales acierta 6/10;
  - con descripciones «TO a level» frente a «BY an amount» acierta 4/10;
  - con una sola herramienta `audio.volume {level|change}` acierta 6/10, pero cambia el error («baja al 15» → change −85).
- **Decisión.** Ninguna presentación mejora, así que el catálogo se queda como está. Es un límite del modelo con este
  arnés.

## 2. Una ruta completa dictada para `file.write` pierde la subcarpeta

- **Qué pasa.**
  - Cuando la persona dicta una ruta completa («guárdalo en C:\Users\…\BAXY-bench como prueba.txt»), el 4B a menudo
    llama `file.write` con `folder: home` y sólo el nombre, sin la subcarpeta.
  - e2e de práctica p5/p6: E006, E017, E020, E024 y E027.
  - Juego propio de rutas: Q1 y Q3.
- **Qué se hizo.**
  - El proveedor acepta la ruta completa tal como la dijo la persona cuando cae dentro de la carpeta nombrada; fuera
    de ella falla antes de cualquier efecto (`0075c505f`, con el arreglo de `Locate` `42a468051`).
  - Cada argumento lleva su significado en la descripción. Con eso el juego de rutas pasó de 3/8 a 6/8 (7/10 con dos
    casos de control).
  - Los recibos de escritura dicen `fullPath` (`cf3acc126`), así que la respuesta dice dónde quedó de verdad aunque no
    sea el sitio pedido. Era la falsedad F013, ya arreglada.
- **Lo que queda.** A veces el archivo queda en la carpeta conocida y no en la subcarpeta pedida. BAXY lo dice con la
  ruta real y no lo afirma como hecho donde se pidió.

## 3. Velocidad por orden en el borde de la meta (≤ 2,5 s del texto al primer sonido)

- **Medido en el producto (PC), primer sonido de cada orden:**
  - p50 2316 ms en la e2e práctica p6 (36 órdenes);
  - en la corrida siguiente, p50 2,54 s, con 18 de 36 órdenes bajo 2,5 s.

  Ese es el orden de la variación entre corridas.
- **De dónde sale el tiempo.**
  - Cada decisión del modelo cuesta unos 0,7 s. El modelo genera 78 tok/s en bruto y 64 con el prefijo de
    herramientas.
  - decision2: p50 0,67 a 0,86 s según la GPU (PC o notebook).
  - Una orden con una herramienta suma dos decisiones (llamar y responder), más la herramienta.
  - Piper empieza a sonar de 138 a 279 ms después de recibir el texto. Antes eran 747 ms: ahora la salida de audio se
    abre al empezar el turno y la respuesta suena por frases.
- **Investigado y descartado:**
  - MTP: el GGUF de Qwen3.5-4B no trae esas capas.
  - Especulación por n-gramas: 0,82 a 0,83 s contra 0,81 s sin ella.
  - KV en f16: de 78,5 a 79,4 tok/s, y peor con 16k de contexto.
- **Conclusión, estimada por la suma de tiempos (no medida orden a orden por número de herramientas).** Una orden con
  una herramienta rápida entra en 2,5 s; una con dos o más herramientas encadenadas, o con una herramienta lenta, no
  entra. Así la mediana queda cerca del borde y cambia de lado entre corridas.

## 4. Renew no tiene instalador

- **Qué pasa.** El empaquetado de `Baxy.Setup` (`PackageContract`) no lleva la mente (`src/baxy_mind` y su runtime de
  Python), ni el modelo GGUF, ni llama-server, ni Piper. Además fijaba nombres viejos del bundle de Field UI (auditoría
  final H26).
- **Hoy.** Renew se arranca con `run_renew.cmd` en una máquina donde ya están el runtime, el modelo y las voces. Las
  rutas de cada máquina se dan por variables de entorno (`BAXY_RENEW_TTS_MODEL`, `BAXY_RENEW_PIPER_DIR` y otras).
- **Confirmado por la re-auditoría de la 2.ª ronda** (`ac2971398`, `reauditoria-ronda2-nb.md`, H26): sigue roto.
  `scripts/product_build_common.ps1:23-24` lista los archivos viejos de Field UI, y la comprobación exacta de
  `build_product.ps1:231` y `build_setup.ps1:259` falla con la salida actual. El paquete tampoco lleva la mente.

## 5. El latido puede usar herramientas de red o de consola sin que nadie lo pida

- **Qué pasa.** El latido (BAXY que mira por iniciativa propia) retiene para el «sí» de la persona sólo las
  operaciones de una lista hecha a mano (`NativeTurnLoop.cs:67-71`, `246`). Según la re-auditoría de `ac2971398`, eso
  deja dos huecos:
  - H3: el contexto del latido lleva valores de memoria, títulos de ventanas y conversación reciente
    (`Heartbeat.cs:117-119`), y `web.search`, `web.fetch`, `weather.current` y `web.download` no se retienen. Una
    consulta armada con esos datos puede salir a un servicio externo sin que nadie lo pida.
  - H2 y H1: `shell.command.run`, `file.write`, `wifi.disconnect`, `system.settings.set`, `memory.save` e
    `input.keyboard.layout` corren solos en un latido; este último manda el cambio de idioma a la ventana de la
    persona.
- **Por qué sigue.** Falta un atributo tipado en el catálogo («sale de la máquina», «escribe», «actúa en una ventana»)
  que la App pueda usar para retener esas llamadas en el latido. La lista a mano es justo lo que dejó fuera esas
  operaciones.
- **Medido.** En las escenas de práctica (notebook, `ac2971398`), el latido llega a 32/40 con 1 molesta y 0 acciones de riesgo solas. Ninguna
  escena de práctica le pide buscar en la web, así que el banco no lo ejercita.

## Bloque para `metas.json`

```json
"limites": [
  {"limite": "volumen «sube/baja a N»", "estado": "medido, sin arreglo en la presentación",
   "evidencia": "E028, P257; juego propio de 10 frases: actual 6/10, TO/BY 4/10, una herramienta 6/10 (cambia el error)"},
  {"limite": "ruta completa dictada en file.write pierde la subcarpeta", "estado": "mitigado: el proveedor acepta la ruta completa y el recibo dice fullPath",
   "evidencia": "e2e práctica p5/p6 E006, E017, E020, E024, E027; juego de rutas 3/8 → 6/8; F013 arreglada (cf3acc126); 0075c505f, 42a468051"},
  {"limite": "velocidad del texto a la voz en el borde de 2,5 s", "estado": "en el borde: la mediana cambia de lado entre corridas (estimado: una herramienta rápida entra, dos o más no)",
   "evidencia": "e2e práctica p6 p50 2316 ms (36 órdenes), corrida siguiente 2,54 s (18/36 bajo 2,5 s); decisión ~0,7 s; Piper 138–279 ms; MTP, n-gramas y KV f16 descartados"},
  {"limite": "Renew sin instalador", "estado": "abierto",
   "evidencia": "re-auditoría ronda 2 H26 (ac2971398): product_build_common.ps1:23-24 lista archivos viejos de Field UI y build_product.ps1:231 / build_setup.ps1:259 fallan; el paquete no lleva la mente, el modelo, llama-server ni Piper; se arranca con run_renew.cmd"},
  {"limite": "el latido actúa en web, consola, archivos y ajustes sin que se lo pidan", "estado": "abierto",
   "evidencia": "re-auditoría ronda 2 H1-H3 (ac2971398): la lista a mano de NativeTurnLoop.cs:67-71 no retiene web.search, web.fetch, weather.current, web.download, shell.command.run, file.write, wifi.disconnect, system.settings.set, memory.save ni input.keyboard.layout, y el contexto lleva memoria, títulos y chat (Heartbeat.cs:117-119); escenas de práctica en el notebook 32/40, 1 molesta, 0 riesgo solo (ac2971398)"}
]
```
