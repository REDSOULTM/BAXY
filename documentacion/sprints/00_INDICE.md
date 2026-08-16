# BAXY en once goals

Once goals. Cada uno se lanza en una sesión nueva, se pega entero, y **se deja
correr hasta que se cumple**. Cuando uno entrega, lanzas el siguiente.

Escritos para **GPT-5.6 Sol, `reasoning.effort: high`**.

## Los once

| # | Goal | Cumplido cuando |
|---|---|---|
| 01 | **La herencia** | Sabes qué hay construido ya, qué funciona de verdad y qué se trae |
| 02 | La base reproducible | La compuerta pasa entera, también en un clon limpio |
| 03 | **La comprensión** | La petición llega a la operación correcta, o a una pregunta útil |
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
- **El catálogo se consolida** —una herramienta hace una cosa, lo demás se
  encadena— y el criterio es **cubrir el PC, no las apps**. El número y la forma
  los mide el goal 03; los huecos los cierra el 07.
- **Buscar en la web está permitido**; enviar contenido del usuario, no.

## Las cuatro leyes

Van dentro de los once prompts, idénticas. Son lo que evita que este intento acabe
como los cuatro anteriores.

**1. Apunta al estado del arte, una sola vez.** Antes de escribir código para un
problema, averigua si ya está resuelto ahí fuera —papers, documentación,
repositorios, la respuesta de alguien que se topó con lo mismo— y si hay una
solución conocida y buena, impleméntala. Y al revés: **que BAXY ya lo haga de una
manera no es razón para conservarla**; la vara es «¿es la mejor opción conocida
hoy?». Pero es una pasada, no una persecución: en cuanto algo cumple el objetivo,
se deja de buscar mejor.

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

Sol es proactivo y persistente por defecto: reanuda tras un fallo de herramienta
sin que se lo pidan, encadena ediciones y paraleliza cuando le conviene. No
necesita que lo empujen — necesita saber **dónde está la frontera** y **cuándo ha
terminado**. Por eso cada prompt dice el destino, el límite y los criterios de
cierre, y no los pasos.

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
