# BAXY en once goals

Once goals. Cada uno se lanza en una sesión nueva, se pega entero, y **se deja
correr hasta que se cumple**. Cuando uno entrega, lanzas el siguiente.

## Con qué modelo se lanza cada uno

| Goals | Modelo | Dónde |
|---|---|---|
| **01–11** | **Grok 4.6**, esfuerzo `high` | Esta carpeta. Son los que están en uso. |
| **03C** | **Grok 4.6** | Esta carpeta. Cierra el alcance y los restos antes del 04. |
| 03B (cerrado) | Se abrió con GPT-5.6 Sol y se cerró con Grok 4.6 | Esta carpeta. El 90 % se midió; el alcance no. |
| 01–04 (versión anterior) | GPT-5.6 Sol, `reasoning.effort: high` | [`sol/`](sol/). Archivo, no se lanzan. |

**Sobre el 03B.** El goal 03 cerró en 46 % con el 90 % **medido inalcanzable**.
El 03B movió el techo y el producto llegó a **112/124 (mediana de tres
corridas)** el 2026-08-21. Lo que **no** cerró es el alcance: 12–15 de 36
fuera de catálogo `acted` (listón ≤5) y 12 filas in-catalog aún fallan.
Detalle en
[`documentacion/base/03B_COMPRENSION_TECHO.md`](../base/03B_COMPRENSION_TECHO.md)
§12.

**El 03C va después del 03B y antes del 04.** No se pasa al 04 con esa
deuda. Prompt y criterios:
[`03C_ALCANCE.md`](03C_ALCANCE.md).

**Cómo se lanza uno.** Sesión nueva y limpia, `/effort high`, y el goal pegado
entero con `/goal` delante: Grok trabaja por rondas y **no lo da por cumplido hasta
que una revisión de evidencia independiente reproduce el resultado**; si no puede
reproducirlo, el goal sigue abierto con los huecos nombrados. Eso es exactamente el
invariante 2 aplicado al agente. `/goal status` para ver dónde está. Una sesión por
goal, no una sesión para todo el día.

**El contenido no cambia entre versiones**: mismo objetivo, misma evidencia
heredada, mismos criterios de cierre. Lo que cambia es el bloque «Cómo trabajas
aquí» de cada goal. Detalle de las versiones anteriores en
[`sol/00_LEEME.md`](sol/00_LEEME.md).

## Los once

| # | Goal | Cumplido cuando |
|---|---|---|
| 01 | **La herencia** | Sabes qué hay construido ya, qué funciona de verdad y qué se trae |
| 02 | La base reproducible | La compuerta pasa entera, también en un clon limpio |
| 03 | **La comprensión** | La petición llega a la operación correcta, o a una pregunta útil |
| 03B | **Romper el techo** | El 90 % que el 03 midió inalcanzable — cambiando la arquitectura que lo limita |
| 03C | **Cerrar el alcance** | ≤5/36 fuera de catálogo `acted` sin bajar de 112/124; las 12 in-catalog restantes no se aplazan al 04 |
| 04 | La honestidad | Cero efectos no pedidos, cero éxitos falsos, cero frases fijas |
| 05 | La ejecución verificada | Lo que dice que pasó, pasó — y algo independiente lo comprueba |
| 06 | La voz del producto | Todo lo que la persona lee lo formula el modelo, y está bien escrito |
| 07 | Las misiones compuestas | Lo que ninguna operación sola logra, encadenando |
| 08 | La primera señal | Nunca hay silencio muerto |
| 09 | La voz y el oído | Oye su nombre, entiende y contesta hablando |
| 10 | El uso diario | BAXY se usa todos los días y no decepciona |
| 11 | **La validación y el cierre** | Aguanta cuando algo va mal — producto terminado |

El 01 va primero porque cambia el trabajo de los otros diez: hay asistentes
anteriores en esta máquina con piezas que ya funcionan. El 09 va casi al final por
decisión del dueño —backend primero—, pero el 01 ya deja localizado lo que se
hereda.

**El 11 es distinto y por eso va aparte.** Del 01 al 10 está prohibido perseguir lo
que *podría* fallar: van rápido a propósito. El 11 invierte esa regla y se dedica
exactamente a eso — los caminos de error, las fragilidades, la regresión completa
sobre el árbol final. Es donde se cobra la deuda que los diez fueron dejando.

## Antes de nada: la identidad

`documentacion/00_IDENTIDAD.md` es **lectura obligatoria de todos los goals**, y va
dentro de cada prompt por eso. No son preferencias: son decisiones tomadas por el
dueño del producto, con los cuatro intentos anteriores sobre la mesa. Si una
decisión de diseño de un agente la contradice, la que cambia es la del agente.

Tres de esas decisiones cambian goals concretos:

- **La accesibilidad es central en el motor y modo en la interfaz.** Todo lo que
  BAXY hace se puede pedir por voz, y BAXY narra lo que hace. No se construye el
  producto y se le añade accesibilidad después.
- **El catálogo: máxima cobertura con el mínimo número de herramientas.** No es
  consolidar: la cobertura no baja nunca, y con la cobertura intacta gana el número
  menor. Se publican **dos números, no uno**. El criterio de qué entra es **cubrir
  el PC, no las apps**; lo que no cabe en una herramienta se **encadena**, que
  amplía cobertura sin añadir catálogo. Lo mide el goal 03 junto con el 07.
- **Buscar en la web está permitido**; enviar contenido del usuario, no.

Y una decisión ya tomada que ahorra un goal entero de deliberación: **la
infraestructura .NET se conserva**. Está auditada —0 advertencias con
`TreatWarningsAsErrors`, 3.865 pruebas verdes, dependencias sin ciclos, AOT y JSON
por generador— y se hereda arreglando tres deficiencias concretas que el goal 01
detalla: los adaptadores por aplicación, `MainWindowViewModel` (3.678 líneas) y los
ocho constructores de `MissionEngine`.

## Las cinco leyes

Van dentro de los once prompts, idénticas. Son lo que evita que este intento acabe
como los cuatro anteriores.

**1. Hereda primero, estado del arte después, construye al final.** En ese orden:
¿lo resolvió ya un BAXY anterior? — entonces trae esa solución, o la **mejor
combinación** de las que hay, buscándola en
[`biblioteca/`](../../biblioteca/00_INDICE.md), donde están los 1.350 documentos de
las cuatro escrituras anteriores. ¿Está resuelto ahí fuera? — entonces impleméntalo en
vez de inventarlo. Construir es el último recurso, y hay que decir por qué. Y al
revés: **que BAXY ya lo haga de una manera no es razón para conservarla**; heredar
es traer lo que funciona, no conservar lo que estaba. Es una pasada, no una
persecución: en cuanto algo cumple, se deja de buscar mejor.

**2. Nada de sobreingeniería.** El mínimo código que cumpla, y que se active sólo
el necesario. Nada de capa sobre capa, ni abstracciones para un segundo caso que no
existe, ni defensas para fallos que nadie ha visto. **Si se añade una capa, se
retira la que sustituye, en el mismo goal.**

**3. Sólo se arregla lo que bloquea** (goals 01–10). Lo demás, una línea en
`documentacion/APLAZADOS.md` y adelante. El goal 11 existe para vaciar esa lista,
así que nada se pierde por anotarlo.

**4. Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo. Entre
dos opciones que cumplen gana la más ligera —RAM, disco, CPU en reposo y arranque
en frío incluidos—. El ahorro se detiene donde BAXY deja de entender a la primera,
de no mentir o de no dejar silencio muerto. La máquina de desarrollo tiene 16 GB de
VRAM: eso es holgura para trabajar, no el presupuesto del producto.

**5. Arquitectura modular: cada pieza sustituible.** BAXY no se termina — dentro de
dos meses saldrá algo mejor y hay que poder cambiarlo sin reescribir el producto.
Va en **dos niveles**, y confundirlos es lo que produce sobreingeniería:

- **Nivel 1, la forma — aplica a todo BAXY y no cuesta nada.** Una responsabilidad
  por pieza, nadie conoce las tripas de nadie, las dependencias apuntan hacia
  dentro, nada global y mutable, **cero código muerto**. Sin esto nada es
  sustituible jamás; con esto, todo lo es.
- **Nivel 2, el mecanismo de cambio — cuesta trabajo, así que se le pone a las
  piezas que de verdad se van a comparar** contra un candidato: la **medición que
  decide** y la declaración en el manifiesto. Están en
  [`documentacion/03_COSTURAS.md`](../03_COSTURAS.md).

La medición es la parte que suele faltar y la que de verdad importa: con un corpus
y un número, cambiar de motor es una tarde; con una interfaz preciosa y sin número
no puedes decidir si mejoraste, así que no lo cambias nunca. Lo que **no** se
escribe: interfaces con un solo implementador «por si acaso», registros de plugins,
configuración para elegir entre implementaciones que no existen.

**Y la consigna que une las cinco:** ésta es la **quinta** escritura de BAXY y
tiene que ser **la más rápida de las cinco**. No porque haga menos —es la
definitiva— sino porque **no vuelve a descubrir nada que ya se descubrió**. Cada
hora gastada re-derivando algo ya medido en estos repositorios es una hora que el
proyecto ya pagó una vez.

## Las reglas de conducta

**Permisos totales.** Acceso completo al PC. Descarga, instala, sobrescribe, borra
lo que sobre. **No preguntes.** Si dudas de una suposición, elige la más razonable
y sigue. Una sola excepción, por daño irreversible fuera de BAXY: borrar datos
personales del usuario o tocar otros proyectos de la carpeta `Programacion`.

**Un solo criterio: lo mejor para BAXY como producto final.** No lo más rápido de
implementar, no lo que ya estaba, no lo que luce mejor en un informe.

**No investigues de más.** Estos repositorios acumulan documentación extensa. Si ya
está respondido, decide con eso. Y no recopiles contexto exhaustivo antes de
empezar: lee lo justo para dar el paso siguiente.

**Termina.** El goal acaba cuando sus criterios de cierre están marcados, o cuando
uno se ha medido inalcanzable y se ha publicado la evidencia. No cuando se acaban
las ideas de mejora.

## Por qué están escritos así

Un agente de código moderno es proactivo y persistente por defecto: reanuda tras un
fallo de herramienta, encadena ediciones y no necesita que lo empujen. Lo que
necesita saber es **dónde está la frontera** y **cuándo ha terminado**. Por eso cada
prompt dice el destino, el límite y los criterios de cierre, y no los pasos.

**Y por eso los goals no repiten lo que el modelo ya trae de fábrica.** El prompt de
sistema de Grok 4.6 ya le ordena mantener a la vista todos los requisitos explícitos
hasta cumplirlos, no afirmar que algo está hecho o probado sin salida de herramienta
que lo sostenga, no ampliar el encargo, y responder en vez de devolver una pregunta
cuando la respuesta está en el contexto. Repetírselo no lo refuerza: gasta sitio y le
dice cosas que ya cree. Lo que sí llevan los goals es el bloque **«Cómo trabajas
aquí»**: las tools, la shell, el esfuerzo, los subagentes y dónde se deja el estado
—que es lo que el harness no le dice—.

Las versiones anteriores llevaban además un bloque de tendencias por modelo. **El de
Grok no está escrito porque no está medido**, y aquí no se escriben bloques por
intuición: la sesión que cerró el 03B está en disco, con 976 mensajes, en
`~/.grok/sessions/`, y ése es el sitio donde se mide antes de escribirlo.

Cada prompt lleva además **lo que ya se midió y se rechazó**, para que ningún
agente pague dos veces la misma corrida. Eso no es andamiaje: es evidencia.

## Fuera de alcance

No se miden, no cuentan como pendientes, no bloquean ningún goal: perfil
certificado de 4 GB de VRAM y perfil CPU de 8 GB; instalación limpia, primer
arranque y purge en cuenta desechable; certificado de firma. Detalle en
`documentacion/00_ALCANCE_DESARROLLO_VS_PRODUCTO.md`.

## Invariantes — ningún goal los re-deriva

1. El catálogo tipado es la única fuente de operaciones. La mente propone, el
   kernel autoriza, el provider ejecuta.
2. Nada se afirma sin verificar.
3. Estados terminales honestos.
4. La confirmación se liga a la invocación exacta.
5. Cero respuestas visibles fijas.
6. Local y privado. El modelo corre en la máquina, sin nube y sin APIs de pago.
   BAXY **sí puede consultar la web** cuando no sabe algo; lo que no puede es
   enviar contenido del usuario. La línea es de dirección, no de conexión.

Todo lo demás se re-deriva midiendo en esta máquina.
