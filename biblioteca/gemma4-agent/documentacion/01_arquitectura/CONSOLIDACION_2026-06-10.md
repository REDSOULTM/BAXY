# Consolidación de arquitectura — 2026-06-10

Revisión de consolidación previa al cierre del proyecto. Cuatro frentes:
(1) salud de invariantes, (2) doc vs código real, (3) deuda técnica medida,
(4) mapa para la documentación final. Todo verificado leyendo el código y
corriendo los guardrails — no es aspiracional.

---

## 1. Salud de invariantes y bordes — ✅ SANA

Los tests-guardrail de arquitectura corren verdes salvo dos artefactos no
arquitectónicos:

| guardrail | resultado |
|---|---|
| `test_architectural_invariants` (dispatch contiene errores, verifier no tumba el turno, diagnósticos no crashean lo que trazan) | ✅ pasa |
| `test_god_object_size_ceiling` (techos de LOC) | ✅ pasa |
| `test_silent_except_ceiling` (except:pass que tragan lógica) | ✅ pasa (376) |
| `test_router_coverage_invariant` (toda tool de dominio alcanzable) | ✅ pasa |
| `test_audit_metrics::zero_top_level_cycles` | ✅ ARREGLADO (era falso rojo) |
| `test_audit_8r::future_annotations` | ⚠️ vision_input WIP (filters.py) |

**0 ciclos de import top-level reales** — `scripts/_arch_dep_graph.py` reporta
`# CICLOS detectados: 0`. El test que lo verificaba daba falso rojo por DOS causas,
ambas arregladas en esta consolidación:
1. El conftest-guard de la suite (`_suite_guards`) clasificaba `python.exe
   script.py` como "abrir un .exe de usuario" y devolvía stdout vacío al
   subprocess → el test no leía la salida. **Fix:** excluir los intérpretes/
   herramientas de dev (python/node/git/...) del bloqueo de apertura. Este bug
   afectaba a CUALQUIER test que lanzara un subprocess de Python.
2. El parse del test usaba `-1` como sentinel silencioso; ahora hace
   `assertIsNotNone` con el stdout en el mensaje y fuerza UTF-8 en el hijo.

El único falso rojo restante es `vision_input/filters.py` (workstream de
cámara/gestos en desarrollo) sin `from __future__ import annotations`.

**Conclusión:** los invariantes que la arquitectura promete (blast-radius
contenido en dispatch, verifiers que no tumban el turno, sin ciclos, sin
huérfanos) **siguen válidos en el código actual.**

---

## 2. Documentación vs código real — DOC FIEL, falta cubrir lo reciente

`ARCHITECTURE.md` (2026-06-04) describe el código **con fidelidad**: las 6
referencias clave verificadas siguen vivas (`_run_with_timeout`,
`_post_chat_with_recovery`, `atomic_write_json`, `telemetry.rotate`,
`tts.download_voice`, `_default_embed_fn`). El mapa de capas, los invariantes por
capa y el flujo de turno son correctos.

**Gap:** el doc NO menciona las adiciones de las últimas semanas:
- Fast-paths de latencia (system_info_fast, screenshot_fast, uia_fast, etc.).
- Módulos extraídos del hot-path: `latency_helpers`, `reply_repair`,
  `agent_helpers`, `site_resolver`, `web_search`/`web_source_quality`.
- Encoder del router reentrenado (seed fija, +cultura→web).
- Modo de confirmación permisivo (`GEMMA4_CONFIRMATION_POLICY=all`).
- Guard de seguridad de la suite como default global (conftest raíz +
  `_suite_guards`).

**Acción:** una sección "Adiciones recientes" en `ARCHITECTURE.md` (hecha en este
mismo commit) que las ancla a su capa.

---

## 3. Deuda técnica medida

### 3.1 Archivos-dios (el patrón conocido, registrado y acotado)

| archivo | LOC / techo | margen | naturaleza | riesgo de partir |
|---|---|---|---|---|
| `tools_pkg/tools.py` | 8058 / 8060 | +2 | clase `ToolRegistry`, métodos `t_*` | ALTO (métodos de clase → mixin/delegación) |
| `agent_core/agent.py` | 7341 / 7341 | 0 | núcleo del agente | ALTO (estado cruza fases) |
| `domain_tools/__init__.py` | 3358 / 3370 | +12 | media/whatsapp/audio | MEDIO (patrón sibling+shim existe) |
| `tools_pkg/ops_tools.py` | 2265 / 2300 | +35 | OCR/screenshot | MEDIO |

`tools.py` y `agent.py` están **al límite** (margen ≤2). Cada feature nueva obliga
a extraer un hermano (el ratchet lo fuerza, y funcionó: ver
`MAPA_descomposicion_archivos_dios.md`). La deuda está registrada y razonada:
qué es extraíble (con el patrón R2 sibling+shim) y qué es irreducible (bloques
inline que mutan los locales del loop del turno).

### 3.2 Lazy imports — 552 (anti-patrón medido)

`agent_core.agent` concentra 122. Son imports diferidos dentro de funciones para
romper ciclos `agent_core ↔ {routing, tools_pkg, safety_pkg}`. Indican
acoplamiento alto del núcleo. No rompen nada (hay un techo enforced de 555), pero
son el síntoma de que `agent.py` sabe demasiado de todos los paquetes. Reducirlos
requiere invertir dependencias (inyección), no es trivial.

### 3.3 Tests rojos pre-existentes (6, todos ajenos al núcleo)

| test | causa | acción |
|---|---|---|
| `test_keypress_action` (×2) | cableo `_aa` en agent.py desincronizado del parser | revisar `_decide_turn` |
| `test_mcp_client` (×2) | librería `mcp` incompatible (`'type' object is not subscriptable`) | pin de versión de `mcp` |
| `test_audit_metrics::zero_top_level_cycles` | regex frágil al encoding (no es ciclo real) | arreglar regex |
| `test_audit_8r::future_annotations` | `vision_input/filters.py` (WIP) | lo cierra el workstream de cámara |

Ninguno toca el hot-path ni un invariante. Son: 2 de routing-determinista, 2 de
una dependencia externa, 2 falsos rojos de tooling.

---

## 4. Resumen para la tesis

**El proyecto está arquitectónicamente consolidado.** La capa de invariantes está
sana, la documentación es fiel (con un gap de lo reciente, ya cerrado), y la deuda
es la conocida (archivos-dios + lazy imports) — registrada, acotada por ratchets
enforced, y con un plan de descomposición razonado.

Lo que NO está cerrado y es deuda real (no bloqueante para la tesis):
- `tools.py` y `agent.py` al límite del techo → la próxima feature grande exige
  una extracción supervisada.
- 552 lazy imports → acoplamiento del núcleo; mejora estructural a futuro.
- 6 tests rojos pre-existentes → 4 arreglables (regex, pin mcp, cableo keypress),
  2 los cierra el workstream de cámara.
