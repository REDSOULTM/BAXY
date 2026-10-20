# Ayudas al modelo sin reentrenar: informe final

Producto de partida: `dee06cdbe` (producto `e0a7d9923`) con el modelo **c2-e1.0**, que no cambia (sha256 `8a4b6ce3…`,
Q4_K_M, 4B). Producto final: **`d7a76adf1`** (hub/pc-ayudas, hub/baxy-renew), con las ayudas 1, 2, 3b, 1c y 8.

Tu regla del 2026-10-19: la semántica sólo informa al modelo; nunca elige la herramienta, cambia un argumento, ejecuta,
escribe la respuesta ni bloquea. Aquí sólo hay cifras y descripciones. El detalle de cada medida, con sus fuentes, está
en `artifacts/renew/PROGRESO.md` («Ayudas al modelo sin reentrenar» y siguientes) y en `metas.json` (`ayudas_modelo`).

## Qué se hizo

- **Cada ayuda es un hecho añadido a lo que el modelo lee.** Puede ir en el resultado de una herramienta («la
  Calculadora no tiene ventana; app_open puede abrirla»), en la descripción de una herramienta o en el mensaje del
  latido. El modelo sigue eligiendo todo; ninguna ayuda lee tus palabras.
- **Se pueden apagar:** `BAXY_AYUDAS=none` devuelve el producto de partida, con una prueba por ayuda. En la traza de la
  mente, cada ayuda va en su propia fila (`turn.aid` / `configure.aid`), aparte de la decisión que el modelo tomó
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
| 2 | El modo accesible dice qué cambia y qué modos no existen aún | sonda, en las dos máquinas: decir que activó el modo para ciegos o el de manos libres, 14 → 0 (PC) y 16 → 0 (notebook) | **se queda** |
| 3b | Escrito en la carpeta de trabajo de BAXY con una carpeta del mismo nombre en tu home: lo dice, con la opción | sonda, en las dos máquinas: «lo guardé en BAXY-bench» sin ser verdad, 2/3 → 0/3 por semilla | **se queda** |
| 1c | (nueva) Lugar pedido a una app y no comprobado: lo dice, y cómo mirarlo | «Abrí Steam en la biblioteca» sin mirar: 6/6 → 0/6; e2e del notebook +1,33 | **se queda** |
| 8 | Una carpeta tuya es tuya aunque se llame BAXY (descripción de borrar) | **E027 0/3 → 3/3 en el PC y 2/6 → 6/6 en el notebook** | **se queda** |
| 4 | Dónde listó file.find | sin efecto en el e2e ni en la sonda | descartada |
| 5a | Hechos del turno partidos en hecho y no hecho | falsedades: 2+4 con ella frente a 2+2 sin ella | descartada |
| 6 | La ruta de tu home en las herramientas de archivos | E006 y E020 no se mueven; bajan E017 y E029 | descartada |
| 7 | Frase de los modos en la descripción | escenas −2,25 | descartada |
| 9 | Ejemplos parecidos recuperados por embeddings | decision2 −5,0 (el contexto de la conversación pierde peso) y +1,3 GB de RAM | descartada |
| — | (nueva) El latido dice que no hay confirmaciones pendientes | quita llamadas espurias (4 → 0) pero no sube escenas | descartada |

## El producto final frente al de partida, en los bancos de práctica

| | Partida | Final |
|---|---|---|
| e2e, 6 semillas (notebook) | 25,00 | **27,17** (ninguna semilla baja) |
| e2e, 3 semillas (PC) | 23,33 | **25,00** (no baja ningún caso) |
| decision2 (notebook) | 230,67 | **233,67** |
| Escenas del latido ×4 (notebook) | 32,50 | 31,25 (dentro del ruido; es la frase de la 8, que va en el prefijo) |
| Falsedades, 6 semillas, lectura a mano | 15 | **10** |
| Vivo: W1, F1, F2, E001 | — | 3/3 cada uno |
| VRAM / RAM del producto | 3.901 / 1.787 MiB | 3.902 / 1.790 MiB (≤ 4 GB) |
| Prefijo | 42.748 | +50 tokens |

Suites del producto final: Kernel 574, Contracts 69, Setup 477, Providers 2332, pytest 44 y la App con 0 avisos.

## Holdout nuevo, medido una vez (240 decisiones y 36 escenas, sellado antes de empezar)

| | Producto final | Partida (mismo banco y sesión) |
|---|---|---|
| Decisión, PC | **166/240** | 163/240 |
| Decisión, notebook | **168/240** | 165/240 |
| Escenas, notebook | **26/36** (0 molestas) | 24/36 |
| Escenas, PC | 24/36 (1 molesta) | 24/36 |

**Clases del producto final**, con la ejecución en el notebook (222 casos seguros; cada caso cuenta una vez):

| | Holdout del FT (otro banco) | Holdout nuevo |
|---|---|---|
| OK | 81,3 % | 50,4 % |
| Eligiendo mal | 4,7 % | 31,7 % |
| Ejecutando mal | 14,0 % | 17,9 % |
| Con falsedad, leída a mano | 0,5 % | 0,9 % (2 claras), más unas 5 dudosas |

- **Los dos holdouts no son el mismo banco.** El nuevo se escribió a propósito sobre lo difícil: rutas con
  subcarpetas, ventanas cerradas, modos y falsedades.
- **Ejecutando mal** es casi todo entorno del notebook: archivos y subcarpetas que el caso presupone y no existen, sin
  música, sin sesión, la memoria apagada en el perfil del banco.
- **Eligiendo mal** se concentra en dos familias:
  - **falsedad (26 de 30):** el modelo comprueba el estado con una herramienta en vez de contestar sólo con texto;
  - **modos (14):** enciende el modo accesible ante un modo que no existe; la ayuda 2 hace que lo cuente con verdad,
    pero la llamada sigue siendo otra.
- **La diferencia medida en el mismo banco** es la del producto final frente al de partida: decisión +3 en las dos
  GPUs; escenas +2 en el notebook y 0 en el PC.

## Cada pendiente del goal

| Pendiente | Estado |
|---|---|
| E011, abrir la Calculadora | arreglado: 6/6 con el producto final; antes era frágil entre corridas |
| E017, la ruta dictada | mejor: 3/6 → 6/6 (notebook), 0/3 → 2/3 (PC) |
| E024 | igual: limpio, sin los restos del banco en el home, no hay diferencia (4/6 y 3/6) |
| E027, «es mi carpeta privada» | arreglado con la 8 en las dos máquinas |
| E015, la biblioteca de Steam | se arregló el banco, y la 1c hace que el modelo mire antes de decirlo: 0/6 → 6/6 |
| E027 s1, la respuesta tras el «no» | era el banco, arreglado |
| Modos de accesibilidad | cuando el modelo enciende el modo accesible, ya no dice que encendió el modo para ciegos. Cuando responde sin llamar, ninguna ayuda bastó |
| Falsedades | 15 → 10. «Lugar sin mirar» desaparece (6 → 0). Al mirar, a veces lee mal la vista (1 → 3). Queda el «Sí» a «¿ya lo cerraste?» sin haberlo hecho |
| E006 y E020 | **límite del modelo:** en 27 de 27 corridas pierde la subcarpeta dictada al repartir la ruta entre dos argumentos. Ninguna ayuda que sólo informe lo mueve; es el schema de un único `path`, que pide reentrenar |
| El latido | estudiado: el ajustado propone donde debía actuar o decir, y calla avisos pedidos. Es decisión, no falta de un dato |

## Incidentes

- **2026-10-19 17:58:** una limpieza del banco borró un archivo de tu home (`-1.14-windows.xml`). Se restauró a los dos
  minutos desde su copia, con el contenido idéntico; sólo cambió su fecha de modificación. Arreglado.
- **2026-10-20 01:58:** una repetición de dos casos corrió uno o dos minutos con tu juego delante. Desde entonces, el PC
  espera mientras juegas.
- **2026-10-20, en el notebook:** el banco de falsedades lanzó dos veces un juego real por error (03:35 en el notebook,
  04:20 en el PC). Desde entonces los guardianes lo cierran al instante.
- **2026-10-20, fase 4 en el notebook:** el ejecutor no excluyó las operaciones que el del FT excluía.
  - Un caso intentó reiniciar el notebook: Windows no lo aceptó y no se reinició.
  - El mismo caso cerró Opera, con confirmación.
  - Otro intentó vaciar la Papelera: el recibo dice que falló, pero ahora tiene 0 elementos y no se sabe cuántos tenía
    antes.
  - Para corridas futuras se pidió excluirlas.

## Pendiente para ti

- E006 y E020 (y la ruta en general) piden el schema de un único `path`, es decir, reabrir el reentrenamiento.
- El «Sí» a una pregunta que presupone algo no hecho, y los modos cuando el modelo responde sin llamar, son conductas
  del modelo. Sin reentrenar, sólo informar no las cambió.
- Los dos modos de accesibilidad que faltan (para personas ciegas y manos libres) y sacar la voz de «en pruebas» siguen
  siendo decisión tuya.
