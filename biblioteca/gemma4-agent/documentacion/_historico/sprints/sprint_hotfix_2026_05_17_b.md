# HOTFIX 2026-05-17 (B) — "Listo" vacío + WhatsApp slot-filling falso

> Continuá el mismo chat de Claude Code (Sprints 0-8b + voice fixes
> 795f7a6/b38ec32 + hotfix A `c1531a1`).
> Dos bugs reportados por el usuario en la sesión de las 16:25-16:26
> del 2026-05-17.

---

## Contexto: los dos turns fallados

Del log `~/.gemma4/logs/_pre_session/chat.log`:

```
[16:26:14] YOU: Perfecto, gracias
[16:26:14] CONTEXT: session
[16:26:16] GEMMA: Listo.

[16:26:33] YOU: Dile a amor en wsp que la amo <3
[16:26:33] CONTEXT: whatsapp, contacts, state, session
[16:26:36] GEMMA: Necesito saber qué mensaje le quieres mandar y a qué contacto debo enviarlo.
```

### Bug 1 — "Listo." como respuesta a "Perfecto, gracias"

Subset: solo `session` (smalltalk gate funcionó). El LLM respondió
**"Listo."** que es absurdo en respuesta a un agradecimiento — uno
dice "de nada" o "no hay de qué", no "listo".

Causa raíz: [gemma4_agent/modes.py:91-98](gemma4_agent/modes.py#L91)
en el mode `fast_action`, el system_hint dice:

```
If a tool finished, ONE confirmation: 'Listo, X.' Nothing more.
```

Pero esa regla colapsa a **"decí Listo"** cuando NO hubo tool y el
contexto es puramente social. El LLM lo aplica como template de
ack universal.

### Bug 2 — WhatsApp no extrae slots de "Dile a amor en wsp que la amo"

Subset: `whatsapp, contacts, state, session` (correcto). El user dio
TODA la info en una sola frase:
- channel = "wsp" → whatsapp ✓
- contact = "amor" (alias guardado en contacts) ✓
- body = "que la amo <3" ✓

El LLM contestó "Necesito saber qué mensaje le quieres mandar y a qué
contacto debo enviarlo" — como si faltara TODO.

Causa raíz: [gemma4_agent/tool_schemas.py:42](gemma4_agent/tool_schemas.py#L42)
el schema de `whatsapp` tiene SLOT FILLING con un único ejemplo de
extracción positiva ("Hey gemma, mandale X a Juan en wsp") y un
ejemplo negativo ("dile amor → ask qué mensaje y a quién"). El LLM
tomó el negativo como template y se aplicó "amor" como caso ambiguo
cuando en realidad TODO el contenido estaba presente. Faltan ejemplos
que enseñen al LLM a parsear **patrones de oración complejos** donde
los tres slots están en distintas posiciones gramaticales.

---

## OBJETIVO DEL HOTFIX

Dos commits chicos, dos archivos modificados, cero cambios en
infraestructura:

1. `fix(modes)`: corregir el system_hint de fast_action para que no
   diga "Listo" cuando no hubo tool.
2. `fix(whatsapp-schema)`: enriquecer la descripción del schema de
   `whatsapp.send_message` con más ejemplos positivos de extracción
   de slots, incluyendo el patrón "Dile a X en wsp que Y".

---

## REGLAS GENERALES

1. PortandoLoMejor. Commits chicos, prefijos `fix(modes):` y
   `fix(whatsapp-schema):`.
2. NO toques router_v2, planner, agent.py, tool_descriptions.yaml,
   ni tools.py.
3. NO instales libs nuevas.
4. NO `git add -A`.
5. Verificación post-commit:
   - `python -m pytest gemma4_agent/ -q` debe seguir en 809 passed +
     1 pre-existing failure.
   - `python -c "import gemma4_agent; from gemma4_agent.modes import _build_mode_fast_action; print('ok')"` OK.
   - `python -m gemma4_agent.launcher status` corre.

---

## FIX 1 — `modes.py`: distinguir ack post-tool de ack social

### 1.1 — Cambiar el system_hint de fast_action

En [gemma4_agent/modes.py](gemma4_agent/modes.py), encontrar el
system_hint actual (línea ~91-98):

```python
system_hint=(
    "Mode: fast_action. You are a VOICE assistant — Alexa/Jarvis style. "
    "Reply in 1-2 sentences MAX, plain text. NO markdown, NO bullet "
    "lists, NO headers, NO emojis, NO disclaimers, NO 'te recomiendo X'. "
    "Direct facts only. If the user asks 'cuando salio GTA 5' say "
    "'17 de septiembre de 2013' — punto. No bullets, no extra context. "
    "If a tool finished, ONE confirmation: 'Listo, X.' Nothing more."
),
```

Reemplazar la última oración por:

```python
system_hint=(
    "Mode: fast_action. You are a VOICE assistant — Alexa/Jarvis style. "
    "Reply in 1-2 sentences MAX, plain text. NO markdown, NO bullet "
    "lists, NO headers, NO emojis, NO disclaimers, NO 'te recomiendo X'. "
    "Direct facts only. If the user asks 'cuando salio GTA 5' say "
    "'17 de septiembre de 2013' — punto. No bullets, no extra context. "
    "If a tool just finished successfully in this turn, ONE confirmation: "
    "'Listo, X.' (replace X with the concrete action, e.g. 'Listo, abrí Spotify'). "
    "If NO tool ran in this turn (small-talk, thanks, greetings, "
    "answering a question), respond naturally and DO NOT use 'Listo' "
    "as an ack — 'gracias' deserves 'de nada' or 'no hay de qué', "
    "not 'Listo'."
),
```

Punto clave: la regla anterior decía "if a tool finished" pero el LLM
la generalizaba. La nueva regla pone explícito el caso negativo
(NO-tool turn) y da el ejemplo concreto "gracias → de nada".

### 1.2 — Test

Crear `gemma4_agent/test_modes_fast_action_hint.py`:

```python
"""Regression test for the fast_action system_hint that previously
caused 'Listo.' to be emitted on no-tool turns (e.g. 'gracias').
"""
from __future__ import annotations

import unittest

from gemma4_agent.modes import _build_mode_fast_action  # adjust if name differs


class FastActionHintTest(unittest.TestCase):
    def test_hint_distinguishes_tool_ack_from_social_ack(self) -> None:
        # Build the mode and read the system_hint.
        # NOTE: if _build_mode_fast_action has different signature, just
        # construct it with whatever args are needed. The test only
        # checks the string content of system_hint.
        mode = _build_mode_fast_action(base_max_tokens=4096)
        hint = mode.system_hint or ""
        # Must still have the old positive: tool ack uses 'Listo, X.'
        self.assertIn("Listo", hint)
        # Must explicitly warn against using 'Listo' on no-tool turns.
        self.assertIn("NO tool ran", hint)
        # Must give a concrete counter-example for social acks.
        # Either 'de nada' OR 'no hay de qué' is fine.
        self.assertTrue(
            "de nada" in hint or "no hay de qué" in hint,
            f"hint should suggest a non-'Listo' social ack: {hint!r}",
        )


if __name__ == "__main__":
    unittest.main()
```

Si la API de `_build_mode_fast_action` no es esa exactamente, leé
`modes.py` para encontrar la función real y ajustar imports / kwargs.
Lo importante es que el test lea el `system_hint` final.

### 1.3 — Commit

`fix(modes): split tool-ack from social-ack in fast_action hint`

Mensaje de commit:

```
fix(modes): split tool-ack from social-ack in fast_action hint

User reported "Perfecto, gracias" → GEMMA responded "Listo." which is
absurd as an answer to a thank-you. Root cause: the fast_action
system_hint said `If a tool finished, ONE confirmation: 'Listo, X.'`,
which the LLM was generalizing as a universal ack template across
no-tool turns too.

Fix: split the rule explicitly. Positive case ('tool just finished
successfully' → 'Listo, X.') and negative case ('NO tool ran' →
natural reply, NOT 'Listo') are now two separate sentences. Adds a
concrete 'gracias → de nada' counter-example to anchor the LLM.

Pure prompt change, no code path affected. Test in
test_modes_fast_action_hint.py pins the contract.
```

---

## FIX 2 — schema de `whatsapp`: más ejemplos positivos de slot extraction

### 2.1 — Editar la descripción

En [gemma4_agent/tool_schemas.py](gemma4_agent/tool_schemas.py) línea
42, encontrar el campo `description` del schema `whatsapp`. En la
sección `SLOT FILLING`, agregar ejemplos POSITIVOS:

Buscar el bloque actual:

```
SLOT FILLING: if channel (whatsapp), contact, AND body are not all known from the conversation, do NOT call send_message — ask ONE missing slot in the user's language (detect from their last message). Order: body, then contact, then channel only if truly ambiguous. Examples:
  user 'dile amor'           -> ask 'qué mensaje le mando y a quién?' (ES)
  user 'tell her I love her' -> ask 'who should I send it to?' (EN)
  user 'dille ti amo'        -> ask 'a chi lo mando?' (IT)
Never reply 'no tengo una herramienta para enviar mensaje' — this tool exists; the slots are missing.
```

Reemplazar por:

```
SLOT FILLING: if channel (whatsapp), contact, AND body are not all known from the conversation, do NOT call send_message — ask ONE missing slot in the user's language (detect from their last message). Order: body, then contact, then channel only if truly ambiguous.

POSITIVE examples (all three slots present → CALL the tool, do NOT ask):
  user 'Dile a amor en wsp que la amo'
    -> whatsapp(action='send_message', contact='amor', text='que la amo')
  user 'Mandale a mama por whatsapp que llego tarde'
    -> whatsapp(action='send_message', contact='mama', text='que llego tarde')
  user 'Mandale a Juan en wsp: nos vemos a las 8'
    -> whatsapp(action='send_message', contact='Juan', text='nos vemos a las 8')
  user 'Decile a mi amiga por wsp que la quiero mucho'
    -> whatsapp(action='send_message', contact='mi amiga', text='que la quiero mucho')
  user 'Send mom on whatsapp: running late'
    -> whatsapp(action='send_message', contact='mom', text='running late')
  user 'Tell Juan I love him on wsp'
    -> whatsapp(action='send_message', contact='Juan', text='I love him')

PATTERN: 'Dile/Decile/Mandale a <CONTACT> [en|por] [wsp|whatsapp] que <BODY>' has all three slots. The contact comes right after the verb (dile/decile/mandale), and the body starts at 'que'. Aliases like 'amor', 'mama', 'papa', 'mi novio', 'mi hermana' ARE valid contact names — pass them as `contact=` and the contacts tool will resolve them.

AMBIGUOUS examples (slots missing → ASK):
  user 'dile amor'           -> ask 'qué mensaje le mando y a quién?' (ES) — no body, only verb + ambiguous word
  user 'tell her I love her' -> ask 'who should I send it to?' (EN) — pronoun, no concrete contact
  user 'dille ti amo'        -> ask 'a chi lo mando?' (IT) — no contact

Never reply 'no tengo una herramienta para enviar mensaje' — this tool exists; the slots are missing.
```

### 2.2 — Test

Crear `gemma4_agent/test_whatsapp_schema_slot_examples.py`:

```python
"""Regression test for the WhatsApp tool schema's SLOT FILLING section.

User reported 'Dile a amor en wsp que la amo' was treated as
ambiguous (LLM asked for body and contact, both of which were
present). The fix adds explicit POSITIVE examples for the
'Dile/Decile/Mandale a X en wsp que Y' pattern. This test pins
that those examples remain in the schema description.
"""
from __future__ import annotations

import unittest

from gemma4_agent.tool_schemas import TOOL_SCHEMAS


class WhatsappSchemaSlotExamplesTest(unittest.TestCase):
    def setUp(self) -> None:
        whatsapp = next(
            (s for s in TOOL_SCHEMAS
             if s.get("function", {}).get("name") == "whatsapp"),
            None,
        )
        self.assertIsNotNone(whatsapp, "whatsapp schema not found")
        self.description = whatsapp["function"]["description"]

    def test_has_positive_example_dile_amor_pattern(self) -> None:
        self.assertIn("Dile a amor en wsp", self.description)

    def test_has_positive_example_mama(self) -> None:
        self.assertIn("Mandale a mama", self.description)

    def test_distinguishes_positive_from_ambiguous_section(self) -> None:
        # Both sections must exist so the LLM has a clean comparison.
        self.assertIn("POSITIVE examples", self.description)
        self.assertIn("AMBIGUOUS examples", self.description)

    def test_lists_alias_examples(self) -> None:
        # The 'amor / mama / papa / mi novio' aliases should be
        # explicitly endorsed so the LLM treats them as valid contacts.
        # We check for a representative subset.
        for alias in ("amor", "mama"):
            self.assertIn(alias, self.description)

    def test_pattern_hint_present(self) -> None:
        self.assertIn("PATTERN", self.description)


if __name__ == "__main__":
    unittest.main()
```

Ajustá el `from gemma4_agent.tool_schemas import TOOL_SCHEMAS` al
símbolo real si el nombre exportado es otro (puede ser
`COMPOUND_TOOL_SCHEMAS`, `SCHEMAS`, etc.). Buscar con:

```bash
grep -n "^SCHEMAS\|^TOOL_SCHEMAS\|^COMPOUND_TOOL_SCHEMAS\|^_SCHEMAS" gemma4_agent/tool_schemas.py
```

### 2.3 — Commit

`fix(whatsapp-schema): add positive slot-extraction examples for 'Dile a X en wsp que Y'`

Mensaje de commit:

```
fix(whatsapp-schema): add positive slot-extraction examples

User reported "Dile a amor en wsp que la amo <3" was treated as
ambiguous — Gemma asked "qué mensaje le mando y a qué contacto?"
even though all three slots (channel=wsp, contact='amor',
body='que la amo') were present.

Root cause: the whatsapp schema's SLOT FILLING section had a strong
NEGATIVE example ('dile amor' → ask) but only one POSITIVE example
('mandale X a Juan en wsp'). The LLM applied the negative as a
template to any sentence containing 'dile amor', missing the body
that followed.

Fix: enriched the description with 6 positive examples covering
the 'Dile/Decile/Mandale a <CONTACT> [en|por] [wsp|whatsapp] que
<BODY>' pattern, an explicit PATTERN line that shows where each
slot lives in the sentence, and a callout that aliases ('amor',
'mama', 'mi amiga') are valid contact names. The ambiguous
section is preserved.

No code changes. Test in test_whatsapp_schema_slot_examples.py
pins the new examples.
```

---

## REPORTE FINAL

Devolveme:

1. Hash de los dos commits.
2. Output completo de `python -m pytest gemma4_agent/ -q --tb=line`
   (debe ser 809 + 4 nuevos = 813 passed, 1 pre-existing failure).
3. El texto FINAL del `system_hint` de fast_action (copy-paste del
   modes.py post-commit).
4. El texto FINAL del bloque SLOT FILLING del schema de whatsapp
   (copy-paste del tool_schemas.py post-commit).

## CRITERIO DE ÉXITO

- 2 commits aterrizados.
- 4 tests nuevos (3 en whatsapp + 1 en modes) verde.
- Suite completa verde (modulo la pre-existing failure de Sprint 3a).
- Working tree limpio.
- `python -m gemma4_agent.launcher status` OK.

## NO HACER (anti-scope)

- NO toques router, planner, agent, voice, tool_descriptions.yaml.
- NO modifiques la implementación real de la tool whatsapp en
  `domain_tools.py` — esto es puro prompt engineering.
- NO agregues casos en otros idiomas (PT/FR/DE) — ES+EN cubre el
  caso reportado y mantenemos el budget de tokens del schema bajo
  control.
- NO inviertas tiempo en validar que el LLM "ahora sí extrae bien"
  — eso lo prueba el usuario en uso real. Los tests sólo pinean el
  texto del prompt.
- NO toques modes.py más allá del system_hint de fast_action.
