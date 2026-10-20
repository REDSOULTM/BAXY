# Ayudas al modelo sin reentrenar: informe final

> **Borrador del 2026-10-20 02:40.** Faltan la confirmación del lote en el PC y el holdout nuevo (fase 4); sus filas
> dicen «pendiente» hasta tenerlas.

Producto de partida: `dee06cdbe` (producto `e0a7d9923`) con el modelo **c2-e1.0**, que no cambia (sha256 `8a4b6ce3…`,
Q4_K_M, 4B). Tu regla del 2026-10-19: la semántica sólo informa al modelo, nunca elige la herramienta, cambia un
argumento, ejecuta, escribe la respuesta ni bloquea. Aquí sólo hay cifras y descripciones. El detalle de cada medida,
con sus fuentes, está en `artifacts/renew/PROGRESO.md` («Ayudas al modelo sin reentrenar» y siguientes) y en
`metas.json` (`ayudas_modelo`).

## Qué se hizo

- **Cada ayuda es un hecho añadido a lo que el modelo lee.** Puede ser en el resultado de una herramienta («la
  Calculadora no tiene ventana; app_open puede abrirla»), en la descripción de una herramienta o en el mensaje del
  latido. El modelo sigue eligiendo todo; ninguna ayuda lee tus palabras.
- **Se pueden apagar:** `BAXY_AYUDAS=none` devuelve el producto de partida, con una prueba por ayuda. En la traza de la
  mente, cada ayuda va en su propia fila (`turn.aid` / `configure.aid`), aparte de la decisión que tomó el modelo
  después.
- **Una palanca a la vez**, contra el producto de partida medido el mismo día en la misma máquina. Lo que subió en una
  máquina se confirmó en la otra.
  - Además del e2e, una **sonda de continuación**: el mismo turno con el resultado con y sin la ayuda, para ver la causa
    de cada una.
  - Tu decisión del 19 a las 15:20 dejó correr el e2e también en el PC, con las dos máquinas en paralelo.

## Cada palanca

| # | Ayuda | Medida | Veredicto |
|---|---|---|---|
| 1 | Calculadora sin ventana: «app_open puede abrirla» | E011: en una semilla en que el modelo se rendía, abre la Calculadora y acierta | **se queda** |
| 2 | El modo accesible dice qué cambia y qué modos no existen aún | sonda: decir que activó el modo para ciegos o el de manos libres, 14 → 0; decir que aún no existen, 0 → 15 (17 casos ×3) | **se queda** |
| 3b | Escrito en la carpeta de trabajo de BAXY con una carpeta del mismo nombre en tu home: lo dice, con la opción | sonda: «lo guardé en BAXY-bench» sin ser verdad, 2/3 → 0/3 por semilla | **se queda** |
| 1c | (nueva) Lugar pedido a una app y no comprobado: lo dice, y cómo mirarlo | «Abrí Steam en la biblioteca» sin mirar: 3/3 → 0/3; e2e del notebook +1,33 | **se queda** |
| 8 | Una carpeta tuya es tuya aunque se llame BAXY (descripción de borrar) | **E027 0/3 → 3/3 en el PC y 2/6 → 6/6 en el notebook** | **se queda** |
| — | (nueva) El latido dice que no hay confirmaciones pendientes, un hecho por construcción | en medida | pendiente |
| 4 | Dónde listó file.find | sin efecto en el e2e ni en la sonda | descartada |
| 5a | Hechos del turno partidos en hecho y no hecho | falsedades: 2+4 con ella frente a 2+2 sin ella | descartada |
| 6 | La ruta de tu home en las herramientas de archivos | E006 y E020 no se mueven; bajan E017 y E029 | descartada |
| 7 | Frase de los modos en la descripción | escenas −2,25 | descartada |
| 9 | Ejemplos parecidos recuperados por embeddings | decision2 −5,0 (el contexto de la conversación pierde peso) y +1,3 GB de RAM | descartada |

## El lote (1 + 2 + 3b + 1c + 8, `d7a76adf1`)

| | Producto de partida | Lote |
|---|---|---|
| e2e de práctica, 6 semillas (notebook) | 25,00 | **27,17** (ninguna semilla baja) |
| decision2 (notebook) | 230,67 | **233,67** |
| Escenas del latido ×4 (notebook) | 32,50 | 31,25 (dentro del ruido; es la frase de la 8, en el prefijo) |
| Falsedades, 3 semillas, lectura a mano (notebook) | 9 | **5** |
| Vivo: W1, F1, F2, E001 | — | 3/3 cada uno |
| VRAM / RAM del producto | 3.901 / 1.787 MiB | 3.902 / 1.790 MiB (≤ 4 GB) |
| Prefijo | 42.748 | +50 tokens |
| Confirmación en el PC (e2e s0-2, falsedades) | pendiente | pendiente |

Suites del lote: Kernel 574, Contracts 69, Setup 477, Providers 2332, pytest 44, todo verde.

## Cada pendiente del goal

| Pendiente | Estado |
|---|---|
| E011, abrir la Calculadora | arreglado: 6/6 con el lote; antes era frágil entre corridas |
| E017 y E024, la ruta dictada | E017 3/6 → 6/6. E024 igual (4/6 y 3/6): limpio, sin los restos del banco en el home, no hay diferencia |
| E027, «es mi carpeta privada» | arreglado con la 8: 0/3 → 3/3 (PC) y 2/6 → 6/6 (notebook) |
| E015, la biblioteca de Steam | el banco se arregló (marcas de la vista) y la 1c hace que el modelo mire antes de decirlo: 0/6 → 6/6 |
| E027 s1, la respuesta tras el «no» | era el banco, arreglado: ahora suena y cuenta |
| Modos de accesibilidad | cuando el modelo enciende el modo accesible, ya no dice que encendió el modo para ciegos (14 → 0). Cuando responde sin llamar, la frase de la 7 no ayudó |
| Falsedades | 9 → 5 en el lote. «Lugar sin mirar» desaparece (3 → 0). Queda el «Sí» a «¿ya lo cerraste?» sin haberlo hecho (2 de 3 en los dos brazos): no hay una llamada fallida que lo contradiga, así que ninguna ayuda del resultado lo toca |
| E006 y E020 | **límite del modelo:** en 27 de 27 corridas pierde la subcarpeta dictada al repartir la ruta entre dos argumentos. Ninguna ayuda que sólo informe lo mueve; es el schema de un único `path`, que pide reentrenar |
| El latido en el holdout del FT (26/36 frente a 29/36) | estudiado. El ajustado tiende a proponer donde debía actuar o decir, y a callar avisos pedidos: es decisión, no falta de un dato. La única ayuda de hecho posible (sin confirmaciones pendientes) está en medida |

## Holdout nuevo (240 decisiones y 36 escenas, sellado antes de empezar)

Pendiente: una sola vez sobre el lote final, la decisión en las dos GPUs y la ejecución en el notebook. Se comparará
con el holdout del ajuste fino (pedidos OK 81,3 %, eligiendo mal 4,7 %, ejecutando mal 14,0 %, falsedad 0,5 %). Son
bancos distintos, así que la comparación orienta y no es una diferencia medida.

## Incidentes

- **2026-10-19 17:58:** una limpieza del banco borró un archivo de tu home (`-1.14-windows.xml`). Se restauró a los dos
  minutos desde su copia, con el contenido idéntico; sólo cambió su fecha de modificación. Arreglado.
- **2026-10-20 01:58:** una repetición de dos casos del e2e corrió uno o dos minutos con tu juego delante. Desde
  entonces el PC espera mientras juegas.

## Pendiente para ti

- E006 y E020 (y la ruta en general) piden el schema de un único `path`, es decir, reabrir el reentrenamiento.
- Los dos modos de accesibilidad que faltan (para personas ciegas y manos libres) y sacar la voz de «en pruebas» siguen siendo decisión tuya.
