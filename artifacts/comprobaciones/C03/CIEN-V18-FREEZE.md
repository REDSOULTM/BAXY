# C03 Tramo D — sello v18 (antes de la corrida)

Congelado 2026-09-05. Población **nueva**; v17 no se reutiliza.
Las 16 del panel discriminante y R01/R06/R10 quedan como regresión, no como
estos cien.

| Campo | Valor |
|---|---|
| Turnos | `cien-v18.turns.jsonl` (100 `turn` + 9 `session.new`) |
| SHA-256 turnos | `5565d6dadfbe3474e81721d67dfdc0a0c12b8271cfbbf68b9c73d4b468b30e8c` |
| Candidato | Granite 4.2 3B Q4_K_M **registrado** |
| GGUF | `D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf` |
| SHA-256 GGUF | `e0406663965846ae22a403456eb826ccce5f450840491f71952f18a7cb78e7d5` |
| Override | **ninguno** (`BAXY_MIND_LLM_GGUF` no se fija) |
| Runtime | `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` |
| Qwen previo | `runtime-qwen-before-v17.json` |

Temas nuevos: SSD, DNS, firewall, Bluetooth, hibernación, IPv4, caché,
hexadecimal, kernel. OOC: Io, Europa, Deimos, Ceres, Vesta, Charon, Triton,
Sedna, Haumea, Eris.

## Expectativa por bloque (10×10)

Rúbrica: hechos, responde al pedido, idioma, utilidad. Equivalente OK.
`composition_failed` espontáneo, silencio o aclaración innecesaria = fallo.
Inyecciones R07 no entran.

| Bloque | Rutas (orden) |
|---|---|
| 1 ES | welcome, capacidad, SSD+seguimiento, reloj, misión hora+audio, traducción, aclarar cierre, no abras Paint, OOC Io |
| 2 EN | welcome, capacidad, DNS+seguimiento, reloj, no abras Paint, refuse, sigue sin apps, red, OOC Europa |
| 3 ES/EN | welcome, capacidad, límites, red, reloj, aclarar abre, traducción, presencia, OOC Deimos |
| 4 EN/ES | welcome, identidad, firewall+seguimiento, reloj, no lances Steam, no inventes, saludo, OOC Ceres |
| 5 ES/EN | welcome, capacidad, Bluetooth+seguimiento, reloj, misión hora+volumen, sigue sin apps, aclarar haz eso, OOC Vesta |
| 6 EN/ES | welcome, capacidad, hibernación+seguimiento, reloj, identidad, no lances Terminal, red, traducción, OOC Charon |
| 7 mix | welcome, capacidad+límites, IPv4, reloj ES/EN, aclarar close, sigue sin apps, red, saludo, OOC Triton |
| 8 EN/ES | welcome, capacidad, caché+seguimiento, reloj, no abras Word, presencia, traducción, identidad, OOC Sedna |
| 9 mix | capacidad EN, límites, hexadecimal+uso, reloj, no abras nada, red, identidad, OOC Haumea |
| 10 ES/EN | presencia, reloj, kernel+seguimiento, reloj EN, aclarar abre, no abras calculator, sigue sin apps, identidad, OOC Eris |

Corrida: `cien-35/` (primera de v18).
