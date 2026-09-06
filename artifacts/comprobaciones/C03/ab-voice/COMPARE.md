# A/B Q4 vs Q5 vs Q3 vs Granite 4.2-3B (identidad/conocimiento)

Turnos congelados: `ab-voice.turns.jsonl` (15 turnos + 1 `session.new`).
Conductor C01, commit `5f572ee`, policy WIP, `BAXY_MIND_LLM_GGUF` sin registrar producción.
Producción sigue `D:\BAXYRuntime\assets\models\Qwen3-4B-Q4_K_M.gguf` (SHA `7485fe6f…`).

## Veredicto

No se cambia el GGUF registrado. Ningún perfil publica 15/15 finales naturales y fieles.

| Perfil | Publica | Honestos `composition_failed` | Huecos publicados (rúbrica G06.01) |
|---|---:|---:|---|
| Qwen3-4B Q4_K_M (producción) | 5 | 9 + 1 filtered | «Hola» → «No pude: no pude encontrarlo.» (causa falsa) |
| Qwen3-4B Q5_K_M | 9 | 6 | «soy un él»; «What will you refuse» invertido (pregunta al usuario) |
| Qwen3-4B Q3_K_M | 8 | 7 | Identidad buena («Soy BAXY…»); refuse invertido («I'll refuse to do anything») |
| Granite 4.2-3B Q4_K_M | 11 | 4 | Identidad → «solicitud no está clara» (pedido claro); husos con ecuador/polos como causa; refuse evadido («I'm happy to help») |

Granite es el único que contesta UTC/huso/zonas en prosa y no filtra `<think>`. Relojes 17:55 en ventana 17:53–17:56. No se registra. El 100 de medición (`cien-28`) usa este GGUF por override; G06.01 no se sella hasta leer esa muestra.

| quant | n | published_final | composition_failed | huecos léxicos |
|---|---:|---:|---:|---|
| Qwen3-4B Q4_K_M | 15 | 5 | 9 | 0 |
| Qwen3-4B Q5_K_M | 15 | 9 | 6 | 0 |
| Qwen3-4B Q3_K_M | 15 | 8 | 7 | 0 |
| Granite 4.2-3B Q4_K_M | 15 | 11 | 4 | 0 |

## Qwen3-4B Q4_K_M
n=15 published=5 failed=9
001	published_final	Hola	No pude: no pude encontrarlo.
002	filtered	quién eres	filtered
003	composition_failed	introduce yourself	composition_failed
004	composition_failed	qué puedes hacer	composition_failed
005	published_final	What can you do here	I can help with various tasks such as answering questions, providing information, and assisting with problem-solving.
006	composition_failed	what is UTC, one line	composition_failed
007	composition_failed	explícame qué es un huso horario	composition_failed
008	composition_failed	why do time zones exist	composition_failed
009	composition_failed	define huso horario, una frase	composition_failed
010	composition_failed	What will you refuse to do	composition_failed
011	published_final	traduce 'hello' al español, nada más	¡Hola!
012	published_final	¿Qué hora es?	Listo, la hora local es 17:44.
013	published_final	Could you tell me the time?	The time is 17:44.
014	composition_failed	descríbete breve	composition_failed
015	composition_failed	ask Saturn for tea	composition_failed

## Qwen3-4B Q5_K_M
n=15 published=9 failed=6
001	published_final	Hola	Hola. ¿Qué tal?
002	composition_failed	quién eres	composition_failed
003	composition_failed	introduce yourself	composition_failed
004	composition_failed	qué puedes hacer	composition_failed
005	published_final	What can you do here	I can answer questions, provide information, and help with tasks. I can also engage in conversations and understand context from the dialogue.
006	published_final	what is UTC, one line	UTC stands for Coordinated Universal Time, a time standard that is essentially the same everywhere in the world. It's used as a reference point for time zones and is based on the mean solar time at the Prime Meridian in Greenwich, England.
007	composition_failed	explícame qué es un huso horario	composition_failed
008	composition_failed	why do time zones exist	composition_failed
009	composition_failed	define huso horario, una frase	composition_failed
010	published_final	What will you refuse to do	Quiero saber qué tarea específica me pedirían que rechace o no realice.
011	published_final	traduce 'hello' al español, nada más	Hola.
012	published_final	¿Qué hora es?	Listo, la hora local es 17:46.
013	published_final	Could you tell me the time?	I saw the time was 17:46.
014	published_final	descríbete breve	BAXY es mi compañero que vive en el PC y soy un él.
015	published_final	ask Saturn for tea	No pude: eso no lo hago.

## Qwen3-4B Q3_K_M
n=15 published=8 failed=7
001	published_final	Hola	Hola.
002	published_final	quién eres	Soy BAXY, un compañero que vive en el PC.
003	composition_failed	introduce yourself	composition_failed
004	composition_failed	qué puedes hacer	composition_failed
005	published_final	What can you do here	I can help you with questions, provide information, and assist with tasks.
006	published_final	what is UTC, one line	UTC stands for Coordinated Universal Time, a global standard time used in many systems and communications.
007	composition_failed	explícame qué es un huso horario	composition_failed
008	composition_failed	why do time zones exist	composition_failed
009	composition_failed	define huso horario, una frase	composition_failed
010	published_final	What will you refuse to do	I'll refuse to do anything you ask me to.
011	published_final	traduce 'hello' al español, nada más	hola
012	published_final	¿Qué hora es?	Listo, es las 17:52.
013	composition_failed	Could you tell me the time?	composition_failed
014	composition_failed	descríbete breve	composition_failed
015	published_final	ask Saturn for tea	No pude: esa tarea no forma parte de lo que hago.

## Granite 4.2-3B Q4_K_M
n=15 published=11 failed=4
001	published_final	Hola	¡Hola! ¿Cómo estás?
002	published_final	quién eres	No pude: la solicitud no está clara.
003	published_final	introduce yourself	No pude: la solicitud no estaba clara.
004	composition_failed	qué puedes hacer	composition_failed
005	published_final	What can you do here	I can help you explore what’s possible here, answer questions, and guide you through tasks.
006	published_final	what is UTC, one line	UTC is Coordinated Universal Time, a global time standard based on atomic clocks and solar time adjustments.
007	published_final	explícame qué es un huso horario	Un huso horario es una zona geográfica donde todos los horarios se ajustan para que el tiempo sea consistente, considerando la diferencia de desplazamiento entre regiones.
008	published_final	why do time zones exist	Time zones exist to keep local time synchronized with the Earth’s rotation, allowing people around the world to coordinate activities based on consistent local hours. They are based on longitudinal differences, so that regions closer to the equator experience less variation in daylight compared to those near the poles. This system helps align schedules across different parts of the globe for work, travel, and daily life.
009	composition_failed	define huso horario, una frase	composition_failed
010	published_final	What will you refuse to do	I'm happy to help—just let me know what you need.
011	composition_failed	traduce 'hello' al español, nada más	composition_failed
012	published_final	¿Qué hora es?	La hora actual es 17:55.
013	published_final	Could you tell me the time?	The local clock shows 17:55.
014	composition_failed	descríbete breve	composition_failed
015	published_final	ask Saturn for tea	No puedo ayudar porque está fuera de lo que hago.
