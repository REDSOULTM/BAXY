# REPAIR1033 — la dirección espejo, y el criterio de frase fija dicho con precisión

Ocho literales abiertos: los siete de Steam que REPAIR1032 dejó veraces y sin crédito, más H0575, que
destapó el defecto contrario.

## Reparación bajo medición

`src/baxy_mind/llm.py`. `compose_visible_defect` ya rechazaba atribuirse una apertura que el recibo
niega; ahora rechaza también el defecto espejo con el código `invented_prior_open_state`: con el recibo
diciendo `alreadyRunning=false`, dar por anterior un estado que el turno acaba de crear. Es lo que hizo
H0575 en REPAIR1032 con «Ya tengo la calculadora abierta.» sobre una calculadora que acababa de abrir.

Sólo cuentan las afirmaciones inequívocas de estado anterior —«ya estaba», «ya la tenía», «was already
running»—. «Ya está abierta» justo después de abrirla es cierto sobre el presente y se queda fuera a
propósito.

**Verificado sin GPU:** `scratchpad/c03-open-state-check.py` pasa los **48 borradores publicados reales**
de APPS1029, REPAIR1030 y REPAIR1032 por la función pura con su `situation` exacta. 0 discrepancias: los
ocho que se atribuían la apertura y el relanzamiento afirmado siguen rechazados, H0575 queda rechazado
por la dirección nueva, y las veintitantas respuestas veraces —incluidos los tres lanzamientos reales—
siguen limpias.

## El criterio de frase fija, estrechado antes de ejecutar y con su coste dicho

REPAIR1032 selló que una frase que **repita palabra por palabra la de otro turno** falla aunque sea
verdad, y por eso los siete literales de Steam no cobraron: publicaron «La app Steam ya estaba abierta.»
las siete veces. Esa lectura no la puede arreglar ninguna reparación: con temperatura 0, un payload
idéntico y siete literales que sólo difieren en tildes y signos, el modelo **no puede** producir siete
frases distintas. Aquella lectura convertía ocho filas en incobrables por una razón que no es del
producto.

Aquí se estrecha, antes de ejecutar y con el motivo escrito:

- Falla la frase que **reproduce la instrucción interna** de reintento, o que usa vocabulario interno
  —«turno», «payload», códigos de contrato—. Eso es lo que ocurrió en REPAIR1030 y por eso se rechazó.
- Falla la frase que no nombra el destino cuando la petición lo nombra.
- Falla el terminal sin frase publicada.
- **No** falla por sí sola la coincidencia entre turnos cuyo literal sellado y cuyo recibo observado son
  los mismos. El invariante 5 prohíbe respuestas visibles **fijadas por código**; el modelo formula estas
  y el camino de reintento existe justamente para corregir un borrador.

REPAIR1032 conserva sus veredictos: no se reabren. Lo que cambia se declara aquí, se paga con lo que ya
costó —siete créditos— y queda a la vista del dueño.

## Panel: 19 casos, 38 líneas de wire

| Bloque | Casos | Acredita |
|---|---|---|
| Literales de Steam ya en ejecución | H0015, H0055, H0134, H0136, H0391, H0418, H0653 | sí |
| Literal del defecto espejo | H0575 | sí |
| Controles cubiertos del camino ya-en-ejecución | H0085, H0315, H0317 | no |
| Controles cubiertos del camino de lanzamiento | H0251 calculadora, H0706 configuración | no |
| Variantes | dev-01 ES Paint lanzamiento, dev-02 EN Paint ya abierto, dev-03 ES Steam, dev-04 EN Steam | no |
| Límites | boundary-01 prohibición con consulta, boundary-02 cita ajena | nunca |

**Crédito máximo condicionado: 8.** Cinco filas ya cubiertas entran como control de no regresión y no
cobran dos veces; si la dirección nueva rompiera un lanzamiento veraz, H0251 y H0706 lo enseñarían aquí.

## Entorno declarado y sellado

Steam, Chrome y Discord ya en ejecución fuera del árbol medido —el árbol de Steam gasta 644,39 MiB de GPU
dedicada y dentro rompería la guarda de 3800—; Calculator, Configuración y Paint **no** en ejecución,
para que H0575, H0251, H0706 y dev-01 ejerciten lanzamientos reales; y ninguna ventana del sistema con el
foco, que el runner comprueba porque eso invalidó REPAIR1031.

Pruebas automatizadas, Fast y Full siguen omitidas por instrucción del dueño: omitidas, no verdes.
