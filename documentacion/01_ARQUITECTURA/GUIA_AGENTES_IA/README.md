# Guía técnica del repositorio

> **Esto es referencia, no instrucción.** Lo que hay que hacer lo dice tu goal, en
> `documentacion/sprints/`; qué es BAXY lo dice `documentacion/00_IDENTIDAD.md`.
> Esta carpeta responde a «¿dónde está esto y cómo se construye?», y por eso vale
> — te ahorra reconstruir el mapa. Si algo de aquí contradice a tu goal, manda el
> goal, y lo anotas en una línea en `documentacion/APLAZADOS.md`.

Esta carpeta explica cómo está formado BAXY, cómo se construye, dónde reside
cada responsabilidad y qué debe validar un agente antes de entregar un cambio.
Está escrita para permitir que un agente nuevo trabaje sin reconstruir la
historia del proyecto ni convertir documentación antigua en arquitectura
vigente.

## Qué documento responde cada pregunta

| Pregunta | Documento |
|---|---|
| ¿Qué debo comprobar antes de tocar el repositorio? | Este archivo |
| ¿Qué proceso, proyecto o módulo es dueño de una conducta? | [01_MODELO_MENTAL_Y_OWNERSHIP.md](01_MODELO_MENTAL_Y_OWNERSHIP.md) |
| ¿Cómo preparo herramientas, ejecuto, compilo, pruebo o genero una entrega? | [02_CONSTRUCCION_EJECUCION_Y_ENTREGA.md](02_CONSTRUCCION_EJECUCION_Y_ENTREGA.md) |
| ¿Cómo viajan texto, voz, operaciones, confirmaciones y resultados? | [03_CONTRATOS_FLUJOS_Y_DATOS.md](03_CONTRATOS_FLUJOS_Y_DATOS.md) |
| ¿Qué archivos debo cambiar para agregar o modificar una capacidad? | [04_RECETAS_DE_CAMBIO.md](04_RECETAS_DE_CAMBIO.md) |
| ¿Qué pruebas corresponden y cómo dejo un handoff verificable? | [05_VALIDACION_SEGURIDAD_Y_HANDOFF.md](05_VALIDACION_SEGURIDAD_Y_HANDOFF.md) |
| ¿Qué hace un script y qué estado puede modificar? | [06_INVENTARIO_DE_SCRIPTS_Y_GATES.md](06_INVENTARIO_DE_SCRIPTS_Y_GATES.md) |
| ¿Dónde se consume la latencia de un turno y qué optimizaciones son seguras? | [07_LATENCIA_END_TO_END.md](07_LATENCIA_END_TO_END.md) |

Los mapas de arquitectura que acompañan a esta guía son:

- [DECISION_VIGENTE.md](../DECISION_VIGENTE.md): decisiones e invariantes
  aceptados;
- [MAPA_DEL_SISTEMA.md](../MAPA_DEL_SISTEMA.md): topología del producto activo;
- [REGISTRO_DE_MANTENIBILIDAD.md](../REGISTRO_DE_MANTENIBILIDAD.md): baseline
  más reciente, deuda, hotspots y puntos oficiales de extensión.

## Inicio seguro en diez minutos

Desde la raíz devuelta por `git rev-parse --show-toplevel`, en PowerShell:

```powershell
git rev-parse --show-toplevel
git status --short --branch
git log -5 --oneline
```

La raíz debe contener `Baxy.slnx`, `main.py` y `AGENTS.md`; la rama base normal
es `codex/baxy-rebuild-v3`. La ubicación física y la forma de abrirla dependen
del equipo: no debe copiarse ni clonarse para continuar una tarea.

Después:

1. Lee [AGENTS.md](../../../AGENTS.md). Sus reglas son operativas y
   obligatorias.
2. Revisa el estado actual en
   [REGISTRO_DE_MANTENIBILIDAD.md](../REGISTRO_DE_MANTENIBILIDAD.md). No
   infieras el baseline vigente desde un informe histórico.
3. Elige el documento de esta guía que corresponde a la tarea.
4. Inspecciona el código y las pruebas del mismo ownership antes de editar.
5. Conserva todo cambio preexistente que muestre `git status`; un árbol sucio
   no autoriza a limpiar, restaurar ni reescribir trabajo ajeno.
6. Formula el cambio mínimo que preserve contratos y autoridad.
7. Ejecuta la validación proporcional indicada en
   [05_VALIDACION_SEGURIDAD_Y_HANDOFF.md](05_VALIDACION_SEGURIDAD_Y_HANDOFF.md).

Para ejecutar el producto durante desarrollo, el único punto de entrada es:

```powershell
py main.py
```

No edites la instalación bajo `%LOCALAPPDATA%\Programs\BAXY`; el código fuente
se modifica y valida en este repositorio.

## Jerarquía de autoridad y evidencia

Hay dos preguntas distintas.

Para saber **qué está autorizado hacer**, aplica:

1. instrucciones vigentes de la tarea y del entorno del agente;
2. `AGENTS.md`;
3. decisiones explícitas del usuario y ADR aceptados;
4. esta guía.

El hecho de que el código permita una acción no concede permiso para ejecutarla.

Para saber **qué existe o qué se comprobó**, consulta:

1. código activo, archivos de proyecto, locks y manifests versionados;
2. pruebas que caracterizan ese código;
3. `DECISION_VIGENTE.md`, `MAPA_DEL_SISTEMA.md` y
   `REGISTRO_DE_MANTENIBILIDAD.md`;
4. evidencia fechada bajo `artifacts/`, solo para el commit y entorno que
   declara;
5. informes históricos bajo `documentacion/`, `contexto/`, historial de
   agentes y `legacy/`.

El código describe la implementación actual; una prueba dice qué se comprobó;
un ADR prescribe y explica una frontera aceptada; un artefacto registra una
ejecución concreta. Ninguna categoría sustituye a las otras.

Si código y decisión aceptada divergen, no elijas uno en silencio: puede ser un
defecto o una decisión que necesita reabrirse. Deja la resolución, prueba y
documentación en el mismo cambio.

## Clasificación práctica del árbol

| Clase | Rutas | Regla |
|---|---|---|
| Producto activo | `main.py`, `src/`, archivos raíz de build | Se puede modificar dentro del alcance de la tarea |
| Pruebas y tooling | `tests/`, `scripts/`, locks | Forman parte del producto mantenible; deben evolucionar con el contrato |
| Decisiones y manuales | `contexto/04_arquitectura/ADR/`, `documentacion/01_ARQUITECTURA/` | Actualizar cuando cambia una frontera o un procedimiento |
| Evidencia | `artifacts/` | Un resultado fechado, no código fuente ni permiso para repetir efectos |
| Investigación | `experiments/` | No entra al runtime por existir; requiere promoción explícita |
| Restauración privada | `bootstrap/`, rutas ignoradas descritas en `AGENT_HANDOFF.md` | No publicar ni regenerar aproximadamente |
| Archivo histórico | `legacy/`, cortes y auditorías antiguas | Solo lectura y contexto; nunca importar como implementación activa |
| Salida generada | `bin/`, `obj/`, caches, builds y runtime ignorados | No editar a mano ni tratar como fuente |

`src/Baxy.FieldUi/dist/` es una excepción deliberada: es un artefacto visual
histórico versionado y sellado por ADR-0008. No debe regenerarse como efecto
secundario de una prueba rutinaria.

## Autoridad: la regla que evita la mayoría de los errores

BAXY separa propuesta, decisión y efecto:

- la interfaz recoge texto o voz y presenta estado;
- `baxy_mind` conversa, clasifica y propone una operación o un plan;
- el catálogo .NET define el universo cerrado de operaciones;
- el kernel valida schema, riesgo, confirmación, identidad, journal y estado;
- los providers realizan efectos o lecturas y aportan evidencia;
- el core decide el outcome verificable;
- la interfaz narra el resultado en lenguaje humano.

Un prompt, skill, corpus, modelo, pantalla o adapter no puede crear autoridad
por sí mismo. Si una implementación hace que una de esas capas pueda saltarse
el catálogo, el schema, la confirmación o la postlectura, la implementación es
incorrecta aunque el caso feliz funcione.

## Qué cambios requieren detenerse y pedir autoridad

Un agente puede leer, diagnosticar, refactorizar internamente y ejecutar
validaciones locales no destructivas dentro del alcance encargado. Debe
detenerse antes de:

- cambiar un contrato público o un formato persistido sin una decisión
  explícita;
- introducir una dependencia mayor o una nueva autoridad de ejecución;
- enviar, borrar, imprimir, instalar, emparejar, comprar o cambiar cuentas,
  redes o dispositivos reales sin un objetivo autorizado;
- instalar o reemplazar la versión activa de BAXY;
- publicar artefactos, hacer push o abrir una entrega externa;
- regenerar corpus privados, sellos finales o el `dist` histórico;
- convertir una omisión ambiental en un supuesto éxito.

Las pruebas contractuales o simuladas sí son el mecanismo normal para cubrir
esas rutas sin producir el efecto externo.

## Cómo investigar sin perderse

Empieza por símbolos y ownership, no por leer árboles completos:

```powershell
rg -n "NombreDelSímbolo" src tests
rg --files src\Baxy.Core tests\Baxy.Integration.Tests
git log --oneline -- ruta\relevante
git blame -L 1,120 -- ruta\relevante
```

Para una operación pública, busca su nombre exacto en:

```powershell
rg -n '"operacion\.exacta"|operacion\.exacta' `
  src tests contexto documentacion
```

Esto revela catálogo, handler, provider, narración, contratos de App/mente y
pruebas. No asumas que el primer resultado es el único dueño.

## Regla de mantenimiento de esta guía

La guía documenta estructura y procedimientos estables. Los números que
cambian con frecuencia —conteos de pruebas, último commit validado, omisiones,
deuda y versión instalada— se mantienen en
`REGISTRO_DE_MANTENIBILIDAD.md`. Los documentos de esta carpeta deben enlazar a
ese registro en vez de copiar un nuevo snapshot.

Cuando una tarea cambia ownership, protocolo, build, persistencia o una receta
de extensión, actualiza aquí la página correspondiente en el mismo commit.
Cuando solo cambia una medición, actualiza el registro o el artefacto de
evidencia, no toda la guía.
