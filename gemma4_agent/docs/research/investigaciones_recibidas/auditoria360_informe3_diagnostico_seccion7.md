# Diagnóstico §7 — Voice-agent Windows / Gemma 4 E4B-it Q4_K_M / vram4

**TL;DR (3 viñetas)**
- **§7.1 — La causa raíz más probable** es que `SetForegroundWindow` es **asíncrono entre procesos** (documentado por Microsoft) y `SendKeys.SendWait` lanzado en un PowerShell nuevo dispara las pulsaciones antes de que el target — frecuentemente un `CoreWindow` hijo dentro de `ApplicationFrameHost.exe` para UWP — termine de procesar la notificación "conviértete en activa". Bajo carga el cold-start del CLR/PowerShell empuja la inyección a una ventana de ~200–1500 ms; los primeros 1–2 keys caen al vacío. La fix correcta y barata: matar el proceso PowerShell por keystroke y mover la inyección a **ctypes/pywin32 SendInput in-process**, con la secuencia canónica de Raymond Chen `SetForegroundWindow → SendMessageTimeout(WM_NULL) → verify GetForegroundWindow → SendInput`, y verificación por **UIA `AutomationId="CalculatorResults"` → `CurrentName`** (no por dHash).
- **§7.2 / §7.5 / §7.6** — Aplicar **GBNF en llama.cpp restringido al subset válido de tools** (elimina el `system(action='calculator')` inexistente, costo µs por token), reforzar router multilingüe con **margen top1−top2 + abstain calibrado por idioma** (no hardcodes), y bajar decode con **n-gram cache nativo de llama.cpp primero** y **drafter `gemma-3-270m` Q4 después** — pero **medir antes**: hay evidencia pública (thc1006/qwen3.6-speculative-decoding-rtx3090) de que en consumer GPUs con Q4 la spec-dec puede degradar.
- **§7.3 / §7.4** — Mantener el `command_splitter` determinista (un 4B realmente falla 0/12 en multi-step y la literatura sobre tool hallucination en small LLMs lo respalda), y reemplazar **frame-diff dHash por UIA `CurrentName`/TextPattern read** como verificador universal de "texto entró", con OCR Tesseract como fallback solo cuando UIA no exponga el provider.

---

## 1. Diagnóstico por fallo

### §7.1 — SendKeys pierde caracteres contra ventana recién creada (FOCO PRIMARIO)

**Causa raíz más probable (jerarquía de hipótesis ordenadas por evidencia):**

**H1 — Alta confianza, evidencia directa de Microsoft.** `SetForegroundWindow` no es atómico cuando el target pertenece a otro process/thread group. Raymond Chen (Microsoft, "The Old New Thing", 18 Nov 2016, *"Why does calling SetForegroundWindow immediately followed by GetForegroundWindow not return the same window back?"*):

> *"The `SetForegroundWindow` function actually does two things, one immediately and one asynchronously. It immediately sets the input queue associated with the window as being the foreground input queue … It also notifies the window, 'Hey, you should make yourself the active window for your queue.' This notification is processed synchronously if the target window's thread belongs to the same input queue as the thread that is calling SetForegroundWindow, and **it is processed asynchronously if the window belongs to a different thread group**."*

Y el remate clave:

> *"at the moment that SetForegroundWindow returns, the window is becoming the foreground window, but it is not necessarily the foreground window yet."*

La fix oficial Microsoft es **enviar `SendMessageTimeout(hwnd, WM_NULL, 0, 0, 0, 5000, &r)`**:

> *"the fact that we sent a message means that our code waits for the window to finish processing the previous message, which was 'Hey, you should make yourself the active window for your queue.' And that's what we are really waiting for."*

**H2 — Alta confianza, repro directo público del síntoma.** Newsgroup `comp.os.ms-windows.programmer.win32` (hilo "SetForegroundWindow + SendInput timing problems"):

> *"I'm using SetForegroundWindow followed by SendInput to send keystrokes to another program. The problem is that apparently it takes some time for Windows … to process the SetForegroundWindow request: **Some of keystrokes sent by SendInput are lost.** But if I call Sleep(50) between SetForegroundWindow and SendInput, everything works fine! I've tried checking GetForegroundWindow immediately after SetForegroundWindow, but this does not help. GetForegroundWindow has the new value immediately."*

Esto explica por qué tu gate "foreground stable for 2 reads" no es suficiente: `GetForegroundWindow()` ya devuelve el HWND nuevo aunque el target todavía no haya bombeado la notificación. Es exactamente lo que muestra `chains5.json/chains6.json` (100%) vs `ref.json/final.json` (25–50%): con la máquina fría el bombeo cabe en la ventana implícita; saturada, no.

**H3 — Alta confianza, oficial Microsoft.** La propia clase `SendKeys` admite la fragilidad (Microsoft Learn, `SendKeys` doc):

> *"The SendKeys class is susceptible to timing issues, which some developers have had to work around. **The updated implementation is still susceptible to timing issues**, but is slightly faster …"*

Y declara explícitamente, cuando usa la implementación moderna `SendInput`:

> *"the SendWait method will not wait for messages to be processed when they are sent to another process."*

Es decir, `SendWait` no espera nada útil cross-process.

**H4 — Alta confianza, arquitectura UWP.** UWP Calculator no es una sola ventana. La top-level visible es `ApplicationFrameWindow` propiedad de `ApplicationFrameHost.exe`; el control real está en un `Windows.UI.Core.CoreWindow` hijo, propiedad del proceso `CalculatorApp.exe` (Shlomi Boutnaru en Medium, "The Windows Process Journey — ApplicationFrameHost.exe"; behind.flatspot.pictures "Hacking and Modding UWP"; AutoHotkey forum thread "MouseGetPos: Why do I only get ApplicationFrameHost.exe…"). En el momento en que SendKeys dispara, el "foreground" puede ser el FrameWindow del host mientras el verdadero target keyboard-focus está migrando al CoreWindow hijo — y como `SetForegroundWindow` solo nudgea al top-level, hay un segundo paso (`WM_SETFOCUS` al CoreWindow) que ocurre en otro thread. Esto es exactamente tu evidencia "UWP Calculator sometimes has another window stealing foreground".

**H5 — Confianza media-alta, hipótesis del cold-start.** PowerShell tiene cold-start dominado por .NET. Microsoft Learn, "CLR Inside Out: Improving Application Startup Performance":

> *"In most cases, cold startup is I/O bound … the time it takes to launch the application is equal to the time it takes the OS to fetch code from disk plus the time it takes to perform additional processing such as JITing the IL code."*

Mediciones públicas confirmadas: PowerShell/PowerShell GitHub issue #17734 reporta **>4 s en Intel i7 sin módulos y >6 s con PSReadLine + oh-my-posh + Terminal-Icons**; woshub.com documenta hasta "varios minutos" en casos patológicos por validación CRL de PSReadLine. El proceso PowerShell que lanzas por cada batch de teclas introduce **0,5–6 s variables** entre tu "decidí inyectar" y el primer `WM_KEYDOWN`; en ese intervalo el foreground del sistema puede haber rotado. Esto **acopla** la latencia de inyección al estado de carga del sistema, lo cual reproduce la varianza load-dependent de `chains5/6` vs `ref/final`.

**H6 — Baja confianza, descartada.** Journal hook vs SendInput: la implementación moderna de `SendKeys` ya elige `SendInput` cuando el journal hook falla bajo UAC. Source code de Microsoft (referencesource.microsoft.com, `SendKeys.cs`): `enum SendMethodTypes { Default=1, JournalHook=2, SendInput=3 }`, con fallback automático a `SendInput` si el hook test falla. Por tanto el problema NO es journal-hook deprecation.

**Asunciones que conviene verificar en tu código real (declarado como hipótesis pendiente):**
- Si tu launcher PowerShell no es el foreground en el momento de invocar `SetForegroundWindow`, la llamada es no-op silencioso. Microsoft Learn, `SetForegroundWindow`: *"A process can set the foreground window by calling SetForegroundWindow only if: The calling process belongs to a desktop application, not a UWP app or a Windows Store app … The foreground process has not disabled calls to SetForegroundWindow by a previous call to the LockSetForegroundWindow function."*
- Si tu launcher no llama `AllowSetForegroundWindow(ASFW_ANY)` antes de spawnar Calculator, el foreground lock puede demotar la ventana recién creada a un botón parpadeante en la barra de tareas — no hay error, simplemente la ventana nunca toma foreground real (Microsoft Learn, `AllowSetForegroundWindow`).

---

### §7.2 — Tool hallucination en 4B (`system(action='calculator')`)

Causa: los 4B con tool-calling nativo no tienen capacidad para reproducir fielmente nombres que solo aparecen en system-prompt; emiten *plausibles* pero inexistentes. Evidencia directa: Healy et al. (Amazon, arXiv 2601.05214, *"Internal Representations as Indicators of Hallucinations in Agent Tool Selection"*):

> *"LLMs … suffer from hallucinations where they choose incorrect tools, provide malformed parameters and exhibit 'tool bypass' behavior by performing simulations and generating outputs instead of invoking specialized tools or external systems."*

Y arXiv 2510.22977 (*"The Reasoning Trap: How Enhancing LLM Reasoning Amplifies Tool Hallucination"*):

> *"reasoning-focused reinforcement learning inherently amplifies tool hallucination across different training methods and model families … current mitigation strategies reduce tool hallucination at the direct expense of reasoning performance."*

Esto último explica directamente tu observación §7.6: reasoning ON ⇒ tool-call 6/6 pero tokens ↑; OFF ⇒ 2/6.

### §7.3 — El 4B no encadena pasos (0/12)

Coincide con la literatura. AgentHallu (Liu et al., arXiv 2601.06818, evalúa 13 modelos incluyendo GPT-5 y Gemini-2.5-Pro como top tier):

> *"The best-performing model achieves only 41.1% step localization accuracy, where tool-use hallucinations are the most challenging at just 11.6%."*

Si los top-tier están en 41,1 % en step-localization multi-step, un E4B-Q4 realísticamente no va a chainear 2-3 pasos sin ayuda externa. El `command_splitter` determinista es la decisión correcta para un 4B en vram4. Few-shot 2-3 ejemplos puede ayudar marginalmente pero la mediana no se moverá lo suficiente.

### §7.4 — Verificación de "texto entró" mejor que dHash

dHash con Hamming≥6 es invariante a cambios pequeños de píxeles — un "2+2" en una calculadora UWP cae bajo el threshold. UIA `Name`/TextPattern es universal en UWP/Win32 y la mayoría de Electron (Chromium expone accessibility tree). UWP Calculator: el código fuente de Microsoft (github.com/microsoft/calculator, `src/Calculator/Views/Calculator.xaml`) declara:

> *"`<controls:CalculationResult x:Name="Results" x:Uid="CalculatorResults" … AutomationProperties.AutomationId="CalculatorResults" AutomationProperties.HeadingLevel="Level1" AutomationProperties.Name="{x:Bind Model.CalculationResultAutomationName, Mode=OneWay}" …/>`"*

— AutomationId es estable, el valor se expone como `Name` con formato `"Display is <n>"` (confirmado en repro vivo en MrExcel y RPA Framework `RPA.Desktop.Windows`). **No** expone `ValuePattern` ni `TextPattern`.

### §7.5 — Router multilingüe mis-rute

La literatura es clara: abstain en multilingüe requiere calibración **por idioma**. Feng et al., EMNLP 2024 (*"Teaching LLMs to Abstain across Languages via Multilingual Feedback"*, ACL Anthology 2024.emnlp-main.239):

> *"directly applying existing solutions beyond English results in up to 20.5% performance gaps between high and low-resource languages."*

Hybrid RRF entre embedder semántico (MiniLM) y signal léxico (BM25 sobre verb-stems / Tool2Vec) tiene literatura sólida; añadir un margin-based abstain *"Decide only when (s1 - s2) ≥ δ and s1 ≥ τ_route"* (proagenticworkflows.ai, "Harnessing Semantic Routing for LLM Agents") sin hardcodear listas.

### §7.6 — Latencia de decode

p90 268 tokens / 4,3 s ≈ 62 tok/s. En E4B-Q4_K_M con 6 GB VRAM ese número es razonable pero no holgado para tier-Alexa. Tres palancas comprobables:

1. **N-gram cache de llama.cpp** (no requiere segundo modelo, no consume VRAM extra). Doc oficial `llama.cpp/docs/speculative.md`: *"An implementation with draft model can be mixed with an implementation without draft model."*
2. **Drafter externo `gemma-3-270m` Q4** (~150-200 MB VRAM). Google Developers Blog ("Introducing Gemma 3 270M"): *"Gemma 3 270M brings strong instruction-following capabilities to a small-footprint model … it establishes a new level of performance for its size"* (51,2 % en IFEval reportado oficialmente).
3. **Reducir thinking budget** sin tirar reasoning: en Gemma 3 hay control de tokens de razonamiento; en lugar de OFF (que da 2/6) cap a 64-128 tokens.

PRECAUCIÓN — caveat de fuente. thc1006/qwen3.6-speculative-decoding-rtx3090 (bench público con metodología verificable):

> *"No speculative-decode configuration achieves a net speedup over the non-speculative baseline on this hardware. Mean decode drops 3–12 % across ngram-cache, ngram-mod, and classic draft … every configuration hits a bimodal tail reaching as low as 59–67 tok/s."*

Es modelo-específico (Qwen3.6 MoE), pero indica que **se debe medir** antes de adoptar.

---

## 2. Recomendaciones priorizadas

### P0 — §7.1: Eliminar PowerShell-per-keystroke, mover a in-process SendInput con secuencia Chen-correct

**Qué cambiar:** reemplazar el spawn de PowerShell + `System.Windows.Forms.SendKeys.SendWait` por una función Python que llame `user32.SendInput` vía ctypes, en el mismo proceso del orquestador. Antes de inyectar, ejecutar la secuencia canónica:

```python
# Pseudocódigo
ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
# launcher: ShellExecute / Process.Start de calc.exe
WaitForInputIdle(hProcess, 5000)
hwnd = find_top_level_for_pid(pid)         # ApplicationFrameWindow
SetForegroundWindow(hwnd)
SendMessageTimeoutW(hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, 1500, byref(_))  # Chen ping
# Recorrer hijos hasta CoreWindow:
target = find_child(hwnd, class_name="Windows.UI.Core.CoreWindow") or hwnd
# Esperar UIA HasKeyboardFocus en el control deseado
wait_uia_focus(target, timeout_ms=800)
SendInput(...)   # KEYEVENTF_UNICODE para "5+3="
```

**Por qué (con fuente):**
- `SendMessageTimeout(WM_NULL)` es la técnica documentada por Raymond Chen para serializar la activación cross-thread-group (devblogs.microsoft.com/oldnewthing, 20161118-00).
- `AllowSetForegroundWindow(ASFW_ANY)` evita la demotación a taskbar (Microsoft Learn, `AllowSetForegroundWindow`): *"If this parameter is `ASFW_ANY`, all processes will be enabled to set the foreground window."*
- `WaitForInputIdle` espera al primer `GetMessage` del proceso (Microsoft Learn): *"enables a thread to suspend its execution until the specified process has finished its initialization and is waiting for user input with no input pending."*
- In-process elimina ~0,5–6 s de cold-start CLR/PowerShell por turno (issue PowerShell #17734).
- `SendInput` con `KEYEVENTF_UNICODE` evita problemas de layout/idioma. Microsoft Learn, `KEYBDINPUT`: *"INPUT_KEYBOARD supports nonkeyboard-input methods … as if it were text input by using the KEYEVENTF_UNICODE flag. If KEYEVENTF_UNICODE is specified, SendInput sends a WM_KEYDOWN or WM_KEYUP message to the foreground thread's message queue with wParam equal to VK_PACKET."* Esto es mucho mejor que SendKeys para multi-user/multi-language.
- **NO usar `AttachThreadInput`** para forzar foreground: Raymond Chen, *"I warned you: The dangers of attaching input queues"* (devblogs.microsoft.com/oldnewthing, 20080801-00): *"`AttachThreadInput(dwCurrentThread, dwFGThread, TRUE); SetForegroundWindow(hwnd); // hangs here` … Their customer feedback data shows that this function often hangs at the second call to SetForegroundWindow."*

**Experimento mínimo de validación:**
Repetir tu eval saturada con N=25 (la condición que daba 0%), midiendo 4 variantes en paralelo:

1. Status quo (PowerShell + SendKeys).
2. PowerShell + SendKeys + Sleep(50) post-SetForeground.
3. In-process ctypes SendInput **sin** ping.
4. In-process ctypes SendInput **con** `SendMessageTimeout(WM_NULL)` + verificación `UIA HasKeyboardFocus`.

Métricas: success_rate, p50/p90 latencia entre "tool decidido" y "primera key vista por UIA `CurrentName` cambiado", varianza entre runs cold/hot.
**Hipótesis falsable:** la varianza load-dependent desaparece (σ < 50 ms) en (4) y success ≥ 95 % bajo saturación.

**Tabla comparativa de métodos:**

| Método | Fiabilidad UWP | Fiabilidad Win32 | Fiabilidad Electron/CEF | Latencia inyección | Depende de foreground | Complejidad | OSS/free | Veredicto |
|---|---|---|---|---|---|---|---|---|
| (a) `System.Windows.Forms.SendKeys.SendWait` (proceso PowerShell nuevo) | Baja (race + AFH) | Media (race en cold) | Media-baja | Alta (cold CLR 0,5–6 s) | Sí | Baja | Sí | Estado actual — RECHAZAR |
| (b) `SendInput` (ctypes/pywin32, in-proc) + ping Chen + UIA gate | Alta | Alta | Alta (acepta SendInput como input físico) | Muy baja (µs) | Sí (pero gestionado) | Media | Sí | **ELECCIÓN P0** |
| (c) `PostMessage(WM_CHAR)` directo al HWND | No fiable (XAML islands, CoreWindow) | Variable; muchos controles no procesan WM_CHAR como real | No fiable (Chromium) | Baja | No | Media | Sí | Solo como fallback para Win32 legacy con HWND de Edit conocido |
| (d) UIA `ValuePattern.SetValue` | No aplica a Calculator (no expone ValuePattern); sí a TextBox UWP | Alta para Edits con ValuePattern | Alta para inputs accesibles | Baja | No | Media | Sí | **Excelente** para campos editables/text inputs; **inútil** para botones (Calculator necesita keys) |
| (e) `keybd_event` | Mismas razas que (a) | Mismas razas | Mismas | Baja | Sí | Baja | Sí | Deprecated por Microsoft a favor de SendInput; no aporta |

**El "ready signal" más fiable** (jerarquía probada):

1. **`UIA AutomationElement.FocusedElement` == el control esperado** + `HasKeyboardFocus == True` + `IsEnabled == True` + `IsKeyboardFocusable == True`. Doc Microsoft "Implementing the UI Automation Value Control Pattern": *"A control should have its IsEnabledProperty set to true and its IsReadOnlyProperty set to false before allowing a call to SetValue."* Para teclas se añade `IsKeyboardFocusable`.
2. Si UIA no expone focus (UWP a veces), caer a `GetGUIThreadInfo(targetThreadId, &info).hwndFocus == hwndExpected` (Microsoft Learn, `GetGUIThreadInfo`).
3. `WaitForInputIdle(hProcess, 5000)` solo para el primer arranque.
4. **Nunca** confiar en "foreground stable for 2 reads": confirmado por Chen que `GetForegroundWindow` cambia inmediatamente aunque la activación no esté terminada.

---

### P0 — §7.4: Cambiar verificador dHash por UIA-name read

**Qué cambiar:** Después de inyectar, no comparar frames. Leer:

```python
# Pseudocódigo UIA (comtypes / uiautomation)
calc_results = root.FindFirst(TreeScope_Descendants,
    automation.CreatePropertyCondition(UIA_AutomationIdPropertyId, "CalculatorResults"))
display_text = calc_results.CurrentName   # "Display is 8"
# Fallback compact mode:
if calc_results is None:
    calc_results = root.FindFirst(..., "CalculatorAlwaysOnTopResults")
```

**Por qué (con fuente):** Código fuente Microsoft/calculator (`src/Calculator/Views/Calculator.xaml`) ya citado arriba. Confirmado en repro vivo en `mrexcel.com/board/threads/using-uiautomation-to-automate-the-windows-10-calculator.1137758`: *"`Condition to find the Calculator results / Name: \"Display is 7.82842712474619\" / AutomationId: \"CalculatorResults\"`"*. Y en RPA Framework `RPA.Desktop.Windows`: *"`Send Keys 5*2= / ${result}= Get element rich text id:CalculatorResults / Should Be Equal As Strings ${result} Display is 10`"*. Latencia típica 10–30 ms.

Para Win32 (Notepad): leer `ValuePattern.Current.Value` del control Edit hijo (clase `RichEditD2DPT` en Notepad moderno).
Para Electron: la mayoría exponen accessibility tree; UIA `TreeWalker.RawViewWalker` lo recorre.

**Experimento mínimo:** N=30 inyecciones "2+2" en Calculator, Notepad, VS Code; assert UIA-read == expected. Métrica: precision/recall de la verificación, latencia.

---

### P1 — §7.2: GBNF grammar restringida al subset de tools en llama-server

**Qué cambiar:** Generar dinámicamente una GBNF que enumere literalmente los nombres de tool válidos (root ::= `"calculator"` | `"notepad"` | …) o, equivalentemente, restringir el JSON-schema de la llamada al enum de tool-names. Enviar como `response_format` o `--grammar-file` al llama-server build b9090.

**Por qué (con fuente):** Doc oficial llama.cpp `grammars/README.md`: *"GBNF grammars are supported in various ways in tools/cli, tools/completion and tools/server … you can use it to force the model to generate valid JSON, or speak only in emojis."* DeepWiki llama.cpp: *"By converting a tool's JSON definition into a GBNF grammar, llama.cpp ensures the model strictly follows the function signature. This is often integrated via the response_format in llama-server."* Costo: overhead micro-segundos por token. Caveat de Hamilton & Mimno (arXiv 2502.14969, *"Lost in Space: Optimizing Tokens for Grammar-Constrained Decoding"*): la elección de tokens dentro de la grammar importa — *"Performance also improves by 5–10% when models are instructed to return tokens incorporating leading whitespace, with smaller models benefiting the most."* En consecuencia: respetar el formato nativo de tool-calling de Gemma (no cambiar el wrapper); la grammar solo restringe el campo `name` al enum válido.

**¿Vale la pena vs latencia?** Sí. Una grammar pequeña (decenas de reglas) añade <1 ms por token y elimina por construcción el `system(action='calculator')`.

**Experimento mínimo:** Re-correr eval de 50 prompts con tool-calls. Métrica: % de tool-calls inválidas pre vs post grammar. Hipótesis: cae a 0 % por construcción; tok/s baja <5 %.

---

### P1 — §7.6: Speculative decoding en llama.cpp — N-gram primero, drafter después

**Qué cambiar (orden):**

1. Habilitar n-gram cache (no requiere modelo extra, no come VRAM). `llama.cpp/docs/speculative.md` confirma: *"speculative decoding … can significantly accelerate token generation by predicting multiple tokens ahead of the main model … An implementation with draft model can be mixed with an implementation without draft model."*
2. Si tras medir el speedup es < 1,3×, probar drafter externo `gemma-3-270m` Q4 (~150-200 MB VRAM). Google Developers Blog: *"Gemma 3 270M brings strong instruction-following capabilities to a small-footprint model."* Bajo Apache-2.0.

**Caveat de fuente (importante):** El bench público thc1006/qwen3.6-speculative-decoding-rtx3090 reporta *"No speculative-decode configuration achieves a net speedup over the non-speculative baseline on this hardware. Mean decode drops 3–12 %"* en Qwen3.6 MoE Q4 sobre RTX 3090. Es modelo-específico, pero indica que **se debe medir** antes de adoptar, no asumir el speedup teórico 2-3×.

**Experimento mínimo:** llama-bench con prompt típico de tool-call de tu sistema, 3 configs: baseline / n-gram / drafter 270m. Métricas: tok/s, p90 latencia end-to-end, success-rate de tool-call (la spec-dec es lossless en teoría, pero gramáticas + spec interactúan: ver discussion ggml-org/llama.cpp #15341 sobre tool-calling internamente usando su propia grammar).

---

### P2 — §7.3: Mantener `command_splitter` determinista

**Qué cambiar:** Nada estructural. Documentar la decisión. El splitter mide FORM (cuántos verbos imperativos, conjunciones coordinantes vía embeddings multilingües) — eso respeta tu restricción "structural guards measuring FORM not content".

**Por qué (con fuente):** AgentHallu (arXiv 2601.06818, evalúa 13 modelos incluyendo GPT-5 y Gemini-2.5-Pro): *"The best-performing model achieves only 41.1% step localization accuracy, where tool-use hallucinations are the most challenging at just 11.6%."* Tu medición 0/12 en E4B-Q4 es consistente con esta literatura: si los top-tier están en 41,1 %, un 4B local realmente no chainea.

**Experimento mínimo (sanity check):** few-shot 5 ejemplos en system-prompt mostrando chain de 2 acciones, re-correr los 12 mismos prompts. Si sigue ≤ 4/12 con few-shot: confirmado, mantener splitter. Si sube a ≥ 9/12: reconsiderar.

---

### P2 — §7.5: Endurecer router multilingüe sin hardcodes

**Qué cambiar:**

1. Re-calibrar abstain head **por idioma** (no globalmente). Recoger 200-500 ejemplos por idioma de prod + sintéticos, fit logistic-regression simple sobre `[s1_minilm, s1_tool2vec, s1-s2, embedding_norm, lang_id_prob]`. Esto **no es hardcode**: es un clasificador entrenado.
2. Hybrid RRF: combinar score MiniLM con score Tool2Vec con `1/(60+rank)`. Margin-abstain con τ y δ por idioma.
3. Para "what is X?" disparando acción: añadir un **clasificador de modalidad** (interrogativa vs imperativa) entrenado con MiniLM multilingüe, NO regex.

**Por qué (con fuente):** Feng et al., EMNLP 2024 (*"Teaching LLMs to Abstain across Languages via Multilingual Feedback"*, ACL Anthology 2024.emnlp-main.239, Feng, Shi, Wang, Ding, Ahia, Li, Balachandran, Sitaram, Tsvetkov): *"directly applying existing solutions beyond English results in up to 20.5% performance gaps between high and low-resource languages."* MKA (arXiv 2503.23687): *"the MKA pipeline can improve the accuracy of an LLM by abstaining when it lacks confidence in the responses instead of confabulating. This validates confidence calibration with multilingual knowledge as a useful tool to tackle model hallucination."* Guía de producción (proagenticworkflows.ai): *"Margin-based abstain: Decide only when (s1 - s2) ≥ δ and s1 ≥ τ_route … Otherwise clarify or hit a safe default."*

**Experimento mínimo:** Hold-out test set 300 ejemplos balanceados ES/EN, métricas precision@route, recall@route, abstain-correctness, vs baseline actual.

---

## 3. Lo que sé con evidencia vs lo que asumo

### Con evidencia documentada (fuentes en §5):
- `SetForegroundWindow` es asíncrono cross-thread-group (Raymond Chen, Microsoft, oficial).
- `SendKeys.SendWait` no espera procesamiento cuando target está en otro proceso (Microsoft Learn, oficial).
- UWP Calculator usa AutomationId="CalculatorResults", expone solo `Name` (no Value, no Text). Source code github.com/microsoft/calculator confirma.
- llama.cpp soporta GBNF y speculative decoding (docs oficiales).
- gemma-3-270m existe como drafter potencial (Google Developers Blog).
- AttachThreadInput puede colgar el proceso (Raymond Chen, oficial).
- SendKeys internamente ya prefiere SendInput cuando journal hook no aplica (referencesource.microsoft.com `SendKeys.cs`).

### Asumido / DEBE verificarse en TU código real antes de aplicar (CRÍTICO):
- **Asumido**: tu launcher PowerShell se invoca como subprocess hijo del orquestador Python. Verificar: ¿qué proceso es foreground cuando spawns Calculator? Si tu Python no es foreground, `SetForegroundWindow` puede ser no-op silente. Trivialmente comprobable con `GetForegroundWindow()` justo antes del spawn.
- **Asumido**: el "window-ready gate" actual solo mira `GetForegroundWindow()`. Si ya mira UIA `HasKeyboardFocus`, ignora esta crítica.
- **Asumido**: la verificación dHash compara la ventana entera de la calculadora (~600×400 px) con 64-bit hash; el display ocupa ~10 % del área. Verificar área de hash exacta — si solo cubre display, Hamming≥6 puede ser razonable; si cubre toda la ventana, "2+2 no detectado" es esperable.
- **Asumido**: `chains5/chains6` (100 %) corrieron en bench fría (sistema recién booteado, pocos procesos), `ref/final` (25–50 %) tras varios runs acumulados. Verificar con timestamps de eval + `Get-Counter '\Processor(_Total)\% Processor Time'` y RAM disponible por run. Sin esta verificación, la conclusión "load-dependent" es plausible pero no comprobada.
- **Asumido**: el splitter actual ya es language-agnostic (embeddings). Si usa lista de conjunciones por idioma, viola la restricción "no hardcodes per language".
- **No verificado**: que el drafter `gemma-3-270m` sea vocabulario-compatible con `gemma-4-E4B-it` para speculative decoding en llama.cpp. Compatibilidad de tokenizer es requisito (LM Studio doc, llama.cpp). Probablemente sí (misma familia), pero **medirlo** antes de comprometer la solución.
- **Asumido**: vuestro `gui_type` ya escapa `+^%~(){}[]` correctamente. Sin ver el código no puedo confirmar; si NO escapa correctamente, sería una segunda fuente independiente de pérdida de chars y conviene auditar antes de migrar a SendInput (Unicode-mode evita el problema por construcción).

### Lo que NO sé y no puedo afirmar:
- Si Electron apps específicas (Discord, VS Code) responden mejor a SendInput o a UIA `ValuePattern.SetValue` — depende del ARIA-role que Chromium publique al árbol UIA.
- El número exacto de tokens drafted óptimo en n-gram cache para tu prompt-mix.
- Si tu prompt actual de tool-call ya viene con grammar implícita del chat-template de Gemma 3 o no — ggml-org/llama.cpp discussion #15341 indica que tool-calling internamente puede usar su propia grammar dependiente del modelo; conviene auditar logs server para ver qué `grammar` queda activa.

---

## 4. Respeto a las restricciones duras

- **OSS / free**: todas las propuestas (ctypes, UIA via comtypes / `uiautomation`, llama.cpp GBNF nativo, gemma-3-270m Apache-2.0, MiniLM router, Tesseract como fallback OCR) son OSS. **Picovoice y cloud APIs no aparecen.**
- **vram4 (~6 GB)**: ctypes/UIA no consumen VRAM. GBNF añade <1 MB CPU. Speculative con `gemma-3-270m` Q4 sumaría ~150-200 MB VRAM — VERIFICAR que cabe junto a E4B-Q4 (~3,8 GB modelo + KV cache; el headroom es de ~2 GB, alcanza). N-gram cache es 0 MB VRAM, primera elección.
- **STT en CPU**: no tocado.
- **Vision (mmproj)**: explícitamente NO requerida. UIA `CurrentName` read sustituye a frame-diff sin necesidad de VLM.
- **Tier-Alexa 4–5 s**: in-process SendInput corta ~0,5–6 s de cold-start PowerShell por turno. Spec-dec / n-gram puede sumar 20–40 % de speedup en decode — pero **no asumir hasta medir**, dada la evidencia de bimodalidad en consumer GPUs.
- **No hardcodes per language**: GBNF tool-grammar es estructural (form), no semántica per idioma. Calibración del router por idioma usa modelos aprendidos, no listas. Splitter mide FORM (verbos imperativos vía embeddings multilingües).
- **Verify by OS state**: TODA la verificación pasa de pixels (dHash) a estado de OS (UIA `CurrentName`, `HasKeyboardFocus`, `IsEnabled`).
- **Multi-user universal**: SendInput con `KEYEVENTF_UNICODE` es layout-independent (no asume QWERTY ni un idioma del sistema). UIA AutomationId es invariante por idioma del usuario. GBNF actúa sobre tokens, no sobre lenguaje natural.

---

## 5. Fuentes (URLs)

Win32 / SendKeys / Foreground race
- Raymond Chen, "Why does calling SetForegroundWindow immediately followed by GetForegroundWindow not return the same window back?", The Old New Thing, 18 Nov 2016 — https://devblogs.microsoft.com/oldnewthing/20161118-00/?p=94745/
- Raymond Chen, "I warned you: The dangers of attaching input queues", The Old New Thing, 1 Aug 2008 — https://devblogs.microsoft.com/oldnewthing/20080801-00/?p=21393/
- Microsoft Learn, `SetForegroundWindow` — https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow
- Microsoft Learn, `AllowSetForegroundWindow` — https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-allowsetforegroundwindow
- Microsoft Learn, `WaitForInputIdle` — https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-waitforinputidle
- Microsoft Learn, `GetGUIThreadInfo` — https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getguithreadinfo
- Microsoft Learn, `KEYBDINPUT` (SendInput + KEYEVENTF_UNICODE) — https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-keybdinput
- Bypassing SetForegroundWindow restrictions (gist) — https://gist.github.com/Aetopia/1581b40f00cc0cadc93a0e8ccb65dc8c
- Raymond Chen sobre input-queue isolation (asincronía focus) — https://devblogs.microsoft.com/oldnewthing/20130607-00/?p=4143
- Empirical lost keystrokes thread — https://comp.os.ms-windows.programmer.win32.narkive.com/rYZnuS6o/setforegroundwindow-sendinput-timing-problems

SendKeys / .NET / journal hook
- Microsoft Learn, `SendKeys.Send` y `SendKeys.SendWait` — https://learn.microsoft.com/en-us/dotnet/api/system.windows.forms.sendkeys.send y https://learn.microsoft.com/en-us/dotnet/api/system.windows.forms.sendkeys.sendwait
- Microsoft Learn, `SendKeys` class — https://learn.microsoft.com/en-us/dotnet/api/system.windows.forms.sendkeys
- .NET ReferenceSource `SendKeys.cs` — https://referencesource.microsoft.com/System.Windows.Forms/winforms/Managed/System/WinForms/SendKeys.cs.html (también dotnetframework.org mirror)
- Microsoft Learn, "Simulate keyboard events — Windows Forms" — https://learn.microsoft.com/en-us/dotnet/desktop/winforms/input-keyboard/how-to-simulate-events
- dotnet/winforms issue #7945, "SendKeys.SendWait sends wrong characters" — https://github.com/dotnet/winforms/issues/7945
- Microsoft/WinAppDriver issue #356, "SendKeys does not always send all characters" — https://github.com/Microsoft/WinAppDriver/issues/356
- pywinauto issue #1023, "Intermittent issues with type_keys going out of focus" — https://github.com/pywinauto/pywinauto/issues/1023

UWP / ApplicationFrameHost / CoreWindow
- Microsoft Calculator source — https://github.com/microsoft/calculator/blob/main/src/Calculator/Views/Calculator.xaml
- Shlomi Boutnaru, "The Windows Process Journey — ApplicationFrameHost.exe", Medium — https://medium.com/@boutnaru/the-windows-process-journey-applicationframehost-exe-210430eebad1
- behind.flatspot.pictures, "Hacking and Modding UWP" — https://behind.flatspot.pictures/hacking-windows-universal-apps-uwp/
- AutoHotkey forum — https://www.autohotkey.com/boards/viewtopic.php?style=7&t=112906
- Microsoft Learn, `CoreWindow` — https://learn.microsoft.com/en-us/uwp/api/windows.ui.core.corewindow
- MrExcel UIA Calculator sample — https://www.mrexcel.com/board/threads/using-uiautomation-to-automate-the-windows-10-calculator.1137758/
- RPA Framework `RPA.Desktop.Windows` — https://rpaframework.org/libraries/desktop_windows/python.html

UIA / Value / Text / Focus
- Microsoft Learn, "Implementing the UI Automation Value Control Pattern" — https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/implementing-the-ui-automation-value-control-pattern
- Microsoft Learn, `ValuePattern.SetValue` — https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.valuepattern.setvalue
- Microsoft Learn, `WindowPattern.WaitForInputIdle` — https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.windowpattern.waitforinputidle
- Microsoft Learn, `IsKeyboardFocusable` — https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.automationelementinformation.iskeyboardfocusable
- Microsoft Learn, "UI Automation TextPattern Overview" — https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-textpattern-overview
- Microsoft Learn, "Text and TextRange Control Patterns (Win32)" — https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-implementingtextandtextrange
- FlaUI ValuePattern source — https://github.com/FlaUI/FlaUI/blob/master/src/FlaUI.UIA2/Patterns/ValuePattern.cs
- pywinauto docs — https://pywinauto.readthedocs.io/en/latest/code/pywinauto.keyboard.html
- KeyWin (ctypes SendInput wrapper) — https://github.com/winstxnhdw/KeyWin

PowerShell / CLR cold-start
- Microsoft Learn, "CLR Inside Out: Improving Application Startup Performance" — https://learn.microsoft.com/en-us/archive/msdn-magazine/2008/march/clr-inside-out-improving-application-startup-performance
- Microsoft Learn, "Troubleshoot PowerShell startup issues" — https://learn.microsoft.com/en-us/powershell/scripting/dev-cross-plat/performance/startup-performance
- woshub.com — https://woshub.com/powershell-slow-startup/
- PowerShell/PowerShell issue #17734 — https://github.com/PowerShell/PowerShell/issues/17734

llama.cpp / GBNF / speculative decoding
- llama.cpp `grammars/README.md` — https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- llama.cpp `docs/speculative.md` — https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md
- llama.cpp README — https://github.com/ggml-org/llama.cpp
- DeepWiki llama.cpp "Grammar and Structured Output" — https://deepwiki.com/ggml-org/llama.cpp/8.1-grammar-and-structured-output
- ggml-org/llama.cpp discussion #15341 (gpt-oss y grammar interacción con tool-calling) — https://github.com/ggml-org/llama.cpp/discussions/15341
- LM Studio 0.3.10 speculative decoding — https://lmstudio.ai/blog/lmstudio-v0.3.10
- Hamilton & Mimno, "Lost in Space: Optimizing Tokens for Grammar-Constrained Decoding", arXiv 2502.14969 — https://arxiv.org/abs/2502.14969
- thc1006 benchmark Qwen3.6 speculative — https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090

Gemma 3 / 270M / Gemma 4 drafters
- Google Developers Blog, "Introducing Gemma 3 270M" — https://developers.googleblog.com/en/introducing-gemma-3-270m/
- Hugging Face `google/gemma-3-270m` — https://huggingface.co/google/gemma-3-270m
- Build Fast with AI, "Gemma 4 MTP Drafter" — https://www.buildfastwithai.com/blogs/gemma-4-mtp-drafter-faster-inference

Tool hallucination / multi-step / abstain multilingüe
- Healy et al. (Amazon), "Internal Representations as Indicators of Hallucinations in Agent Tool Selection", arXiv 2601.05214 — https://arxiv.org/abs/2601.05214
- "The Reasoning Trap: How Enhancing LLM Reasoning Amplifies Tool Hallucination", arXiv 2510.22977 — https://arxiv.org/abs/2510.22977
- Liu et al., "AgentHallu: Benchmarking Automated Hallucination Attribution of LLM-based Agents", arXiv 2601.06818 — https://arxiv.org/abs/2601.06818
- Feng et al., EMNLP 2024, "Teaching LLMs to Abstain across Languages via Multilingual Feedback" — https://aclanthology.org/2024.emnlp-main.239/
- MKA, "Leveraging Cross-Lingual Consensus for Model Abstention", arXiv 2503.23687 — https://arxiv.org/abs/2503.23687
- proagenticworkflows.ai, "Harnessing Semantic Routing for LLM Agents" — https://proagenticworkflows.ai/harnessing-semantic-routing-for-llm-agents-in-ai-agentic-workflows
- Microsoft Multilingual MiniLM — https://huggingface.co/microsoft/Multilingual-MiniLM-L12-H384

---

**Nota final sobre cómo aplicar este informe:** cada recomendación trae su experimento mínimo. **No despleguéis ningún cambio sin correr antes su experimento bajo la condición saturada** (la que daba `ref/final` 25-50 %). El cambio de mayor ROI esperado es P0-§7.1 (in-process SendInput + Chen ping + UIA gate); si ese solo no levanta la success-rate por encima del 90 % bajo saturación, no tiene sentido tocar §7.2/§7.6 todavía — significaría que hay un segundo factor independiente (probablemente el escaping `gui_type` o que el HWND elegido es el `ApplicationFrameWindow` y no el `CoreWindow` hijo, lo que sería confirmable inspeccionando el árbol UIA con Accessibility Insights).