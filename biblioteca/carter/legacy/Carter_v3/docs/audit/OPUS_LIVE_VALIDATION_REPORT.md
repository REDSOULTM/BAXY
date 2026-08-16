# OPUS_LIVE_VALIDATION_REPORT.md
# Reporte de validación live — Carter v3
# Fecha creación: 2026-05-06
# Generado por: Claude Code (claude-sonnet-4-6)
# ESTADO: PENDIENTE — No ejecutado (usuario en sesión de juego durante auditoría)

---

## Estado: DEFERIDO

Este documento está reservado para la validación live con LLM real.
**No se ejecutó en esta sesión.** El usuario solicitó explícitamente no abrir
apps ni ventanas durante la sesión de auditoría del 2026-05-06.

---

## Qué requiere esta validación

### Ambiente necesario:
1. Ollama corriendo: `ollama serve`
2. Modelo cargado: `ollama pull llama3` o equivalente
3. Carter iniciado: `python -m carter_v3.cli` o `python -m carter_v3.agent`
4. Sistema libre: sin apps compitiendo por RAM/VRAM
5. Grabación de pantalla o log para evidencia

### Spotchecks a ejecutar:

Los spotchecks completos están definidos en `docs/audit/CLAUDE_MANUAL_SPOTCHECK_SET.md`.
Mínimo requerido para declarar validación:

| # | Input | Verificación esperada | Bloqueador |
|---|---|---|---|
| 1 | "Abre el Bloc de notas" | Notepad abre, verifier=CONFIRMED, <8s | — |
| 2 | "¿Puedes abrir el Bloc de notas?" | Ejecuta sin preguntar | B6 |
| 3 | "Sí" (tras pending_intent) | Activa pending_intent correctamente | B2 |
| 4 | "OK dale" (tras pending_intent) | Activa pending_intent | B2 |
| 5 | "Ponme un recordatorio en 5 minutos" | Crea reminder local, no abre nada | — |
| 6 | "¿Qué recordatorios tengo?" | Lista reminders, respuesta limpia | — |
| 7 | "Cierra el Bloc de notas" | Cierra, verifier=CONFIRMED | — |
| 8 | Misión compuesta (abre X, luego Y) | Progress reporting visible entre steps | B5 |
| 9 | Request con fake success en texto LLM | Guard bloquea, no responde "listo" | B3 |
| 10 | "Recuerda que prefiero modo oscuro" | Guarda en memory, no en reminder | — |

### Métricas a registrar:
- Latencia de cada input (time to first token + time to response complete)
- VerifierStatus de cada tool call
- Si guards se activaron (y cuáles)
- Si pending_intent funcionó en tests B2
- Si progress reporting fue visible en B5

---

## Sección de resultados (rellenar cuando se ejecute)

### Fecha de ejecución: ___________
### Modelo usado: ___________
### Hardware: ___________

| # | Input | Status real | Latencia | Verifier | Guards | Notas |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |
| 6 | | | | | | |
| 7 | | | | | | |
| 8 | | | | | | |
| 9 | | | | | | |
| 10 | | | | | | |

### Veredicto post-live-validation:
- [ ] B2 confirmado cerrado / abierto
- [ ] B3 confirmado cerrado / abierto
- [ ] B4 confirmado cerrado / abierto
- [ ] B5 confirmado cerrado / abierto
- [ ] B6 confirmado cerrado / abierto
- [ ] Latencia trivial < 8s: SÍ / NO
- [ ] Sin fake success en ningún spotcheck: SÍ / NO

---

*Plantilla creada por Claude Code (claude-sonnet-4-6) — 2026-05-06. Rellenar en próxima sesión con Ollama disponible.*
