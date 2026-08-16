# Investigación propia — Control GUI tipo humano (computer-use) para vram4

**Fecha:** 2026-05-24
**Por:** Claude (investigación con fuentes web reales, en paralelo al prompt
`PROMPT_RESEARCH_computer_use_gui_control.md` enviado a claude.ai).
**Propósito:** evidencia de primera mano para CONTRASTAR con la respuesta de
claude.ai y decidir con triangulación, no con una sola fuente.

---

## TL;DR (lo que la evidencia ya deja claro, con fuentes)

1. **El techo del SOTA es bajo y caro.** El mejor agente de computer-use en
   Windows hoy (CoAct-1, multi-agente con modelos frontera) llega a **52.5% en
   WindowsAgentArena** y 60.8% en OSWorld; humanos ~72%. Incluso lo mejor falla
   ~half. (arXiv 2508.03923, arXiv 2409.08264)
2. **Un VLM de 7B PURPOSE-BUILT para GUI (UI-TARS-1.5-7B) saca 27.5% en OSWorld
   y 49.6% de grounding en ScreenSpot-Pro, y es vision-native (pixeles, ~8-16GB
   cuantizado).** O sea: el camino "VLM que ve la pantalla" NI cabe en vram4 NI
   es muy fiable (acierta el click ~la mitad en UIs difíciles). Esto es la
   evidencia más fuerte CONTRA depender de visión por paso. (HF ByteDance-Seed/
   UI-TARS-1.5-7B)
3. **El patrón que SÍ transfiere: UIA primario + visión solo para huecos
   (UFO², Microsoft).** "hybrid UIA–vision identifies custom elements missed by
   UIA alone"; y **speculative multi-action baja el costo de inferencia 51.5%**
   consolidando varios pasos en 1 LLM call. Esto encaja con vram4 (UIA es texto
   barato) y con latencia. (arXiv 2504.14603)
4. **La visión es además un VECTOR DE ATAQUE.** Botones falsos / parches de
   imagen / perturbaciones inducen acciones maliciosas en agentes que leen
   pixeles (Visual Confused Deputy 2603.14707, MIP 2503.10809, VPI-Bench
   2506.02456). Leer el árbol UIA (estructura) es menos spoofeable que leer
   pixeles → otro argumento PRO UIA-first.
5. **Verificación sin VLM es viable y es lo correcto:** UIA expone
   *property-change events* (señal de que algo cambió sin screenshot), pero
   pueden dispararse de más → hay que diff-checkear. (MS Learn UIA events)

**Conclusión de mi parte:** la arquitectura ganadora para vram4 NO es "darle
ojos (VLM) al 4B por cada paso". Es **UIA-first + verificación estructural
(frame-diff/UIA-delta) + visión como último recurso raro**, con el 4B decidiendo
el OBJETIVO y macros deterministas resolviendo los pasos. Coincide con lo que ya
intuíamos — pero ahora con números.

---

## Hallazgos por tema (con fuentes)

### 1. Benchmarks reales — el techo del computer-use (2025-2026)

| Sistema | Modelo | OSWorld | WindowsAgentArena | Modalidad |
|---|---|---|---|---|
| CoAct-1 (SOTA, ago 2025) | multi-agente frontera | 60.8% | **52.5%** | híbrido |
| Agent S2.5 | frontera | 56.0% | — | visión |
| UI-TARS-1.5 (full) | grande | 42.5% | — | visión-native |
| **UI-TARS-1.5-7B** | **7B local** | **27.5%** (100 pasos) | — | **visión-native (pixeles)** |
| UI-TARS-1.5-7B grounding | 7B | ScreenSpot-Pro **49.6%** | — | pixeles |
| Humano | — | ~72% | ~72% | — |

**Lectura para nosotros:** un 4B-text (Gemma 4 E4B) NO va a igualar a un 7B
visión-native entrenado para GUI. El objetivo "misiones GUI arbitrarias
confiables" es, hoy, NO alcanzable de forma general ni siquiera por el SOTA. Lo
**alcanzable** es el subset de apps con buen árbol UIA + misiones acotadas +
verificación dura. Hay que ser honesto con RED: techo real, no promesa de "todo".

Fuentes: [WindowsAgentArena (arXiv 2409.08264)](https://arxiv.org/pdf/2409.08264),
[CoAct-1 (arXiv 2508.03923)](https://arxiv.org/pdf/2508.03923),
[UI-TARS-1.5-7B (HuggingFace)](https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B).

### 2. UFO² — la arquitectura de referencia (Microsoft, abr 2025)

- **HostAgent** (descompone la tarea) + **AppAgents** especializados con APIs
  nativas + capa de acción GUI–API unificada.
- **Hybrid control detection**: fusiona UIA con parsing visual para los widgets
  custom que UIA no ve. UIA es el primario; visión rellena.
- **Speculative multi-action**: predice y valida una SECUENCIA de acciones en 1
  LLM call → **−51.5% de costo de inferencia sin perder fiabilidad**. o1 logró
  −58.5% de pasos.
- **Para nosotros:** la idea de "1 LLM call decide varios pasos" es oro para la
  latencia tier-Alexa, PERO el caveat es que un 4B predice secuencias peor que o1
  → adoptarlo con cautela y medición (no asumir el −51% en Gemma 4).

Fuente: [UFO² (arXiv 2504.14603)](https://arxiv.org/abs/2504.14603).

### 3. Verificación post-acción SIN VLM (el corazón de la viabilidad vram4)

- **UIA property-change events** (`UIA_AutomationPropertyChangedEventId`): señal
  nativa de "algo cambió" sin screenshot. CAVEAT oficial de MS: pueden dispararse
  aunque el estado NO haya cambiado → siempre diff-checkear el valor real.
- **Frame-diff** (hash de pixeles antes/después con mss): barato (~decenas de ms),
  detecta cambio visual. Trampa conocida: cursor/blink/reloj generan falsos →
  threshold por canal + ignorar regiones volátiles.
- **Win32 SetWinEventHook** (EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_*): eventos
  push, ~0ms, ideal para confirmar foco/ventana nueva.
- **Combinación recomendada (mi lectura):** UIA-delta como señal primaria
  (estructural, barata), frame-diff como respaldo cuando no hay UIA, Win32 events
  para foco. Visión NUNCA para verificar (carísimo + spoofeable).

Fuente: [MS Learn — UIA Events Overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-eventsoverview).

### 4. CEF / Electron (Discord, Spotify, Obsidian) — el caso difícil + su gotcha

- El flag **`--force-renderer-accessibility=complete`** existe y fuerza el árbol
  de accesibilidad en Chromium/Electron.
- **GOTCHA CRÍTICO (verificado):** Chromium construye el árbol AX **lazy y async**
  — *la primera lectura tras activar devuelve VACÍO; las siguientes funcionan*.
  Cualquier cascada debe **reintentar el walk UIA tras un delay** antes de caer a
  OCR/visión, o va a fallar el primer intento siempre en estas apps.
- Electron también responde a `app.setAccessibilitySupportEnabled(true)` y a la
  presencia de tecnología asistiva (JAWS/NVDA) — por eso a veces "se despierta"
  solo.

Fuentes: [Chromium a11y overview](https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/overview.md),
[screenpipe issue #3002 (Obsidian/Discord/Spotify árbol vacío → OCR caro)](https://github.com/screenpipe/screenpipe/issues/3002).

### 5. Seguridad — un agente que mueve mouse/teclado es superficie de ataque

- **Prompt injection es el riesgo #1 (OWASP LLM Top-10 2025)** y OpenAI admite que
  para agentes de browser "puede que nunca se resuelva del todo".
- **La VISIÓN agrava el riesgo:** botones falsos / parches de imagen invisibles /
  perturbaciones inducen acciones maliciosas en agentes que leen pixeles
  (Visual Confused Deputy, Malicious Image Patches, VPI-Bench). → leer UIA
  (estructura) es MENOS spoofeable que leer pixeles.
- **Mitigaciones de la literatura:** (a) clasificar la acción GUI por riesgo y
  bloquear/confirmar las irreversibles; (b) detectar campos de password/secreto
  para NO teclear/loguear; (c) "single-shot planning" (planear antes de observar
  contenido potencialmente malicioso → integridad de control-flow); (d) guardrail
  fuera del loop perceptivo (clasificador dual del target visual + del
  razonamiento).
- **Para nosotros:** ya tenemos `safety.classify_tool_call` + `grounding_gate` +
  honesty guard. Hay que EXTENDERLOS a las acciones GUI crudas (un `gui.click` en
  coords arbitrarias hoy no pasa por gate de riesgo). Y nunca teclear en campos de
  contraseña.

Fuentes: [VPI-Bench (arXiv 2506.02456)](https://arxiv.org/pdf/2506.02456),
[Visual Confused Deputy (arXiv 2603.14707)](https://arxiv.org/pdf/2603.14707),
[OpenAI sobre prompt injection en browser agents (CyberScoop)](https://cyberscoop.com/openai-chatgpt-atlas-prompt-injection-browser-agent-security-update-head-of-preparedness/).

---

## Puntos de CONTRASTE con el prompt enviado a claude.ai

Cuando vuelva la respuesta de claude.ai, contrastar específicamente:

1. **¿Confirma que visión-por-paso NO cabe en vram4?** Mi evidencia: UI-TARS-7B
   es ~8-16GB y solo 27.5% OSWorld. Si claude.ai propone un VLM residente,
   rechazar con estos números.
2. **¿Propone UIA-first + verificación estructural?** Debería coincidir con UFO².
   Si propone "screenshot + VLM cada paso", contrastar con el costo/fiabilidad.
3. **¿Menciona el gotcha del árbol AX lazy/async en Chromium?** Es un detalle de
   implementación que separa una respuesta teórica de una aplicable. Si no lo
   menciona, su cascada CEF fallará en la práctica.
4. **¿Pone un techo honesto?** Si promete "misiones arbitrarias confiables con
   4B", es sobre-venta — el SOTA frontera no llega. Buscar que delimite el subset
   alcanzable.
5. **¿Trata speculative multi-action con cautela para 4B?** El −51.5% de UFO² es
   con o1/GPT-4o, no con un 4B. Si lo da por hecho en Gemma 4, marcar como
   hipótesis a medir.
6. **¿Incluye el riesgo de seguridad del control de mouse + injection visual?**
   Si lo omite, agregarlo (es tier-1 risk 2026).

---

## Mi recomendación preliminar (a validar contra claude.ai + medición propia)

**Arquitectura para vram4 (orden de prioridad):**
1. **Cerrar el "click ciego"** primero: verificación post-acción por UIA-delta +
   frame-diff (sin VLM). Es lo de menor riesgo y mayor honestidad. Cabe seguro.
2. **Macros deterministas observe→act→verify** (`click_label`, `fill_field`): el
   4B da el objetivo, el código resuelve los pasos. UFO²-style sin el VLM.
3. **Cascada UIA → OCR (PaddleOCR, ya instalado) → visión (Gemma mmproj) SOLO de
   último recurso**, con reintento del walk UIA por el bug lazy de Chromium.
4. **CEF flag** para Discord/Spotify (con relaunch cuidado + el gotcha async).
5. **Gate de riesgo para acciones GUI crudas** + no-teclear-en-passwords +
   confirmación de irreversibles. Extender lo que ya tenemos.
6. **Speculative multi-action** SOLO si medimos que Gemma 4 lo hace fiable
   (probable que no al nivel de o1 — medir antes).

**Techo honesto para RED:** "controlar el PC como humano" es alcanzable para el
**subset de apps con buen UIA + misiones acotadas + verificación dura**. Para
UIs arbitrarias / juegos / apps custom-render, el SOTA mundial falla la mitad —
no se lo prometamos. La meta realista: subir nuestra tasa de éxito en misiones
GUI medidas, no "completar cualquier misión imposible".

---

## Fuentes (todas verificadas esta sesión)

- WindowsAgentArena: https://arxiv.org/pdf/2409.08264
- CoAct-1 (SOTA Windows 52.5%): https://arxiv.org/pdf/2508.03923
- UI-TARS-1.5-7B (27.5% OSWorld, 49.6% ScreenSpot-Pro, vision-native): https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B
- UFO² Desktop AgentOS (UIA+vision híbrido, speculative −51.5%): https://arxiv.org/abs/2504.14603
- MS Learn UIA Events (property-change, verificación sin screenshot): https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-eventsoverview
- Chromium accessibility (flag + árbol lazy/async): https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/overview.md
- screenpipe #3002 (Discord/Spotify/Obsidian árbol vacío): https://github.com/screenpipe/screenpipe/issues/3002
- VPI-Bench visual prompt injection: https://arxiv.org/pdf/2506.02456
- Visual Confused Deputy: https://arxiv.org/pdf/2603.14707
- MIP malicious image patches hijack OS agents: https://arxiv.org/pdf/2503.10809
- OpenAI: prompt injection puede no resolverse en browser agents: https://cyberscoop.com/openai-chatgpt-atlas-prompt-injection-browser-agent-security-update-head-of-preparedness/
