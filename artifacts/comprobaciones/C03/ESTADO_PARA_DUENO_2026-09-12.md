# Estado para el dueño — 12 de septiembre, relevo recibido en el PC nuevo

El PC nuevo ya está al día y sin pérdidas. La rama `Goal-c03` pasó de `2bf3d4c5` a `ed305c38`
por fast-forward, 192 commits, sin borrar nada: siguen ahí el stash del goal 10, las ramas
`goal-10` y `rewrite-10-11-descartado`, los tres worktrees temporales y `main` intacta.
No había otro agente ni compilación en marcha. Sí estaba corriendo BAXY del arranque automático
de Windows; lo cerré, con eso liberé memoria y compilé Release en 21 segundos, 0 errores y
0 advertencias, con el Core de al lado de `Baxy.exe` idéntico al de `Baxy.Core`. Compilar no
demuestra calidad ni pantalla, y no ejecuté pruebas: suites, Fast y Full siguen omitidas por tu
instrucción, omitidas y no verdes.

**Necesito que me traslades dos cosas, y sólo dos.**

1. El ZIP privado `C03_OPUS5_RELEVO_PRIVADO.zip` (SHA `95bc3f23…fd8c704`, 2 025 743 bytes).
   No está en este PC: lo busqué por nombre exacto en las seis unidades y en
   `%LOCALAPPDATA%/BAXY`, que aquí tiene 1489 carpetas pero ninguna de las tandas 1010–1027 —
   su evidencia más reciente es del 6 de septiembre. Sin el registro de la encuesta que va dentro
   no puedo escribir cobertura ni sellar una tanda nueva: los literales exactos de los 742 casos
   sólo están ahí, y lo que sí está en Git sólo lleva identificadores y estados.
2. Los pesos decididos, Qwen3-4B-Instruct-2507 Q4_K_M, SHA `3605803b…c4c67e597`. Hashé los cuatro
   GGUF de este PC y ninguno es ése. Ojo con uno: `Qwen3-4B-Q4_K_M.gguf` en D: **se llama igual**
   que el que espera el manifiesto pero su contenido es otro, así que no lo registré. Habría
   quedado un modelo distinto con aspecto correcto. El backend llama-server sí es el mismo de la
   decisión. El manifiesto de activos dice que BAXY no descarga modelos, así que no improviso una
   descarga.

Lo pedido exacto, con rutas y hashes, está en `OPUS5_DESTINO/SOLICITUD_TRASLADO.md`.

**Mientras tanto avancé lo que no depende de eso.**

La tanda 1025 queda **cerrada en cobertura**: su crédito es 3, los que ya estaban escritos, y no
puede dar más. No es una estimación. Las dos conductas que quedaban vivas —descripción de juegos y
comparación ficcional— ya tienen dos de tres y una de dos variantes caídas, así que no llegan a las
dos variantes en pie que exige un crédito, y la única tanda anterior de la categoría con
adjudicación pública, la 998, cubrió aritmética y conversiones, nada pertinente. Por eso H0236,
H0239 y H0582 siguen abiertos pase lo que pase con su literal, y el contador 126 no se mueve.

De los 25 casos ya tengo 14 juzgados: 5 pasan y 9 fallan con causa. Los fallos son de dos clases
claras. Hechos inventados en fichas de juegos: Marvel vs. Capcom fechado en 2000 cuando el estreno
original fue arcade en 1998; Doom Eternal atribuido a Bethesda Game Studios y a 2023 cuando es id
Software, Bethesda Softworks y 20 de marzo de 2020; Chell descrita como hombre y Portal como mundos
alternativos. Y referente ausente resuelto inventándolo: H0424, H0645 y la variante inglesa
respondieron hablando de la identidad de BAXY en vez de preguntar de quién se hablaba, que era
justo lo que el panel iba a detectar. Dos más terminaron sin respuesta útil. Contrasté las fechas y
los estudios con fuentes primarias antes de darlos por fallidos; ninguno se acredita por sonar bien.
Los 11 que faltan necesitan el texto de sus terminales, que está en el ZIP, y ninguno puede cambiar
el contador.

También revisé la reparación 1024 de los avisos con plazo. El diseño es el más simple que resuelve
el caso, pero encontré algo que su diagnóstico no menciona: la función que amplía tiene un segundo
uso en el código que hace que el reconocedor se abstenga de producir el efecto, y ampliarla amplía
también esa abstención. No la integro sin ver el parche real y sin medir controles de aviso sin
plazo y de aviso con título ya dado. Es exactamente el tipo de regresión silenciosa que preferiría
no meter por ir rápido.

**Lo que no hice, a propósito:** ningún crédito nuevo, ningún panel sellado, ninguna tanda
ejecutada, ninguna reclasificación de la encuesta, ningún modelo sustituido en silencio, ninguna
prueba. Sellar un panel sin los literales exactos o registrar un modelo por coincidencia de nombre
habría sido inventar cobertura, y eso no es ir más rápido.

En cuanto lleguen el ZIP y los pesos: cierro las 11 causas de 1025, registro el runtime con su
hash, mido el subconjunto de 1024 y sello la siguiente categoría por masa abierta ejecutable.
C03 no está completado y no lo declaro.
