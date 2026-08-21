# BAXY — lo primero que lees

Este repositorio es **BAXY Definitivo**. Confirma que estás en él:
`git rev-parse --show-toplevel` termina en `BAXY Definitivo`, y la raíz contiene
`Baxy.slnx`, `main.py` y este fichero. Rama de trabajo: **`main`**.

**Cuidado con el nombre.** En la misma carpeta `Programacion` hay otro repositorio
llamado `BAXY` a secas: es el intento anterior, **fuente de herencia, no sitio de
trabajo**. Nada de lo que escribas va allí.

## Qué haces aquí

El trabajo está en **once goals**, en `documentacion/sprints/`. Cada uno se lanza en
una sesión nueva, se pega entero, y corre hasta cumplirse.

**Si te han dado un goal, ésa es tu única instrucción.** Este fichero no te dice qué
hacer, sólo dónde estás y cómo moverte. Si no te han dado ninguno, empieza por
[`documentacion/sprints/00_INDICE.md`](documentacion/sprints/00_INDICE.md).

## Los dos documentos que mandan

1. **[`documentacion/00_IDENTIDAD.md`](documentacion/00_IDENTIDAD.md)** — qué es
   BAXY. No son preferencias: son decisiones del dueño del producto con los cuatro
   intentos anteriores sobre la mesa. Si un diseño tuyo las contradice, cambias tú.
2. **Tu goal**. Trae dentro las cinco leyes, lo ya medido y rechazado, y sus
   criterios de cierre.

Cualquier otro documento que parezca decirte qué hacer y no sea tu goal está
caducado: es **evidencia**, no instrucción. Si contradice al goal, manda el goal y
lo anotas en `documentacion/APLAZADOS.md`.

## Las cinco leyes

Aquí en corto; enteras, con su porqué, en
[`documentacion/sprints/00_INDICE.md`](documentacion/sprints/00_INDICE.md) y dentro de
cada goal.

1. **Hereda primero, estado del arte después, construye al final.**
2. **Nada de sobreingeniería.** Si añades una capa, retira la que sustituye.
3. **Sólo se arregla lo que bloquea** (goals 01–10). Lo demás, una línea en
   `documentacion/APLAZADOS.md`.
4. **Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo.
5. **Arquitectura modular.** Una responsabilidad por pieza, cero código muerto.

## Los seis invariantes

No se re-derivan, nunca:

1. El catálogo tipado es la única fuente de operaciones. La mente propone, el kernel
   autoriza, el provider ejecuta.
2. Nada se afirma sin verificar.
3. Estados terminales honestos.
4. La confirmación se liga a la invocación exacta.
5. Cero respuestas visibles fijas.
6. Local y privado. El modelo corre en la máquina. BAXY puede consultar la web; lo
   que no puede es enviar contenido del usuario — la línea es de dirección, no de
   conexión.

## Mapa mínimo

Producto híbrido **.NET 10 + Python 3.12 + React/TS**, sólo Windows.

| Pieza | Dónde | Qué hace |
|---|---|---|
| Entrada de desarrollo | `main.py` | Único arranque en desarrollo: `py main.py` |
| Mente | `src/baxy_mind/` | Conversa, clasifica, propone operación o plan |
| Contratos | `src/Baxy.Contracts/` | Tipos del protocolo mente↔kernel |
| Catálogo + kernel | `src/Baxy.Kernel/` | Universo cerrado de operaciones; autoriza |
| Core | `src/Baxy.Core/` | Decide el outcome verificable |
| Providers | `src/Baxy.Providers.Windows/` | Efectos y lecturas reales sobre el PC |
| App / UI | `src/Baxy.App/`, `src/Baxy.FieldUi/` | Shell y GUI (React+TS) |
| Setup | `src/Baxy.Setup/` | Instalación reproducible |
| Pruebas .NET | `tests/Baxy.*.Tests/` | Por proyecto dueño |
| Pruebas Python | `tests/test_*.py` | ~400 ficheros, pytest |
| Tooling | `scripts/` | Gates, builds, corpus, evidencia |

**Enrutador completo — dónde miro si quiero tocar X, qué archivos importan si falla
Y:** [`docs/AI_CONTEXT_MAP.md`](docs/AI_CONTEXT_MAP.md). Ábrelo antes de explorar a
ciegas.

## Tres cosas de esta máquina

- La shell es **PowerShell** y el producto es sólo Windows. Los comandos de este
  fichero son literales, no traducciones de otro sistema.
- El esfuerzo de razonamiento de este repositorio es **`high` como suelo**. `xhigh` se
  sube en la sesión concreta que lo merezca —un diseño abierto, un fallo que no se
  explica—, nunca de forma fija.
- **BAXY no es una aplicación web.** Su interfaz vive en `src/Baxy.FieldUi` dentro de
  un shell de escritorio y aquí no hay herramientas de navegador: un cambio de interfaz
  se verifica ejecutando el producto (`py main.py`) y con sus pruebas, y dices qué no
  pudiste verificar.

## Escalera de validación

Sube un peldaño sólo cuando el cambio lo justifique. No ejecutes la compuerta entera
después de cada línea.

| Nivel | Cuándo | Comando |
|---|---|---|
| 0 | Diagnóstico sin editar | `git status --short --branch`, `grep` acotado |
| 1 | Tras editar | El test dueño: `py -m pytest tests/test_X.py -q` o `dotnet test tests/Baxy.Kernel.Tests -c Release` |
| 2 | Cambio integrado que toca fuente | `.\scripts\test_source_quality.ps1` (estática multilenguaje + build Release) |
| 3 | Cierre de tanda, contrato compartido, ejecución, persistencia | `.\scripts\test_source_quality.ps1 -Mode Full` (+ suites .NET y pytest) |
| 4 | Publish, hardware, voz, ciclo instalado | No es implícito en Full. Ver `05_VALIDACION_SEGURIDAD_Y_HANDOFF.md` |

**La entrega se cierra en nivel 3, verde entero.** Un rojo bloquea, sin excepción y
sin nota al pie. No se cierra con `skip`, `xfail`, umbral relajado ni fallback. Un
skip no cuenta como pass: dilo como «suite X: N pass, M skips ambientales».

Detalle por ownership y matriz de pruebas: `GUIA_AGENTES_IA/05_VALIDACION_SEGURIDAD_Y_HANDOFF.md`.

## Buscar antes de leer

El árbol tiene ~6.400 ficheros versionados, y **la mayoría es evidencia histórica, no
código**: una búsqueda sin acotar devuelve ~1.800 ficheros donde el código dueño son
174. Ámbito por defecto: **`src tests scripts main.py`**.

- Localiza con la tool `grep` —es ripgrep por dentro— acotada a ese ámbito, y **lee
  sólo el rango** con `read_file`, no el fichero entero. Para una operación pública
  extremo a extremo, busca su nombre literal (`"operacion.exacta"`) en `src tests`.
- En la shell **no existe `rg`**: es PowerShell. `run_terminal_command` se reserva para
  lo que de verdad necesita shell —git, pytest, dotnet, procesos—, no para leer ni
  buscar.
- `artifacts/`, `biblioteca/` y `experiments/` **se abren con ruta exacta, nunca se
  recorren** — son 5.200 ficheros de evidencia fechada.
- Antes de abrir una línea de investigación, busca en la biblioteca: 1.350 documentos
  de las cuatro escrituras anteriores, con rechazos ya medidos. Es la ley 1. El
  procedimiento para hacerlo sin inundar el contexto está en la skill
  **`evidencia-baxy`**.

## Ficheros que no se leen enteros

60 ficheros versionados pasan de 1 MB. Abrir uno entero cuesta la sesión:

- `tests/data/historical_messages.jsonl` — 69 MB
- `artifacts/corpus_cutoff/source_manifest.json` — 16 MB
- `tests/data/historical_message_mapping.jsonl` — 16 MB
- `artifacts/development/*.jsonl`, `artifacts/fixes/*.json` — hasta 11 MB

Comprueba el tamaño antes de abrir: `git ls-tree -r -l HEAD -- ruta`. Con JSONL, lee
las primeras líneas con `read_file` y cuenta con `grep`; con JSON grande, `grep` por
clave. Nunca completo, y nunca `Get-Content` sin `-TotalCount`.

## Salida de comandos

Pide una señal pequeña primero y sube el detalle sólo si hace falta.

- `pytest -q` (nunca `-v` de entrada). Si falla: `--lf -x -q`, y sólo entonces el
  traceback del test concreto.
- `dotnet build`/`test`: `--nologo`, `-v:minimal`. Nunca `-v:detailed`.
- Lo que tarda —la compuerta, una corrida de medición, un build Release— va en
  **segundo plano** y sigues con trabajo independiente; recoges el resultado con
  `get_command_or_subagent_output`, sin sondear en bucle.
- Salida enorme e imprevisible: redirígela a un fichero temporal fuera del árbol y
  consúltala con `grep`. No la traigas entera al contexto.
- `git log --oneline -10`, `git diff --stat` antes de `git diff`.
- Nunca `git status` sin `--short`, ni recorrer `artifacts/` o `biblioteca/`.

Pero no ocultes lo que necesitas para diagnosticar: si un fallo no se explica con la
señal corta, sube el detalle de ese fallo concreto, no de la suite entera.

## Subagentes

Por defecto, **no**. `spawn_subagent` arranca una sesión hija que **hereda tu modelo**:
paga contexto y razonamiento otra vez para volver con un informe que además tienes que
leer. El intento anterior de este proyecto gastó 322 sesiones de subagente
(`documentacion/agentes/INDICE.md`): ahí está la advertencia.

Delega sólo cuando se cumplan las tres: (a) es **exploración de sólo lectura** y
acotada, (b) el resultado cabe en rutas + rangos + conclusión, (c) traerlo al hilo
principal costaría más contexto que la respuesta. Arquitectura, implementación difícil
y revisión final se quedan contigo.

## Handoff y terminado

El estado se deja **escrito en el repositorio a medida que avanzas**, no al final: una
compactación no puede borrar horas de trabajo pensado.

Al cerrar una sesión larga o al agotar el contexto, deja el handoff siguiendo
[`docs/AI_HANDOFF_TEMPLATE.md`](docs/AI_HANDOFF_TEMPLATE.md) — pequeño, de alta
utilidad, no un diario de la conversación.

Una tarea está terminada cuando: la conducta pedida existe o el diagnóstico está
demostrado; el ownership es correcto; el nivel de validación que corresponde pasó y lo
dices con el comando y el resultado exactos; el diff no lleva código, flags ni assets
sin propósito; la documentación vigente sigue siendo cierta; y otro agente puede
continuar sin reconstruir tus decisiones.

---

*Este fichero tiene un tope duro: Grok lo trunca a los 10.000 caracteres, por el
final. Si lo alargas, mide con `grok inspect` en el mismo commit.*
