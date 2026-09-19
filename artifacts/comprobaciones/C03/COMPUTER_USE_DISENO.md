# Computer use en BAXY — diseño

Decisión del dueño, 2026-09-19: BAXY no debe resolver cada fila con un contrato a medida,
sino usar el ordenador como lo usaría una persona. De las 53 filas abiertas del registro,
**32 son computer use**: las 24 de vídeo y ocho más (navegar a un sitio nombrado, pulsar
algo en pantalla, completar el diálogo de descarga de Steam, descargar en Epic, leer el
último mensaje de un chat, y las dos misiones compuestas).

Lo que sigue es el diseño, con lo que lo sostiene: lo medido fuera, lo que BAXY ya tiene,
y el modelo concreto que corre aquí.

## 1. Los ojos son el árbol de accesibilidad, no la captura

OSWorld mide las tres formas de mirar una pantalla sobre las mismas tareas: árbol de
accesibilidad solo, **18–21 %**; captura sola, **5–15 %**; las dos juntas, **18–25 %**. La
causa que dan es directa: los modelos de visión no aciertan las coordenadas a partir de
una captura, y el árbol se las da hechas.

Para BAXY la elección ni siquiera está reñida. **La mente de este PC es Qwen3-4B, de
texto**: una captura no la puede leer. El árbol no es la mejor de dos opciones, es la
única que el modelo entiende.

Eso ya está hecho y es de lo que hay que partir: `input.visible.click` recorre primero
UIA, y sólo si no encuentra el control cae a OCR y después a visión
(`WindowsVisibleControlAdapter`, cascada de tres). El orden es el correcto y no se toca.

## 2. Un solo acto por paso, nombrado, nunca por coordenadas

Los trabajos de agentes de interfaz convergen en un repertorio mínimo y atómico —pulsar,
escribir, desplazar, tecla, esperar, terminar— y en que el objetivo se nombre por su
elemento, no por su píxel. `input.visible.click` ya toma exactamente eso: una etiqueta,
256 bytes, nada más. No hay coordenadas en el contrato, y es lo que evita el fallo en el
que caen los modelos de visión.

El repertorio de BAXY para el bucle queda en lo que ya existe:

| Acto | Operación |
|---|---|
| pulsar lo que se ve | `input.visible.click` (etiqueta) |
| escribir | `input.key.press` |
| enfocar / mover ventana | contratos de ventana |
| abrir la aplicación | `app.open` |
| mirar | lectura de pantalla (UIA, OCR) |
| terminar | decir lo que ve y parar |

## 3. Lo que falta es el bucle

Hoy un turno propone un puñado de operaciones, la raíz las aprueba de una vez y se
ejecutan. No hay ciclo. El bucle es: **mirar → elegir un acto → ejecutarlo → volver a
mirar**, hasta llegar al objetivo o hasta ver que no se llega.

Reglas del bucle, y por qué cada una:

- **Cada paso conserva su aprobación y su postlectura.** Un bucle multiplica las
  decisiones; multiplicar también las revisiones es lo que impide que un clic equivocado
  se encadene. Es además lo que miden los bancos de seguridad de agentes de ordenador
  (OS-Harm): el daño no viene del acto aislado, viene de la cadena sin freno.
- **Un clic sólo cuenta si la superficie cambió.** Ya es el criterio del instrumento de
  interfaz de esta campaña (`controlGoneAfterClick`, verificación de cambio de
  superficie). Pasa a ser la postlectura de cada paso del bucle.
- **Presupuesto de pasos y regla de parada.** Si la pantalla no cambia tras un acto, o el
  modelo elige dos veces el mismo control, el bucle para y BAXY dice qué ve. Terminar
  diciendo la verdad es un final válido; dar vueltas no lo es.

## 4. Especializado para Qwen3-4B

El modelo que corre aquí tiene 4096 de contexto y temperatura cero. Eso manda sobre el
diseño más que cualquier otra cosa:

- **El árbol se filtra, no se vuelca.** Los trabajos publicados le dan al modelo el árbol
  entero; aquí no cabe. Se le dan como mucho ~40 controles, sólo los visibles, habilitados
  y con nombre, uno por línea y en una línea corta: `id · tipo · nombre`. Todo lo demás
  sobra y, peor, empuja fuera del contexto lo que importa.
- **Una pregunta por paso, no un plan.** A un modelo de 4B no se le pide que planifique
  cinco actos: se le pide *uno*, con los controles delante y el objetivo escrito.
- **«Ninguno de estos» es siempre una opción explícita.** Sin esa salida, un modelo
  pequeño elige el control menos malo con tal de contestar algo. Con ella, puede decir que
  no ve por dónde seguir, que es la respuesta honesta y la que esta campaña acredita.
- **Temperatura cero es una ventaja, no una limitación.** La misma pantalla da el mismo
  acto, así que un fallo se reproduce y se repara. Toda la campaña depende de eso: la
  lección de hoy, cuatro veces, es que lo que no se reproduce no se arregla.

## 4b. Medido en Steam: el árbol de accesibilidad puede estar vacío

El diálogo de instalación de Steam se abrió y se leyó con la lectura nueva. UIA devuelve
**un solo nodo, «Chrome Legacy Window», sin un solo hijo**. Se pidió dos veces, por si
Chromium activaba su árbol bajo demanda tras la primera petición; no lo activa.

La interfaz de Steam —y la de Epic y la de Discord, que son de la misma familia— es
Chromium incrustado. Para ellas **el canal que los papers miden como el mejor no existe**,
y manda la cascada de OCR que el clic ya tiene detrás de UIA. Es el caso inverso al de una
aplicación nativa como la Calculadora, donde UIA lo da todo.

De aquí salen dos consecuencias para el bucle:

- **La lectura de controles tiene que decir cuándo no ve nada.** Un único nodo contenedor
  no es una pantalla sin controles: es una pantalla que este canal no sabe leer. El bucle
  debe pasar a OCR en ese caso, no concluir que no hay nada que pulsar.
- **Un paso puede necesitar más de un clic.** El diálogo de DOOM Eternal viene con la
  unidad por defecto (C:, 54,62 GB libres) para un juego de 89,52 GB: completarlo de
  verdad exige elegir antes otra unidad. La fila que dice «completalo haciendo click en
  instalar» no se cumple con un clic, y el criterio tiene que decirlo.

## 5. Lo que este diseño no resuelve

- **Las sesiones.** Que BAXY sepa pulsar «Reproducir» no le da la cuenta de Netflix. El
  perfil de navegador con sesión iniciada es un requisito aparte y lo pone el dueño.
- **El DRM.** El navegador que BAXY levanta corre sin GPU; Netflix y Disney+ pueden
  negarse a reproducir por eso aunque la sesión esté puesta. Hay que medirlo antes de
  prometer las 24 filas.
- **Lo que no está.** Among Us no está instalado: ningún bucle lo va a encontrar. Ahí lo
  correcto es mirarlo y decir que no está, que es lo que el dueño pidió.

## Fuentes

- [OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments](https://arxiv.org/html/2404.07972v2)
- [OS-Harm: A Benchmark for Measuring Safety of Computer Use Agents](https://arxiv.org/html/2506.14866v1)
- [Agent S: An Open Agentic Framework that Uses Computers Like a Human](https://arxiv.org/pdf/2410.08164)
- [Agent S2: A Compositional Generalist-Specialist Framework for Computer Use Agents](https://arxiv.org/pdf/2504.00906)
- [Structuring GUI Elements through Vision Language Models: Towards Action Space Generation](https://arxiv.org/html/2508.16271v1)
- [AgentCPM-GUI: Building Mobile-Use Agents with Reinforcement Fine-Tuning](https://arxiv.org/pdf/2506.01391)
