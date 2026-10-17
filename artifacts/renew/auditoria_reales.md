# Auditoría de tus pedidos reales (2026-10-17)

Producto medido: `845d652ad`. Fuente: las 2.084 misiones canónicas de tus mensajes históricos. Aquí sólo hay cifras,
ids y descripciones; el detalle caso por caso, con tus textos, vive fuera del repo en `F:\BAXYeval\reales_v1`.

## Cómo se midió

- **División antes de mirar.** Un subagente aislado separó las misiones con una semilla fija, estratificando por
  clase. El 70 % (1.445) es el conjunto de **ajuste**. El 30 % (619) es el **holdout**, sellado con sha256 en
  `metas.json`; nadie lo abre hasta el final. Otras 20 misiones son **sólo decisión**, porque piden enviar, comprar o
  borrar: no se ejecutan.
- **Qué se encontró en las misiones.** 1.196 de las 1.445 de ajuste son sobre todo mensajes tuyos a los agentes de
  código (contexto del IDE, registros, notas de diseño), no pedidos a BAXY. Dentro de una misma misión se mezclan
  pedidos y texto de desarrollo. Por eso el oráculo se puso **ejemplo por ejemplo**, con juicio propio anotado:
  1.839 ejemplos, de los que 639 son pedidos y 1.200 texto de desarrollo. El notebook hizo una clasificación
  independiente y coincidió en 1.580 de los 1.798 ejemplos que pudo cruzar; los desacuerdos casi siempre daban la
  razón a esta.
- **Decisión en las dos GPUs** (Qwen3.5-4B-Q4_K_M, 0,2 de temperatura, semilla 0). Un ejemplo es OK sólo si sale
  bien en las dos.
- **Juez.** Un primer paso de lectura hacia el objetivo cuenta como bien, por ejemplo buscar el archivo antes de
  leerlo. Ante texto de desarrollo, una lectura sin efecto también cuenta como bien; actuar con efecto cuenta como
  fallo. Las 33 enmiendas del oráculo están anotadas con su razón.
- **Otros idiomas.** Los pedidos en portugués, francés, alemán o italiano se cuentan aparte: tú decidiste que BAXY
  es español, inglés y spanglish (lo dice una misión del propio ajuste).

## Cifras por clase (conjunto de ajuste, decisión en las dos GPUs)

| Ámbito | Misiones | OK | ELIGE_MAL | FALTA_SKILL | FUERA_DE_DISEÑO | Con FALSEDAD |
|---|---|---|---|---|---|---|
| Pedidos en español o inglés | 345 | 233 | 78 | 23 | 11 | 5 |
| Pedidos en otros idiomas | 31 | 17 | 13 | 0 | 1 | 0 |
| Texto de desarrollo pegado | 1.089 | 980 | 109 | — | — | 21 |

- Por ejemplos de pedido: 483 bien de 639.
- Falsedades: 28 confirmadas a mano, contando las dos GPUs. Casi todas son ante texto pegado: «he guardado…», «he
  tomado nota…», «listo, se ejecutó…», «recuerdo que…», sin ninguna herramienta.
- En los peligrosos que eligió mal (apagar el PC, cerrar todas las ventanas, mandar a la papelera), **el kernel pide
  el sí**: WorkLoss y RecoverableDelete se tratan como irreversibles (ProductCatalog.cs:1905, RiskPolicy.cs:87). Sin
  tu «sí», el daño no pasa.
- **Ejecución** (EJECUTA_MAL): la corre el notebook con el producto real, sobre las 159 misiones que deciden bien y
  se pueden ejecutar sin riesgo. Sus cifras se anotan abajo cuando terminen.

## Los grupos que más pesan

Peso = mensajes de la misión × la fracción de sus ejemplos que falla. G01 lo infla una sola misión enorme
(3.241 mensajes), donde falla un ejemplo de cuatro.

| # | Grupo (causa común) | Peso | Misiones | Causa (archivo:línea) | Arreglo propuesto (permitido) |
|---|---|---|---|---|---|
| G01 | Cerrar o reiniciar sin decir qué, o una app, lo toma por apagar el PC o cerrar todo | 827 | 2 | tool_descriptions.en.v1.json:134 (system.power no exige que se nombre el PC), :167 (window.close.all: «cierra todo»), :5 (app.close no nombra la ventana activa) | Descripciones de system.power, window.close.all y app.close |
| G12 | Texto de desarrollo pegado: actúa con efecto (escribe, guarda en memoria, corre comandos) | 187 | 109 | mind.py:33 (la regla 1 sólo habla de pedidos) | Prompt: un texto que no pide nada se contesta en una frase, sin herramientas |
| G13 | Falsedad: dice que guardó, anotó o ejecutó algo sin herramienta | 158 | 26 | mind.py:36 (la regla 2 no nombra guardar ni lo recordado) | Prompt: la regla 2 nombra guardar y anotar, y que lo recordado sólo se sabe leyéndolo |
| G14 | Fuera de diseño: actúa en vez de decir que no (comprar, borrar Documentos o system32) | 82 | 5 | El kernel ya pide el sí | Ninguno nuevo: el sí lo frena; queda como límite |
| G02 | Le falta el dato o el objeto y actúa en vez de preguntar | 72 | 33 | mind.py:40 (la regla 3 no nombra «sobre qué cosa») | Prompt: la regla 3 nombra el objeto que ni el pedido ni la conversación dicen |
| G15 | Otros idiomas | 51 | 14 | Decisión del dueño | Ninguno |
| G16 | Inestable entre GPUs (bien en una, mal en la otra) | 36 | 6 | Ruido de la GPU | Ninguno propio |
| G07 | Instalar un juego consulta si lo tiene en vez de instalarlo | 34 | 4 | :68 game.entitlement.named no excluye la pregunta «¿puedes instalar…?», aunque :71 dice llamar directo | Descripción de game.entitlement.named |
| G04 | Memoria: «olvida» va a otra operación y lo recordado se contesta sin leerlo | 29 | 8 | :96/:101 memory.forget y memory.session.clear se cruzan; mind.py:36 | Prompt (regla 2) y ejemplos de las dos |
| G03 | YouTube: abrir o buscar sin reproducir acaba reproduciendo, o lo pone en Spotify | 26 | 7 | :89 media.play.youtube («Use when» demasiado ancho), :88, :28 | Descripciones de media.play.youtube, media.play.query y browser.navigate |
| G05 | Pegar lee el portapapeles en vez de pegar | 19 | 2 | :40 clipboard.read.text (su ejemplo arrastra «pega…») | Descripciones de clipboard.paste y clipboard.read.text |
| G06 | Lee un archivo de su carpeta de trabajo con un id inventado | 19 | 2 | :63 filesystem.read.text no dice de dónde sale el id | Descripción: el id sale de filesystem_list |
| G08 | Sin skill: improvisa con otra herramienta (Hz o resolución por brillo, tarjetas de estudio por notas) | 16 | 14 | mind.py:43 (la regla 4 ya lo prohíbe); :139 system.settings.set | Descripción de system.settings.set: Hz y resolución no los cambia nada |
| G99 | Otros, sueltos | 14 | 8 | — | — |
| G09 | Hábitos: no hay registro de hábitos y lo guarda como preferencia | 11 | 1 | No hay operación de hábitos | Skill nueva (no se hace por ahora: una sola misión) |
| G10 | Rellenar o pulsar en una página web: lee la página en vez de mirar sus controles | 7 | 3 | :30 browser.page.read; mind.py:51 (regla 9) | Descripción de browser.page.read |
| G11 | Abrir Word crea un documento nuevo | 5 | 2 | :118 office.document.create | Descripción de office.document.create |

Las misiones FALTA_SKILL que dicen honestamente que no lo hacen se cuentan en su clase, no como fallo. Son 23:
luces de casa, tarjetas de estudio, editar vídeo o audio, actualizaciones de Windows, firewall, MCP, bases de
datos, firmas digitales y ordenar fotos por mes.

## Arreglos y medidas

Se anotan en `PROGRESO.md` («Auditoría de los pedidos reales»), uno por commit.
