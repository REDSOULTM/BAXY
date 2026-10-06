# Goal — computer use universal de BAXY (Fase 4, 2026-10-06)

Misión corta. Objetivo: que BAXY haga **cualquier paso dentro de una app o una página que su catálogo no tiene**
con un solo motor general, sin código por aplicación. Se construye sobre lo que ya está estable; no se rehace
nada que funcione.

## 0. Rápido, ante todo (orden del dueño)
**Termina lo antes posible.** El dueño quiere esto en horas, no en días:
- Nada de campañas de medición, tandas selladas, conjuntos DEV ni investigaciones largas: la verificación es
  probar las misiones del §2.3 en vivo y la compuerta Full al final. Lee sólo lo que necesites para el paso que
  estás dando.
- Paraleliza: subagentes en worktrees propios para lo independiente (p. ej. fusión y conflictos / enrutado en la
  mente / misiones en vivo), mientras compilas o corren pruebas. Nunca esperes sin hacer nada.
- Decide tú con el criterio por defecto razonable y sigue; pregunta al dueño sólo si de verdad bloquea.
- Pruebas por nivel (`AGENTS.md`): sólo las del tema mientras trabajas; la Full una vez al final (y otra si
  algo cambió después).
- Un arreglo por fallo concreto, el mínimo que lo resuelva de forma general; nada de refactorizaciones ni
  mejoras que el cierre no pida.
- Informes cortos, con cifras; ni diarios ni documentos largos.

Repositorio `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`, base `codex/kiro-goal-c03` (HEAD estable:
limpieza, auditoría de código, semántica C03 cerrada, navegador predeterminado con pestañas, Disney+ y HBO Max;
Full verde). Antes de nada lee `AGENTS.md`, `documentacion/00_IDENTIDAD.md`, `documentacion/SEMANTICA.md`
(«Segunda vuelta»), `documentacion/NAVEGADOR_USUARIO.md` y `documentacion/APLAZADOS.md` (§«Para la fase de
computer use»). La evidencia histórica está fuera del repo, en `..\BAXY-archivo-2026-10-06\` (lee su `LEEME.md`):
el diseño medido está en `artifacts/comprobaciones/C03/COMPUTER_USE_DISENO.md` (§1–§4, §10) y el back heredado
del agente gemma4 en `biblioteca/gemma4-agent/documentacion/04_computer_use/`. Nunca vuelvas a meter evidencia en
el repo.

## 1. Reutiliza el motor que ya existe (no lo rehagas)
La rama `fable/computer-use-engine` (6fcb7824, en GitHub; base 2026-09-20) ya trae, con 12 commits y ~4 500
líneas en `src`:
- **Contrato** `documentacion/computer-use/CONTRATO_VISTA_ACCION.md`: vista compacta v2 (≤ 60 controles UIA
  con índice, tipo, nombre, estado, rect, zona y color; OCR por zonas; `waitForLabel` ≤ 24 s;
  `processId`/`application`; `coveredBy`), repertorio cerrado con postlectura, protocolo `computer.use.step`
  y memoria de procedimientos.
- **Piezas**: `DesktopUiaWorker.ps1` + `UiaWorkerHost.cs` (worker UIA persistente), `WindowsVisibleControlAdapter`,
  `WindowsScrollAdapter`, `DesktopKeyPress.ps1`; Kernel `input.scroll`, `mission.computer.use` (nombres
  canónicos sólo con puntos), `input.visible.click {controlId?, index?, label}`, `input.visible.controls` v2,
  `input.key.press {key, target?}`; `RiskPolicy.Evaluate` por argumentos (canal de voz / envío → confirma);
  App `ComputerUseMission.cs` (bucle, `ComputerUseSuccessCheck`, procedimientos en el data root),
  `MindSidecarClient.DecideComputerUseStepAsync`; mente `src/baxy_mind/computer_use.py` (`mission_request`,
  `decide_step` JSON estricto a T=0, `deterministic_step` que dicta los pasos obvios).
- **Lecciones** (no las redescubras): la Calculadora UWP vive en ApplicationFrameHost (`app.open` no la
  verifica: tolerar si está delante); el 4B pulsando dígitos uno a uno agota el presupuesto → `deterministic_step`;
  Progman/WorkerW no son superficie; el dueño usa el PC mientras corres → `idle_gate` (sin entrada ≥ 3 min y sin
  pantalla completa) antes de cada prueba que mueva ratón o teclado.

**Paso 1:** rama nueva `fable/computer-use-universal` desde `codex/kiro-goal-c03` en un worktree propio, y
fusiona `fable/computer-use-engine`. Hay ~13 ficheros en conflicto con el trabajo de comprensión posterior al
20-09 (`__main__.py`, `effect_intent.py`, `ProductCatalog.cs`, `MindPlanSession.cs`, `PlannerExecutionSupport.cs`,
`VisibleControlSurface.cs`, `WindowsVisibleControlAdapter.cs` y sus pruebas): **gana el comportamiento actual de
la base** y se le añade el del motor. Lo que la limpieza archivó (`experiments/`, pruebas de evidencia, pines de
identidad) se queda fuera. Full verde antes de seguir.

## 2. Lo que falta, y nada más
1. **Enrutado universal**: un pedido que pide pasos dentro de una app o una página que ninguna operación del
   catálogo cubre va a `mission.computer.use` con su objetivo y su comprobación de éxito; lo que el catálogo ya
   hace sigue directo. Una sola vía, decidida por la capa semántica actual (lectores + decisor `full3`), sin
   listas de apps.
2. **El navegador es el predeterminado de la persona** (hoy Opera GX), nunca el Edge del producto. Reutiliza
   `UserBrowser*` (ventana de delante, `WM_APPCOMMAND`, recorrido UIA desde el último hijo en Opera GX, SMTC).
3. **Misiones que deben salir, en la App real, verificadas** (las 6 originales + las aplazadas):
   «ve a Cotele en Discord» (un canal de voz pregunta antes y se queda; canal de prueba «Ron92»), «cerrá todas
   las pestañas del navegador» (con confirmación; el navegador queda con una), «abre Steam y ve a la
   biblioteca», «en Discord apretá enter», «abrí Configuración y activá el modo avión», «en la calculadora
   calculá 12×7», «ve a la pestaña de YouTube», «pon La Casa del Dragón en HBO Max» (título escrito distinto
   en el servicio), y una página o app que BAXY no conoce elegida por ti ese día.
4. **Final honesto**: se dice qué se hizo con lo observado; si no se pudo, qué lo impidió. Nada afirmado sin
   verificar; ninguna respuesta fija.

## 3. Reglas
- Modelo local Qwen3.5-4B Q4_K_M + LoRA `full3`; VRAM de BAXY ≤ 3,8 GB (hoy ~3,79 GB): nada nuevo en GPU.
  Encoders de imagen sólo si una misión lo exige, en CPU, y con números al dueño antes de entrar.
- Si el 4B falla sistemáticamente al **elegir** el paso, mide y presenta opciones con números; no cambies el
  modelo solo.
- Cero código por aplicación fuera de alias; un clic sólo cuenta si la superficie cambió.
- `RiskPolicy`: en modo normal sólo confirma lo destructivo o lo que llega a una persona; cerrar todas las
  pestañas confirma.
- PC del dueño: nunca cierres VS Code ni su navegador si ya estaba abierto (sólo lo que abriste, cerrado de forma
  normal y por PID exacto); nunca mates por patrón; nada de reiniciar ni apagar; restaura volumen y brillo; si
  el clasificador de permisos bloquea algo, para y pregúntale al dueño.
- Worktree nuevo: `pnpm install --frozen-lockfile` en `src/Baxy.FieldUi`, `dotnet restore`, copiar
  `tests/data/turn_evidence_runtime.v1.jsonl`; App de prueba con `BAXY_MIND_PYTHONPATH=<worktree>\src` y perfil
  bajo `%LOCALAPPDATA%\BAXY`; capturas fuera del repo.

## 4. Cierre (no pares antes)
- Las 9 misiones del §2.3 probadas en vivo en la App real: **≥ 8 logradas y verificadas**; la que falle, con su
  causa medida y dicha honestamente en el final.
- Compuerta `scripts/test_source_quality.ps1 -Mode Full` verde.
- `documentacion/computer-use/` al día (contrato + qué cubre, por tipo de app: Win32, UWP, Electron, navegador),
  latencia por paso y ahorro de la memoria de procedimientos.
- Merge a `codex/kiro-goal-c03` con `--no-ff`, push, y un informe corto en español con cifras.
