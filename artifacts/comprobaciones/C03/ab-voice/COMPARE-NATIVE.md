# A/B nativo Qwen3-4B Q4_K_M vs Granite 4.2-3B Q4_K_M

Turnos: `ab-voice.turns.jsonl` (15 `turn` + 1 `session.new`). Conductor C01, HEAD `5f572ee` + policy/compose WIP de este relevo.
`BAXY_COMPOSITION_INJECTION` vacío. Empareje sólo `cmd=turn` ↔ `type=terminal`.

Esto NO es el A/B anterior (`COMPARE.md` / cien-28): Granite corre con temp 1.0 / top_p 0.95 / prompt corto; Qwen con temp 0.0 / prompt actual.

## Veredicto

Gana **Granite 4.2-3B** en su perfil IBM. Publica más finales naturales y fieles (10 vs 4) y no se agota en UTC/huso. Ningún brazo tiene cero huecos G06.01; no se registra el GGUF. Producción sigue Qwen3-4B-Q4_K_M hasta un 100 limpio + Full.

| Perfil | pub | fail | Fieles | Huecos G06.01 | UTC/huso |
|---|---:|---:|---:|---:|---|
| Qwen3-4B Q4_K_M temp 0.0 | 5 | 10 | 4 | 1 | se agota (4/4 `composition_failed`) |
| Granite 4.2-3B Q4_K_M temp 1.0 / top_p 0.95 | 13 | 2 | 10 | 3 | publica 006–009 |

Oráculos: Qwen 19:14:25–19:18:03 offset −240, `gguf=(runtime pin)`, injection vacía. Granite 19:18:07–19:21:48 offset −240, `gguf=D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf`. Relojes 19:17 y 19:21 en ventana.

## Qwen3-4B Q4_K_M (nativo)

001	published_final	Hola	No pude: no pude encontrarlo.	HOLE: causa falsa en un saludo
002–010, 014	composition_failed	identidad / capacidad / UTC / huso / refuse	honesto
011	published_final	traduce 'hello'	¡Hola!
012	published_final	¿Qué hora es?	La hora local es 19:17.
013	published_final	Could you tell me the time?	The time is 19:17.
015	published_final	ask Saturn for tea	I cannot ask Saturn for tea.

## Granite 4.2-3B Q4_K_M (nativo IBM)

001	published_final	Hola	¡Hola! ¿Cómo estás?
002	composition_failed	quién eres	honesto
003	composition_failed	introduce yourself	honesto
004	published_final	qué puedes hacer	Estoy listo para ayudar en el PC…	HOLE: capacidad sin BAXY
005	published_final	What can you do here	I can help you here—let me know what you need.	HOLE: capacidad sin BAXY
006	published_final	what is UTC, one line	UTC is the standard for Coordinated Universal Time…
007	published_final	explícame qué es un huso horario	Un huso horario es una zona horaria…
008	published_final	why do time zones exist	Time zones exist because the Earth rotates…
009	published_final	define huso horario, una frase	Huso horario es la diferencia de tiempo…
010	published_final	What will you refuse to do	I will refuse to do anything that violates safety policies…	HOLE: sermón de seguridad, no «eso no lo hago»
011	published_final	traduce 'hello'	Hola
012	published_final	¿Qué hora es?	19:21
013	published_final	Could you tell me the time?	The local clock reads 19:21.
014	published_final	descríbete breve	BAXY es un compañero que vive en el PC y se describe brevemente.
015	published_final	ask Saturn for tea	No puedo pedirle al Saturn que prepare té; eso está fuera de lo que hago.

014 nombra BAXY; el cierre «se describe brevemente» restatea el pedido. No lo cuento como hueco de identidad (el nombre está). El 100 debe exigir primera persona.

## Qué sigue

El repo ya selecciona sampling y prompt por GGUF. Antes del 100: el compose `welcome` debe pasar `IsSafeConversationReply` (capacidad exige `baxy`; refuse no puede ser un sermón de safety). Luego cien fresco v16 con override Granite. No sello con esta A/B.
