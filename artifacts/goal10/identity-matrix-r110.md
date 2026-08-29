# Identity matrix — live use after r110 (not code reading)

Tree: Release `Baxy.exe` (`src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0`).
Probes: `scripts/goal10_launch_probe.ps1` twice (`identity-r110-1`, `identity-r110-2`).
Turns: `scripts/goal10_dose_turns.ps1` + `scripts/goal10_uia_dump.ps1`.
Host power was **not** sent. `BAXY_DENY_HOST_POWER_TRANSITION=1`.
Evidence under this scratch and `%LOCALAPPDATA%\BAXY\dev-mente-v2\journal\missions.jsonl`.

| Identidad decision | Live evidence | Verdict |
|---|---|---|
| Starts, window shown, core stays alive | probe 1 pid 25636, probe 2 pid 27212; `core visto alguna vez: True`; `app sigue viva: True`; no `last-crash.txt` | pass |
| Cold start + BAXY process restart | probe 1 then probe 2 killed and relaunched Baxy; both reached `startup.ready` (15.0 s then 12.2 s) | pass |
| Input accepts a turn | UIA Edit `message input` `enabled=True` `offscreen=False`; four later turns `submit.received` | pass |
| Speaks always (narration) | probe 2 `voice.speak accepted` → `voice.state speaking` → `silent` on welcome «Hola.» | pass |
| Name is BAXY | UIA label `BAXY` on the assistant messages | pass |
| Tuteo, breve, confirma estado | Welcome «Hola.»; conversation «Bien.»; memory save «Guardé el dato en la memoria local.» | pass (those turns) |
| When it fails, plain cause | First open-ended turn: `decision.ready unavailable` then visible «No pude usar esa respuesta.» | pass (honest fail text) |
| Does not invent an effect | First open-ended turn did not claim a tool ran (`coreOperation` null / decision unavailable) | pass |
| Ordinary daily-use, not closed catalog, model decides | «qué me conviene para despejar la cabeza un rato»: `decision.ready unavailable`, visible «No pude usar esa respuesta.» Retry «hola, como estas»: model conversation «Bien.» in 1.5 s, no core op | fail then pass |
| Memory save (synthetic key) | t3 `coreOperation=memory.save` «Guardé el dato en la memoria local.» UIA MEMORY went 0→1 | pass |
| Memory visible / recall | t4 visible «azul» for «cual es mi color de prueba goal10» | pass |
| Memory delete | t5 and t6 `olvidate de mi color de prueba goal10` → «No pude: no responde.» (t5 had `memory.forget`); UIA still MEMORY 1 after t5 | fail |
| Local, no telemetry chrome | UIA text `local · no telemetry` | pass (chrome only) |
| Web search without sending user content | Not exercised live this session (llama contended; not converted to pass) | fail (untested) |
| Normal mode confirms only if data destroyed | Not toggled live; no destructive turn sent | fail (untested) |
| Bypass stays on until turned off | Not toggled live | fail (untested) |
| Apagar / reiniciar el equipo | **Not exercised on this host.** Catalog identity remains the stubbed NUnit + r110 fail-closed receipts (`msg_91e9247cb7f365871f12` confirmation; `msg_ed8e5ebffa54520906e1` `power_transition_physical_gate_required`). | environmental (not a live pass) |
| Tray / stays running | Both probes left Baxy.exe + baxy-core.exe alive after 25 s | pass |
| Voice interruptible | t1 `voice.cancel accepted` then later `voice.speak rejected` then `speaking` | mixed |
| Catalog coverage chrome | UIA `TOOLS 169` | pass (count only) |
| Does not send a live apagar | No such turn was submitted | pass (constraint) |

## Turns (identity-r110-b / c)

| Turn | Visible | Core | Notes |
|---|---|---|---|
| qué me conviene… | No pude usar esa respuesta. | — | decision unavailable; dose script raced `response.final` before `visible.text` |
| hola, como estas | Bien. | none | model conversation |
| acordate … azul | Guardé el dato en la memoria local. | memory.save | |
| cual es mi color… | azul | memory.status | |
| olvidate… (×2) | No pude: no responde. | memory.forget then none | delete not proven |

## Not a close

Criterion 4 is not green: delete, confirmation modes, and web-egress were not demonstrated. Criterion 2 is still **1484 pass / 463 fail**, not 1.947/0.
