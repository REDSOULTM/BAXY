# Goal 09.5.7 — Síntesis: tools, skills, providers y misiones

Cerrado 2026-08-31. Fuente de verdad machine-readable:
[`artifacts/goal095/synthesis/09.5.7_tools_skills_misiones.v1.json`](../../artifacts/goal095/synthesis/09.5.7_tools_skills_misiones.v1.json).
Inventario desde tarjetas 09.5.2–09.5.4, Goal 01
(`00_MAPA.md`, `D_ADAPTADORES_POR_APP.md`), Goal 05
(`documentacion/base/05_EJECUCION_VERIFICADA.md`), Goal 07
(`documentacion/03_COSTURAS.md`) y `_09510_requirements.json`. No se leyeron
cuerpos de `biblioteca/` ni se recorrieron árboles fuente.

Siguiente prompt humano:
[`../sprints/09.5.8_RUNTIME_UI_RECURSOS.md`](../sprints/09.5.8_RUNTIME_UI_RECURSOS.md).

Catálogo vivo, providers y `MissionEngine` **no se tocaron**. `transplants: []`.
67/31/16/158 son linaje, no un recorte de las 170 operaciones actuales
(169 públicas + `app.status`; 158 alcanzables).

## Invariantes (todos true)

Catálogo único tipado. El kernel autoriza. La confirmación se liga a la
invocación exacta. La postcondición la observa alguien que no es el ejecutor.
Una skill no sustituye al kernel.

## Capacidades (18/18)

Cada fila: operación actual, prueba dueña o hueco comprobado, mejor pieza,
evidencia, coste, mecanismo de fracaso. Citas = `card_id` de 09.5.2–09.5.4.

| Id | Operación actual | Prueba / hueco | Mejor pieza |
|---|---|---|---|
| Catálogos 67/31/16/158 | `ProductCatalog` 170/169; 158 alcanzables | `ProductCatalogTests` | No consolidar a 16: 540 midió 75,93→62,96 |
| Tools | `OperationRegistry` | `ProductCatalogTests` + `MissionEngineTests` | Mente propone, kernel autoriza |
| Skills | `skill_registry` (no opera) | `test_skill_registry.py` | 16 SKILL.md cerradas al catálogo público |
| Microagentes | ninguno | `MissionEngineTests`; hueco: no hace falta un segundo ejecutor | Rechazo del loader Carter/PG4 |
| UIA/OCR/visión | `input.visible.click` + `ocr.read` + `vision.describe` | `VisibleClickCascade*` | UIA→OCR WinRT→visión último; Qwen-VL R-023 rechazado |
| Adapters/providers | `Baxy.Providers.Windows` | `ExternalAdaptersTests` | No apilar Steam/Spotify; retiro = 09.5.9/10 |
| Planes | `planner.py` DAG de catálogo | `test_compound_missions.py` | Sin motor de workflows |
| Confirmación | `ConfirmationAuthority` | `ConfirmationAuthorityTests` | Token ↛ otro `invocationId` |
| Verificación | `VerifierContractId` | `Goal05CatalogExecutionMatrixTests` | 82 observadas, 88 unverifiable con razón |
| Steam/media | `app.open`+Click X; SMTC; `game.*` | `test_compound_missions.py`; sesión Steam/SMTC hueco | Click Steam 2026-08-23 |
| Archivos | `filesystem.*` `note.*` `backup.*` | `CoreNotesEndToEndTests` | SHA/CAS; no creer a Create |
| Apps | `app.open/close` `window.*` | `AppOpenHandlerTests` | Identidad de proceso, no título parecido |
| Navegador | `browser.*` `web.search` | `ExternalCapabilityHandlerTests`; CDP hueco | Sin Playwright segundo |
| Office | `office.document.*` | misma; cuenta hueco | Skill no autoriza |
| Comunicación | `message.*` `email.*` `calendar.*` | `DesktopMessagingAdapterTests`; halt sin sesión | Halt de «envía un mensaje» |
| Sistema | `system.*` `audio.*` | `AudioVolumeHandlerTests`; power no restaurable | Postread Core Audio |
| Conectividad | `network.*` `wifi.*` `bluetooth.*` | `WindowsNetworkStatusProviderTests` | Dos lecturas; sin SSID |
| Misión compuesta | `app.open` + `input.visible.click` | `test_compound_missions.py` | R6 6/6 22/22; Steam→biblioteca |

## Misiones Goal 10 (inventariadas, no reconstruidas)

Completas y verificadas: `app.open` Bloc de notas, `audio.volume`, `note.create`,
cadena «Abre Steam y ve a la biblioteca», forma abrir+volumen. Incompleta:
smoke Carter v2 scripted (detector ciego). Goal 10.16 pedirá C10≥74; aquí no
se ejecuta esa campaña.

## Rechazos (no propuestas)

- Routers en serie (Carter v4/v5, FunctionGemma planner no standalone).
- Listas hardcodeadas por app (F0, steam.py allowlist, adapters 2.454 líneas).
- Respuestas fijas (CORE_PROMPT, anti-echo post-LLM, stubs de hora).
- Éxitos no verificados (`tool ok`, mute sin readback, Qwen-VL visual-diff).

## Qwen-VL

No se silencia. R-023: inventó juegos. El escalón de visión de Click X es
`WindowsVisibleVisionLocator`; en esta máquina no hay endpoint. Cámara/Field UI
= 09.5.8.

## Trasplantes

Ninguno. El árbol vivo ya cubre catálogo+kernel+confirmación+postcondición+
cascada+planner. Un tools/skill/microagente histórico o duplica esa
responsabilidad o rompe un invariante.

Pesos, catálogo y providers vivos: **no se tocaron**.
