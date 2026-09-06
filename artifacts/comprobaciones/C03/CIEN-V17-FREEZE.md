# C03 Tramo D — sello v17 (antes de la corrida)

Congelado 2026-09-05. Población **nueva**; v16 no se reutiliza.

| Campo | Valor |
|---|---|
| Turnos | `cien-v17.turns.jsonl` (100 `turn` + 9 `session.new`) |
| SHA-256 turnos | `7a905ce3d7f7573bd62eee271b4fb1b77dee88e2d746f56b1dda3a67d6c209e4` |
| Candidato | Granite 4.2 3B Q4_K_M **registrado** |
| GGUF | `D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf` |
| SHA-256 GGUF | `e0406663965846ae22a403456eb826ccce5f450840491f71952f18a7cb78e7d5` |
| Override | **ninguno** (`BAXY_MIND_LLM_GGUF` no se fija) |
| Runtime | `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` |
| Qwen previo | `runtime-qwen-before-v17.json` |

## Expectativa por bloque (10×10)

Rúbrica: hechos, responde al pedido, idioma, utilidad. Equivalente OK.
`composition_failed` espontáneo, silencio o aclaración innecesaria = fallo.
Inyecciones R07 no entran.

| Bloque | Rutas (orden) |
|---|---|
| 1 ES | welcome, capacidad, conocimiento+seguimiento, reloj, misión hora+audio, traducción, aclarar cierre, no abras, fuera de catálogo |
| 2 EN | welcome, capacidad, UTC+seguimiento, reloj, no abras Calculator, refuse, sigue sin apps, red, OOC Callisto |
| 3 ES/EN | welcome, capacidad, límites sin abrir, red, reloj, aclarar abre, traducción, presencia, OOC Titan |
| 4 EN/ES | welcome, identidad, RAM+seguimiento (tema nuevo), reloj, no abras Steam, no inventes, saludo, no inventes hora |
| 5 ES/EN | welcome, capacidad, proceso+seguimiento (tema nuevo), reloj, misión hora+volumen, sigue sin apps, aclarar haz eso, OOC Encélado |
| 6 EN/ES | welcome, capacidad, time zone+seguimiento, reloj, identidad, no lances Terminal, red, traducción, límite |
| 7 ES | welcome, capacidad+límites, time zones, reloj, reloj EN, aclarar close, sigue sin apps, red, saludo, OOC Miranda |
| 8 ES | welcome, capacidad, RAM EN+seguimiento, reloj, no abras Notepad, presencia, traducción, identidad, OOC Oberón |
| 9 mix | spanglish hora, capacidad, huso+uso, reloj, no abras nada, red, identidad, OOC Mimas |
| 10 ES/EN | presencia, reloj, portapapeles+seguimiento (tema nuevo), reloj EN, aclarar abre, no abras calculator, sigue sin apps, identidad, OOC Ganymede |

Corrida: `cien-34/` (primera de v17). Adjudicación turno a turno en `CIEN.md`.
