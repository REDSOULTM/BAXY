# Handoff — Goal 10 — 2026-08-30 — r129 overlay scored

## Objetivo
BAXY cumple la identidad (es/en/spanglish) y cada mensaje real in-scope pasa
con veredicto individual. In-scope fail = 0. Ambientales omitidas, no convertidas.

## Estado
Hecho: r129 20/20 + overlay quirúrgico 13 + 3 consent-ask→conversación.
In-scope **1577/143** (r128 era 1576/144). `abre Steel` → Steam pasa.
LastBoot `2026-08-27 21:25:24`.
En curso: owner-fix afirmación puntuada `Sí. Abre…` (prefijo con lookahead
de open). pytest 2606 ×2. Siguiente: UNA remake r130.
Sin empezar: overlay r130, 808/2036/holdouts, matriz viva, ABBA, Full.

## Decisiones tomadas
- Overlay no pisa journal. 205 blocked_lost_journal.
- `consent_ask_to_conversation`: pregunta de guardar en memoria local →
  saludo, sin journal. Familia, no `message_id`.
- `Tiempo` con `system.time` + journal **sigue fail**: mapping
  `outcome_type=clarify` / ops []. No es clima ni reloj pedido con
  claridad. No otra remake para eso.
- `zzqwx123` ejecuta y falla cerrado (`app_not_found`); verification
  sigue fail. No inventar éxito.
- Afirmación puntuada `si|yes` + `abre|open` se quita del sobre. `Sí, sí,
  te oigo` no: el lookahead exige verbo de abrir.

## Archivos tocados
- `artifacts/goal10/goal10-in-scope-r129.json` — 1577/143
- `%LOCALAPPDATA%\BAXYRuntime\goal10\overlay_r129.py` —
  `consent_ask_to_conversation`
- merge SHA `df0072258deb9a9ef86311c2972b0462ff59b2c15801671a1fd065d92b615080`

## Hipótesis
Confirmadas: prefix 3 chars abre Steam; nombres implícitos saludan en
shard r129; overlay sin journal no los copiaba.
Descartadas: overlay wholesale; r129 in-scope 0 fail.

## Comandos ejecutados y resultado
- wait_r129 → **DONE**. 20/20 empty=0 + `campaign done`. LastBoot `2026-08-27 21:25:24`
- overlay unique 1947, overlaid 13 then +3 names, blocked 205
- in-scope `artifacts/goal10/goal10-in-scope-r129.json` → **1577/143**

## Siguiente acción recomendada
Owner-fix familia `app.open` restante: afirmación `Sí.`/`Yes.` delante
de un open de catálogo único; `Abrelo`; terminal HWND. Tests verdes dos
veces, luego UNA remake r130. No overlay incompleto.
