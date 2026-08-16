# Handoff — Computer-use / Accesibilidad (noche 2026-05-31)

**Para Emmanuel, cuando despiertes.** Resumen honesto de lo que hice, qué está
verificado, y la prueba física de 1 minuto que te toca a vos.

---

## El bug que reportaste ("NO lo hizo")

Tu test por voz fue: **"Abre el bloque de notas y escríbele Hola Mundo"**.
Lo rastreé en los logs: routeó a **`notes_tasks`** (creó una nota), NO a
computer_use → por eso no escribió nada en el Notepad.

**Causa raíz (la encontré + arreglé):** el detector de escritura asumía el stem
`escrib-` SIN acento, pero **"escríbele"** (imperativo tú + clítico -le) lleva el
acento en la PRIMERA i (`escrí-bele`). El regex `escrib[íie]` no lo matcheaba →
el comando se escapaba al flujo normal → el 4B lo mandó a notes. **Fix:**
`escr[íi]b` (matchea escrib… Y escríb…). Commit `762a502`.

---

## Qué hice esta noche (3 commits)

| Commit | Qué |
|---|---|
| `762a502` | Fix del acento "escríbele/escríbe" (la causa de tu "NO lo hizo") |
| `da13178` | **Routing**: detector estructural "escribí/hacé X en app Y" / "andá a Y y hacé X" → computer_use (antes solo ~1/10 llegaba; el resto charlaba o iba a notes/browser/whatsapp) |
| `ac40748` | **Plan determinista** focus_app+type: el 4B planner a veces daba plan VACÍO o tipeaba toda la frase; ahora se construye estructuralmente (app + texto exactos) |

---

## Qué está VERIFICADO (medido, sin tocar tu máquina)

Corrí el agente + LLM real con la ejecución física **mockeada** (cero SendInput).
Barrida de robustez: **18/18 comandos de tipeo** (varios verbos escribí/tipeá/poné/
digitá/escribe/write, apps notepad/calc/word/discord/claude code, ES+EN, variantes
STT "Claudio Code"/"bloque de notas") + **2/2 screenshots** → ruta correcta; y
**11/11 controles** que NO deben ir a computer_use rutearon bien (whatsapp/notes/
audio/web/media/reminder/calendar). Ejemplos del plan CORRECTO:
  - "Abre el bloque de notas y escríbele Hola Mundo" → `focus_app('bloque de notas') + type('Hola Mundo')` ✓
  - "poné reunión a las 5 en el bloc de notas" → `type('reunión a las 5')` ✓ (antes tipeaba toda la frase)
  - "abrí la calculadora y escribí 5+5" → `type('5+5')` ✓ (antes: plan vacío = no hacía nada)
  - "andá a Claude Code y escribí continuá" → `focus_app('Claude Code') + type('continuá')` ✓
- **"sacá un screenshot"** → tool de captura (`gui.screenshot`) ✓
- **8/8 controles** siguen bien (NO se rompió nada): "mandale a juan"→whatsapp,
  "anotá X en mi lista"→notes, "subí el volumen"→audio, "reproducí en spotify"→media…
- **206 tests verde** + la suite amplia (exit 0).
- `_focus_app` ya **abre la app si está cerrada** (app.open + reintento) → "ABRE el
  bloc de notas y…" funciona aunque el Notepad no esté abierto.

## Qué NO pude verificar (y por qué — esto es honesto)

**La ejecución física real (el tipeo por SendInput).** Corro como terminal DENTRO
de VS Code (lo confirmé: mi proceso es hijo de `Code.exe`). El tipeo sintético
(SendInput) va a la ventana en foco; si algo falla, le pega a VS Code y **lo cierra
→ mato mi sesión y pierdo toda la noche de trabajo**. Además, mientras dormías el
sistema de permisos auto-denegaba abrir/cerrar apps (no había quién apruebe). Por
responsabilidad NO arriesgué tu máquina ni mi sesión.

**Lo que verifiqué es exactamente lo que estaba roto** (routing + el plan). El tipeo
en sí lo hace la máquina existente (`type_into`, con todos sus fixes de foco) — la
misma que ya daba 92.7% en el eval de GUI.

---

## TU PRUEBA (1 minuto, cuando despiertes)

Por voz o por la UI, probá estos. **Observá: ¿escribe el texto correcto en la app
correcta?**

1. **"escribí hola mundo en el bloc de notas"** (con el Notepad abierto) → debe
   tipear "hola mundo" ahí.
2. **"Abre el bloque de notas y escríbele Hola Mundo"** (el que falló) → debe
   abrir/enfocar Notepad y tipear "Hola Mundo".
3. **"andá a Claude Code y escribí continuá"** → enfoca Claude Code, tipea "continuá".
4. **"sacá un screenshot"** → captura la pantalla.
5. Controles que NO deben cambiar: **"subí el volumen"**, **"mandale a juan que ya
   voy"** (debe pedir/usar whatsapp, no tipear en una app).

Si **1-3 escriben el texto correcto** → el núcleo de accesibilidad quedó destrabado.
Si algo falla, decime QUÉ pasó (¿abrió la app? ¿tipeó algo? ¿texto equivocado?) y lo
cierro al toque.

---

## Lo que sigue (con vos despierto, para poder verificar físico)

- **Etapa 4 — desktop aislado** (CreateDesktop, como el PiP de UFO2): correr el
  computer-use en un escritorio separado para que YO pueda probar el SendInput real
  sin cerrar tu VS Code. **Esto es lo próximo a construir** — destraba que verifique
  todo físico yo, y que vos sigas usando la máquina mientras el agente actúa.
- **Etapa 2 — encadenar tools de alto nivel**: instalar (ya anda por `package`),
  "hazme un Word", navegar web multi-paso (UNIEJ→Canvas). Lo difícil (web con login)
  tiene techo bajo hasta para el SOTA (~52%); se hará con handoff honesto.
- **Etapa 5 — grounding (OmniParser local)** para apps sin UIA (juegos, web custom).

## Notas técnicas (para mí / la próxima sesión)

- `extract_app_action` + `parse_type_action` viven en `routing/command_splitter.py`.
  El short-circuit está en `agent.py::_decide_turn` (ANTES del split y del reply-net),
  gate `GEMMA4_APP_ACTION_NET=0`. Llama `t_computer_use` DIRECTO para el plan
  determinista (execute() rechaza `steps` por `additionalProperties:false`).
- Precisión por estado del SO: `_window_title_in_text` (act_in_app exige ventana real;
  por eso "poné X en mi lista" NO se hijackea → notes).
- Harness reusables: `scripts/_diag/_diag_accessibility_gap.py` (routing+plan),
  `_diag_app_action.py`, `parse_type_action` offline.
- **GOTCHA crítico:** NUNCA correr `run_content` con un comando de tipeo SIN mockear
  `PlanExecutor.execute` → dispararía SendInput físico → cierra VS Code.
