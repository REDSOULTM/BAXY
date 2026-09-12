# REPAIR1030 — medir la reparación del hecho «ya estaba en ejecución»

Reparación dirigida, no panel nuevo. En APPS1029 los once turnos de `app.open` sobre un destino ya en
ejecución recibieron **el mismo payload**, con `was_running_before_open: true`, y la prosa publicó el
hecho en tres y lo omitió en ocho, afirmando un lanzamiento que el producto no hizo. La causa exacta
está en `APPS1029/DIAGNOSIS.md`: ese hecho no estaba en ninguna lista obligatoria, así que omitirlo era
legal.

**Cambio bajo medición:** commit `27a1f231`, `src/baxy_mind/llm.py`. `compose_visible_defect` rechaza
con el código `unstated_already_running` un borrador que se atribuye la apertura cuando el recibo dice
que el destino ya estaba en ejecución y el borrador no lo dice, con su instrucción de reintento en los
dos idiomas. No se añade capa: se usa la misma lista de defectos que ya rechazaba
`missing_failure`. No se toca el prompt, ni el muestreo, ni el catálogo, ni el reconocedor.

**Ya verificado sin GPU:** `scratchpad/c03-already-running-probe.py` pasa los catorce borradores
publicados reales de APPS1029 por la función pura con su `situation` exacta: los ocho infractores
quedan rechazados y los seis fieles siguen limpios, incluido el lanzamiento real de Paint con
`alreadyRunning: false`. 0 discrepancias.

**Lo que la sonda no puede decir, y es la razón de esta tanda:** que tras el rechazo el producto
publique una frase útil en vez de agotar reintentos. Por eso el criterio sellado dice explícitamente
que un terminal sin frase publicada **falla**.

## Panel: 17 casos, 34 líneas de wire

| Bloque | Casos | Acredita |
|---|---|---|
| Literales fallados por esta causa | H0015, H0055, H0134, H0136, H0391, H0418, H0653 | sí, hasta 7 |
| Controles de no regresión ya cubiertos | H0085, H0315, H0317 | no: ya están cubiertos, no se acreditan dos veces |
| Variantes de lanzamiento real | dev-01 ES «abrime Paint», dev-02 EN «open Paint» | no |
| Variantes de destino ya en ejecución | dev-03 ES «abrime el Steam», dev-04 EN «can you open Steam» | no |
| Límites | boundary-01 prohibición con consulta, -02 cita ajena, -03 pregunta de capacidad | nunca |

Los tres controles son las tres respuestas que hoy son veraces. Si la reparación las rompiera, se ve
aquí y no en la siguiente categoría. Su fila queda cubierta antes y después: **crédito máximo 7**, no
10.

Entorno declarado y sellado antes de ejecutar, como en APPS1029: Steam, Chrome y Discord ya estaban en
ejecución fuera del árbol medido —el árbol de Steam gasta 644,39 MiB de GPU dedicada y dentro del árbol
rompería la guarda de 3800 MiB—; Paint **no** estaba en ejecución, así que dev-01 ejercita un
lanzamiento real y dev-02 el estado ya en ejecución del mismo destino.

Sin fixtures, sin valores prefijados y sin frases esperadas. Material sellado antes de ejecutar; los
criterios no se cambian después de ver resultados. Pruebas automatizadas, Fast y Full siguen omitidas
por instrucción del dueño: omitidas, no verdes.
