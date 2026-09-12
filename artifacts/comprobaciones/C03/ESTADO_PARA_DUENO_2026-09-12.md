# Estado para el dueño — 12 de septiembre, relevo asumido en la máquina original

Corregido tu punto: REDPC es el BAXY original y el portátil sólo replicó el repositorio, con raíz en
`D:` porque su `C:` estaba lleno. Eso encaja con lo que encontré: el trabajo de C03 desde el 6 de
septiembre se hizo en la réplica, y por eso la evidencia privada de esas tandas y la descarga del
modelo decidido quedaron allí, no aquí.

## Lo que quedó funcionando

`Goal-c03` pasó de `2bf3d4c5` a `ed305c38` por fast-forward, 192 commits, sin borrar nada: siguen ahí
el stash de goal-10, las ramas `goal-10` y `rewrite-10-11-descartado`, los tres worktrees temporales
y `main` intacta. Cerré la instancia de BAXY del arranque automático de Windows, compilé Release en
21 segundos con 0 errores y 0 advertencias, y el Core de al lado de `Baxy.exe` es idéntico al de
`Baxy.Core`. Compilar no demuestra calidad ni pantalla. No ejecuté pruebas: suites, Fast y Full
siguen omitidas por tu instrucción, omitidas y no verdes.

**El modelo decidido ya está registrado y cargando.** Esto era la mitad de lo que te iba a pedir y lo
resolví. No estaba en `assets/models`: vivía en
`D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/`, carpeta que aquí no existía. De
los 93 GGUF de esta máquina ninguno era el correcto, y hay una trampa que conviene que sepas:
`D:/BAXYRuntime/assets/models/Qwen3-4B-Q4_K_M.gguf` **se llama igual** que el primer candidato del
manifiesto, pero el propio repositorio lo identifica como el modelo activo **anterior**, el Instruct
AWQ. Registrarlo por nombre habría dejado BAXY corriendo con otro modelo y aspecto correcto.

Lo restauré desde la procedencia que el repositorio ya tenía sellada en agosto: repositorio de
cuantización, revisión fijada, bytes y SHA-256 esperados, licencia Apache-2.0, y su propio orden de
verificación. Descarga a `.partial`, 2 497 281 120 bytes exactos, SHA `3605803b…` exacto, y sólo
entonces renombrado. No abrí ninguna campaña de modelos ni cambié de modelo: es el activo de la
decisión 792 puesto donde el proyecto lo declara.

Después `bootstrap.ps1` falló con `installed_missing`: el entorno Python de la mente estaba desfasado
respecto a los 192 commits nuevos. Bootstrap instaló lo que faltaba y terminó con «BAXY arranca: los
activos obligatorios y el runtime registrado son validos». Guardé copia del manifiesto anterior y
`wake_on_start` volvió a `true` como estaba, para no dejarte la máquina distinta de como la
encontré.

Comprobé la carga con las banderas exactas del producto, no inventadas: 3 slots, 4096 por slot,
`/health` en `ok`. VRAM atribuible por delta 3513 MiB, en línea con los 3499 de las tandas de la
réplica y por debajo de la guarda de 3800 y del techo de 4096. Es comprobación de runtime, no una
tanda: sin panel, sin turnos, sin crédito.

## Lo único que necesito de ti

El ZIP privado `C03_OPUS5_RELEVO_PRIVADO.zip` (SHA `95bc3f23…fd8c704`, 2 025 743 bytes), que está en
la réplica en `C:/Users/usuario/AppData/Local/BAXY/C03-opus5-transfer-20260911/`. Lo busqué por nombre
exacto en las seis unidades de aquí: no está. Sin el registro de la encuesta que va dentro no puedo
escribir cobertura ni sellar una tanda nueva, porque los literales exactos de los 742 casos sólo
están ahí y lo que viaja en Git sólo lleva identificadores y estados. Déjalo en cualquier carpeta y
yo lo verifico contra su manifiesto.

## Lo que avancé sin él

La tanda 1025 queda **cerrada en cobertura**: su crédito es 3, los que ya estaban escritos, y no
puede dar más. No es estimación. Las dos conductas que quedaban vivas ya tienen dos de tres y una de
dos variantes caídas, así que no llegan a las dos variantes en pie que exige un crédito, y la única
tanda anterior de la categoría con adjudicación pública, la 998, cubrió aritmética y conversiones,
nada pertinente. Por eso H0236, H0239 y H0582 siguen abiertos pase lo que pase con su literal.

De los 25 casos tengo 14 juzgados: 5 pasan y 9 fallan con causa, en dos clases claras. Hechos
inventados en fichas de juegos: Marvel vs. Capcom fechado en 2000 cuando el estreno original fue
arcade en 1998; Doom Eternal atribuido a Bethesda Game Studios y 2023 cuando es id Software,
Bethesda Softworks y 20 de marzo de 2020; Chell descrita como hombre y Portal como mundos
alternativos. Y referente ausente resuelto inventándolo: H0424, H0645 y la variante inglesa
respondieron hablando de la identidad de BAXY en vez de preguntar de quién se hablaba. Contrasté las
fechas y los estudios con fuentes primarias antes de darlos por fallidos.

De esa segunda clase saqué un diagnóstico que sí pude demostrar sin GPU, ejecutando las funciones
puras: **la ruta de aclaración por referente ausente existe, está sana, y no se alcanza**. El
reconocedor que la dispara sólo cubre órdenes de apertura tipo «ábrelo», así que una pregunta en
tercera persona sin antecedente nunca llega y el modelo hace lo único que puede: suponer que «su» es
él. La reparación mínima es ampliar ese reconocedor y reutilizar la misma ruta, sin capa nueva. No la
escribí porque «su» en español es también tratamiento formal: una regla amplia convertiría
«¿Cuál es su nombre?» dirigido a BAXY en una pregunta innecesaria, y esa categoría tiene 7 casos ya
cubiertos que no pienso perder por ir rápido. La tanda que lo mida necesita controles de segunda
persona y de antecedente presente.

También revisé la reparación 1024 de los avisos con plazo. El diseño es el más simple que resuelve el
caso, pero su diagnóstico no menciona que la función que amplía tiene un segundo uso que hace al
reconocedor abstenerse de producir el efecto: ampliarla amplía también esa abstención. No la integro
sin ver el parche real y sin controles.

## Lo que no hice, a propósito

Ningún crédito nuevo, ningún panel sellado, ninguna tanda ejecutada, ninguna reclasificación de la
encuesta, ninguna prueba, ningún modelo sustituido en silencio. C03 no está completado y no lo
declaro.
