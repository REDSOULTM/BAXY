# Integration fail inventory — Goal 10.0

Live Full (this session): **0 of the historical 85 reappeared.**
Integration `Correctas! - Con error: 0, Superado: 2828, Omitido: 1, Total: 2829`.

No edit. Cluster already repaired in inherited 09.5.11C (`c28cd62`).

## Historical red (pre-09.5, Goal 09 close `8c57747`)

Source: `documentacion/sprints/10.0_BASE_VERDE.md`, `10_APRENDIZAJES.md`.

Full before 09.5: static/build green; Contracts 60/60; Kernel 137/137;
Providers 451/451; Setup 477/477; Integration **2.742 pass, 85 fail, 1 skip**.

Cause of all 85: tests compared canned natural-language phrases to
`OperationOutcomeNarration.For` / `ProductOperationNarrator.Narrate`, which
already emitted `OperationVisibleFacts` JSON (`kind`, `operation`, `polarity`,
`verified`, `observed`, `error`). Goal 6 contract: facts for the model to
compose; no fixed visible replies.

Arithmetic: 2742 + 85 + 1 = 2828 counted rows. After the 85 became passes and
09.5.11C added Integration coverage, 09.5.12 and this Full report **2828 pass,
1 skip**.

## Inherited repair (not this meta)

`c28cd62` (Goal 09.5.11C) added `OperationOutcomeNarration.Facts` and rewrote
phrase assertions to schema/keys/observed values. Sample:

| Test | Old (fixed phrase) | New (facts/schema) |
|---|---|---|
| `BluetoothRadioNarrationTests` | `Is.EqualTo("Listo, Bluetooth está encendido y verificado.")` | `facts["polarity"] == "success"` + observed `"state"` |
| `TaskNarrationTests` empty list | `Is.EqualTo("No encontré tareas en esa lista.")` | polarity/operation + `IsSafe` |
| `TaskNarrationTests` failure | `Is.EqualTo("Los datos de la tarea no tienen el formato esperado.")` | polarity=failure, `error=invalid_arguments` |
| `AppOpenHandlerTests` | `Is.EqualTo("Listo, abrí Steam.")` / `"Listo, abrí Bloc de notas."` | polarity + operation + observed `appId` |
| `AudioMuteHandlerTests` | `"Listo, silencié el audio del sistema."` | polarity success/failure |
| `MediaStatusNarrationTests` | `"No hay ninguna reproducción visible..."` | polarity=failure, `error=media_session_not_found` |

Product narrator unchanged: `ProductOperationNarrator.Narrate` →
`OperationVisibleFacts.FromOutcome` JSON. `Goal06VisibleVoiceTests` asserts
structured facts and `Does.Not.Contain("Listo")`. Composer tests inject model
prose through a stub; they do not publish a canned product reply.

No remaining 85-style assertion expects a fixed visible phrase from
`OperationOutcomeNarration`. None of those phrases was moved into another
helper.

## Distinct defects

None. The 85 share one cause. No fail was converted to skip.
