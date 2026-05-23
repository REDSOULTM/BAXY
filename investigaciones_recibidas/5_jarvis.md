# CARTER OS — Loop proactivo de aprendizaje de patrones en vram4 (Gemma 4 E4B-it Q4_K_M)

## TL;DR
- **Sí es viable en vram4 SI separas roles**: la minería de patrones se hace con código determinista (PrefixSpan/BIDE + conteo contextual con ventana temporal) sobre un log SQLite, y el LLM de 4B sólo redacta y conversa la propuesta — nunca decide qué patrón existe. Esto cabe en ~4–6 GB de VRAM y respeta el presupuesto de 4–5 s por turno.
- **El umbral de sugerencia debe ser conservador** (≥5 repeticiones en ≥7 días, consistencia ≥0.6) y la oferta debe llegar en un "breakpoint" del usuario (fin de boot, cambio de foco, silencio del micrófono), no a media tarea — siguiendo Horvitz 1999 (dos umbrales: act / ask / wait, derivados de utilidad esperada) y Edwards et al. 2021, que reporta literalmente *"people interrupted sooner when interruptions were urgent"* y *"people also varied phrasing and delivery of interruptions to reflect urgency"*.
- **La conexión al `routine_tool` existente es una traducción 1-a-1**: cada patrón minado se mapea a un trigger ya soportado (`on_app_open`, `on_app_close`, `on_process_start`, `cron`, `on_phrase`) más una acción; el LLM sólo genera el texto de la propuesta y el handshake "sí/no/edítalo", igual al patrón "draft → blessing" de TaraHome (*"Tara does not guess. It observes. When behavior becomes structure, Tara drafts an automation, hands it to you in YAML, and waits for your blessing"*).

## Key Findings

1. **Existe un precedente directo y reciente (feb 2026): TaraHome / taraassistant-public** — un sidecar local para Home Assistant que observa eventos, detecta rutinas "consistentes" y redacta una automatización en YAML que el usuario aprueba. La filosofía es exactamente la que pide RED. El detector se describe en el README como *"conservative. It waits for consistency and avoids racing to conclusions. The goal is to surface things you clearly do on purpose, not noise from experiments or guests"*. Los umbrales numéricos exactos NO se publican (el README usa lenguaje cualitativo: "consistent enough", "stable enough", "opinionated"), pero la arquitectura — Event Collector → Pattern Detector → Automation Generator → human-in-the-loop — es replicable y prácticamente idéntica a lo que CARTER OS necesita.

2. **El marco teórico está claro y es estable desde 1999**: los 12 principios de Horvitz para interfaces mixed-initiative siguen siendo la base. Los más relevantes para CARTER OS son el #2 (considerar incertidumbre sobre las metas del usuario: *"Computers are often uncertain about the goals and current focus of attention of a user"*), #3 timing (*"Agents should employ models of the attention of users and consider the costs and benefits of deferring action to a time when action will be less distracting"*), #5 (usar diálogo para resolver incertidumbre), #6 (eficiencia para invocar/terminar), #7 (minimizar el costo de un mal "guess"), #10 (comportamiento socialmente apropiado) y #12 (*"Automated services should be endowed with the ability to continue to become better at working with users by continuing to learn"*). Horvitz formaliza el "cuándo ofrecer" como un umbral de probabilidad p\*: *"it is best for the system to take action if the probability of a goal is greater than p\* and to refrain from acting if the probability is less than p\*"*, con dos umbrales que dan tres regiones: act / ask / wait.

3. **El algoritmo correcto para vram4 es PrefixSpan (o su variante BIDE para patrones cerrados)** sobre el log SQLite. PrefixSpan es Python-puro, sin GPU, sin red, y trabaja con soporte mínimo configurable. La librería `prefixspan` en PyPI (chuanconggao/PrefixSpan-py) ofrece la API: `PrefixSpan(db).frequent(minsup)` y `top-k`; BIDE *"is usually much faster than PrefixSpan on large datasets, as only a small subset of closed patterns sharing the equivalent information of all the patterns are returned"*. Para detección de eventos individuales repetidos (no secuencias), conteo simple con ventana temporal es más barato y suficiente — *"cerrar Discord al boot"* es un patrón de soporte simple, no una cadena larga.

4. **El LLM 4B NO debe minar**. Según los benchmarks de InsiderLLM (Gemma Models Guide, mayo 2026), Gemma 4 E4B alcanza 69.4% MMLU-Pro, 52.0% LiveCodeBench v6, 42.5% AIME 2026 y 58.6% GPQA Diamond — sólido para conversar, pero un gist de Daniel Farina (abril 2026) advierte explícitamente que *"E4B is much weaker at tool calling than 26B"*. Pedirle al 4B que infiera patrones desde logs crudos sería: (a) lento (rompería el budget de 4–5 s al cargar cientos de eventos), (b) poco confiable (function-calling débil a 4B), (c) caro en contexto. La regla: **código determinista decide, LLM presenta y dialoga**.

5. **Anti-poison: el incidente del 52% de DB contaminada** se previene con (a) whitelist estricta de tipos de evento, (b) separación física entre `ExperienceMemory` (interacciones de chat) y `BehaviorLog` (eventos de SO), (c) versionado del esquema con migración destructiva si se detecta contaminación, (d) "stable signal only" — sólo se loguean eventos que pasan un filtro de relevancia.

6. **Privacidad y multi-usuario**: todo local en SQLite, perfil por usuario de Windows separado en `%LOCALAPPDATA%\carter_os\{username}\behavior.db`. El "modelo base" (prompts, lógica) NO se modifica; sólo la capa de perfil. Esto evita el riesgo de "over-personalization" señalado en la literatura de Dual User-Adaptation (arxiv 2003.13296), que disocia adaptación-de-usuario en una capa separada de la lógica del modelo base, *"with desirable properties regarding scalability and privacy constraints"*.

---

## Details

### 1. Detección barata, privada y local de patrones de comportamiento *(PRIORITARIO)*

**Diagnóstico**: el caso de uso de RED ("cierro X cada vez que arranco el PC") es un patrón de **soporte simple con contexto temporal** (no una secuencia larga). Tres clases de algoritmos cubren el espectro:

| Algoritmo | Precisión detección | Costo CPU/RAM | Privacidad | Complejidad código | Viable vram4 |
|---|---|---|---|---|---|
| **Conteo + umbral por contexto** (e.g., "evento E ocurrió N veces dentro de M minutos del trigger T") | Alta para patrones simples (1 evento ↔ 1 trigger) | Trivial (<10 MB, <50 ms) | Total local | ~50 líneas Python | ✅ Sí |
| **Association rules — Apriori / FP-Growth** (mlxtend) | Detecta co-ocurrencias ("abro Steam ⇒ cierro Discord") sin orden | Bajo. FP-Growth supera a Apriori en datasets densos (Heaton, "Comparing Dataset Characteristics…", arXiv 1701.09042) | Total local | Librería madura, ~100 líneas | ✅ Sí |
| **Sequential pattern mining — PrefixSpan / BIDE / SPADE** | Detecta secuencias ordenadas ("boot → abrir Chrome → cerrar Discord") | Bajo a moderado. Pei et al. (IEEE TKDE 16(11), 2004): *"PrefixSpan, in most cases, outperforms the apriori-based algorithm GSP, FreeSpan, and SPADE"* | Total local | `pip install prefixspan` | ✅ Sí |
| **HMM / RNN / LSTM** | Alta para anomalías | Requiere GPU para entrenar | Local pero costoso | Alto | ❌ NO en vram4 — competiría por VRAM con Gemma |
| **LLM como minero** (pedirle al modelo "encuentra patrones aquí") | Baja, alucinógeno | Alto en latencia | Local | Trivial pero engañosa | ❌ NO — rompería el budget de 4–5 s y daría falsos positivos |

**Recomendación**: pipeline en dos capas:

- **Capa A — Conteo contextual** (cubre el 80% de casos como el de RED): para cada par `(trigger_event, target_event, time_delta)`, mantén un contador. Cuando `count ≥ N_min` y `consistency = count / total_trigger_occurrences ≥ 0.6`, marca el patrón como candidato.
- **Capa B — PrefixSpan periódico** (cron nocturno, fuera del loop de chat): mina cadenas de 2–5 eventos sobre la ventana de los últimos 30 días con `minsup ≥ 0.5`. Esto descubre rutinas compuestas ("al abrir un juego, baja volumen de Spotify y cierra Discord").

**¿Cuántas repeticiones antes de sugerir?** La literatura no da un número canónico (TaraHome dice sólo "consistent enough"). Recomendación operativa basada en (a) la práctica de Horvitz (umbral p\* derivado de utility), (b) la precaución de TaraHome, (c) el hecho de que la asistencia errónea cuesta confianza:

- **Mínimo absoluto**: 5 ocurrencias del trigger.
- **Consistencia mínima**: 60% (3 de cada 5 veces que ocurre el trigger, el target también ocurre).
- **Ventana mínima**: 7 días (filtra experimentos de un día).
- **Cooldown anti-spam**: si el usuario rechaza el patrón, no volver a ofrecerlo por 30 días o hasta que `count` se duplique.

**Pseudocódigo de la Capa A** (encaja al lado de `experience.py`, **sin contaminarlo**):

```python
# behavior_log.py — tabla aparte, NO contamina ExperienceMemory
CREATE TABLE behavior_events (
    ts        INTEGER NOT NULL,    -- epoch ms
    user      TEXT NOT NULL,       -- Windows username
    kind      TEXT NOT NULL,       -- 'boot' | 'app_open' | 'app_close' | 'cmd' | 'correction'
    key       TEXT NOT NULL,       -- 'discord.exe', 'spotify.exe', etc.
    context   TEXT,                -- JSON: hour, foreground_app, prev_kind
    PRIMARY KEY (ts, user, kind, key)
);
CREATE INDEX idx_behavior_kind_key ON behavior_events(kind, key);

# pattern_miner.py — corre cada N horas, NO en el loop de chat
def mine_simple_patterns(db, user, window_days=30,
                        min_count=5, min_consistency=0.6,
                        delta_max_seconds=120):
    triggers = ['boot', 'app_open:steam.exe', 'cmd:start_work', ...]
    candidates = []
    for trig in triggers:
        trig_times = db.fetch_times(user, trig, window_days)
        if len(trig_times) < min_count:
            continue
        follow_counter = Counter()
        for t in trig_times:
            for ev in db.fetch_window(user, t, t + delta_max_seconds):
                follow_counter[(ev.kind, ev.key)] += 1
        for (kind, key), c in follow_counter.items():
            consistency = c / len(trig_times)
            if c >= min_count and consistency >= min_consistency:
                candidates.append(PatternCandidate(
                    trigger=trig, action=(kind, key),
                    count=c, consistency=consistency,
                    window=delta_max_seconds))
    return candidates
```

### 2. Cuándo y cómo sugerir sin ser intrusivo *(PRIORITARIO)*

**Diagnóstico**: el problema central de un asistente proactivo no es detectar — es **ofrecer en el momento correcto, con la fraseo correcto, y aceptar un "no" sin insistir**. Horvitz 1999 lo enmarca como un cálculo de utilidad esperada con dos umbrales: *"These two thresholds provide an instant index into whether to act, to engage the user in a dialog about action, or to do nothing, depending on the assessed likelihood of the user having a goal."* Edwards et al. 2021 (CUI '21, arXiv:2106.02077) aporta los hallazgos empíricos sobre cómo hablar: *"We found that people interrupted sooner when interruptions were urgent… People also varied phrasing and delivery of interruptions to reflect urgency."*

**Señales que deben gatillar la sugerencia** (todas tienen que cumplirse):

1. **Confianza del patrón** ≥ umbral (consistencia ≥ 0.6, count ≥ 5).
2. **Momento oportuno** — uno de:
   - El trigger acaba de ocurrir Y el usuario está en silencio (no hay TTS sonando, no hay STT activo).
   - El usuario acaba de cerrar una conversación con el asistente ("breakpoint" natural).
   - El sistema está idle (no se está reproduciendo media, no hay foco en juego fullscreen).
3. **Cooldown global**: máximo 1 sugerencia proactiva por hora, 3 por día.
4. **Cooldown por patrón**: si fue rechazado, espera 30 días.

**Fraseado por voz — patrón "Tara-style + Edwards"**:

```
"Oye, RED — noté que cada vez que prendes el PC,
cierras Discord a los pocos segundos. Lo hiciste 8 de
las últimas 10 veces. ¿Quieres que lo haga yo automáticamente?
Sí / no / edítame los detalles."
```

Tres elementos clave (alineados a Edwards et al. 2021):
- **Evidencia explícita** ("8 de las últimas 10 veces") → activa el principio Horvitz #1 (value-added) y #9 ("*We should design agents with the assumption that users may often wish to complete or refine an analysis provided by an agent*"). El usuario puede contestar "no, sólo cuando no esté Steam abierto" → CARTER edita la condición.
- **Access ritual opcional, no por default**: Edwards et al. reporta literalmente *"Some participants used access rituals to forewarn interruptions, but most rarely used them"* — la mayoría rara vez los usa. Hazlo una preferencia, no un comportamiento por default. Usa "Oye, RED" sólo en la primera sugerencia del día.
- **Tres salidas claras (sí / no / edita)** → cumple Horvitz #6 ("*efficient direct invocation and termination*") y #5 ("*If a system is uncertain about a user's intentions, it should be able to engage in an efficient dialog with the user, considering the costs of potentially bothering a user needlessly*").

**Cómo evitar el problema Clippy**:

| Anti-patrón Clippy | Mitigación en CARTER |
|---|---|
| Interrumpe a media tarea | Sólo en breakpoints (post-boot, post-chat, idle) |
| Repite la misma sugerencia | Cooldown 30 días tras rechazo |
| No aprende del rechazo | Persistir rechazos en `rejected_patterns` table |
| Confianza falsa ("¡seguro quieres X!") | Lenguaje hedge: "noté", "podría", "si quieres" |
| Sin canal de "cállate" | Comando global `/no_sugerencias_hoy` y `/no_sugerencias_nunca` |

**Comparativa de estrategias de timing**:

| Estrategia | Intrusividad | Precisión "momento" | Implementación | Viable vram4 |
|---|---|---|---|---|
| Inmediato al detectar | Alta (rompe foco) | Baja | Trivial | Sí pero NO recomendado |
| En el próximo breakpoint observado (silencio + foco estable) | Baja | Alta | ~30 líneas | ✅ Recomendado |
| Modelo de atención (eye tracking, working-memory modeling tipo ProMemAssist UIST '25) | Media | Muy alta | Muy alto | ❌ NO en vram4 |
| Diferir a "review semanal" (batch) | Mínima | Media | Trivial | ✅ Buena opción secundaria |

**Recomendación**: combinar **breakpoint inmediato** para 1 sugerencia/día como máximo + **review semanal opcional** ("¿revisamos las rutinas que detecté esta semana?") iniciado por el usuario.

### 3. Conectar el patrón detectado al sistema de rutinas existente *(PRIORITARIO)*

**Diagnóstico**: el handoff observación → rutina es una **traducción puramente sintáctica**. CARTER ya tiene los triggers (`on_app_open`, `on_app_close`, `on_process_start`, `on_process_exit`, `on_phrase`, `cron`, `once`, `manual`). El minero entrega un `PatternCandidate`; sólo hay que mapear.

**Tabla de mapping patrón → trigger del `routine_tool`**:

| Patrón detectado | Trigger del routine_tool | Acción |
|---|---|---|
| `boot → close X` (count≥5, consist≥0.6) | `on_process_start: explorer.exe` (proxy de "post-boot") o trigger custom `on_boot` | `close_app(X)` |
| `open A → close B` | `on_app_open: A` | `close_app(B)` |
| `close A → open B` | `on_app_close: A` | `open_app(B)` |
| `cada día a las HH:MM → comando C` | `cron: "MM HH * * *"` | ejecutar `C` |
| `frase F → acción A` (3+ veces con la misma frase) | `on_phrase: F` | acción mapeada |

**Flujo de datos completo**:

```
[Watcher de eventos]  ← psutil + win32gui + ExperienceMemory hook
        ↓ (insert)
[behavior_events SQLite]
        ↓ (cron job, e.g. cada 6h)
[pattern_miner.py]  → conteo + PrefixSpan
        ↓ (PatternCandidate list)
[suggestion_queue]   ← cooldowns, rechazo, dedup
        ↓ (cuando hay breakpoint)
[proactive_presenter] → llama a Gemma 4B SÓLO para redactar el texto
        ↓ (TTS)
       Usuario
        ↓ (STT respuesta)
[response_parser]    → sí / no / edit
        ↓ (si "sí")
[routine_tool.create]  ← API ya existente
```

**Pseudocódigo del handoff**:

```python
# proactive_loop.py
def on_breakpoint_detected(state):
    if state.tts_busy or state.foreground_is_fullscreen_game:
        return
    if global_cooldown.active():
        return

    candidate = suggestion_queue.pop_best()  # ya filtrado por cooldown/rechazo
    if not candidate:
        return

    # El LLM SÓLO redacta. La lógica está pre-decidida.
    prompt = render_suggestion_prompt(candidate)  # template fijo
    spoken = llm.generate(prompt, max_tokens=80, temperature=0.3)
    tts.speak(spoken)

    answer = stt.listen(timeout=8)
    parsed = parse_yes_no_edit(answer)  # regex + LLM fallback

    if parsed.kind == 'yes':
        routine = candidate.to_routine()  # ← traducción mecánica
        routine_tool.create(**routine)
        tts.speak("Listo, lo configuré.")
        log_acceptance(candidate)
    elif parsed.kind == 'no':
        rejected_patterns.add(candidate.fingerprint(), ttl_days=30)
        tts.speak("Entendido, no lo ofrezco más por un tiempo.")
    elif parsed.kind == 'edit':
        # Aquí SÍ usamos el LLM en modo conversacional para refinar
        refined = clarify_loop(candidate, parsed.edit_text)
        routine_tool.create(**refined)

def PatternCandidate.to_routine(self):
    # Mapping mecánico
    if self.trigger == 'boot':
        return {'trigger': 'on_process_start', 'trigger_arg': 'explorer.exe',
                'action': f'close_app:{self.action.key}',
                'name': f'auto_{self.action.key}_at_boot',
                'source': 'learned', 'confidence': self.consistency}
    if self.trigger.startswith('app_open:'):
        app = self.trigger.split(':')[1]
        return {'trigger': 'on_app_open', 'trigger_arg': app,
                'action': f'{self.action.kind}:{self.action.key}',
                ...}
    # etc.
```

**Verdict viabilidad vram4**: ✅ totalmente. La inferencia de Gemma sólo se invoca para (a) generar el texto de la sugerencia (~80 tokens, <2 s en E4B Q4_K_M sobre RTX 4060), y (b) parsear respuestas ambiguas como fallback al regex. Ambos caben holgados en el budget de 4–5 s/turno.

### 4. Rol del LLM vs reglas deterministas

**Diagnóstico**: la tentación de pedirle al LLM "mira estos logs y dime qué patrones ves" es alta pero rota para vram4. Razones:

1. **Latencia**: leer 1000 eventos como contexto + razonar puede tomar 10–30 s en E4B Q4_K_M. Fuera del budget.
2. **Confiabilidad a 4B**: aunque la guía de InsiderLLM (mayo 2026) reporta benchmarks decentes para E4B (MMLU-Pro 69.4%, LiveCodeBench v6 52.0%), el mismo ecosistema advierte que *"E4B is much weaker at tool calling than 26B"* (gist de Daniel Farina, abril 2026). Los SLMs alucinan patrones inexistentes en datos tabulares.
3. **Auditabilidad**: si el patrón se mina con código, RED puede leer el SQL que lo justificó. Si lo mina el LLM, es una caja negra.

**Arquitectura recomendada (división estricta)**:

| Componente | Implementación | Por qué |
|---|---|---|
| Watcher de eventos | Python + psutil + win32gui | Determinista, barato |
| Almacén | SQLite (separada de `ExperienceMemory`) | Anti-poison |
| Minería | `prefixspan` + conteo contextual | Reproducible, auditable |
| Scoring de patrones | Reglas (count, consistency, recency) | Sin alucinaciones |
| Cola de sugerencias + cooldowns | Reglas | Predecible |
| **Redacción de la sugerencia hablada** | **Gemma 4 E4B Q4_K_M** | Aquí brilla el LLM |
| **Parseo de respuesta ambigua del usuario** | **Gemma 4 E4B Q4_K_M (fallback)** | NLU robusto |
| **Diálogo de refinamiento ("edita")** | **Gemma 4 E4B Q4_K_M** | Aquí brilla el LLM |
| Creación de la rutina final | `routine_tool.create` (mecánico) | Sin riesgo |

**Esta división mantiene el sistema dentro del budget**: una sola invocación de LLM por sugerencia, ~80–200 tokens generados, latencia <3 s.

### 5. Privacidad y multi-usuario

**Diagnóstico**: todo es local, pero "local" no es lo mismo que "privado": si CARTER mezcla aprendizaje de varios usuarios de Windows en el mismo perfil, lo aprendido del operador degrada la experiencia de los demás.

**Recomendaciones**:

1. **Partición física por usuario**: `%LOCALAPPDATA%\carter_os\{windows_username}\behavior.db`. Cada usuario tiene su SQLite.
2. **Base lógica inmutable**: el system prompt, las reglas de seguridad, y los triggers válidos del `routine_tool` viven en una capa "base" que NO se modifica por aprendizaje. El perfil de usuario sólo agrega rutinas y `memory.py` k/v personales.
3. **Aislamiento al iniciar sesión**: al cambiar de usuario de Windows, CARTER recarga el perfil correspondiente. No usar caché compartida en RAM entre usuarios.
4. **Riesgo "over-personalization"**: el framework DUA (arxiv 2003.13296) demuestra que disociar adaptación-de-usuario del modelo base mantiene "scalability and privacy constraints". Mitigación práctica: las rutinas aprendidas viven en `routines_learned.json` separado de `routines_system.json`.
5. **Right to forget**: comando explícito `olvida lo que aprendiste de mí` → borra `routines_learned.json` y `behavior_events` del usuario, pero preserva la base.

### 6. Anti-poison: qué loguear y política de retención

**Diagnóstico**: la lección del incidente del 52% de contaminación es que **lo que se loguea silenciosamente termina dominando la realidad del sistema**. La regla es: *whitelist estricta, no blacklist*.

**Eventos que SÍ loguear** (señal estable, alto valor):

| Evento | Por qué | Frecuencia esperada |
|---|---|---|
| `boot` / `shutdown` | Trigger natural, ocurre 1–3×/día | ~3/día |
| `app_open` / `app_close` para procesos de usuario (no servicios del SO) | Patrón principal del caso de uso | ~50/día |
| `voice_command` (la frase exacta) | Para detectar comandos repetidos | ~20/día |
| `voice_correction` (cuando RED reformula tras un error) | Señal de fricción que el sistema puede automatizar | ~5/día |
| `routine_executed` | Para evaluar acceptance | bajo |
| `suggestion_accepted` / `suggestion_rejected` | Feedback loop crítico | bajo |

**Eventos que NO loguear** (ruido, poison, o privacidad):

- Contenido de texto en aplicaciones (keyloggers son no-go).
- URLs visitadas o títulos de ventana completos (sólo el nombre del proceso).
- Cualquier cosa con `test_`, `debug_`, `mock_` en nombre — filtro hard-coded.
- Procesos del SO (svchost.exe, etc.) — whitelist de procesos "interesantes" definida por el usuario.
- Eventos durante modo "dev/debug" de CARTER mismo.

**Política de retención**:

| Categoría | Retención | Pruning |
|---|---|---|
| `behavior_events` crudos | 90 días | Diaria, hard delete |
| `pattern_candidates` activos | Indefinido | Sólo si support cae <0.3 |
| `rejected_patterns` | 30 días por rechazo | Auto-expira |
| `routine_executed` log | 30 días | Para auditoría |

**Detección de corrupción**:

- Schema version chequeada al arrancar.
- Si >30% de eventos son del mismo tipo en <1 hora → flag "anomaly", alerta al usuario, no minar hasta limpiar.
- Backup semanal del SQLite a `behavior.db.bak`.

---

## Recommendations

**Roadmap por fases (cada fase deja el sistema funcional)**:

**Fase 1 — Logger + minería offline (1–2 semanas)**
1. Crear `behavior_log.py` con la tabla SQLite descrita arriba, **separada** de `ExperienceMemory`.
2. Implementar el watcher con `psutil.process_iter()` + `win32gui.GetForegroundWindow()` polling cada 5 s (latencia aceptable, CPU <1%).
3. Hookear el chat phrase logging en el módulo existente (sólo el intent, no el texto crudo).
4. NO sugerir nada todavía. Sólo recolectar.
5. **Benchmark de éxito**: 2 semanas de logs, <50 MB de DB, 0 contaminación.

**Fase 2 — Minería + cola de candidatos (1 semana)**
6. Implementar `pattern_miner.py` con la Capa A (conteo contextual). Correr como Windows Scheduled Task cada 6 horas.
7. Persistir `pattern_candidates` table.
8. Dashboard CLI: `carter routines learned` muestra candidatos sin ofrecerlos aún.
9. **Benchmark**: tras 30 días, al menos 3 patrones reales descubiertos manualmente verificables.

**Fase 3 — Presentación proactiva (1–2 semanas)**
10. Implementar `proactive_loop.py` con breakpoint detection.
11. Template de prompt fijo para Gemma 4 E4B (≤200 tokens generados).
12. Conectar al `routine_tool.create` existente.
13. Cooldowns y `rejected_patterns`.
14. **Benchmark**: ratio aceptación ≥40% en las primeras 10 sugerencias. Si <20%, subir umbral de consistencia a 0.75.

**Fase 4 — PrefixSpan para secuencias compuestas (opcional, +1 semana)**
15. Agregar Capa B con `prefixspan` Python para patrones de 2–5 eventos.
16. Sólo correr nocturno (no en hot path).

**Benchmarks que cambiarían la recomendación**:

- Si Gemma 4 E4B Q4_K_M no parsea respuestas `yes/no/edit` con ≥95% accuracy → forzar todo a regex + comando explícito `/sí` `/no`.
- Si el ratio de aceptación de sugerencias cae <20% → el umbral de consistencia es muy bajo; subir a 0.75 y `min_count` a 8.
- Si el logger consume >100 MB en 30 días → reducir polling a 15 s o restringir whitelist.
- Si CARTER pierde turnos por latencia (>5 s) cuando hay sugerencia → mover la generación de texto a un buffer pre-renderizado en background.

---

## Caveats

1. **TaraHome no publica sus umbrales numéricos**. Los valores que propongo (5 ocurrencias, 60% consistencia, 7 días, 30 días cooldown) son derivados de Horvitz 1999 (umbral p\* de utilidad esperada), de la regla práctica de TaraHome ("conservative", "consistent enough") y de la práctica común de "confidence threshold" en asistentes (defaults 50–70% según Practifi Follow-up Assistant docs). Hay que calibrar empíricamente con los datos reales de RED en las primeras 4 semanas.

2. **Gemma 4 tiene un bug conocido con `enable_thinking`**: documentado en ggml-org/llama.cpp Discussion #21338 ("Can't disable thinking in gemma4") y en el blog de CompleteTech LLC (29 abril 2026): *"The local template logic had the guard inverted. It emitted a closed empty thought block when enable_thinking was false, while thinking mode did not get the open thought channel it needed."* Workaround: lanzar `llama-server` con `--jinja --chat-template-kwargs '{"enable_thinking":false}'`.

3. **El benchmark de velocidad de Gemma 4 sobre vLLM tiene un bug**: vllm-project/vllm GitHub Issue #38887 (3 abril 2026) reproduce el log del servidor: *"Gemma4 model has heterogeneous head dimensions (head_dim=256, global_head_dim=512). Forcing TRITON_ATTN backend to prevent mixed-backend numerical divergence"* y *"Avg generation throughput: 9.2 tokens/s, Running: 1 reqs"*. Para CARTER OS hay que usar **Ollama o llama.cpp**, no vLLM, hasta que el issue se resuelva.

4. **La arquitectura propuesta tiene un single point of failure**: el watcher de eventos. Si falla silenciosamente, el sistema deja de aprender. Recomiendo healthcheck cada 24 h ("hace 24 h no veo eventos — ¿el watcher está OK?").

5. **No-Viable-en-vram4 (explícito)**: cualquier solución que requiera (a) un segundo LLM en VRAM (e.g., un "modelo de patrones" separado), (b) embeddings densos en GPU para clustering en tiempo real, (c) un modelo ≥7B para razonamiento sobre logs, (d) modelado de atención tipo ProMemAssist (UIST '25) que requiere pipeline multimodal. Si en el futuro RED quisiera estas capacidades, requieren un perfil distinto (`vram12` o `vram24`); en vram4 hay que quedarse con conteo + PrefixSpan + Gemma 4B sólo conversando.

6. **El caso de uso "RED corrige al asistente y este aprende"** es más complejo que "RED cierra X en boot". Las correcciones son secuenciales (`comando → respuesta errónea → corrección`), requieren parsing semántico, y son más propensas a falsos positivos. Recomiendo abordarlo en Fase 5 (no incluida en el roadmap inicial), sólo después de que el flujo simple funcione 3 meses sin issues.

7. **TaraHome ya existe y resuelve un problema casi idéntico en otro dominio (Home Assistant en lugar de Windows)**. El repo público (TaraHome/taraassistant-public) no expone los umbrales numéricos pero sí el código Python del Pattern Detector y el Automation Generator. Vale la pena leerlo para aprender de su scoring concreto antes de implementar — no para copiar, sino para evitar errores ya pisados.

8. **Sobre los hallazgos de Edwards et al. 2021**: el paper aporta evidencia sobre cómo los humanos modulan urgencia (*"people interrupted sooner when interruptions were urgent"* y *"varied phrasing and delivery"*) y sobre el uso minoritario de access rituals (*"most rarely used them"*), pero NO reporta explícitamente que las interrupciones no urgentes se difieran a breakpoints. El uso de breakpoints como momento de bajo costo cognitivo proviene de la literatura más amplia de interruption-cost modeling (Iqbal & Horvitz 2007; ProMemAssist UIST '25), no de Edwards et al. directamente.