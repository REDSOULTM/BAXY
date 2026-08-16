# Goal 02 — La base reproducible

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Acabas cuando los criterios de cierre estén
> marcados, o cuando hayas medido que uno es inalcanzable y publicado la evidencia
> que lo demuestra. No hay una tercera forma de acabar.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY`. Modelo: GPT-5.6 Sol,
`reasoning.effort: high`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Para sólo si vas a tocar datos personales del usuario u
otros proyectos de la carpeta `Programacion`.

No recopiles contexto exhaustivo antes de empezar: lee lo justo para dar el paso
siguiente. Si algo ya está documentado en estos repositorios, decide con eso.

## Qué es BAXY

Un compañero que vive en el PC de una persona y hace lo que le pide —tipo Jarvis,
local y privado—. Tiene carácter propio, es un «él», tutea, y confirma lo que hizo
comprobándolo: *«Listo, Spotify está abierto y sonando»*. Cuando falla lo dice
plano y con la causa. Nunca inventa que hizo algo, nunca actúa sin que se lo
pidan, nunca manda datos del usuario fuera.

Todo está en `documentacion/00_IDENTIDAD.md`, y **es lectura obligatoria antes de
tocar nada**. No son preferencias: son decisiones tomadas por el dueño con los
cuatro intentos anteriores del proyecto sobre la mesa. Si un diseño tuyo las
contradice, el que cambia eres tú.

## Las cinco leyes

Gobiernan este goal y los otros diez. Están por encima de cualquier preferencia
técnica tuya.

**1. Hereda primero, estado del arte después, construye al final.** En ese orden,
y sin saltarte pasos:

1. **¿Ya está resuelto en un BAXY anterior?** Este proyecto se ha escrito cuatro
   veces y muchos problemas ya cayeron. Trae esa solución — o la **mejor
   combinación** de las que hay, que muchas veces es lo que gana. El goal 01 dejó
   el mapa de qué existe y dónde.
2. **¿Está resuelto ahí fuera?** Papers, documentación, repositorios, la respuesta
   de alguien que se topó con lo mismo. Si hay una solución conocida y buena,
   **impleméntala** en vez de inventar la tuya.
3. **Sólo si ninguna de las dos**, constrúyelo. Y entonces di en el cierre por qué
   ninguna servía.

Y al revés: **que BAXY ya lo haga de una manera no es razón para conservarla.** La
vara es «¿es la mejor opción conocida hoy?», no «¿es lo que había?». Heredar es
traer lo que funciona, no conservar lo que estaba.

Es una pasada, no una persecución. En cuanto tengas algo que cumple el objetivo,
deja de buscar mejor: perseguir el estado del arte sin parar es una carrera sin
final, y este producto tiene que salir.

**2. Nada de sobreingeniería.** Escribe el mínimo código que cumpla, y que se
active sólo el necesario. Nada de capa sobre capa, ni abstracciones para un
segundo caso que no existe, ni opciones que nadie pidió, ni defensas para fallos
que nadie ha visto ocurrir.

No es estética: es la causa de muerte documentada de las cuatro versiones
anteriores de este mismo proyecto. Carter se diagnosticó a sí mismo —*«el proyecto
crece por acumulación, no por reemplazo»*— con tres routers en serie, ocho capas
de reescritura y un `agent.py` de 1.397 líneas contra su propio objetivo de 400.
Diez de sus dieciséis segundos por turno eran sobrecarga suya.

**Si añades una capa, retira la que sustituye, en este mismo goal.** Un goal que
cierra con menos código del que encontró y el objetivo cumplido es mejor goal.

**3. Sólo se arregla lo que bloquea.** Un fallo que impide usar BAXY o avanzar
este goal se arregla. Una fragilidad teórica o un camino de error que nadie ha
recorrido: una línea en `documentacion/APLAZADOS.md` y sigues. El goal 11 existe
para vaciar esa lista, así que nada se pierde por anotarlo.

**4. Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo. Entre
dos opciones que cumplen gana la más ligera, contando RAM, disco, CPU en reposo y
arranque en frío. El ahorro se detiene donde BAXY deja de entender a la primera,
de no mentir o de no dejar silencio muerto.

**5. Cada pieza sustituible, y ninguna más.** BAXY no se termina. Dentro de dos
meses saldrá un STT mejor o un modelo más pequeño que entiende igual, y hay que
poder cambiarlo sin reescribir el producto: **el código de hoy no tiene por qué ser
el de mañana**.

Pero «que todo sea intercambiable» es la puerta directa a la sobreingeniería que
prohíbe la ley 2 —interfaces con un solo implementador, registros de plugins,
configuración infinita—, y así murieron las cuatro versiones anteriores. La regla
que resuelve las dos: **una costura por pieza que de verdad se vaya a sustituir, y
ninguna más.** La lista está cerrada y vive en `documentacion/03_COSTURAS.md`; no
la amplías sobre la marcha.

Y una costura no es una interfaz. Son tres cosas, y sin las tres la pieza no es
sustituible:

1. **Un borde que nombra qué hace, no cómo.** El kernel no sabe que Windows existe;
   ése es el modelo, y ya funciona en este repositorio.
2. **La medición que decide si el candidato es mejor.** Esto es lo que de verdad
   hace sustituible una pieza: con un corpus y un número, cambiar de motor es una
   tarde; con una interfaz y sin número no puedes decidir, así que no lo cambias
   nunca.
3. **Que instalar lo nuevo incluya retirar lo viejo.**

**Cero código muerto.** Una pieza sustituida se borra: no se queda detrás de una
bandera «por si acaso». Dos implementaciones vivas de lo mismo son la acumulación
otra vez, con otro nombre.

Si este goal toca una pieza del registro, **rellena su fila antes de cerrar**: qué
medición decide un sustituto, qué elegiste y por qué, y la fecha. La fecha importa
— una medición de hace ocho meses decidió entre candidatos que hoy ya no son los
mejores.

## Y una consigna que une las cinco

Ésta es la **quinta** escritura de BAXY, y tiene que ser **la más rápida de las
cinco**. No porque haga menos —es la definitiva— sino porque **no vuelve a
descubrir nada que ya se descubrió**.

Cada hora que gastes re-derivando algo que ya está medido en estos repositorios es
una hora que este proyecto ya pagó una vez. Si te encuentras diseñando desde cero
algo que suena a que alguien ya resolvió, para y ve a buscarlo primero.

---

## El objetivo

**La compuerta `.\scripts\test_source_quality.ps1 -Mode Full` pasa entera, y pasa
también en un clon recién hecho de este repositorio.**

Eso es todo. Es la base sobre la que se apoyan los nueve goals siguientes: sin
ella, cada medición posterior se hace sobre un árbol que no se puede reproducir, y
un número que no se puede reproducir no es un número.

Es el goal más corto de los once. Trátalo así: entra, arregla, cierra. Si te ves
rediseñando algo, te has salido del goal.

## Dónde está hoy — la mitad del trabajo ya está hecha

Quince pruebas rojas, todas diagnosticadas. Su causa está publicada en R279 y
R280; léela antes de empezar:

- **Nueve** comparan un preregistro histórico contra lo que su constructor
  regenera hoy. Como el constructor lee el catálogo vivo, cualquier cambio legítimo
  del catálogo las rompe para siempre. La decisión de disciplina ya está tomada y
  escrita en el §7 de la meta: *un preregistro sellado se audita por la integridad
  de su sello, no por su regeneración desde el árbol presente.* Aplícala. Verifica
  el hash publicado del artefacto; no omitas la prueba.
- **Una** falta un artefacto (`bge_m3_operation_recovery_r160_attested.json`).
- **Una** exige un checkpoint binario que no está en la máquina. Descárgalo.
- **Una** es no determinista:
  `test_dispatch_crash_exits_while_redirected_stdin_remains_open` falla por
  contención en `process.wait(timeout=3.0)` y pasa 5 de 5 aislada. Arréglala
  quitando la dependencia del reloj de pared, no subiendo el número.
- **Tres** tienen causa propia: recibos de V8, `product_packaging`, y el árbol WPF
  del torneo.

Hay además un defecto de reproducibilidad que conviene cerrar de paso: un test
.NET reescribe un artefacto versionado a partir de un fichero que `.gitignore`
excluye, así que sus números dependen del estado local de la máquina.

## Dos avisos que ahorran horas

**Los finales de línea ya rompieron esta compuerta una vez.** `core.autocrlf` con
un `.gitattributes` incompleto reventó tres etapas independientes a la vez,
porque los sellos SHA-256 se calculan sobre los bytes en disco. Si ves fallos de
sello en masa, mira ahí antes que al código.

**No redirijas stderr de un ejecutable nativo dentro de PowerShell 5.1.** Lo
envuelve en un `NativeCommandError` y te inventa un rojo sobre un proceso que
devolvió 0. Ya pasó, y costó una investigación entera.

## Cómo se arreglan los defectos

De verdad: nada de bajar el umbral que lo detectó, marcar `skip`/`xfail`, mover a
pendientes ni envolverlo en un fallback. Un rojo tapado es peor que un rojo, porque
miente sobre el estado del producto.

Y aplica la ley 2 mientras lo haces: si un arreglo te pide una capa nueva, casi
seguro es que hay una capa vieja que sobra.

## Criterios de cierre

- [ ] La compuerta pasa **entera** dos veces seguidas sobre un árbol congelado.
- [ ] Pasa una tercera vez sobre un **clon limpio** del repositorio.
- [ ] Ningún rojo se cerró con `skip`, `xfail`, umbral relajado ni fallback.
- [ ] El artefacto .NET dependiente del estado local ya no lo es, o está declarado
      con su causa.
- [ ] Registro de qué cambiaste y por qué, prueba por prueba.

## Cuando lo cumplas

La compuerta verde, y el registro. Si algo resulta irreparable por una causa fuera
del código de BAXY, dilo con su evidencia y sigue con el resto — una limitación
nombrada no bloquea el cierre; una oculta sí.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
