# REPAIR1032 — las dos reparaciones de «Abrir aplicaciones», medidas juntas

Doce literales abiertos, todos fallados en APPS1029 por una de estas dos causas y por ninguna otra.

## Reparación 1 — el hecho «ya estaba en ejecución» es obligatorio

`src/baxy_mind/llm.py`, commit `bfd35802`. `compose_visible_defect` rechaza con
`unstated_already_running` un borrador que se atribuye la apertura cuando el recibo dice que el destino
ya estaba en ejecución y el borrador no lo dice, y también el relanzamiento afirmado sobre un proceso
reutilizado. La instrucción de reintento es imperativa corta, porque en REPAIR1030 la versión
declarativa se publicó literal en cuatro de siete turnos.

Verificado sin GPU sobre los 28 borradores publicados reales de APPS1029 y REPAIR1030:
`scratchpad/c03-already-running-check.py`, 0 discrepancias.

## Reparación 2 — «la app está abierta» no exige que su ventana tenga el foco

`src/Baxy.Providers.Windows/Applications/`: `WindowsApplicationOpenVerifier`,
`WindowsInstalledApplicationOpenProvider` y `WindowsCalculatorOpenProvider` seguían pidiendo el primer
plano como prueba. Ahora lo piden y no lo exigen: la observación es una ventana **visible** del proceso
vinculado por el recibo.

La evidencia es de esta máquina y de estas tandas:

- REPAIR1031 perdió sus diecisiete vueltas —incluidas Steam y Discord, que ocho minutos antes habían
  verificado con recibo— porque «Configuración rápida» de ShellHost.exe tenía el foco y no lo cede.
  Steam, Discord y el Paint recién lanzado estaban visibles en pantalla.
- En APPS1029, `CalculatorApp` pid 40560 arrancó a las 01:50:51 locales, dentro de la ventana de la
  tanda, mientras su recibo devolvía `verification_failed` con `effectMayHaveOccurred=true`.

Compilado por el arranque vigente: `build_exit 0`, `warmup_exit 0`, `shutdown_exit 0`, Core efectivo
igual al publicado, y el producto arrancó y contestó «Hola, ¿en qué puedo ayudarte?». Una compilación
correcta no demuestra conducta: eso lo mide esta tanda.

## Panel: 23 casos, 46 líneas de wire

| Bloque | Casos | Acredita |
|---|---|---|
| Literales de calculadora y configuración | H0251, H0575, H0588, H0683, H0706 | sí |
| Literales de Steam | H0015, H0055, H0134, H0136, H0391, H0418, H0653 | sí |
| Controles ya cubiertos | H0085, H0315, H0317 | no |
| Variantes de lanzamiento real | dev-01 ES Paint, dev-02 ES Mapa de caracteres | no |
| Variantes de ya en ejecución | dev-03 EN Paint, dev-04 ES Steam, dev-05 EN Steam | no |
| Límites | boundary-01 prohibición con consulta, -02 cita ajena, -03 pregunta de capacidad | nunca |

**Crédito máximo condicionado: 12.** Las dos variantes de lanzamiento son españolas y se declara: el
inglés del camino de lanzamiento lo ejercitan los propios literales H0588 y H0683, y la regla de
cobertura pide dos variantes pertinentes de la conducta, no una por idioma. El par de destino ya en
ejecución sí tiene los dos idiomas.

Seis abiertos de la categoría quedan aparcados con razón en el mapa del panel, no rellenados aquí.

## Entorno declarado y sellado

Steam, Chrome y Discord ya en ejecución fuera del árbol medido; Calculator, Configuración, Paint y
Mapa de caracteres **no** en ejecución, para que el camino de lanzamiento se ejercite de verdad; y
ninguna ventana del sistema con el foco, que el runner comprueba antes de arrancar porque eso es lo que
invalidó REPAIR1031.

El presupuesto de GPU está medido: el pico del árbol fue 3494,93 MiB en APPS1029 y 3492,93 MiB en
REPAIR1030 **con Paint lanzado dentro de la tanda**, así que las apps que Windows activa por servicio
no se atribuyen al árbol. La guarda de 3800 MiB sigue intacta.

## Criterio, escrito antes de ejecutar

Al criterio de APPS1029 se le añade lo aprendido: una frase que copie la instrucción interna, que
repita palabra por palabra la de otro turno o que use vocabulario interno **falla aunque sea verdad**,
porque el invariante 5 prohíbe respuestas visibles fijas. Un terminal sin frase publicada falla.
Afirmar un relanzamiento sobre un proceso reutilizado falla.

Pruebas automatizadas, Fast y Full siguen omitidas por instrucción del dueño: omitidas, no verdes.
