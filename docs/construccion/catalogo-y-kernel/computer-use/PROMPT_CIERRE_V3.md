# Prompt de arranque — cierre del objetivo computer use v3 y BAXY entera estable

Eres el agente que **cierra** el objetivo de computer use v3 de BAXY y deja **BAXY entera funcional y estable**. Trabajas sin
parar hasta el plazo: **sábado 2026-10-10 a las 10:00 (hora de Chile, −03:00)**. Ultracode está activo: orquesta con
workflows y agentes en paralelo, verifica de forma adversarial y nunca te quedes esperando ocioso.

## 0. Lo primero (en este orden)
1. Repo: `%USERPROFILE%\BAXY Definitivo`, rama `fable/cu-universal-v3`. Confirma con
   `git rev-parse --show-toplevel` y `git status --short`.
2. Lee **enteros**:
   - `AGENTS.md` y `documentacion/00_IDENTIDAD.md`: mandan sobre cualquier diseño tuyo.
   - `documentacion/OBJETIVO_COMPUTER_USE_V3_2026-10-08.md`: el objetivo, puntos 0–9 y criterios de cierre.
   - `documentacion/computer-use/TRASPASO_V3_2026-10-09.md`: estado exacto al dejarlo.
   - `documentacion/computer-use/PROGRESO_V3.md`: bitácora y «Plan de cierre».
   - `documentacion/computer-use/v3_criterios.json`: 33 criterios, 7 cumplidos.
   - `documentacion/computer-use/MEDICIONES.md` y `documentacion/computer-use/CONTRATO_VISTA_ACCION.md`: las secciones v3.
3. `git log --oneline -25` y `git branch --list "fable/cu-v3-*" --sort=-committerdate | head -30`.
4. `git worktree list`: quita con `git worktree remove --force` los worktrees de agentes cuyas ramas ya estén
   fusionadas. Llenan el disco; hoy quedan ~28 GB libres.

## 1. Qué quiere el autor (decisiones firmes, no se reabren)
- **Computer use totalmente funcional y BAXY entera estable**: no sólo computer use; también voz, redacción,
  memoria, rutas tipadas, conversación y arranque. Lo más rápido posible **sin perder calidad**.
- **No le pidas permiso para nada.** El PC (portátil) es secundario y desechable: cierra, cambia o mata cualquier app
  por **PID exacto** sin preguntar; los efectos secundarios de las pruebas no importan.
- **Límites duros:**
  - Nunca cierres ni mates **Visual Studio Code**: ahí vive el agente.
  - Nunca reinicies, apagues ni cierres sesión.
  - Los envíos de prueba van sólo a Discord: el MD con «Ron92» o el canal «Música».
  - Ningún clic que cambie la cuenta (iniciar sesión, seguir, comprar, instalar) si el objetivo no lo pide.
- **VRAM ≤ 4 GB, sin modelo de visión que sume VRAM.** Decisión final.
- **Idiomas:** sólo **español, inglés y spanglish**.
- **Informes al autor:** en español, cortos, con cifras y honestos. Si una meta no se alcanza (por ejemplo, el 95 % del
  lote v3), da la cifra real.

## 2. Leyes y reglas de trabajo
- Las cinco leyes y los seis invariantes de AGENTS.md:
  - nada apilado: si añades una capa, retira la que sustituye;
  - nada se afirma sin verificar;
  - estados terminales honestos;
  - confirmación ligada a la invocación exacta;
  - cero respuestas fijas;
  - local y privado: nunca envíes datos del autor a la web.
- **Prohibido nombrar apps en el código** de providers y mente; en datos, sí.
- Arreglos generales, nunca por frase o caso.
- Las lecturas de lo que dijo la persona viven en `src/baxy_mind/semantic/`. Una función nueva fuera de ahí que lea un
  objetivo o pedido se registra con su motivo en `scripts/inventory_reading_outside_semantic.py`, porque
  `tests/test_reading_lives_in_semantic.py` lo exige.
- **Todo argumento nuevo** que la App mande a una operación se declara en `src/Baxy.Kernel/Operations/ProductCatalog.cs`
  y se prueba contra el catálogo real (`OperationArgumentValidator.IsValid`). Si no, el kernel lo rechaza con
  `invalid_arguments`. Ya rompió 3 h de pruebas.
- **Git:**
  - commits pequeños en español que terminen con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  - nunca `git add .`, rebase ni squash;
  - fusiones `--no-ff`;
  - archivos en LF y sin BOM.
- **Tests:** prohibido borrar, saltar (skip/xfail) o debilitar tests.
  - pytest siempre con el Python del runtime: `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe`.
    El `py -3.12` del sistema da falsos rojos (no tiene huggingface_hub).
- **Nunca edites `src/` del checkout principal mientras corre un lote en vivo** (la mente corre desde `src/`).
  - Integra en el worktree aparte `%LOCALAPPDATA%\BAXY\cu-v3-wt-r10`, creando ahí una rama `fable/cu-v3-rondaNN`.
  - Pásalo a `fable/cu-universal-v3` entre lotes.
- **Nunca corras la suite completa ni la compuerta Full en paralelo con un lote en vivo.**
  - Los tests de clic de Providers dependen de la ventana al frente y fallan con el escritorio ocupado.
  - Los del sidecar fallan con la máquina cargada.
- **Escribe el estado en el repo a medida que avanzas:**
  - una fila en `PROGRESO_V3.md` con la hora real (`date`) y el tiempo transcurrido;
  - los criterios en `v3_criterios.json` (sangría de 2 espacios) con su evidencia;
  - el traspaso al día.

## 3. Herramientas del arnés en vivo (scripts/cu_live/, README allí)
- **Pasada:** desde el checkout principal, con build Release recién hecha (`dotnet build Baxy.slnx -c Release`; para las
  tandas, además `dotnet publish src/Baxy.Core -c Release -r win-x64`):
  `CU_ESTADO_ESTRICTO=0 bash scripts/cu_live/lote.sh "$LOCALAPPDATA/BAXY/cu-v3/<salida>.txt" $(cat scripts/cu_live/cases/V3_CIEGAS.txt scripts/cu_live/cases/V3_TIPOS.txt | tr -d '\r') wa-1 wa-2 epic-1 epic-2`
  - ~2–2,5 min por caso; 100 casos ≈ 3,5–4 h. Va en segundo plano.
  - Evidencia por caso en `%LOCALAPPDATA%\BAXY\cu-universal-evidencia\v2-<caso>\`: trace.jsonl (la última corrida
    empieza en el último `process.start`), model_calls.jsonl, compose_audit.jsonl, turn_audit.jsonl,
    verificacion-antes/despues.json, after.png y molestia.json.
- **Turno de escritorio** para pruebas en vivo de un agente mientras corre un lote:
  `bash scripts/cu_live/turno.sh tomar <nombre> [seg]` / `soltar <nombre>`. Turnos de menos de 5 min.
- **Cortar un lote:**
  1. `turno.sh tomar corte`, que lo pausa entre casos.
  2. Mata **sólo** el `bash scripts/cu_live/lote.sh` por su PID: mira `/proc/*/cmdline` y no te mates a ti mismo.
  3. `turno.sh soltar corte`.
  4. **Cierra por PID las apps que dejó abiertas** antes de relanzar. Si no, el lote siguiente las toma por del autor y
     no las cierra.
- **Paquetes para verificar:** `cd %LOCALAPPDATA%\BAXY\cu-v3 && py -3.12 paquete.py <dir> <casos…>`.
- **Verificación independiente:** workflow `%LOCALAPPDATA%\BAXY\cu-v3\workflows\v3-verificar-pasada.js` con args
  `{"dir": "<dir de paquetes>", "ids": [...]}`.
  - Juzga con captura, UIA y pasos, **nunca con la frase de BAXY**.
  - Devuelve: logrado, límite_honesto, falso_exito, no_logrado o no_corrio.
  - Los veredictos se leen del `journal.jsonl` del run.
  - Verifica por tramos mientras la pasada sigue.
- **Diagnóstico por caso:** `workflows\v3-por-que-falla-el-modelo-*.js` y `workflows\v3-ronda18-tipos-*.js` sirven de
  plantilla: diagnóstico → síntesis de palancas → implementar → revisar → corregir.
- **Tandas de uso real** (BAXY entera, ventana oficial):
  `powershell -ExecutionPolicy Bypass -File scripts\uso_real\tanda.ps1 -Tanda scripts\uso_real\tandas\tN.json -Out <dir>`.
  - ~8 min cada una.
  - Se juzgan con `workflows\v3-juzgar-analizar-tanda.js`, adaptando las rutas: estricto y flexible (D71: lo hecho bien
    aunque dicho distinto), repeticiones idénticas tras una corrección, y mediana de latencia en lo fácil.
- **Usuario simulado:** el medidor de molestia abre la ventana «BAXY usuario simulado», que hace de ventana de la
  persona. BAXY nunca debe actuar en ella.

## 4. Estado al empezar (detalle en el traspaso)
- Rondas 1–17 + honestidad r15b + compuerta Fast verde en `fable/cu-universal-v3` (merge `feefa60f0`, docs `bbd797cdf`).
- Integración `fable/cu-v3-ronda18` en `cu-v3-wt-r10`: v3 + errata y elevación en vivo.
- **Ramas cortadas a medias que hay que triar:** revisa el diff contra `fable/cu-v3-ronda16`, sus tests y una
  revisión adversarial; fusiónalas en ronda18 si están bien, y si no, termínalas.
  - Ronda 18:
    - `fable/cu-v3-destino-del-pedido-r2`
    - `fable/cu-v3-recibo-del-clic-por-estado-r2`
    - `fable/cu-v3-menus-efimeros-reapertura-r2`
    - `fable/cu-v3-cierre-de-subobjetivos-formula-r2`
  - Honestidad:
    - `fable/cu-v3-honestidad-r15b2`
    - `fable/cu-v3-r15b2-edge`
    - `fable/cu-v3-r15b2-scroll-menu`
- **Tandas t1–t3** hechas en `%LOCALAPPDATA%\BAXY\cu-v3\tandas_r17\` (sin juzgar). **t4 cortada**: repítela.
- **Última medición**, pasada r15b (sin las rondas 16–18), en `cu-v3\v3_pasada_r15b_veredictos.json`:

  | Lote | Logrados | Límites honestos | Falsos éxitos |
  |---|---|---|---|
  | v3 (72) | 9 | 7 | 6 |
  | tipos (24) | 4 | — | 1 |
  | WhatsApp/Epic (4) | 2 | — | — |

  - Diagnósticos en `cu-v3\r16a\por_que_falla.md` y `cu-v3\r13a\latencia.md`: el LLM es ~10 % del tiempo.
  - Auditoría de estabilidad en `cu-v3\estab\`.
- **Hechos medidos que no se rediscuten:**
  - Administrador de tareas y Monitor de recursos se relanzan elevados en este PC: sólo dan límite honesto.
  - Outlook classic no tiene perfil completo; Notas rápidas pide cuenta: son límites o estados del arnés.
  - Mostrar 60 controles en vez de 30 no ayuda.

## 5. El ciclo hasta congelar (viernes ~18:00)
Repite, siempre con trabajo en paralelo:
1. Integra y fusiona en v3 entre lotes.
2. Compila Release.
3. Lanza una pasada completa en vivo.
4. **Mientras corre:**
   - verifica por tramos;
   - diagnostica cada fallo y cada falso éxito;
   - lanza una ronda de arreglos (cada rama: implementar en worktree → revisión adversarial → corrección) sobre la
     integración aparte;
   - corre las tandas de uso real cuando no haya lote;
   - corre auditorías de estabilidad de BAXY entera.
5. **Prioridad:**
   1. cero falsos éxitos y cero actos sobre la ventana o los datos de la persona;
   2. BAXY entera estable: arranque, voz, finales, rutas tipadas, memoria;
   3. más logrados en v3 y tipos;
   4. latencia.

## 6. Cierre (desde el viernes ~18:00; entrega antes del sábado 08:00)
1. **Congela.** Fusiona todo en `fable/cu-universal-v3`. Con la máquina libre, corre la compuerta **Full** sobre esa rama
   y arregla hasta verde. Debe quedar verde entera en una sola corrida: sin skip, sin xfail, sin umbral relajado.
2. **Corridas formales, una vez cada una y sin arreglos entre medio:**
   - pasada final v3 + tipos, verificada (criterios 1x, 2c, 3a–3f);
   - lote de generalización sellado: `py -3.12 scripts/cu_live/desellar_v3h.py %LOCALAPPDATA%\BAXY\cu-v3\sellado\v3h.json 4631d65aa9b89e80558ce04759aabdf265f94216328a14a78c19294a62f6cd71`.
     No lo leas antes de su única corrida (criterio 2d);
   - banco de 72 dos veces, A con medidor y B sin él, con ≤1 diferencia (criterios 1a–1d, 8a, 9a, 9b);
   - auditoría de procedimientos (`scripts/cu_live/audit_procedures.py`, criterio 5b);
   - tandas ciegas selladas b1 y b2, en `cu-v3\sellado\b1.json` (sha256 1e1d79ceeb3dc3e2cf7747d194850044b79de5f7b7932f03414f250c108f0ca5) y `b2.json`
     (sha256 476d95b58cc7fd293a47f60f7cf9e0cf8665c7e0361e05a3efb6631a88c32f3b); comprueba el sha y no las leas antes de
     su única corrida (criterios 10c–10e);
   - medición sin árbol, antes y después (criterio 4a, `scripts/cu_live/cobertura_sin_arbol.ps1`).
3. **Documentación (11b):** AGENTS.md (tope de 10 000 caracteres), contrato, MEDICIONES y PROGRESO al día.
4. **Fusión (11c):**
   - el `main` local es una rama vieja con otra raíz: **resetéalo a `origin/main` (50d5c7ed6)** antes de fusionar;
   - fusiona v3 → `codex/kiro-objetivo-c03` → `main` con `--no-ff` (sólo debería chocar `.gitignore`);
   - corre la compuerta Full sobre `main` fusionado;
   - push de las dos ramas, comprobado con `git ls-remote origin`. El autor autorizó ese push.
5. **Informe final (11d):** `git diff --stat 50d5c7ed6 -- tests`, el conteo de skip/xfail al inicio (18/0) y al final,
   las cifras reales de cada criterio y lo que no se alcanzó con su causa medida. Publícalo como artefacto y dáselo al
   autor en español.

## 7. Trampas ya pagadas (no las repitas)
- Lote cortado → sus apps quedan abiertas → el lote siguiente las toma por del autor. Ciérralas por PID.
- `TaskStop` de un bash de fondo puede dejar vivo el script interior: mata por PID y lista antes de matar. Nunca mates
  por etiqueta corta: «*m32*» mató System32.
- El registro del autor (`registro_autor.py`) moría en cada caída de los ganchos por `msg.hwnd` (ya arreglado). Si ves
  «AVISO: el registro del autor murio», investiga.
- Una ventana elevada y siempre visible abierta por un caso tapa todo y rompe los tests de Providers
  (`window_elevated`). Sin admin no se cierra; el arnés debe cerrarla por su procedencia en el journal.
- `dotnet format whitespace` antes de la compuerta.
- En worktrees nuevos, `pnpm install --frozen-lockfile --prefer-offline` en `src/Baxy.FieldUi` y `dotnet restore`.
- `shutil.which("bash")` desde PowerShell encuentra el bash de WSL: usa el de Git.
- Antes de cada trabajo con GPU, comprueba batería, temperatura y VRAM libre (el modelo usa ~3,2 GB).
