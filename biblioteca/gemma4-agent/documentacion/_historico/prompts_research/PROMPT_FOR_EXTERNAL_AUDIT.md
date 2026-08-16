# Prompt para auditoría externa de Carter Agent

> Copy/paste el bloque de abajo a una conversación nueva con Claude
> (claude.ai, Sonnet 4.6 o superior recomendado). Después pegale los
> 9 archivos `.md` listados al final.

---

## Bloque a pegar (con los .md adjuntos)

```
Necesito que audites la arquitectura de un agente local Windows
voice-first llamado Carter Agent. El objetivo del proyecto es:
"asistente de voz local que cubre el uso TOTAL del PC del usuario"
(similar a Jarvis/Alexa pero 100% local, sobre llama.cpp + Gemma 4
GGUF).

Características clave:
- 100% local (sin cloud, sin API keys externas obligatorias).
- Voice-first: Vosk (wake) + Whisper (STT) + Piper (TTS), todo offline.
- 65 compound tools del LLM cubren: filesystem, audio, app launching,
  Steam, browser, media, whatsapp, gui automation, etc.
- 4 superficies de entrada: CLI, UI desktop PyQt6, UI Field React +
  FastAPI, servidor MCP para clientes externos.
- Stack: Python 3.11+, ~54 000 LOC, llama-server.exe como subprocess
  hijo, sqlite-vec para experience replay.

Contexto del proyecto:
1. Hice una auditoría exhaustiva del repo en su estado inicial.
2. Sobre esa auditoría diseñé un plan de 9 sprints de optimización.
3. Se ejecutaron 8 de los 9 sprints (el 9no — Sprint 3b — quedó
   diferido a propósito esperando 7-10 días de uso real para medir
   personas/microagents/skills).
4. Los documentos adjuntos describen EL ESTADO ACTUAL del repo
   post-plan (no el inicial). Cubren delta vs baseline para que veas
   qué se decidió y qué no.

Lo que quiero de vos:

A) VALIDAR EL RESULTADO
   - ¿La arquitectura actual está bien diseñada para el objetivo
     declarado ("voice-first local agent que cubre uso total del PC")?
   - ¿Hay alguna decisión arquitectónica que sea claramente incorrecta
     para ese caso de uso, aunque parezca razonable a primera vista?
   - ¿Falta algún componente crítico que el objetivo requeriría y que
     no veo en los docs?

B) SEÑALAR LO QUE SIGUE MAL
   - Tengo god classes conservadas conscientemente (MainWindow,
     SettingsDialog, los workers AgentWorker/AgentRunner divergentes).
     ¿Estás de acuerdo con conservarlas o es cobardía técnica?
   - El stack NLI (capability_classifier + mDeBERTa 280MB) lo maté por
     cache hit 3.2%. ¿Era buena decisión o me perdí valor en
     casos no-cache-hit?
   - `domain_tools.py` tiene 10 489 LOC con 33 functions. Top-level
     imports son livianos (lazy en cada función). ¿Está bien así o
     valdría splitearlo?
   - `state.json` con 84% zombies pendientes de purga (no se atacó):
     ¿es problema real o me preocupo de gusto?
   - Hay 3 sinks de observability (TraceLogger + LogRecorder/full +
     LogRecorder/chat + Telemetry opt-in). TraceLogger tiene 50+
     callers y migrarlo es alto riesgo. ¿Vale la pena migrar o el
     riesgo es real?

C) CUESTIONAR DECISIONES
   - ¿Conservar las 65 tools sin importar uso medido es defendible
     o estoy acumulando deuda?
   - ¿Mantener 6 personas hardcoded + 5 microagents + 10 skills sin
     datos de uso real es defendible o debería borrar sin esperar?
   - El `CORE_PROMPT` de 8.7 KB + `TOOL_RULES` con 35 entries:
     ¿es señal de un agente bien definido o de un prompt-bloated
     que el modelo va a ignorar partes?
   - 9 fuentes de apps en `AppResolver` (path + shortcuts + start_apps
     + uninstall_registry + 2× Steam + Epic + common_exe_roots + manual
     launch): ¿overengineering o cobertura razonable?

D) RECOMENDACIONES ACCIONABLES
   - 3 cosas concretas que harías DISTINTO si fueras yo, ordenadas por
     ROI/riesgo.
   - 1 cosa que NO tocarías aunque el código se vea feo.
   - 1 trampa silenciosa que probablemente todavía no detecté.

Reglas para tu respuesta:
- Sé crítico. No me digas "bien hecho" si no lo está. Prefiero un
  audit duro pero honesto.
- Cita archivo:línea cuando referencies código específico (los docs
  ya tienen esas referencias).
- Si una decisión está justificada en mis docs, decímelo
  explícitamente ("vi que justificaste X por Y, estoy de acuerdo")
  o cuestionalo ("justificaste X por Y, pero Y no se sostiene
  porque..."). No me digas "deberías X" sin haber leído mi razón
  para no hacer X.
- Distinguí: "deuda real" vs "no-es-lindo-pero-funciona" vs
  "decisión de diseño consciente". No las mezcles.
- Si no podés decidir sin ver código, pedime el archivo específico.
  No inventes lo que dice un archivo que no leíste.
- Formato: secciones A/B/C/D del prompt arriba, en ese orden.

Archivos adjuntos (en este orden):

1. README.md — guía de navegación de los docs.
2. PLAN_CERRADO.md — cierre formal del plan, métricas globales.
3. 00_delta_inventory.md — qué archivos cambiaron, +/- por módulo.
4. 01_delta_system.md — containers actualizados, diagrama Mermaid.
5. 02_delta_components.md — los 9 módulos nuevos en detalle.
6. 03_delta_classes.md — UML de god classes post-refactor.
7. 05_delta_data.md — persistencia (3 sinks, state.json status).
8. 06_delta_dependencies.md — grafo, requirements.txt, pyproject.toml.
9. 08_findings_post_plan.md — deuda restante + Sprint 3b pendiente.

Por favor leé los 9 archivos completos antes de responder. Tomate el
tiempo que necesites.
```

---

## Los 9 archivos a adjuntar (en este orden)

| # | Path | Tamaño |
|--:|---|--:|
| 1 | `docs/architecture/README.md` | ~3.5 KB |
| 2 | `docs/architecture/PLAN_CERRADO.md` | ~9.6 KB |
| 3 | `docs/architecture/00_delta_inventory.md` | ~9.9 KB |
| 4 | `docs/architecture/01_delta_system.md` | ~10.8 KB |
| 5 | `docs/architecture/02_delta_components.md` | ~11.5 KB |
| 6 | `docs/architecture/03_delta_classes.md` | ~9.6 KB |
| 7 | `docs/architecture/05_delta_data.md` | ~8.4 KB |
| 8 | `docs/architecture/06_delta_dependencies.md` | ~5.2 KB |
| 9 | `docs/architecture/08_findings_post_plan.md` | ~11.7 KB |

**Total: ~80 KB de markdown.** Cabe holgado en el contexto de
Sonnet 4.6 / Opus 4.7. No necesitás dividir el mensaje.

---

## Por qué este prompt es mejor que "audita esto"

1. **Le doy contexto del objetivo** ("voice-first local agent que
   cubre uso total del PC"). Sin esto, Claude te recomienda
   genericidades de Python clean code.
2. **Le digo qué tipo de audit quiero** (validar resultado +
   señalar deuda + cuestionar decisiones). Sin esto, derivás en
   resumen ejecutivo aburrido.
3. **Le doy preguntas específicas** que vos ya viste como
   delicadas (god classes, NLI muerto, state.json, sinks). Sin
   esto, Claude no sabe dónde puede aportar más.
4. **Le pongo reglas anti-sycophancy** ("Sé crítico, no me digas
   bien hecho si no lo está"). Importante con Claude 4.x.
5. **Le pido formato específico** (secciones A/B/C/D). Sin esto,
   tirás 4000 tokens de prosa de difícil parseo.
6. **Le pido cita por archivo:línea**. Tus docs ya tienen
   referencias; sin esto la auditoría se queda en abstracción.
7. **Le doy permiso de pedir código que necesite**. Si dice
   "necesito ver agent.py:1234" se lo pasás. Auditoría iterativa.

## Cómo iterar después de recibir respuesta

Cuando Claude te conteste, vas a recibir:
- Sección A (validar resultado): si dice "está bien" en general,
  buscá la sección C donde sí cuestiona.
- Sección B (lo que sigue mal): tomá esas observaciones y compará
  con `docs/architecture/08_findings_post_plan.md §2/3`.
  Si menciona algo que vos ya documentaste como conservado
  conscientemente, está confirmando tu decisión.
  Si menciona algo NUEVO no documentado, es valor real.
- Sección C (cuestionar decisiones): es donde más vas a aprender.
  Las decisiones que defendiste explícitamente (god classes UI,
  workers divergentes) son donde más vas a recibir pushback —
  evaluá si los contraargumentos son sólidos.
- Sección D (3 acciones + 1 no-hacer + 1 trampa): el oro. Esto
  es lo que te puede orientar a un Sprint 7 si decidís que vale
  la pena.

## Para auditorías de segunda opinión

Si querés validar la respuesta de Claude contra otro modelo
(GPT-5, Gemini 2.5 Pro), usá el MISMO prompt cambiando el "Por
favor leé los 9 archivos" por instrucciones de carga apropiadas.
Comparar respuestas te dice qué hallazgos son robustos (los que
ambos modelos señalan) vs cuáles son artefacto de un modelo
específico.
