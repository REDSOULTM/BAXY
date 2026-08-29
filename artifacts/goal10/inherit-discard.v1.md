# Goal 10 — inventario heredar / descartar (2026-08-29)

Reinicio limpio desde el cierre del Goal 9. Los agentes anteriores del Goal 10
son **evidencia histórica**, no el producto certificado de esta corrida.

## Baseline

- Goal 9 close: `8c57747` (`goal09: idle con escucha on; FAR 2 h terminada, no parcial`)
- HEAD al arranque de esta corrida: `67c621a` (4 commits locales sin push)
- Commits `8c57747..HEAD`: **167**. No se reescribe `origin/main` (163 de esos
  commits ya están publicados). No `reset --hard` ni force-push.

## Host

- `LastBootUpTime`: `2026-08-27 21:25:24` (sin cambio; no se toca power del PC)
- r123: **incompleta**. 1 shard `0000-0100` (~29 filas), remake abortado `^C`.
  Marcador: `%LOCALAPPDATA%\BAXYRuntime\goal10\r123-INCOMPLETE.txt`.
  **No overlay.** No había testhost / llama-server / Baxy.exe vivos.
- r121: descartada. r122: voided por el dueño. No overlay.

## Heredar

| Pieza | Por qué |
|---|---|
| Corpus congelado Nivel 1 **1.947 / 626**, Nivel 2 **808 / 281** | Builder + manifiesto; 0 conflictos de contrato |
| `scripts/build_observed_user_corpora.py` | No reconstruir |
| `scripts/adjudicate_observed_product_replay.py` | No reconstruir |
| Testhost `ObservedUserCorpusReplayTests` | NUnit OptIn; orden Source / LocationOrdinal / MessageId |
| Host-power fail-closed | `BAXY_DENY_HOST_POWER_TRANSITION=1` → `DeniedHostPowerTransitionPlatform`; nunca `InitiateSystemShutdownEx` en este PC |
| Tray, autostart, panel de memoria, `IsInputEnabled` | Identidad: presencia, Windows startup, memoria visible/editable/borrable |
| `1d3df17` «let the 4B own tool calling; keep schema help only» | Anti-acumulación: la mente es el LLM |
| Recuento del dueño | In-scope = es/en/spanglish y no ambiental. Ambientales y de/fr/it/pt se omiten del fail count, **no** se convierten en pass. Goal 11 cobra ambiente |
| Docs Goal 11 / 12 | `11_AMBIENTE.md`, `12_CIERRE.md`; el índice pasa a doce goals |

## Descartar

| Pieza | Por qué |
|---|---|
| Dump sucio de `effect_intent.py` (+842 líneas uncommitted) | Un `_direct_*` por fail restante; enseña el examen |
| Filas de test `Abre stea` / `Abre Steel` / `zzqwx123` | Literales del corpus / id sintético |
| Overlay de r121, r122, r123 incompleta | Campañas voided o incompletas |
| Notas de agente pegadas al sprint como spec | El sprint vuelve a los criterios de cierre originales |
| r120 surgical (1507/217 in-scope) como certificación | Diagnóstico histórico, no esta corrida |
| HANDOFF 2026-08-24 «la mente no sube» | Caducado |

## Producto de esta corrida

La mente parte de HEAD (post-`1d3df17`) más **un** reconocedor de familias de
uso diario (`_daily_use_family_intent`): hora/estado, ventana, media, procesos,
shell, timer, portapapeles, calendario, carpetas conocidas, búsqueda de archivo,
navegación nombrada, deícticos. No hay un regex por `message_id`.

## Números históricos (no certificar)

r120 surgical: raw 1507 pass / 440 fail. In-scope 1507 / 217 fail. Env 216.
Otros idiomas 7 (`wie spät`, `öffne den Rechner`, `ouvre la calculatrice`,
`che ore sono`, `apri la calcolatrice`, `alza il volume`, `que horas são`).
