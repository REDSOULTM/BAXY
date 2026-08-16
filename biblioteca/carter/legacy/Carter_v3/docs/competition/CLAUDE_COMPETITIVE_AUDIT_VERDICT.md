# CLAUDE_COMPETITIVE_AUDIT_VERDICT.md
# Veredicto Final — Auditoría Competitiva Carter v3
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06
# Basado en: código fuente real de Carter v3, Mark XXXIX, OpenClaw + conocimiento público de otros competidores

---

## VEREDICTO OFICIAL

# CARTER_ARCHITECTURE_GOOD_RUNTIME_WEAK

---

## Justificación del veredicto

Carter v3 tiene la **mejor arquitectura de su clase** para el nicho de asistente personal local en Windows. Sus fundamentos son superiores a todos los competidores analizados en las dimensiones más importantes: honestidad, verificación, seguridad, privacidad, y no-hardcode.

**PERO**, el runtime nunca fue validado con un LLM real corriendo, y hay bloqueadores activos que degradan la calidad de la experiencia real del usuario. La arquitectura es sólida. El runtime es incierto.

---

## 1. Veredicto brutal y honesto

### Qué Carter hace MEJOR que todos los competidores:

- **Verifier system (único en su clase)**: Carter es el único de los competidores analizados con 14 verifiers que distinguen CONFIRMED/UNVERIFIED/FAILED con causal baseline. Mark no tiene verifier. OpenClaw no tiene verifier. Open Interpreter no tiene verifier. Este es el diferenciador más importante.

- **Policy pre-LLM**: Carter evalúa seguridad ANTES de llamar al LLM. Ningún competidor local hace esto. El LLM nunca ve solicitudes destructivas en Carter.

- **Zero hardcodes verificado por AST**: Carter tiene un hardcode_guard que escanea el árbol de sintaxis real. 58 archivos limpios. Ningún competidor tiene esto.

- **Privacy local-first por diseño**: Carter puede correr 100% offline con Ollama. Mark falla sin internet. OpenClaw puede hacer lo mismo pero no está diseñado para PC personal.

- **Fuzzy resolver sin alias**: Carter resuelve "stean" → Steam sin tener "Steam" hardcodeado. Mark tiene 64 aliases fijos. Esto es arquitectura superior.

- **Fake success guards**: 8 guards estructurales post-reply, incluyendo fake_success_guard. Ningún competidor tiene esto.

- **WindowsNative app control con CEF support**: AttachThreadInput + mouse_event para Steam/Discord/Spotify. Nadie más puede hacer esto.

### Qué Carter tiene que mejorar:

- **Browser automation**: Mark y OpenClaw tienen Playwright. Carter no puede automatizar formularios, hacer clicks en webs, o manejar múltiples tabs. Esta es la brecha más grande.

- **Progress reporting**: Carter está en silencio durante misiones. Mark y OpenClaw muestran progreso. Esto viola Valor 17 de ContextoCarter.

- **Validación live**: Los 490 tests usan ScriptedAdapter. Nunca se validó con LLM real corriendo. Esto es inaceptable antes de declarar READY.

- **Follow-ups rotos**: "Sí"/"OK"/"YES" no activan pending_intent (Bug B2). Esto es un bug funcional de alta prioridad.

- **Recovery limitada**: Solo app_open tiene retry. El resto de herramientas no tienen recovery.

---

## 2. Posición de Carter vs Mark XXXIX

**Carter es MEJOR que Mark en:**
- Todo lo importante: privacidad, verifier, policy, seguridad, hardcodes, tests, CEF app control, honestidad
- Mark es un thin wrapper sobre Gemini. Sin internet → inútil. Sin Gemini → inútil.
- Mark tiene fake success por diseño (sin verifier)
- Mark tiene 64 app aliases hardcodeados
- Mark usa identidad de marca ajena ("JARVIS", "Tony Stark") — problema legal
- Mark tiene cero test suite

**Mark es mejor que Carter en:**
- Voz (Gemini Live nativo, funcional en producción)
- Cámara (mss + cv2 + Gemini vision, funcional)
- Progress reporting visual (estados de UI claros)
- Browser automation (Playwright)
- UX visual (HUD PyQt6 animado)

**Veredicto**: **Carter gana** si lo que importa es confiabilidad, honestidad, privacidad y arquitectura sólida. Mark gana solo en presentación visual y funcionalidades cloud.

---

## 3. Posición de Carter vs OpenClaw

**Carter es MEJOR que OpenClaw en:**
- Diseñado para el nicho correcto (PC personal Windows tipo Jarvis)
- Windows native app control (nadie más tiene esto)
- Verifier por tool (CONFIRMED/UNVERIFIED/FAILED)
- Hardware adaptation (VRAM 85% rule, CPU profiles)
- Compacto y simple para single-user
- Sin infraestructura pesada (sin Docker obligatorio, sin gateway daemon)

**OpenClaw es mejor que Carter en:**
- Browser automation (Playwright en Docker)
- Memory semántica (vector embeddings + dreaming)
- Terminal PTY support
- Model failover automático
- Extensibilidad (plugin SDK, ClawHub, MCP)
- Test coverage (vitest + pytest + E2E)
- Multi-canal de mensajería (si es lo que necesitas)

**Veredicto**: **Empate con ventaja contextual**. Para PC personal Jarvis → Carter gana. Para orquestación multi-canal → OpenClaw gana. Son nichos distintos y Carter está mejor posicionado para su nicho.

---

## 4. Posición de Carter vs agentes públicos

| Competidor | vs Carter |
|---|---|
| Open Interpreter | Carter gana (mejor seguridad, verifier, no fake success, hardcode guard) |
| OpenHands | Empate (OpenHands tiene mejor browser y sandbox; Carter tiene mejor Windows control) |
| AutoGPT | Carter gana claramente (AutoGPT tiene anti-patrones clásicos: loop infinito, fake success, sin step budget) |
| AutoGen | Diferente nicho (framework vs asistente). Carter es más correcto para PC personal. |
| LangGraph | Diferente nivel (framework vs producto). State machine de LangGraph es inspiración para Carter. |
| Goose | Carter gana (Carter tiene mejor Windows control, verifier, guards) |
| OS-Copilot | Carter gana (más completo, más robusto, mejor mantenido) |
| Agent-S | Empate en GUI (Agent-S especializado; Carter más general). Agent-S requiere VLM obligatorio. |
| Claude Computer Use | CU gana en GUI visual (VLM nativo de Anthropic); Carter gana en privacidad, offline, memory |
| Windows Copilot | Carter gana en privacidad, extensibilidad, local control. Windows Copilot gana en integración OS nativa. |

---

## 5. Qué falta para ser "el mejor"

### Para ser mejor que TODOS los competidores en su nicho (PC personal Windows local):

1. **Validación live** con LLM real — urgente, no es código, es proceso
2. **Fix B2**: confirmaciones follow-up
3. **Fix B3**: fake_success mid-text
4. **Fix B4**: notify_toast honesto
5. **Fix B5**: progress reporting en misiones
6. **Fix B6**: system prompt no ejecuta al preguntar
7. **Browser Playwright** (P1) — la brecha más grande vs competidores
8. **SSRF protection** (P1) — seguridad que falta
9. **Model failover** (P1) — sin punto de fallo único en Ollama
10. **Degradación VRAM/RAM** (P1) — cumplir Valor 22 de ContextoCarter

### Para ser el mejor asistente local de Windows, punto:

Carter necesita cerrar el núcleo texto al 100% (puntos 1-10 arriba). Luego voz. Luego cámara. En ese orden. Exactamente como dice ContextoCarter.md.

---

## 6. Qué NO debe copiarse (top 10)

1. **Cloud obligatorio** (Mark XXXIX) — rompe privacidad y local-first
2. **Sin verifier = fake success** (Mark, AutoGPT, la mayoría) — rompe confianza
3. **Hardcodes de app** (Mark 64 aliases) — viola Valor 6 y 7
4. **Identidad de marca ajena** (Mark "JARVIS") — problema legal
5. **Sin test suite** (Mark) — inaceptable para software de confianza
6. **LLM para generar scripts de fix** (Mark generate_fix) — superficie de ataque
7. **Multi-agent para tareas simples de PC** (AutoGPT, AutoGen) — overhead innecesario
8. **VLM obligatorio para GUI** (Agent-S) — imposible en hardware limitado
9. **Docker obligatorio** (OpenClaw) — overhead para single-user local
10. **Mission status via texto del LLM** (casi todos) — alucinación puede reportar éxito falso

---

## 7. Qué debe hacer Codex

En orden estricto:

1. **Committear working tree** (B1) — primero siempre
2. **Fix B2** (session_state.py) — confirmaciones rotas
3. **Fix B3** (guards.py) — fake success mid-text
4. **Fix B4** (catalog.py) — notify_toast honesto
5. **Fix B5** (agent.py) — progress reporting
6. **Fix B6** (turn_support.py) — system prompt
7. **pytest → 0 fallos, hardcode_guard → CLEAN, commit**
8. **P1-A**: SSRF protection
9. **P1-B**: Model failover
10. **P1-C**: VRAM degradation
11. **P1-D**: Error taxonomy
12. **P1-E**: Memory categories
13. **pytest → 0 fallos, hardcode_guard → CLEAN, commit**
14. **Validación live manual** con Ollama real (proceso, no código)
15. **Documentar resultados** en docs/audit/LIVE_VALIDATION_POST_COMPETITIVE_UPGRADE.md

Ver PROMPT_FOR_CODEX_COMPETITIVE_UPGRADE_CARTER.md para instrucciones exactas.

---

## 8. Qué debe esperar voz/cámara

Voz y cámara deben esperar hasta que:

- [ ] Todos los bloqueadores B2-B6 estén cerrados
- [ ] pytest → 0 fallos
- [ ] hardcode_guard → CLEAN
- [ ] Spotcheck manual de 10+ casos con Ollama real documentado
- [ ] Latencia real medida: inputs triviales < 8s
- [ ] "Sí"/"OK"/"YES" funcionan como confirmaciones
- [ ] Progress reporting visible en misiones de 2+ pasos
- [ ] Sin fake success mid-text en ningún caso del spotcheck

---

## 9. Próximo paso exacto

**HOY, inmediatamente:**

1. Abrir PROMPT_FOR_CODEX_COMPETITIVE_UPGRADE_CARTER.md
2. Pegarlo en ChatGPT Codex
3. Indicarle a Codex que empiece por el Fase 1 (solo P0 blockers)
4. Validar que pytest pasa después de los fixes
5. Ejecutar el spotcheck manual con Ollama real

**Esta semana:**
- Cerrar P0 blockers en 1-2 sesiones de Codex
- Ejecutar spotcheck manual live
- Documentar resultados

**Próxima semana:**
- Implementar P1 ideas (SSRF, failover, degradation, error taxonomy, memory categories)
- Opcional: Playwright básico para browser automation

**Solo cuando núcleo texto esté 100% validado:**
- Comenzar implementación de voz (FASE I del CARTER_BEST_OF_ALL_TECHNICAL_PLAN.md)

---

## Declaración final

Carter v3 NO está al 100% pero está **más cerca que cualquier competidor local de su nicho** en las dimensiones que importan: honestidad, verificación, privacidad, seguridad y arquitectura sin hardcodes.

La arquitectura de Carter es la correcta. El problema es que el runtime no está validado live y hay bloqueadores de experiencia real que deben resolverse.

Voz y cámara deben esperar. El núcleo texto debe cerrarse primero. Exactamente como dice ContextoCarter.md.

**Si Carter cierra los P0 blockers y valida live, será el mejor asistente personal local de Windows disponible en el ecosistema open-source en 2026.**

---

## ADENDUM 2026-05-06 � Veredicto reforzado con codigo real de 8 competidores adicionales

Tras descargar y auditar (con citas archivo:linea) los 8 competidores que en la v1 eran [inferencia], el veredicto **CARTER_ARCHITECTURE_GOOD_RUNTIME_WEAK se mantiene y se refuerza**. Detalles en COMPETITOR_LANDSCAPE_AUDIT.md (v2).

### Hallazgos que refuerzan el veredicto

1. **Goose es el unico competidor con policy pre-LLM superior a Carter**: pipeline de 5 inspectores (Security, Egress, Adversary LLM, Permission, Repetition) con anotaciones por tool y mode SmartApprove. Carter tiene policy pre-LLM (mejor que 7 de 8) pero monolitica. Idea P1 anadida en BEST_IDEAS.

2. **Agent-S es el unico con verifier visual real (BBON)**: BehaviorNarrator + ComparativeJudge marcan screenshots before/after y comparan visualmente. SOTA OSWorld 72.60%. Carter tiene verifier de estado logico (mejor que 7 de 8); falta capa visual opcional. Idea P1 anadida.

3. **LangGraph es el unico con checkpointing/replay/fork**: backend SQLite/Postgres, source in {input,loop,update,fork}. Carter no tiene rewind. Idea P2 anadida.

4. **AutoGPT classic Forge NO IMPLEMENTA la llamada al LLM** (stub literal 'I cannot solve the task!' en forge_agent.py:195). Anti-patron documentado.

5. **OpenHands oculta su agent loop** en un paquete externo no auditable. Patron de transparencia de Carter (agent.py legible) es superior.

6. **Ningun competidor combina TODO lo que Carter combina**: local-first puro + verifier de estado + policy pre-LLM + zero-hardcode AST-verified + Windows-native CEF + 490 tests.

### Hallazgos que matizan el veredicto

- Carter sigue **sin BBON visual** (Agent-S lo tiene, Carter no).
- Carter sigue **sin pipeline de inspectores componibles** (Goose lo tiene mejor).
- Carter sigue **sin checkpointing/replay** (LangGraph lo tiene).
- Carter sigue **sin ActionRequired bidireccional** (Goose lo tiene; el LLM puede pedir DATOS al usuario, no solo confirmacion).
- Carter sigue **sin TerminationCondition componibles** (AutoGen las tiene).

### Veredicto reforzado

**Carter v3 es la mejor ARQUITECTURA combinada de los 12 competidores analizados** para el nicho de asistente personal local en Windows. Cada competidor individual gana en UNA dimension especifica (Goose en policy, Agent-S en verificacion visual, LangGraph en checkpointing, AutoGen en termination, Mark en voz cloud, OpenClaw en multi-canal). **Ninguno gana en TODAS las dimensiones que importan para Carter (local + honesto + sin hardcodes + Windows-native).**

**Carter sigue ganando por combinacion arquitectonica**, pero quedan 4 ideas concretas de alto valor a portar (P1): pipeline de inspectores, tool annotations, ActionRequired bidireccional, TerminationCondition componibles. Los P0 blockers siguen siendo prioritarios sobre estos enriquecimientos arquitectonicos.

