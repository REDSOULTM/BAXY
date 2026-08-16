# Modos de accesibilidad — Baxy

**Fecha:** 2026-05-26
**Estado:** implementado y medido (capa lógica); verificación física end-to-end pendiente del usuario.

## Propuesta de valor (lo "defendible")

Baxy es un asistente de voz **100% local y gratuito** que corre en **≤4 GB de
VRAM** (perfil único `vram4` = E2B-Q4, con voz + transcripción en CPU + visión
residente). Esto habilita una propuesta de valor que un asistente en la nube no
puede igualar de forma trivial:

1. **Privacidad.** Todo el procesamiento (voz, pantalla, acciones) ocurre en la
   máquina del usuario. Para alguien con discapacidad, que el asistente "vea" su
   pantalla y opere su PC sin enviar nada a un servidor es un diferencial real.
2. **Inclusión en hardware modesto.** No requiere GPU cara ni suscripción. Corre
   en una laptop típica.

Sobre esa base se construyeron **tres modos de accesibilidad**, separados porque
las necesidades **perceptuales** (no vidente) y **motoras** (movilidad reducida)
son distintas y, en parte, opuestas — distinción respaldada por WCAG 2.1/2.2.

## Los tres modos

| Modo | Para quién | Garantía central |
|------|-----------|------------------|
| `normal` | uso general | sin cambios (anti-regresión) |
| `no_vidente` | no ve la pantalla | **todo por audio**: narra cada acción, lee la pantalla a pedido (capturándola con la tool de visión), describe errores/diálogos |
| `movilidad` | no usa teclado/mouse, ve bien | **control 100% por voz**: el agente nunca le pide tocar nada; confirma por voz lo irreversible |

Por qué separados y no un único "modo discapacitado": un no vidente quiere **más
audio** (narración total); alguien con discapacidad motriz **ve perfecto** y no
la necesita — quiere que el agente **actúe** por él. Un solo modo serviría mal a
ambos.

## Arquitectura (alineada a CLAUDE.md)

- **`accessibility.py`** — catálogo de modos: cada uno con un `system_hint`
  (multilingüe, describe el COMPORTAMIENTO esperado, **sin frases enlatadas**) +
  flags estructurales (`narrate_all_actions`, `hands_free_only`,
  `read_screen_on_demand`, `confirm_irreversible_spoken`, `preferred_tools`).
  Persistencia en `~/.gemma4/active_accessibility_mode.txt`.
- **`accessibility_voice.py`** — activación por voz **por embeddings multilingües**
  (no keywords por idioma): clasifica el turno contra centroides de anclas en 5
  idiomas + una clase `none` que absorbe el uso normal. Solo cambia de modo si un
  switch es argmax, le gana a `none` por margen y cruza un piso. Fallback seguro:
  encoder caído → no cambia.
- **`reply_validator.py`** — dos **guardas estructurales** (miden la FORMA del
  reply del LLM, nunca su contenido ni el texto del usuario):
  - `asks_user_manual_action` (movilidad): si el reply le pidió al usuario hacer
    clic/teclear, inyecta corrección "actuá vos". Por embeddings.
  - `reply_too_terse_for_blind` (no_vidente): si corrió una acción pero el reply
    es mudo/escueto ("Listo"), pide una confirmación hablada descriptiva. Por
    longitud + actividad de tools.
- **Integración en `agent.py`**: el `system_hint` del modo se inyecta en el
  bloque estable del system prompt (cache-friendly); las `preferred_tools` se
  nudgean al subset del router; las guardas se aplican gateadas al modo activo
  (default-off para `normal`).
- **UI**: chip de modo en el panel substrate (React) + endpoints `GET/PUT
  /accessibility`. También conmutable por voz.

## Medición (gates definidos de antemano — CLAUDE.md §3)

Reproducible con `python scripts/accessibility_eval.py` (encoder real). Última
corrida 2026-05-26:

| Gate | Criterio | Resultado |
|------|----------|-----------|
| G1 activación por voz | aciertos ≥90% ∧ falsos-positivos = 0 | **PASS** — 10/10, 0 FP |
| G2 movilidad hands-free | FP = 0 ∧ recall ≥0.70 | **PASS** — recall 100%, 0 FP |
| G3 no_vidente narración | 100% correcto | **PASS** — 6/6 |
| G4 anti-regresión `normal` | hint vacío ∧ sin flags ∧ sin preferred_tools | **PASS** |

Sobre un set más amplio y ruidoso (incluyendo fraseos borderline), la activación
por voz midió ~30/31 y la guarda hands-free ~13/14, **siempre con 0 falsos
positivos** — la propiedad de seguridad clave: ningún comando cotidiano dispara
un cambio de modo espurio, y ninguna respuesta legítima se corrige de más.

**Tests unitarios:** 58 (mock-only, deterministas) — catálogo/persistencia,
lógica de activación, ambas guardas. Cero regresión en los 24 tests previos de
`reply_validator`.

## Límites honestos (lo que falta / no se garantiza)

- **Verificación física end-to-end pendiente del usuario.** La capa lógica está
  medida; falta correr en vivo (con voz real + pantalla real) que, p.ej., en
  no_vidente la narración efectivamente se escuche por TTS en cada acción. Esa
  prueba la corre el usuario (correr input sintético cierra el entorno de dev).
- **La guarda hands-free es conservadora**: prefiere un falso-negativo ocasional
  (una instrucción manual que se cuela) antes que molestar con una corrección
  espuria. El `system_hint` es la defensa primaria; la guarda es el backstop.
- **La confirmación de lo irreversible la decide el LLM** (vía system_hint), no
  un clasificador de "irreversibilidad" (que sería keywords frágiles). Multi-
  lingüe por diseño.
- **Techo del control por voz** = el del computer-use: apps con UIA rico; en
  Chromium la lectura cae a OCR/visión. Heredado, no específico de accesibilidad.

## Fuentes

- WCAG 2.2 — https://www.audioeye.com/post/wcag-22/
- WCAG 2.1 success criteria — https://www.levelaccess.com/blog/wcag-2-1-exploring-new-success-criteria/
