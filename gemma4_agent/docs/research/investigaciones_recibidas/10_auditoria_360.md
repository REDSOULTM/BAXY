# Auditoría 360° — 3 informes recibidos de claude.ai (2026-05-24)

Llegaron **3 informes** (compass_artifact wf-1e4c3be0, wf-441be52e, wf-61ede3e0).
Procesados acá. Regla del repo: NO aplicar nada sin verificar contra código real +
gate + medir. Abajo: lo verificado, las contradicciones resueltas, y el plan.

## CONTRADICCIONES RESUELTAS verificando contra el código

### 1. `--swa-full` — informe #2 dice SACARLO. VERIFICADO: NO tocar. ❌ el informe.
El informe #2 cita issue #21468 (cache-reuse roto con swa-full) y recomienda quitarlo.
PERO `llama_server.py:369-378` documenta que **--swa-full es CRÍTICO para cache-reuse
en Gemma 4** y que el **PR #22288 arregló la lógica** (nuestro build b9090+ lo incluye).
La síntesis decisional ya lo midió: cache-reuse funciona con swa-full (617/625 cacheados).
El informe #2 desconoce el PR #22288 → está desactualizado en este punto. **DESCARTADO.**
(Ejemplo perfecto del "los informes fallan en detalles del entorno" de CLAUDE.md.)

### 2. `AttachThreadInput` — informes se CONTRADICEN entre sí.
- #1 dice usarlo (cita PowerToys PR #1282).
- #3 dice NUNCA (cuelga el proceso; cita Raymond Chen "I warned you" 20080801).
RESOLUCIÓN: #3 tiene razón sobre el riesgo (el propio Chen lo desaconseja para forzar
foreground). La secuencia correcta NO necesita AttachThreadInput: alcanza
`SetForegroundWindow → SendMessageTimeout(WM_NULL) → verificar → SendInput`. Solo usar
AttachThreadInput como fallback acotado con timeout si el SetFocus al CoreWindow hijo
falla. **Preferir la vía sin AttachThreadInput.**

## CONVERGENCIA FUERTE (los 3 coinciden, bien fundado) — §7.1 SendKeys

CAUSA RAÍZ (unánime, fuentes Microsoft/Raymond Chen):
1. `SetForegroundWindow` es ASÍNCRONO cross-process; `GetForegroundWindow` devuelve el
   HWND nuevo ANTES de que el target bombee la activación → nuestro gate "foreground
   estable 2 lecturas" NO alcanza.
2. `SendKeys.SendWait` NO espera procesamiento cross-process (doc oficial .NET).
3. PowerShell cold-start (CLR JIT) por llamada = 0.5-6s variable → acopla la inyección
   a la carga del sistema. EXPLICA nuestra evidencia: chains5/6 fresca 100% vs
   ref/final saturada 25-50% (mismo código).
4. Calculator UWP vive tras ApplicationFrameHost.exe; el control real es un CoreWindow
   hijo → SetForegroundWindow nudgea el frame, el foco real migra en otro thread.

VERIFICADO en código: `tools.py::gui_type` (línea ~5270) lanza
`subprocess.run(["powershell","-NoProfile","-Command", SendKeys::SendWait...])` por
llamada. Confirma el diagnóstico de los informes.

FIX CONVERGENTE: matar PowerShell-por-keystroke → **SendInput in-process** (ctypes/
pywin32) con `KEYEVENTF_UNICODE` (layout/idioma-independiente = bonus multi-usuario),
secuencia: `AllowSetForegroundWindow(ASFW_ANY) → SetForegroundWindow →
SendMessageTimeout(WM_NULL, ~1500ms) → verificar GetForegroundWindow → gate UIA
HasKeyboardFocus/IsEnabled → SendInput`.

## ⚠️ CONTAMINACIÓN Gemma 3 vs Gemma 4 en el informe #3 (wf-61ede3e0)
RED detectó que un informe mezcla Gemma 3. ES el #3, SOLO en §7.6 (latencia):
propone drafter `gemma-3-270m` Q4 para speculative decoding y cita "control de
reasoning de Gemma 3". ESO NO APLICA: estamos en Gemma **4** E4B; asumir
compatibilidad de tokenizer/vocab gemma-3-270m ↔ gemma-4-E4B es justo lo que NO se
puede dar por sentado (Gemma 4 cambió la arquitectura salvo PLE). **§7.6 del #3 =
NO CONFIABLE, descartar el drafter gemma-3-270m.**
PERO el resto del #3 (§7.1 SendKeys, §7.4 verify UIA) es Win32/UWP puro, INDEPENDIENTE
del modelo → se sostiene (es su parte mejor citada: Chen + source de microsoft/calculator).
Los informes #1 y #2 SÍ son Gemma-4-específicos (MTP oficial, b9090, Gemma4Assistant).
CONCLUSIÓN §7.6: la única vía de latencia que sobrevive a los 3 es la conservadora
(ngram-cache + cap reasoning). NINGÚN drafter externo sin medir compat de tokenizer.

## OTROS HALLAZGOS (accionables, verificar antes)

- **§7.4 verify**: reemplazar dHash por **UIA read** (`AutomationId="CalculatorResults"`
  → `CurrentName` = "Display is N"). Universal por estado del SO. Los 3 coinciden +
  citan el source de microsoft/calculator. **Fuerte.** (Notepad: ValuePattern del Edit.)
- **§7.2 alucinación de tools**: GBNF con enum cerrado de tool-names (TOOLDEC arXiv
  2310.07075: 0%→52%). CAVEAT de los 3: con `--jinja` Gemma 4 ya tiene grammar interna;
  componer mal es posible → usar lazy-grammar o post-validar. MEDIR.
- **§7.6 latencia**: drafter MTP oficial de Gemma 4 **NO carga en mainline b9090**
  (arquitectura Gemma4AssistantForCausalLM desconocida; Discussion #22735 sin merge;
  PR #22673 es solo Qwen3.6). Opciones reales: (a) ngram-cache (0 VRAM, gana solo en
  prompts repetitivos — Maher midió ~0% en conversación variada), (b) cap reasoning
  ~96-128 tok. NO migrar a vLLM (pierde prefix-cache, no cabe en 6GB). NO usar forks
  (rompen reproducibilidad). VERIFICAR: ¿b9090 tiene siquiera `--spec-type`?
- **§7.3 no-encadenamiento**: los 3 dicen MANTENER el command_splitter determinista
  (literatura: top-tier 41% en step-localization; un 4B no chainea). Confirma nuestra
  decisión. NO tocar.
- **§7.5 router**: abstain calibrado POR IDIOMA (no global) + RRF. Coincide con lo que
  ya hicimos; mejora incremental.

## CAVEATS de los informes (sus propias dudas, a verificar en NUESTRO código)
- ¿`gui_type` ya escapa `+^%~(){}[]`? → SÍ (verificado sesión previa, líneas 5254-5260).
  SendInput Unicode-mode lo evita de raíz igual.
- ¿El HWND que enfocamos es el ApplicationFrameWindow o el CoreWindow hijo? → verificar.
- ¿chains5/6 vs ref/final fue realmente carga? → nuestra propia medición ya lo confirmó
  (degradación progresiva tras ~25 evals).

## P3 CALIBRACIÓN — MEDIDA y NO-VIABLE hoy (2026-05-24)
Intenté calibrar umbrales abstain POR IDIOMA. Medido sobre router_eval_corpus.curated
(dev 1394 filas): es=1248 (337 no-tool), fr=103 (13), pt=35 (12), en=8 (1). DOS
hallazgos: (1) el threshold global 0.66 YA es el de español (corpus ~90% es), nada
que ganar en es; (2) fr/pt/en tienen 1-13 filas no-tool = INSUFICIENTE, calibrar ahí
sería RUIDO que podría EMPEORAR esos idiomas. Por eso NO calibré (no forzar mejora
falsa). La infra threshold_for(lang)+thresholds_by_lang queda lista (cae al global,
cero regresión). Para calibrar de verdad: PRIMERO recolectar más queries no-tool
multilingües (de traces reales o síntesis). El routing multilingüe NO está roto por
umbral — es falta de DATOS. Commit 7b1e528 (infra), gotcha registrado.

## PLAN (orden por ROI, cada uno con gate)
**P0 — §7.1 SendInput in-process** (el de mayor ROI; si esto no sube >90% bajo carga,
no tocar el resto). Gate: re-correr cadenas Tier-4 {fresca, saturada} → estable.
**P0b — §7.4 verify por UIA** (va de la mano: confirma que el texto entró sin píxeles).
**P1 — §7.2 GBNF tool-names** (medir que compone con --jinja, sino post-validar).
**P2 — §7.6 ngram-cache** (medir; esperar ~0% en conversación, sí en RAG).
**P3 — §7.5 router abstain per-idioma** (incremental).
NO TOCAR: --swa-full, command_splitter, no migrar a forks/vLLM.
