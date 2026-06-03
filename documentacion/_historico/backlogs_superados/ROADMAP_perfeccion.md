# Roadmap de perfeccionamiento — Carter Agent (2026-05-29)

> Síntesis de **10 auditorías multi-agente sobre el CÓDIGO REAL** (no los docs, que
> están parcialmente obsoletos post-R1–R8) + el research no-digerido (auditorías 360
> + informes temáticos). Hallazgos críticos **verificados de primera mano** contra el
> árbol actual. **Alcance:** todo el agente EXCEPTO transcripción/STT (otro dueño).
>
> Método (ley del proyecto): cada ítem se MIDE contra un gate, se implementa GATEADO
> (flag default-off cuando aplica), se valida EN VIVO con variantes de fraseo, y recién
> se flippea. Nada se shippea contra ruido. Respeta: 4GB VRAM / OSS-free / sin listas
> hardcoded por idioma / el LLM decide / no mentir (verify estructural) / universal.

---

## 1. Diagnóstico — esto NO es un greenfield

El equipo hizo trabajo enorme y riguroso: B1–B8 shipped, 8 investigaciones aplicadas,
refactor R1–R8 (1632 tests verde), disciplina "medí, no celebres" institucionalizada.
La arquitectura de seguridad correcta ya está en los huesos. **"Perfección" = cerrar
los últimos gaps reales, no reconstruir.** El daño residual viene de: (a) caminos donde
el "ya está" tiene un agujero concreto, (b) honestidad estructural incompleta, (c)
expansión de público bloqueada por falta de binario CPU/Vulkan. Ninguno requiere re-entrenar.

---

## 2. Lo que PUEDE FALLAR HOY (verificado, por daño × frecuencia)

### Críticos — daño irreversible o mentira

| # | Falla | Evidencia (file:line) | Impacto |
|---|---|---|---|
| **C1** | WhatsApp al **destinatario equivocado**: el fallback GUI-search teclea el nombre + Enter ciego al 1er match cuando no hay teléfono | `domain_tools/__init__.py:3317-3601` (`_whatsapp_send_via_gui_search`), disparado en `:3886` | Mensaje a persona/grupo equivocado = **irreversible**. El happy-path (deeplink por phone, PATH 1 `:3966`) ya está bien |
| **C2** | `is_group` **no existe** en metadata de contactos (VERIFICADO: grep vacío) | `domain_tools/contacts.py:121-127` (metadata `{name,email,phone,notes,created_at}`) | "mandale a mamá" puede aterrizar en grupo "Música". Sin distinción estructural |
| **C3** | `app.open` **fire-and-hope**: devuelve `ok=True` sin verificar proceso | `tools.py:3768` | "abrí Discord" cuando no se abrió → downstream falla en silencio. Mentira por optimismo |
| **C4** | `state_changed=None` se coacciona a `verified=False` (VERIFICADO) | `computer_use.py:580-581` | "No sé" → "falló" → recovery → **doble-click físico** |
| **C5** | Click reporta **éxito con `state_changed=False`** | `tools.py:5920`, `computer_use.py:346` | "Listo, hice click" contradicho por su propia señal. False-PASS 14.3% medido |
| **C6** | Primera **imagen sin pre-flight**; mmproj WARN solo loguea (VERIFICADO: recicla solo en DEGRADE) | `agent.py:1298-1335`, `vram_watchdog.py:116` | OOM/zombie en 4GB con ~1050 MiB libres |
| **C7** | `atexit` cleanup solo si se llamó `get_shared_manager()` | `llama_server.py:167-184` | Cerrás la app, el modelo come 6GB VRAM; `:8080` ocupado |

### Altos
- **H1** `error_type` declarado pero **nunca seteado** por ningún verifier (`verify_core.py:64`).
- **H2** Sin **budget de retry por-clase** → research "466/513 retries desperdiciados".
- **H4** `/health` miente bajo carga; recovery no consulta `/slots` (`llm_client.py:290`).
- **H5** Sin binario CPU/Vulkan; no auto-default a perfil 'cpu' sin NVIDIA (`config.py:19`) = **bloqueador de mercado**.
- **H6** Double-start race en `:8080` (`restart()` simple sin loop de espera).
- **H8** WhatsApp deeplink dispara sin pre-check de login (QR) → reporta `sent=True` falso.
- **H9** Circuit breaker OFF por default (`"0"` verificado) — pero **medido-y-rechazado** (v15), NO tocar.

---

## 3. Roadmap por olas

### Ola 1 — Fiabilidad y honestidad (no mentir, no dañar)
1. **WhatsApp contact_id + is_group** (C1/C2/H8): resolver candidatos con `is_group` ANTES de actuar; si hay phone → deeplink (no GUI-search); GUI-search solo último recurso con elección por enum dinámico (el LLM decide, no lista). Pre-check de login. → **Gate: wrong-entity-rate <1%, 0 contacto-vs-grupo.**
2. **Tri-estado de verify** (C4/C5): `None` deja de colapsar a `False`; nunca "hice click" con `state_changed=False`. → **Gate: 0 falsos éxitos, doble-click <2%.**
3. **app.open con verificación de proceso real** (C3). → **Gate: 0 false-positive verified con proceso ausente.**
4. **Taxonomía de error + budget por-clase + error_type en verifiers** (H1/H2). → **Gate: TOOL_NOT_FOUND=0 retried, TRANSIENT ≥80%.**
5. **Catálogo de preconditions** (`support/preconditions.py`). → **Gate: check <50ms p95.**
6. **3ª señal de verify (SetWinEventHook) + anchor-gate labels cortos** (opt-in). → **Gate: false-PASS <2%.**

### Ola 2 — Robustez de hardware (expandir el público)
- ✅ **Auto-default 'cpu' sin NVIDIA** (H5, software): `has_usable_cuda_gpu()` + `recommend_profile`
  cae a `cpu` sin NVIDIA + guard del default forzado (`profiles.py`). Gate `GEMMA4_NO_GPU_AUTOCPU`,
  override `GEMMA4_LLAMA_GPU_VENDOR`. 25 tests + EN VIVO 5/5. **PENDIENTE OPERACIONAL (usuario):**
  bundlear el binario CPU/Vulkan de llama.cpp y apuntarlo con `GEMMA4_LLAMA_SERVER_EXE` (el perfil
  `cpu` usa `-ngl 0` y ya funciona con un binario no-CUDA; el build-check avisa si falta).
- ✅ **vram_watchdog que ACTÚA + pre-flight de imagen INLINE** (C6): el pre-flight de _decide_turn solo
  cubría mode=='vision_action' (imagen de entrada); una imagen pedida por el LLM inline (gui.screenshot
  en turno de texto) cargaba mmproj sin chequeo → OOM en 4GB. `_image_inject_vram_safe` ahora actúa antes
  de `_inject_tool_image`: seguro→inyecta, inseguro→recicla+remide, sigue inseguro→NO inyecta + nota
  honesta. Fail-open ante error; no-op sin GPU. `agent.py:3088,4746`. 22 tests + EN VIVO 5/5.
- **vram_watchdog que ACTÚA + pre-flight de imagen** (C6). → **Gate: 0 OOM en 4GB con visión.**
- 🟡 **mmproj Q8_0** (560 vs 940 MiB): **el artefacto NO EXISTE (verificado 2026-05-29)** — Unsloth solo
  publica F16/F32/BF16 y `llama-quantize` falla con "unsupported architecture: clip" (cuantización de
  mmproj es feature AÚN ABIERTO, [llama.cpp#18881](https://github.com/ggml-org/llama.cpp/issues/18881)).
  El research asumía un Q8_0 que no está → **0 ahorro real hoy**. Implementado: `_resolve_mmproj_path`
  prefiere una variante Q* cuando exista (gate `GEMMA4_MMPROJ_PREFER_QUANT`), 0 cambio de comportamiento
  hoy (devuelve F16). El agente queda LISTO: dejar un mmproj-Q8_0 en models/E2B/ lo activa sin tocar
  código. `profiles.py:_resolve_mmproj_path`. 5 tests. **DESBLOQUEA cuando exista el GGUF.**
- ✅ **Frugalidad RAM** (CPU profile): -t 4 + --prio low (idle-unload NO existe en la build, verificado). 33 tests.
- ✅ **Estabilidad lifecycle** (C7/H4/H6): los 3 bugs CONFIRMADOS reales (workflow de auditoría). **C7**:
  atexit POR INSTANCIA en `LlamaServerManager.__init__` (`_atexit_stop_self`, registro fuerte) — antes solo
  el singleton se limpiaba, las 4 rutas directas (chat/ui×2/server) dejaban el child huérfano →6GB VRAM.
  El fix_sketch original del auditor estaba MAL (el handler del singleton solo mira `_SHARED_MANAGER`); el
  workflow lo detectó y dio el approach correcto. **H4**: el recovery del cliente exige `/health AND /slots`
  (gemelo `_probe_slots_alive` en LLMClient, evita ciclo de import) — `/health` miente bajo carga. **H6**:
  `restart()` toma `_restart_lock` + port-wait loop (break inmediato, ~0 latencia) — race en :8080 entre
  stop/start marcaba el server propio como 'external'. `llama_server.py:824,1222`, `llm_client.py:297,499`.
  12 tests nuevos + 66 regresión + EN VIVO 5/5 (subprocesos propios, server del usuario INTACTO).

### Ola 3 — Capacidad estratégica
- ✅ **MCP client (B9)** con disciplina de router-subset: el cliente (descubrir/llamar) y la tool-puente
  `mcp` ya existían; agregué el ENROLAMIENTO al router. Tools MCP descubiertas → namespaced `mcp__server__tool`
  → enroladas en `TOOL_DESCRIPTIONS` (router las rankea por embeddings) → cap `MAX_SELECTED_TOOLS=5` las
  limita junto a las compound → dispatcher las rutea transparente a `call_mcp_by_id`. Enrolamiento al boot,
  best-effort, gated `GEMMA4_MCP` (default OFF). **GATE VERDE: con 40 tools MCP el subset nunca trae las 40.**
  SDK `mcp` 1.27.1 instalado + servidor de prueba (`scripts/_mcp_test_server.py`). `mcp_client.py`,
  `semantic_router.py:enroll_mcp_tools`, `tools.py:execute+schemas_for_names`. 9 tests + EN VIVO 4/4 fases
  end-to-end con servidor real (discover→enroll→route+cap→dispatch). **Falta operacional: declarar servidores
  reales en `~/.gemma4/mcp_servers.json` + validar que el 4B no degrada con catálogo grande antes de flip ON.**
- **Slot-extraction deíctico** (ring de entidades) — **multilingüe por embeddings, NO regex es-only.**
- **Code-exec sandbox** — solo si el gate 0-escapes es satisfacible en Windows (probablemente no).

### Ola 4 — Latencia y pulido
- Cap defensivo de reasoning (NO prefill `<|tool_call|>`, ya medido como mala apuesta).
- Housekeeping: `state.json` borra zombies, `traces.jsonl` rotación, crear `requirements.txt`/`pyproject.toml`.

---

## 4. Definición de "perfecto" — los números

| Área | Número para "hecho" |
|---|---|
| WhatsApp destinatario | wrong-entity-rate **<1%**, 0 contacto-vs-grupo |
| Tool-call success | **≥5/6** con thinking ON u OFF |
| False-PASS GUI | **0** "Hecho" sin `state_changed`; general <2% (hoy 14.3%) |
| OOM en 4GB con visión | **0 OOM/zombie**, headroom ≥1.5GB |
| Boot sin GPU | **100%** success, perfil='cpu' auto |
| Recovery server | **≥95%** primer chat OK (hoy ~70%) |
| Orphan VRAM | **<500 MiB** en 5s tras kill |

**Regla transversal:** ningún subgrupo fuerte (ES/EN) debe degradarse al mejorar el promedio.

---

## 5. Riesgos del plan / qué NO hacer
- **MCP** puede degradar tool-calling si bypassea el cap de 5 → test obligatorio antes de default-on.
- **Code-exec sandbox** inescapable en Windows probablemente imposible (R6 ya eliminó eval/exec).
- **Eager read-only pre-exec** puede violar "nunca pre-ejecutar una escritura".
- **NO re-litigar medido-y-rechazado:** circuit-breaker ON, prefill `<|tool_call|>`, FR-CoT, core-set, fine-tune sobre voz del operador, rewrite/async-total/Pydantic-args.
