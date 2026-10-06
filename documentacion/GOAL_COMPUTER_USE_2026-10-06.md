# Goal — computer use universal de BAXY (Fase 4, 2026-10-06)

<objetivo>
Haz que BAXY complete **cualquier paso dentro de una app o una página que su catálogo no cubre** («ve a la pestaña
de YouTube», «en Steam ve a la biblioteca», «activa el modo avión en Configuración») con un único motor general,
sin código específico de ninguna aplicación. Por qué: el dueño quiere un asistente universal; hoy BAXY se detiene
en cuanto un pedido sale de su catálogo, y esa es la limitación que más se nota en el uso diario.

Es una misión **rápida**: el dueño la quiere en horas, no en días. Termina lo antes posible con el cierre de
`<cierre>` cumplido; no hay nada que pulir más allá de él.
</objetivo>

<contexto>
- Repositorio `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`, base estable `codex/kiro-goal-c03`
  (limpieza y auditoría de código hechas, semántica C03 cerrada, navegador predeterminado con pestañas, Disney+ y
  HBO Max; compuerta Full verde). Producto: .NET 10 (App, Kernel, Core, providers de Windows) + mente Python
  (`src/baxy_mind`) + modelo local Qwen3.5-4B Q4_K_M con LoRA del decisor `full3`.
- Lee primero, enteros: `AGENTS.md`, `documentacion/00_IDENTIDAD.md`, `documentacion/SEMANTICA.md` («Segunda
  vuelta»), `documentacion/NAVEGADOR_USUARIO.md` y `documentacion/APLAZADOS.md` («Para la fase de computer
  use»). Son cortos y fijan las reglas del producto.
- La evidencia histórica vive fuera del repo, en `..\BAXY-archivo-2026-10-06\` (ver su `LEEME.md`): el diseño
  medido en `artifacts/comprobaciones/C03/COMPUTER_USE_DISENO.md` (§1–§4, §10) y el diseño heredado del agente
  gemma4 en `biblioteca/gemma4-agent/documentacion/04_computer_use/`. Consúltala sólo si la necesitas; la
  evidencia nueva también va fuera del repo, porque el dueño lo limpió para que el contexto del siguiente agente
  sea pequeño.
</contexto>

<reutiliza>
El motor ya existe en la rama `fable/computer-use-engine` (6fcb7824, en GitHub; base 2026-09-20; 12 commits,
~4 500 líneas en `src`). Fusiónalo; no lo reescribas.
- Contrato: `documentacion/computer-use/CONTRATO_VISTA_ACCION.md` (vista compacta v2 de ≤ 60 controles UIA con
  estado, rect, zona, color y OCR por zonas; `waitForLabel` ≤ 24 s; `processId`/`application`; `coveredBy`;
  repertorio cerrado con postlectura; protocolo `computer.use.step`; memoria de procedimientos).
- Piezas: `DesktopUiaWorker.ps1` + `UiaWorkerHost.cs`, `WindowsVisibleControlAdapter`, `WindowsScrollAdapter`,
  `DesktopKeyPress.ps1`; Kernel `input.scroll`, `mission.computer.use`, `input.visible.click`,
  `input.visible.controls` v2, `input.key.press`; `RiskPolicy.Evaluate` por argumentos; App
  `ComputerUseMission.cs` (bucle, comprobación de éxito, procedimientos); mente `src/baxy_mind/computer_use.py`
  (`mission_request`, `decide_step` con JSON estricto a temperatura 0, `deterministic_step` para los pasos obvios).
- Lecciones ya pagadas:
  - los nombres canónicos de operación sólo llevan puntos;
  - la Calculadora UWP vive en ApplicationFrameHost (`app.open` no la verifica: tolerar si está delante);
  - el 4B pulsando dígitos uno a uno agota el presupuesto, por eso `deterministic_step` dicta lo obvio;
  - Progman/WorkerW no son superficie;
  - en Opera GX el árbol UIA se recorre desde el último hijo tras abrir una pestaña nueva;
  - Opera atiende `WM_APPCOMMAND` atrás/adelante/recargar;
  - el dueño usa el PC mientras trabajas: comprueba que esté inactivo antes de mover ratón o teclado.
</reutiliza>

<tareas>
1. **Fusión.** Rama `fable/computer-use-universal` desde `codex/kiro-goal-c03` en un worktree propio; fusiona
   `fable/computer-use-engine`. Habrá ~13 ficheros en conflicto con el trabajo de comprensión posterior al 20-09
   (`__main__.py`, `effect_intent.py`, `ProductCatalog.cs`, `MindPlanSession.cs`, `PlannerExecutionSupport.cs`,
   `VisibleControlSurface.cs`, `WindowsVisibleControlAdapter.cs` y sus pruebas). Conserva el comportamiento de
   la base y añade el del motor: la semántica actual está medida y es la que el dueño validó. Lo que la limpieza
   archivó (`experiments/`, pruebas de evidencia, pines de identidad) se queda fuera.
2. **Enrutado universal.** Un pedido que exige pasos dentro de una app o página y que ninguna operación del
   catálogo cubre va a `mission.computer.use` con su objetivo y su comprobación de éxito; lo que el catálogo ya
   hace sigue directo. Que lo decida la capa semántica actual (lectores + decisor), por la forma del pedido, nunca
   por una lista de apps.
3. **Navegador = el predeterminado de la persona** (hoy Opera GX) a través de `UserBrowser*`; el Edge del producto
   sólo existe para mediciones aisladas.
4. **Finales honestos**: se dice lo que se hizo con lo observado; si algo no se pudo, qué lo impidió. Un clic
   cuenta sólo si la superficie cambió.
</tareas>

<misiones_de_prueba>
En la App real, cada una verificada por lo que se observa después:
1. «ve a Cotele en Discord»: un canal de voz pregunta antes de unirse; canal de prueba «Ron92».
2. «cerrá todas las pestañas del navegador»: con confirmación; el navegador queda con una pestaña.
3. «abre Steam y ve a la biblioteca».
4. «en Discord apretá enter».
5. «abrí Configuración y activá el modo avión».
6. «en la calculadora calculá 12×7».
7. «ve a la pestaña de YouTube».
8. «pon La Casa del Dragón en HBO Max»: el servicio escribe el título distinto.
9. Una app o página que BAXY no conoce, elegida por ti ese día.
</misiones_de_prueba>

<reglas>
- **Recursos:** modelo local con VRAM de BAXY ≤ 3,8 GB (hoy ~3,79 GB), porque es el límite del producto. No
  añadas nada en GPU; un encoder de imagen sólo si una misión lo exige, en CPU, y presentado antes al dueño con
  números.
- **Modelo:** si el 4B falla sistemáticamente al *elegir* el paso, mídelo y presenta opciones con números al
  dueño en vez de cambiar el modelo.
- **Generalidad:** las soluciones deben ser generales. Si una prueba sólo pasa con un caso especial para esa
  frase o esa app, el arreglo está mal: busca la causa.
- **Riesgo:** `RiskPolicy` en modo normal confirma sólo lo destructivo o lo que llega a otra persona (cerrar
  todas las pestañas confirma).
- **PC del dueño:**
  - cierra sólo lo que tú abriste, de forma normal y por PID exacto;
  - deja VS Code y el navegador del dueño como estaban;
  - restaura volumen y brillo;
  - no reinicies ni apagues el PC;
  - si el clasificador de permisos bloquea una acción, detente y explícale al dueño qué necesitas.
- **Worktree nuevo:** `pnpm install --frozen-lockfile` en `src/Baxy.FieldUi`, `dotnet restore`, copia
  `tests/data/turn_evidence_runtime.v1.jsonl`. La App de prueba lleva `BAXY_MIND_PYTHONPATH=<worktree>\src` y un
  perfil bajo `%LOCALAPPDATA%\BAXY`; las capturas van fuera del repo.
</reglas>

<forma_de_trabajo>
- **Paraleliza.** Lanza en paralelo las llamadas a herramientas independientes y usa subagentes en worktrees
  propios para el trabajo independiente (p. ej. conflictos de la fusión, enrutado en la mente, misiones en vivo).
  Mientras compila o corren pruebas, avanza en otra cosa.
- **Verifica rápido.** Mientras trabajas, corre sólo las pruebas del tema (escalera de `AGENTS.md`); la compuerta
  `scripts/test_source_quality.ps1 -Mode Full` una vez al final, y otra si algo cambió después. Sin campañas de
  medición, tandas selladas ni conjuntos DEV: la prueba son las misiones en vivo.
- **Investiga antes de cambiar.** Lee el código que vas a tocar; no supongas cómo funciona.
- **Decide y avanza.** Usa el criterio por defecto razonable; pregunta al dueño sólo si algo bloquea de verdad.
- **Haz sólo lo que el cierre pide:** el arreglo mínimo y general para cada fallo, sin refactorizaciones extra.
- **Guarda el estado.** Lleva `documentacion/computer-use/PROGRESO.md` (qué está hecho, qué falta, cada misión
  con su resultado) y haz commits pequeños a menudo: si tu contexto se compacta, retomas desde ahí sin repetir
  trabajo. No pares por el tamaño del contexto.
- **Informes** cortos, en español, con cifras.
</forma_de_trabajo>

<cierre>
- Misiones de `<misiones_de_prueba>` probadas en vivo en la App real: **≥ 8 de 9 logradas y verificadas**; la que
  falle, con su causa medida y dicha con honestidad en el final de BAXY.
- Compuerta Full verde.
- `documentacion/computer-use/` al día: contrato, cobertura por tipo de app (Win32, UWP, Electron, navegador),
  latencia por paso y ahorro de la memoria de procedimientos.
- Merge a `codex/kiro-goal-c03` con `--no-ff`, push, y el informe final al dueño.
</cierre>
