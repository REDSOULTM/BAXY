# C03 — censo de rutas de prosa (recorrido, no léxico)

Instrumentación: `ConversationMessage.Route` viaja en el evento `activity.entry.route`.
La narración accesible es `ConversationMessage.AccessibleText` = `{Speaker}: {Body}`
(el mismo cuerpo que TTS `VoiceSpeakAsync`). No hay un segundo compositor.

| Ruta | Python | C# | TS |
|---|---|---|---|
| welcome | `compose_user_message` intent=welcome | `TurnVisibleFacts.Welcome` → compose | activity `src=BAXY` |
| conversation | `turn.decide` reply | `formulatedByMind` + `IsSafeConversationReply` | mismo |
| clarification | kind=clarify / extract question | `UserMessageEvent.Clarification` → compose | mismo |
| confirmation | intent=confirmation | `UserMessageEvent.Confirmation` → compose | mismo |
| progress | `_emit_early_turn_signal` → compose `cause=acting` | `TryEmitDueMilestone` → compose acting (producción); `FormulateProgress` sólo con bypass de tests | `boot_stage.label` null en etapas; ProgressLabel es compose |
| result | compose status + `observed` | 1 paso: hechos de operación, no `mission_completed` | mismo |
| error | compose intent=error | `UserMessageEvent.Error` → compose | `composition_failed` SYSTEM si agota |
| mission-summary | cause=mission_completed | ≥2 pasos `MissionNarration` | mismo |

Plantilla `Sigo con {snippet}` retirada de la publicación de producto.
Personalidad: `USER_MESSAGE_PROMPT` (compañero, un él, tuteas). Política de
seguridad («no envíes nada») vive en otro bloque de `llm.py`, no en ese prompt.
