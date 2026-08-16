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
obligatoria antes de cualquier sprint.

## Por dónde se empieza

El trabajo está organizado en **once sprints**, uno por prompt, en
[`documentacion/sprints/`](documentacion/sprints/). Cada uno se lanza en una
sesión nueva con un agente nuevo; cuando entrega, se lanza el siguiente.

Empieza por [`00_INDICE.md`](documentacion/sprints/00_INDICE.md) y luego por el
sprint 01.

| # | Sprint | Qué entrega |
|---|---|---|
| 01 | Herencia | Mapa de los BAXY anteriores y qué se trae de cada uno |
| 02 | Base reproducible | Compuerta verde en un clon limpio |
| 03 | Comprensión | La petición llega a la operación o a una pregunta útil |
| 04 | Honestidad | Cero efectos no pedidos, cero éxitos falsos, cero frases fijas |
| 05 | Ejecución verificada | Lo que dice que pasó, pasó |
| 06 | Voz del producto | Todo lo que la persona lee lo formula el modelo |
| 07 | Misiones compuestas | Varias operaciones encadenadas |
| 08 | Primera señal | Nunca hay silencio muerto |
| 09 | Voz y oído | Wake word, transcripción y habla |
| 10 | Uso diario | BAXY usable de verdad |
| 11 | Validación y cierre | BAXY aguanta cuando algo va mal |

## De dónde viene este repositorio

BAXY no empieza de cero. Es la continuación del intento más avanzado, con años de
trabajo previo detrás en otros nombres —Carter, Agent Gemma, Jarvis— que viven en
la misma carpeta y de los que el sprint 01 hereda lo que valga.

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
- [`documentacion/sprints/`](documentacion/sprints/) — los once prompts.
- [`documentacion/APLAZADOS.md`](documentacion/APLAZADOS.md) — lo que los sprints
  01–10 ven y no persiguen; el 11 lo vacía.
- [`documentacion/00_ALCANCE_DESARROLLO_VS_PRODUCTO.md`](documentacion/00_ALCANCE_DESARROLLO_VS_PRODUCTO.md)
  — qué se mide ahora y qué se difiere.
- [`documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md`](documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md)
  — el registro de todo lo medido, promovido y **rechazado**. Léelo antes de
  proponer una línea: muchas ya se midieron y murieron con el mecanismo
  entendido.
- [`documentacion/02_COMPETIDORES.md`](documentacion/02_COMPETIDORES.md) — contra
  qué compite BAXY y en qué se diferencia.

## Compuerta

```powershell
.\scripts\test_source_quality.ps1 -Mode Full
```

Verde antes y después de cada tanda. Toda compuerta en rojo bloquea la entrega,
sin excepción y sin nota al pie.
