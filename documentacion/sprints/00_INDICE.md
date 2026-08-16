# BAXY por sprints — once prompts para GPT-5.6 Sol

Once prompts. Cada uno se lanza en una sesión nueva con un agente nuevo, en
**GPT-5.6 Sol, `reasoning.effort: high`**. Cuando uno entrega, lanzas el
siguiente.

## Los once

| # | Sprint | Qué entrega |
|---|---|---|
| 01 | **Herencia** | Mapa de los BAXY anteriores y qué se trae de cada uno |
| 02 | Base reproducible | Compuerta verde en un clon limpio |
| 03 | **Comprensión** | La petición llega a la operación o a una pregunta útil |
| 04 | Honestidad | Cero efectos no pedidos, cero éxitos falsos, cero frases fijas |
| 05 | Ejecución verificada | Lo que dice que pasó, pasó |
| 06 | Voz del producto | Todo lo que la persona lee lo formula el modelo |
| 07 | Misiones compuestas | Varias operaciones encadenadas |
| 08 | Primera señal | Nunca hay silencio muerto |
| 09 | Voz y oído | Wake word, transcripción y habla, heredando lo que ya funciona |
| 10 | Uso diario | BAXY usable de verdad |
| 11 | **Validación y cierre** | BAXY aguanta cuando algo va mal — producto terminado |

El 01 va primero porque cambia el trabajo de los otros diez: hay asistentes
anteriores en esta máquina con piezas que ya funcionan. El 09 va casi al final
por decisión del responsable —backend primero—, pero el 01 ya deja localizado lo
que se hereda.

**El 11 es distinto de los otros diez y por eso va aparte.** Del 01 al 10 está
prohibido perseguir lo que *podría* fallar: van rápido a propósito. El 11 invierte
esa regla y se dedica exactamente a eso — los caminos de error, las fragilidades,
la regresión completa sobre el árbol final. Es donde se cobra la deuda que los
diez fueron dejando, y después de él BAXY es un producto terminado.

## Las reglas que llevan los diez

**Permisos totales.** Acceso completo al PC. Descarga, instala, sobrescribe,
borra lo que sobre. **No preguntes.** Si dudas de una suposición, elige la más
razonable y sigue: siempre se puede ajustar después. Sólo hay una excepción, y es
por daño irreversible fuera de BAXY — borrar datos personales del usuario o tocar
otros proyectos de la carpeta `Programacion`. Ahí, y sólo ahí, para y pregunta.

**Un solo criterio: lo mejor para BAXY como producto final.** No lo más rápido de
implementar, no lo que ya estaba, no lo que luce mejor en un informe.

**Cuanto menos consuma, mejor.** 4 GB de VRAM es el techo, no el objetivo. Entre
dos opciones que cumplen, gana la más ligera — RAM, disco, CPU en reposo y
arranque en frío incluidos. El ahorro se detiene donde BAXY deja de entender a la
primera, de no mentir o de no dejar silencio muerto. La máquina de desarrollo
tiene 16 GB de VRAM: eso es holgura para trabajar, no el presupuesto del producto.

**Sólo se arregla lo que bloquea** (sprints 01–10). Un fallo que impide usar BAXY
o avanzar el sprint se arregla. Un fallo que *podría* pasar, una fragilidad
teórica, un camino de error que nadie ha recorrido: se anota en una línea en
`documentacion/APLAZADOS.md` y se sigue. El test: ¿alguien lo ha visto ocurrir, o
va a verlo mañana usando BAXY con normalidad? Si no, no es de ese sprint.

Anotar no es aplazar indefinidamente: `APLAZADOS.md` es la entrada del sprint 11,
que existe para vaciarla. Cada línea acaba arreglada, medida y descartada, o
declarada limitación ambiental con su degradado. Eso es lo que permite que los
diez primeros vayan rápido sin que nada se pierda.

**No investigues de más.** Estos repositorios acumulan documentación extensa:
decisiones de arquitectura, torneos de tecnología, comparativas de modelos. Si ya
está respondido, decide con eso y sigue. Y no recopiles contexto exhaustivo antes
de empezar: lee lo que necesitas para dar el siguiente paso, no todo lo que
existe. Apóyate en lo que ya sabes.

**Termina.** El sprint acaba cuando su resultado está, no cuando se te acaban las
ideas de mejora. Si algo queda imperfecto pero no bloquea, publícalo como está y
cierra.

## Por qué están escritos así

Sol es proactivo y persistente por defecto: reanuda tras un fallo de herramienta
sin que se lo pidan, encadena ediciones y paraleliza cuando le conviene. No
necesita que lo empujen — necesita saber **dónde está la frontera**.

Por eso cada prompt dice el destino y el límite, y no los pasos. Los prompts
escuetos le suben la puntuación; el muro de reglas se la baja. Si un prompt te
parece corto, está bien: lo que falta es andamiaje que a este modelo le estorba.

Cada prompt lleva además **lo que ya se midió y se rechazó**, para que ningún
agente pague dos veces la misma corrida. Eso no es andamiaje: es evidencia.

## Fuera de alcance

No se miden, no cuentan como pendientes, no bloquean ningún sprint: perfil
certificado de 4 GB de VRAM y perfil CPU de 8 GB; instalación limpia, primer
arranque y purge en cuenta desechable; certificado de firma. Detalle en
`documentacion/00_ALCANCE_DESARROLLO_VS_PRODUCTO.md`.

## Invariantes — ningún sprint los re-deriva

1. El catálogo tipado es la única fuente de operaciones. La mente propone, el
   kernel autoriza, el provider ejecuta.
2. Nada se afirma sin verificar.
3. Estados terminales honestos.
4. La confirmación se liga a la invocación exacta.
5. Cero respuestas visibles fijas.
6. Local y privado. Sin nube, sin APIs de pago.

Todo lo demás se re-deriva midiendo en esta máquina.
