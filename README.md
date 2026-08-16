# BAXY

Un asistente local para Windows que se siente como Jarvis de uso diario en un PC
normal.

La persona habla o escribe cualquier cosa —español, inglés o spanglish— y BAXY lo
entiende, lo hace, comprueba que pasó y lo cuenta en una frase. Desde una petición
simple hasta una misión que encadena varias operaciones para lograr lo que ninguna
sola puede.

Todo local. Sin nube, sin APIs de pago, sin enviar datos a ningún lado.

## Las tres cosas que son el producto

La sensación de Jarvis no viene de terminar rápido. Viene de tres cosas, y si
falla una, no hay producto:

1. **Nunca hay silencio muerto.** Primera señal en p50 ≤ 1,0 s. El listón del
   dueño es más crudo: *más de 3 s sin señal y cierro la ventana y lo hago a
   mano*. Lo que mata no es la espera — es el silencio.
2. **Nunca miente.** Nada se afirma sin que un verificador independiente lo
   confirme. Y BAXY actúa sobre el PC: por eso mentir aquí no es un detalle.
3. **Entiende a la primera.** En los tres idiomas, sin depender de las palabras
   exactas del catálogo.

Quién es BAXY, cómo habla, qué nunca hace y qué se decidió sobre catálogo, voz,
accesibilidad y privacidad está en
[`documentacion/00_IDENTIDAD.md`](documentacion/00_IDENTIDAD.md). Es lectura
obligatoria antes de cualquier goal.

## Por dónde se empieza

El trabajo está organizado en **once goals**, uno por prompt, en
[`documentacion/sprints/`](documentacion/sprints/). Cada uno se pega entero en una
sesión nueva y **se deja correr hasta que se cumple**; cuando entrega, se lanza el
siguiente.

Empieza por [`00_INDICE.md`](documentacion/sprints/00_INDICE.md) y luego por el
goal 01.

| # | Goal | Cumplido cuando |
|---|---|---|
| 01 | La herencia | Sabes qué hay construido ya, qué funciona y qué se trae |
| 02 | La base reproducible | La compuerta pasa entera, también en un clon limpio |
| 03 | La comprensión | La petición llega a la operación correcta, o a una pregunta útil |
| 04 | La honestidad | Cero efectos no pedidos, cero éxitos falsos, cero frases fijas |
| 05 | La ejecución verificada | Lo que dice que pasó, pasó — y algo independiente lo comprueba |
| 06 | La voz del producto | Todo lo que la persona lee lo formula el modelo |
| 07 | Las misiones compuestas | Lo que ninguna operación sola logra, encadenando |
| 08 | La primera señal | Nunca hay silencio muerto |
| 09 | La voz y el oído | Oye su nombre, entiende y contesta hablando |
| 10 | El uso diario | BAXY se usa todos los días y no decepciona |
| 11 | La validación y el cierre | Aguanta cuando algo va mal — producto terminado |

Los once llevan dentro las mismas **cinco leyes**: heredar antes que construir,
nada de sobreingeniería, arreglar sólo lo que bloquea, quedarse con la opción más
ligera que cumpla, y dejar cada pieza sustituible —pero sólo las que de verdad se
van a sustituir. Están explicadas en el índice.

## De dónde viene este repositorio

BAXY no empieza de cero. Es la continuación del intento más avanzado, con años de
trabajo previo detrás en otros nombres —Carter, Agent Gemma, Jarvis— que viven en
la misma carpeta y de los que el goal 01 hereda lo que valga.

Lo que se trajo: el código, las pruebas, los programas de experimento, la
documentación y la evidencia viva (el ledger, las auditorías, los sellos ciegos
sin consumir).

Lo que se dejó atrás a propósito: binarios de compilación, modelos descargables,
corpus regenerables y el historial de sesiones de agentes. El repositorio guarda
**fuente y evidencia**, no artefactos que un script puede reconstruir. El
repositorio anterior conserva esa evidencia completa si alguna vez hace falta.

## Arquitectura — lo que no se re-deriva

Seis invariantes. Sobreviven a cualquier cambio de modelo, runtime o
implementación:

1. **El catálogo tipado es la única fuente de operaciones.** Texto, corpus,
   skills, UI, modelos y prompts no pueden agregar una operación ni elevar su
   autoridad. La mente propone, el kernel autoriza, el provider ejecuta.
2. **Nada se afirma sin verificar.** «Se envió el comando» no es «se completó la
   misión».
3. **Estados terminales honestos.** `pending` es sólo reintentable; un efecto
   ambiguo no reintentable es `failed` con `effectMayHaveOccurred`.
4. **La confirmación se liga a la invocación exacta**, no a la intención
   aproximada.
5. **Cero respuestas visibles fijas.** El modelo formula cada mensaje.
6. **Local y privado.** El modelo corre en la máquina. BAXY puede consultar la
   web cuando no sabe algo, pero no envía contenido de la persona a ningún lado —
   la línea es de dirección, no de conexión. Y la persona inspecciona, corrige y
   borra todo lo que BAXY sabe de ella.

Todo lo demás —modelo decisor, cuantización, runtime, recuperador, reconocedor,
planner, wake word, STT, TTS— se re-deriva midiendo en la máquina de destino.

## Presupuesto de recursos

BAXY corre en el PC de una persona normal y compite con lo que esa persona está
haciendo de verdad. **4 GB de VRAM es el techo, no el objetivo**: entre dos
opciones que cumplen, gana siempre la más ligera, contando también RAM, disco,
CPU en reposo y arranque en frío.

El ahorro se detiene donde BAXY deja de cumplir las tres cosas que son el
producto. Un modelo diminuto que no entiende no ahorra recursos: arruina el
asistente.

## Cómo se trabaja aquí

- [`documentacion/00_IDENTIDAD.md`](documentacion/00_IDENTIDAD.md) — qué es BAXY.
  Decisiones tomadas, no preferencias. Léelo primero.
- [`biblioteca/`](biblioteca/00_INDICE.md) — **1.350 documentos** de las cuatro
  escrituras anteriores: estudios, auditorías, investigaciones y rechazos medidos.
  Se busca aquí **antes** de abrir cualquier línea de investigación.
- [`documentacion/sprints/`](documentacion/sprints/) — los once prompts.
- [`documentacion/APLAZADOS.md`](documentacion/APLAZADOS.md) — lo que los goals
  01–10 ven y no persiguen; el 11 lo vacía.
- [`documentacion/00_ALCANCE_DESARROLLO_VS_PRODUCTO.md`](documentacion/00_ALCANCE_DESARROLLO_VS_PRODUCTO.md)
  — qué se mide ahora y qué se difiere.
- [`documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md`](documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md)
  — el registro de todo lo medido, promovido y **rechazado**. Léelo antes de
  proponer una línea: muchas ya se midieron y murieron con el mecanismo
  entendido.
- [`documentacion/02_COMPETIDORES.md`](documentacion/02_COMPETIDORES.md) — contra
  qué compite BAXY y en qué se diferencia.
- [`documentacion/03_COSTURAS.md`](documentacion/03_COSTURAS.md) — las piezas que
  se pueden sustituir y **qué medición decide** el cambio. Es lo que hace que
  mejorar BAXY dentro de dos meses sea una tarde y no una reescritura.

## Compuerta

```powershell
.\scripts\test_source_quality.ps1 -Mode Full
```

Verde antes y después de cada tanda. Toda compuerta en rojo bloquea la entrega,
sin excepción y sin nota al pie.
