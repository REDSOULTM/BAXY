# BAXY — arreglar sólo lo que impide usarlo, sin voz ni STT

Eres el agente responsable de BAXY, en `D:\BAXY\source`. Lee **`goal.md`** entero
antes de tocar nada.

Este prompt **no te da un diagnóstico ni un orden de trabajo**. Deliberadamente.
El diagnóstico lo haces tú, sobre el sistema entero, y lo justificas con tus
propias mediciones.

---

## La barra de esta pasada

**Arregla lo que impide usar BAXY. Nada más.**

El criterio para decidir si algo entra: *¿una persona que se sienta hoy delante
de BAXY se topa con esto y no puede seguir, o deja de fiarse?* Si la respuesta es
sí, es tuyo. Si es un caso raro, una cifra de rigor estadístico o un defecto
cosmético, **no lo trabajes en esta pasada** — pero tampoco lo cierres.

Y una segunda mitad del mismo encargo: **quita lo que sobra.** Cada mecanismo que
no se gana su sitio cuesta latencia, cuesta superficie donde esconder defectos y
encarece el siguiente cambio. Audita el sistema buscando sobreingeniería y
retírala.

## Reglas que no negocias

- **No cierres nada aparcándolo.** El §6 de `goal.md` prohíbe cerrar un defecto
  moviéndolo a pendientes. Lo que despriorizas sigue **abierto y contado** en
  `known_defects_open`.
- **No declares la meta cumplida.** Con voz y STT fuera de tu alcance, y con
  defectos aparcados a propósito, el §7 no puede cerrarse. Dilo en cada informe.
- **Quitar se mide igual que añadir.** No borres un mecanismo porque «parece de
  más». Tásalo primero —qué caza, y qué se rompería sin él— sobre las poblaciones
  ya consumidas, y publica el resultado aunque salga que hay que conservarlo.
  Criterio: **un mecanismo se queda si puedes nombrar una fila de una población
  consumida donde cambia el resultado.**

## Alcance excluido

**Voz, wake word y STT son del dueño.** No abras esas campañas, no toques sus
corpus, no cuentes sus defectos como tuyos.

---

## Cómo empiezas: diagnostica tú

**Antes de proponer un solo cambio, produce tu propio diagnóstico** y publícalo
con sus mediciones. Que tu primera tanda sea entender, no arreglar.

Las fuentes están todas en el repositorio:

| Qué | Dónde |
|---|---|
| Defectos abiertos, enumerados | `artifacts/fixes/integral_review_ledger_20260811.json` → `known_defects_open` |
| Historia completa de la campaña | `documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md` (va por **R135**) |
| Estado y criterios de cierre | `documentacion/00_META_VIGENTE.md`, `documentacion/00_MVP_CONSOLIDADO_2026-08-11.md` |
| Recibos de medición | `artifacts/development/`, `artifacts/product/`, `artifacts/holdout/` |
| Instrumentos ya escritos | `experiments/mind_router_spike/`, `scripts/` |

**Lee el registro como evidencia, no como veredicto.** Contiene las conclusiones
de agentes anteriores, y algunas fueron **refutadas por mediciones posteriores de
la misma campaña**. Cuando una entrada afirme dónde está un problema, trátalo
como hipótesis que puedes reproducir o tirar. Lo que sí es fiable ahí son los
**recibos**: las cifras medidas y las poblaciones sobre las que se midieron.

Lo que el registro te ahorra de verdad es saber **qué se intentó ya y con qué
resultado**, para que no vuelvas a pagar corridas que el proyecto ya pagó. Busca
las entradas marcadas como rechazos antes de construir cualquier cosa que se les
parezca — y si crees que una merece reintentarse, dilo y mide por qué esta vez
sería distinto.

---

## Disciplina de medición

Reglas pagadas con corridas perdidas. Son de método: valen sea cual sea tu
diagnóstico.

- **Nunca midas sobre el corpus que el componente ya posee.** El holdout es
  ciego, congelado y jamás se usa para ajustar.
- **No derives una regla de los casos que fallan y la compruebes sólo ahí.**
  Siempre parecerá gratis. Compruébala contra lo que hoy funciona **antes** de
  adoptarla.
- **Un cero sobre un corpus que no puede contener el fallo no es evidencia de
  seguridad.** Al tasar cualquier regla, di explícitamente **qué población podría
  haberla refutado**. Si ninguna de las que usaste podía, el cero no vale.
- **Lee los textos visibles, no sólo las decisiones contractuales.** Una decisión
  correcta puede acompañar una respuesta inservible.
- **Congela el árbol antes de un probe.** Editar código con una corrida en vuelo
  la invalida: mata la corrida, borra la telemetría parcial y relanza.
- **Instrumenta el crudo:** qué se le ofreció al modelo y qué propuso *antes* de
  que cualquier veto lo toque.
- **La dificultad de una población la eliges tú.** Dentro de un sello sólo es
  comparable lo binario; no construyas series temporales entre poblaciones que
  redactaste tú.
- **Empareja para aislar una variable.** Si comparas idiomas, usa la misma
  petición traducida; si no, mides el contenido.
- **El código de medición tiene que estar cerrado ANTES de sellar**, y una
  preinscripción no puede predecir los dos resultados a la vez.
- **Toda tasa se reporta partida por causa** — recuperación, decisión, vetos.
  Tienen arreglos opuestos.

---

## Mecánica de la máquina

Hechos operativos, no conclusiones.

- Compuerta: `.\scripts\test_source_quality.ps1 -Mode Full`, **verde antes y
  después de cada tanda**. Al recibir esto está verde: 11/11 etapas, 8.308
  Python + 446 subpruebas + 3.865 .NET.
- Ejecutar y correr pytest: `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1`
  con `PYTHONPATH=D:\BAXY\source\src`.
- Ruff: `%LOCALAPPDATA%\BAXYQuality\source-quality-v1`. **No es el mismo
  intérprete** y no tiene pytest.
- Tras cualquier cambio en `src/baxy_mind`, `scripts` o
  `experiments/voice_latency`, **re-pinea el hash del árbol congelado**: cinco
  constantes `EXPECTED_PROGRAM_TREE_SHA256` en `experiments/stt_quality/`. Si no,
  la compuerta se pone roja en `tests/test_stt_quality_evaluators.py`.
  Verifica además que el pin sigue donde lo dejaste al terminar la compuerta.
- **Sellos ciegos consumidos: V1–V7.** No los reutilices para promover nada; el
  siguiente es **V8**. Los constructores y ejecutores están en
  `experiments/mind_router_spike/build_veto_reach_v*.py` y `run_veto_reach_v*.py`.

---

## Cómo trabajas

Autoridad total. Decide, ejecuta, mide, **publica también lo negativo**: un
candidato descartado con su mecanismo entendido vale tanto como uno promovido,
porque evita que el siguiente gaste una tanda en él. No te detengas ante el
primer error.

Reporta cada tanda con `Ritmo | Progreso | Errores | Falsos positivos | Tiempo
restante` más una línea humana, y añade siempre **una frase sobre qué puede hacer
hoy una persona que ayer no podía**. Si no puedes escribirla, la tanda no movió
el bloqueante.

**El porcentaje sólo se mueve con evidencia**: sube al cerrar una parte
verificada y **baja cuando la evidencia muestre que algo que contabas no estaba
cerrado**.
