# REPAIR1031 — misma reparación, instrucción que ya no se puede publicar

REPAIR1030 midió el primer intento y dejó dos cosas claras: exigir el hecho es correcto —los siete
literales dejaron de atribuirse un lanzamiento que no hicieron y los tres controles cubiertos volvieron
idénticos— y el texto de la instrucción estaba mal. Llegaba como oración declarativa y cuatro de los
siete la publicaron byte a byte, con vocabulario interno («antes de este turno»). Una respuesta visible
fija está prohibida por el invariante 5, así que aquello no acreditó nada.

**Cambio bajo medición:** commit `bfd35802`, `src/baxy_mind/llm.py`.

1. La instrucción de `unstated_already_running` pasa a imperativa corta, al estilo de las demás
   entradas de la lista: «Nombra la app. Di que ya estaba abierta. Nunca digas que la abriste ni que la
   volviste a abrir.» / «Name the app. Say it was already open. Never say you opened, launched or
   reopened it.»
2. El chequeo rechaza además el relanzamiento afirmado sobre un proceso reutilizado, que
   REPAIR1030 dev-02 colaba diciendo el hecho y añadiendo «but I launched it again».

**Ya verificado sin GPU:** `scratchpad/c03-already-running-check.py` pasa los 28 borradores publicados
reales de APPS1029 y REPAIR1030 por la función pura con su `situation` exacta. 0 discrepancias: los
ocho infractores de 1029 rechazados, el relanzamiento afirmado de 1030 rechazado, y las diez respuestas
veraces —incluidos los dos lanzamientos reales de Paint— intactas.

**Lo que sólo puede decir esta tanda:** si con la instrucción imperativa el producto formula frases
distintas entre sí, que nombran el destino y no copian la instrucción. Eso es exactamente lo que
REPAIR1030 falló, y no hay forma pura de comprobarlo.

## Panel: 17 casos, 34 líneas de wire

| Bloque | Casos | Acredita |
|---|---|---|
| Literales de la causa | H0015, H0055, H0134, H0136, H0391, H0418, H0653 | sí, hasta 7 |
| Controles ya cubiertos | H0085, H0315, H0317 | no |
| Variantes de lanzamiento real | dev-01 ES «abrime Paint», dev-02 EN «open Paint» | no |
| Variantes de ya en ejecución | dev-03 ES «abrime el Steam», dev-04 EN «can you open Steam» | no |
| Límites | boundary-01, -02, -03 | nunca |

Criterio idéntico al de REPAIR1030, sin relajar nada, y con lo aprendido escrito antes de ejecutar:
una frase que copie la instrucción, que repita byte a byte la de otro turno o que use vocabulario
interno **falla**, aunque sea veraz. Un terminal sin frase publicada también falla.

Entorno declarado y sellado: Steam, Chrome y Discord ya en ejecución fuera del árbol medido; Paint no en
ejecución al empezar. Pruebas automatizadas, Fast y Full omitidas por instrucción del dueño: omitidas,
no verdes.
