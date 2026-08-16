# Carter v3 — RESIDUAL

> Backlog honesto de lo que **NO** está cerrado al final de FASE 0.
> Cada item es real, observable o por contrato decidido como deferido.
> Esta lista es el contrato de "qué no podemos olvidar en FASE 1+".
>
> Convención de IDs:
> - `R-Vx-...`  → riesgo residual heredado de Carter_v2 que v3 todavía debe resolver.
> - `R-V3-...`  → riesgo nuevo introducido por una decisión de FASE 0.
> - `I-...`     → investigación pendiente (no riesgo, pero requiere experimento).

---

## Sección A — Backlog heredado de Carter_v2 que v3 debe resolver

### R-V2-B1 — Action-route fallback estructural (cases 7, 8 de C7 / C12)

**Origen.** `legacy/Carter_v2/RESIDUAL_BACKLOG_AFTER_BLOCK.md` B-1.

**Estado FASE 0.** Cubierto **por contrato** en D5 ("Action-route
fallback si el LLM no llama tool"). Sin código todavía.

**Lo que falta.**
- implementación del sintetizador de tool call estructural.
- pytest unit suite que pruebe "imperativo + ventana resuelta →
  tool call sintetizado" sin regresar C9 / C10 / C13 (chat-only).
- evidencia live: cases 7 y 8 deben pasar 2 de 3 corridas safe-live
  consecutivas.

**Owner.** FASE 1 / módulo `agent_loop` o `action_router` (TBD en PARTE 2).

---

### R-V2-B2 — Detector estructural de declarative-fact (case 11 de C4)

**Origen.** `legacy/Carter_v2/RESIDUAL_BACKLOG_AFTER_BLOCK.md` B-2.

**Estado FASE 0.** Cubierto por contrato en D3. La "versión simple
defendible" (fallback post-LLM con offer "¿quieres que lo recuerde?")
está aceptada como mínimo viable.

**Lo que falta.**
- decisión de tooling POS-light: `spacy` (tamaño/latencia), `udpipe`,
  `stanza`, o regex morfológico mínimo. Investigación I-1 abajo.
- pytest parametrizado ES + EN sin tokens hardcoded.
- evidencia: case 11 debe pasar 2 de 3 corridas safe-live sin
  hardcodear `intelectra` / `placilla` / `Microsoft` / `Google`.

**Owner.** FASE 2 (capa de detección de intención).

---

### R-V2-B3 — Cold-start residual del primer turno

**Origen.** `legacy/Carter_v2/RESIDUAL_BACKLOG_AFTER_BLOCK.md` B-3.

**Estado FASE 0.** D8 establece preload + heartbeat; el cold-start
de Ollama (>8s para case 1 `a`) **no** queda cerrado por contrato
de FASE 0. Mitigaciones contractuales:

- adapter `OllamaAdapter` debe enviar `keep_alive=10m` por default.
- `preload()` se invoca desde el launcher antes de aceptar primer
  input del usuario (no en `__post_init__` del agent).
- selector descarta modelo si `estimated_first_token_ms >
  latency_budget_ms` para ese rol.

**Lo que falta verificar live.**
- case 1 (`a`) ≤ 8.0s en 2 de 3 corridas contra Ollama recién
  lanzado.

**Riesgo residual conocido.** Si el usuario hace launch en frío y
escribe inmediatamente, el primer turno seguirá excediendo 8s.
Mitigación UX: el launcher muestra un spinner "Carter calentando…"
hasta que `preload()` termina.

**Owner.** FASE 1 (launcher) + FASE 4 (live validation).

---

### R-V2-B4 — Contrato para `que?` y entradas ambiguas mono-token

**Origen.** `legacy/Carter_v2/RESIDUAL_BACKLOG_AFTER_BLOCK.md` B-4.

**Estado FASE 0.** Resuelto **por contrato**: una entrada
estructuralmente clasificada como "ambigua mono-token" debe producir
una **clarifying question** (no fallback genérico) y `mission_status
= "trivial"`. Esto es la opción "runtime genera la pregunta", no la
opción "el contrato relaja la matriz".

**Lo que falta.**
- el detector estructural de "ambigua mono-token" (parte de D2
  señal A ampliada).
- una plantilla de clarifying question parametrizable por idioma
  detectado (no listas humanas; el modelo genera el texto bajo
  prompt corto del system "ask one short clarifying question").
- actualizar `acceptance_checks` del runner v3 para aceptar
  pregunta de aclaración.

**Owner.** FASE 2.

---

### R-V2-B5 — Reescritura de `recovery/classifier.py`

**Origen.** `legacy/Carter_v2/RESIDUAL_BACKLOG_AFTER_BLOCK.md` B-5.
Tech debt léxico pre-existente.

**Estado FASE 0.** Carter v3 **no porta** `recovery/classifier.py`.
La lógica de retry vive en D10 (un retry estructural por step,
decidido por `VerifiedOutcome.status`, no por keywords).

**Lo que falta.** Confirmar en FASE 1-2 que ningún módulo nuevo
introduce el patrón viejo. `audit/hardcode_guard.py` debe portarse
a v3 con allowlist vacío para módulos de recovery.

**Owner.** FASE 1 (hardcode_guard portado).

---

### R-V2-B6 — Dry-run no es evidencia live

**Origen.** `legacy/Carter_v2/RESIDUAL_BACKLOG_AFTER_BLOCK.md` B-6.

**Estado FASE 0.** Aceptado como **invariante de PARTE 2/3**: el
runner v3 (FASE 4) debe etiquetar dry-run como `[ROUTER-ONLY: NOT
live evidence]` y los gates de cierre deben rechazar dry-run como
prueba de runtime correctness.

**Lo que falta.** Implementación del runner con esa etiqueta y
gates que la consuman.

**Owner.** FASE 4 (audit / validation).

---

### R-V2-B7 — Cases 1, 2, 6, 11 del transcript real del usuario

**Origen.** `legacy/Carter_v2/audit/results/CARTER_TEXT_BLOCK_LANDING_AUDIT.md`.

**Estado FASE 0.** Mapeado: B7 = consolidado de B1+B2+B3+B4 más el
caso C18 ("Que pasa chaval", C18.07). Cierra cuando B1..B4 cierran
y C18 pasa al `acceptance_checks` ampliado.

**Riesgo nuevo.** "Que pasa chaval" es **memoria de estilo no
durable** (Valor 5 + C5). El detector debe distinguir
"preferencia oneshot" de "preferencia con confirmación de
durabilidad". D3 + D9 + nueva lógica de estilo en FASE 2.

**Owner.** FASE 2 (preferencias) + FASE 4 (regression).

---

## Sección B — Riesgos nuevos introducidos por FASE 0

### R-V3-1 — POS-light universal sin librería pesada (D2/D3)

**Decisión.** D2 y D3 dependen de detección morfológica universal
sin keyword lists.

**Riesgo.** Las dos opciones realistas son:

- `spacy` con modelo multilingüe `xx_sent_ud_sm` (~12MB) o
  `xx_ent_wiki_sm` (~10MB): cumple R1 pero añade ~80-150ms al
  pre-LLM, peligroso para L0 (<500ms para chat).
- regex morfológico mínimo (sufijos verbales para imperativo
  ES/EN/PT + heurística de pronombre interrogativo): rápido pero
  cubre 4-5 idiomas, no universal.

**Estado.** Sin decidir. La versión simple defendible para FASE 1
es la regex morfológica con cobertura ES/EN, y un fallback "ningún
recurso resuelto + sin signo imperativo → no tools". I-1 explora
spacy.

**Mitigación contractual.** Si un detector falla, Carter cae a
ruta segura ("no tools, conversación normal"). Cero falsos positivos
de tools por idioma no soportado.

---

### R-V3-2 — Anchors hardcoded en SecretFilter (D9)

**Decisión.** Lista cerrada de 8-12 anchors universales como
excepción auditada a R1.

**Riesgo.** Drift: futuras PRs pueden expandir la lista
silenciosamente, normalizando el patrón "agregar keywords cuando
algo no funcione".

**Mitigación contractual.**
- la constante `SECRET_ANCHORS` vive en `Carter_v3/src/carter_v3/security/secret_filter.py`
  con **comentario obligatorio** justificando cada anchor y un
  contador en CI: si crece >12 entries sin update del comentario
  raíz, falla.
- la PR que la edite debe etiquetarse `audit-required`.

**Estado.** Pendiente implementación FASE 1-2. Hasta entonces,
el riesgo es contractual.

---

### R-V3-3 — `model_registry` requiere YAML que aún no existe

**Decisión.** D2.4.2 declara `Carter_v3/configs/models.yml` como
fuente de verdad runtime.

**Riesgo.** PARTE 2 debe crear el YAML con al menos N=3 perfiles
(uno por adapter: ollama, openai_compat, openai_api). Si el YAML
no existe → `model_selector` devuelve None → Carter no responde.

**Mitigación contractual.**
- launcher exige `models.yml` válido al startup; si falta, error
  amigable y guía al usuario a copiarlo desde
  `Carter_v3/configs/models.example.yml`.
- el ejemplo (no creado en FASE 0) debe incluir entradas que
  funcionen out-of-the-box en RTX 4060 Ti 16 GB.

**Estado.** Pendiente PARTE 2.

---

### R-V3-4 — `_VERIFIABLE_TOOLS` heredado vs cap de 32 tools

**Decisión.** D10 limita las tools registradas a **32**. El dict
`_VERIFIABLE_TOOLS` de `legacy/Carter_v2/src/carter_v2/turn/verification.py`
contiene >180 entries.

**Riesgo.** PARTE 2 debe seleccionar el subconjunto de **≤32**
tools que quedarán en v3, conservando cobertura de las categorías
con `expected_tool_policy != "none"` de la matriz v2.

**Lista mínima propuesta (revisar en PARTE 2):**

```
clock_now
system_get_time
system_get_volume
system_set_volume
system_mute
system_get_battery
system_get_cpu_info
system_get_ram_info
system_get_gpu_info
network_get_ip
process_list
window_list
app_open
app_close
process_stop_app
window_close
window_focus
filesystem_list_directory
filesystem_read_text
filesystem_write_text
filesystem_search_files
desktop_screenshot
web_open_url
web_search
web_extract
memory_save
memory_recall
memory_delete
heartbeat_status
notify_toast
terminal_run_command
gui_click
```

= 32. Cubre C1, C2, C3 (sin tools), C4, C6, C7, C8, C9, C11
(refusal), C12, C13 (parcial), C15, C16, C17. C10 (terminal) y C14
(typos) cubiertos por composición.

**Estado.** Lista propuesta, **no decidida**. PARTE 2 debe revisar
y cerrar.

---

### R-V3-5 — `tool_call_mode = none` para roles tool_caller

**Decisión.** D2.4.5 permite `none` solo para chat / knowledge.

**Riesgo.** Si el usuario solo tiene modelos `none` (ej. CPU-only
con un GGUF muy pequeño que no soporta tools fiable), Carter no
puede ejecutar acciones. Resultado: `mission_status = failed` con
`termination_reason = verification_required_but_unavailable` para
toda categoría 6-13.

**Mitigación contractual.**
- launcher detecta esta condición y muestra al inicio: "Tu
  configuración actual no soporta acciones; Carter responderá solo
  en modo conversación. Para acciones, instala un modelo
  compatible."
- `mission_status = trivial` con `termination_reason =
  trivial_chat` permanece funcional sin tools.

**Estado.** Pendiente PARTE 2 (UX del launcher).

---

### R-V3-6 — Contrato D5 vs C13 (visión)

**Decisión.** D5 sintetiza tool call si LLM no llama y D4 resolvió
target. D6 ladder favorece niveles bajos.

**Riesgo de regresión.** Para cases C13 que piden "verifica que
notepad está abierto", D5 podría sintetizar un `vision_*` si
interpreta el imperativo. Pero D6 ladder dice "process > vision".
La interacción correcta:

1. D4 resuelve "notepad" → existe en `process_list`.
2. D6 ladder responde con info de proceso (nivel 1) sin tool
   call adicional ni vision.
3. D5 no sintetiza nada porque ya hay respuesta correcta.

**Verificar en FASE 4.** Tests para C13 deben confirmar que vision
NO se carga para estos verbos cuando process basta.

---

### R-V3-7 — Heartbeat thread vs Windows GIL

**Decisión.** D8 + T4 usan thread daemon para el heartbeat.

**Riesgo.** En Python con GIL bajo carga de generación del LLM
síncrona (Ollama HTTP request bloqueante en el main thread), el
thread del heartbeat puede no recibir scheduling. Resultado: el
heartbeat se emite tarde (>3s).

**Mitigación contractual.** Las llamadas al LLM se hacen con
`requests` con timeout y la respuesta se streamea (no `chat()`
sync para turnos largos). Eso libera el GIL durante I/O.

**Estado.** Implementación de FASE 1.

---

### R-V3-8 — window_focus verificacion best-effort

**Decision.** `window_focus` usa Win32 `SetForegroundWindow` y se
verifica con el titulo activo (WindowProbe).

**Riesgo.** Algunas apps bloquean el focus o cambian el titulo muy
rapido; la verificacion puede quedar `pending` o `unverifiable`
aunque el foco haya cambiado.

**Mitigacion contractual.** Respuesta honesta con sugerencia de
`window_list` o `window_focus` con target mas especifico.

**Estado.** Aceptado (round 2).

---

### R-V3-9 — pywinauto cold-start latencia primera llamada UIA

**Decision (round 3).** `UiaProbe` inicializa `Desktop(backend="uia")`
de pywinauto bajo demanda. La primera llamada a `is_available()` /
`find_window()` / `inspect_active_window()` puede tardar ~150-400ms
inicializando comtypes + cargando UIAutomationCore.

**Riesgo.** Si esa primera llamada cae dentro del verifier de
`app_open` durante un turno con presupuesto L0 ajustado, el budget
del turno puede degradarse.

**Mitigacion contractual.**
- `verifier._get_uia_probe()` devuelve la misma instancia a nivel
  modulo; subsecuentes llamadas no repagan el costo.
- `_init_attempted` evita reintentos de import si pywinauto fallo.
- Preload opcional desde el launcher: `from carter_v3.tools.verifier
  import _get_uia_probe; _get_uia_probe().is_available()` en startup.
- Si pywinauto no esta instalado, el costo es 0 (modulo no se importa).

**Estado.** Aceptado (round 3); preload opcional pendiente.

---

### R-V3-10 — UIA reporta is_visible=False en DPI scaling / RDP

**Decision (round 3).** Algunos hosts (DPI > 150%, sesiones RDP,
multi-monitor con virtualizacion) hacen que pywinauto reporte
`is_visible()=False` para ventanas que el usuario sigue viendo.

**Riesgo.** El verifier ve `ui_root_available=False` y degrada la
evidencia, aunque la accion realmente ocurrio.

**Mitigacion contractual.** UIA es **enriquecedor**, no gate. El
verifier de `app_open` confirma con `process_list` o `WindowProbe`
y solo anade UIA como evidence opcional. Un `ui_root_available=False`
nunca convierte un CONFIRMED en PENDING.

**Estado.** Aceptado (round 3).

---

### R-V3-11 — filesystem_delete con backup sin restore publico

**Decision (round 4).** `filesystem_delete` ahora mueve el target a
`data_dir/fs_backups` cuando el estimado de tamano permite rollback.

**Riesgo.** No existe tool publico para restaurar desde backup; el
rollback requiere mover manualmente el backup. Si el estimado supera
el cap, se exige `allow_no_backup=true` con `user_approved=true`.

**Mitigacion contractual.** El tool devuelve `backup_path` y
`backup_root` para que el LLM explique el restore manual. El limite
de tamano evita operaciones gigantes sin confirmacion explicita.

**Estado.** Aceptado (round 4); restore tool pendiente.

---

## Sección C — Investigaciones pendientes (no riesgos)

### I-1 — Decidir la stack de POS-light universal

**Pregunta.** ¿spacy multilingüe + descarga lazy del modelo, o
regex morfológico ES/EN extendido luego a otros idiomas, o un
módulo aún más liviano (tinytokenizer + heurísticas)?

**Criterio de decisión.**
- latencia: pre-LLM total <500ms en chat, <1000ms en acción.
- tamaño: <30MB total para no inflar el venv.
- cobertura: ES, EN obligatorios; PT, FR, DE deseables; resto al menos
  no rompe.
- mantenimiento: cero modelos descargados en runtime sin permiso.

**Acción para PARTE 2.** Spike de 1 día midiendo latencia en
RTX 4060 Ti contra los 3 candidatos.

---

### I-2 — Threshold óptimo de `rapidfuzz` para nombres cortos

**Pregunta.** D4 usa score_cutoff=85 calibrado en C7. Apps con
nombres ≤4 chars ("CMD", "Vim", "VLC") pueden pasar el cutoff con
falsos positivos.

**Acción para PARTE 2.** Evaluar si el cutoff debe ser una función
del largo del span: por ejemplo `cutoff = 85 + max(0, 4 - len(span)) * 5`.

---

### I-3 — `keep_alive` por adapter

**Pregunta.** Ollama tiene `keep_alive`. ¿openai_compat (llama.cpp,
vllm, lmstudio) tienen equivalente útil?

**Acción para PARTE 2.** Documentar en cada adapter cuál es el
mecanismo de "mantener modelo cargado" si existe. Si no existe,
documentar el costo del cold-load por turno y cómo el contrato L
se relaja para ese adapter.

---

### I-4 — Rollback automático de `filesystem_delete`

**Pregunta.** D2.10 propone backup en `~/.carter/trash/<token>/`.
¿Cuál es el límite de tamaño / política de cleanup? ¿Qué pasa con
archivos > 1GB?

**Acción para PARTE 3.** Política con default sano: backup hasta
500MB; >500MB → confirmación extra "no puedo respaldar este archivo,
continuar?".

---

### I-5 — Calibración del watcher de heartbeat

**Pregunta.** ¿3000ms es el umbral correcto? ¿Hay tipos de turn
donde 5000ms sea más apropiado para no saturar la UI con
"buscando…"?

**Acción para PARTE 2.** Default 3000ms; configurable en
`configs/runtime.yml` por familia de turn (chat, action, mission).

---

## Sección D — Lo que NO está en este backlog (a propósito)

- **Voz, cámara, vision LLM avanzada.** ContextoCarter Valor 26-27
  los marca como capas externas posteriores al núcleo texto. No se
  diseñan en FASE 0-4.
- **Plugin system.** D10 lo prohíbe explícitamente.
- **Mission graph / DAG de pasos.** D10 lo prohíbe.
- **Caches especulativos complejos.** Anti-overengineering.
- **Persistencia distribuida / sync entre dispositivos.** Fuera de
  scope local-first FASE actual.
- **Multi-usuario / perfiles concurrentes.** Carter es un asistente
  personal de un usuario.

---

## Sección E — Cierre

Backlog total: **7 heredados + 7 nuevos + 5 investigaciones = 19 items**.

Ninguno bloquea el cierre de FASE 0. Todos quedan documentados con
owner y criterio de cierre.

PARTE 2 debe leer este RESIDUAL antes de empezar FASE 1.

---

## Seccion F — Estado residual despues de PARTE 2 (FASE 1-4 cerradas)

### R-P3-1 — Runner de matriz completa 654 casos (live)

- Estado: pendiente.
- Lo que existe: `audit/full_matrix_runner.py` en modo smoke/dry-run.
- Faltante: portar matriz completa equivalente a v2 y ejecutar baseline live repetible.

### R-P3-2 — Evidencia live real (no dry-run)

- Estado: pendiente.
- Lo que existe: smoke runner marca correctamente `[ROUTER-ONLY: NOT live evidence]`.
- Faltante: harness de ejecucion live con validadores y gates de aceptacion por categoria.

### R-P3-3 — Cobertura verificable de herramientas con side-effects reales

- Estado: parcial.
- Lo que existe: verifiers estructurales y dispatcher base.
- Faltante: implementaciones productivas para varios handlers actualmente stub (`desktop_screenshot`, `terminal_run_command`, `web_extract`, `gui_*`) y su readback robusto.

### R-P3-4 — recovery estructural corto por accion

- Estado: parcial.
- Lo que existe: settlement honesto y estados `partial/unverified/failed`.
- Faltante: estrategia de recuperacion corta por familia de tool antes de fallo definitivo en mas rutas.

### R-P3-5 — Capa de rendimiento live bajo carga real

- Estado: pendiente de medicion live.
- Lo que existe: caps, heartbeat, selector por capacidad, probes lazy.
- Faltante: benchmark reproducible por hardware para confirmar contrato de latencia en sesiones largas.

### R-P3-6 — Config de registry en formato final de despliegue

- Estado: parcial.
- Lo que existe: `configs/models.example.yml` y loader funcional.
- Faltante: archivo de despliegue definitivo del usuario (`models.yml`) y perfilado fino por runtime local.

### R-P3-7 — Perception avanzada y vision real

- Estado: base lista, capa avanzada pendiente.
- Lo que existe: ladder process/window/screenshot/ocr/vlm con priorizacion correcta.
- Faltante: integracion completa de OCR/VLM con verificacion y costos de VRAM en pruebas live.

### R-P3-8 — Auditoria de politicas adicionales (self-harm/prompt leak profundo)

- Estado: parcial.
- Lo que existe: deteccion estructural de patrones destructivos y exfil directa.
- Faltante: ampliar cobertura de escenarios complejos manteniendo cero keyword-hacks y falso positivo bajo.

### Cierre

FASE 1-4 quedan ejecutadas con tests verdes y limites cumplidos.
Lo pendiente para PARTE 3 es principalmente: validacion live completa, harness/matriz 654, y hardening de rutas productivas no cubiertas por smoke.

---

## Seccion G — Residual real despues de PARTE 3

### R-P3-9 — Contaminacion de resolver/active-app en chat, identidad y conocimiento

- Evidencia: `active_app_policy` fue el hallazgo mas frecuente en `full_matrix_run01..04`.
- Ejemplos reales:
  - `C1.04 buenos dias -> "No estoy seguro a cual te refieres..."`
  - `C2.05 Who are you -> candidatos de procesos/ventanas`
- Impacto: rompe `ContextoCarter.md` valores 2, 11, 12, 20 y 21.
- Estado: bloqueante.

### R-P3-10 — Categoria 11 no aterrizada

- Evidencia: `category_11_pass_rate = 69.39%` en las 4 corridas live-safe.
- Hallazgo tecnico: Carter aun ejecuta o intenta tools en prompts destructivos donde el contrato exigia bloqueo pre-LLM o pre-tool.
- Impacto: rompe valores 3, 4, 15 y el criterio obligatorio `cat 11 = 100%`.
- Estado: bloqueante.

### R-P3-11 — Tool use espurio en identidad, conocimiento y memoria declarativa

- Evidencia: `tool_policy` fue el segundo fallo mas frecuente.
- Casos visibles:
  - identidad (`C2.02`, `C2.16`)
  - conocimiento (`C3.22`, `C3.28`, `C3.29`)
  - memoria (`C4.02`, `C4.14`, `C4.22`)
- Impacto: Carter responde como pipeline de tools, no como companero de PC sobrio.
- Estado: bloqueante para aterrizaje pleno.

### R-P3-12 — Cobertura live-safe incompleta para categorias 8 y 13

- Evidencia: pass rate `0.00%` en ambas categorias dentro del baseline final.
- Motivo: el subset live-safe actual no cubre todavia web/browser y GUI/vision con suficiente seguridad y verificacion real.
- Impacto: impide declarar baseline landed aunque otros buckets pasen.
- Estado: bloqueante.

### R-P3-13 — Latency spikes cross-model en `phi3.5:latest`

- Evidencia: run 04 mostro trivial turns de `12s`, `16s` y `20s`; `p95 = 1054.8 ms`, pero con outliers grandes.
- Impacto: no rompe el gate numerico de `p95 <= 12s`, pero si la sensacion de Carter "rapido y vivo".
- Estado: no bloquea por si solo, pero es hallazgo de identidad/comportamiento.

### R-P3-14 — Heartbeat no consistente en todas las corridas

- Evidencia: `heartbeat_turns` = `1`, `1`, `0`, `7`.
- Impacto: la mecanica existe, pero no quedo probada de forma consistente en todas las familias de turno/modelo.
- Estado: residual tecnico, no bloqueante por si solo.

### R-P3-15 — El score global puede sobre-representar early exits honestos pero incorrectos

- Evidencia: global `81.55%` a `83.33%` convive con fallos graves en cat 11 y contamination de chat/identity.
- Interpretacion: parte del pass rate proviene de respuestas triviales o `needs_user` que preservan contratos formales, pero no siempre resuelven la intencion real del usuario.
- Impacto: exige auditoria cualitativa ademas de score numerico.
- Estado: hallazgo auditor, no simple bug unitario.

### Cierre PARTE 3

El harness y las corridas live ya existen y son reutilizables.
El veredicto honesto de esta parte es que Carter v3 **todavia no aterrizo** como baseline live verificado.

---

## Seccion H — Estado residual despues de la correccion minima post-PARTE 3

### R-P3-9 — Contaminacion de resolver/active-app en chat, identidad y conocimiento

- Estado: mitigado por cambio de ruta, no cerrado por full baseline.
- Lo aterrizado: las rutas no-accion ya no abren resolver, active-app ni catalogo de tools por defecto.
- Evidencia local: tests de saludo, identidad, conocimiento y memoria declarativa pasan sin tool use espurio.
- Pendiente real: re-ejecutar full matrix live-safe completa para confirmar que el hallazgo desaparece en todas las variantes de C1/C2/C3/C4/C16/C18.

### R-P3-10 — Categoria 11 no aterrizada

- Estado: mitigado en runner minimo de categoria, no cerrado por full baseline.
- Lo aterrizado: bloqueo pre-tool por `target` no resuelto/verificable; resolver fuzzy mas conservador; sin hardcodes nuevos de lenguaje natural en policy.
- Evidencia real: runner minimo `--mode live-safe --category 11` reporto `cat11=100.0%`.
- Pendiente real: full matrix live-safe completa y auditoria de prompts destructivos complejos. La defensa actual evita ejecutar tools sin target verificable; no pretende resolver semantica destructiva universal por listas de frases.

### R-P3-11 — Tool use espurio en identidad, conocimiento y memoria declarativa

- Estado: mitigado por contrato de allowed-tools, no cerrado por full baseline.
- Lo aterrizado: tool calls del backend se ignoran si la ruta no expuso esa tool; solo quedan permitidas herramientas read-only sin contexto para hora.
- Evidencia local: regresiones de identidad, conocimiento y memoria declarativa pasan.
- Pendiente real: validar en matriz completa con backend live y modelos secundarios.

### R-P3-12 — Cobertura live-safe incompleta para categorias 8 y 13

- Estado: parcial.
- Lo aterrizado: subset minimo live-safe para `C8.05`, `C8.11`, `C13.05`, `C13.15`.
- Evidencia real: runner minimo de C8 y runner minimo de C13 reportaron `global=100.0%` en sus subsets elegibles.
- Pendiente real: ampliar cobertura realista de web/browser y GUI/vision sin romper la regla de no usar vision/tools por defecto.

### Riesgos que siguen abiertos

- No se re-ejecuto full matrix completa despues de la correccion minima.
- `phi3.5:latest` conserva riesgo de outliers de latencia hasta nueva medicion cross-model.
- Heartbeat sigue necesitando validacion consistente en familias de turno largas.
- El score global antiguo no debe reinterpretarse como baseline landed.

### Cierre de esta correccion

La correccion minima redujo los bloqueos inmediatos con tests verdes,
`hardcode_guard` limpio y runners minimos reales. El baseline completo sigue
pendiente hasta una nueva corrida full live-safe/live de la matriz completa.

---

## Seccion I — Estado despues de corregir regresiones de routing y secretos

### R-P3-16 — Acciones legitimas formuladas como pedido cortes

- Estado: mitigado con test focalizado.
- Lo aterrizado: la deteccion morfologica de accion revisa tokens tempranos no-target, por lo que `por favor abre notepad` y `puedes abrir notepad` vuelven a rutear como accion cuando `notepad` es resoluble.
- Salvaguarda: el target final ya no se interpreta como verbo, evitando el falso positivo `force kill explorer -> app_open`.
- Evidencia real: tests focalizados pasaron; ejemplos directos rutearon a `app_open` con `mission_status=unverified` por verificacion inconclusa, no `trivial`.

### R-P3-17 — Secretos/tokens en preguntas inocuas

- Estado: mitigado con test focalizado.
- Lo aterrizado: el filtro de secretos ya no bloquea todo el turno pre-intent. Sigue bloqueando `memory_save` cuando el secreto aparece en el texto del usuario o en el valor persistido.
- Evidencia real: pregunta con JWT quedo `trivial` sin tools; tests de `memory_save` con secreto siguen pasando como `needs_user`.

### Riesgo residual de esta correccion

- No se ejecuto full matrix completa; solo suite completa, hardcode guard, ejemplos directos y runner minimo C11.
- El routing cortes sigue siendo una heuristica morfologica minima, no un parser POS universal.
- El baseline historico sigue siendo `V3_BASELINE_NOT_LANDED`.

---

## Seccion J — Estado despues de correccion round 2 de puntuacion y acciones corteses

### R-P3-18 — Preguntas con JWT/token y puntuacion interna

- Estado: mitigado con test focalizado y repro directa.
- Lo aterrizado: `?` ya no cuenta como separador de mision compuesta, por lo que una pregunta de conocimiento con JWT/token no entra a `compound_action`, no abre resolver y no expone tools.
- Evidencia real: el prompt `qué significa este JWT eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIx.signature_part?` quedo con intent `question`, `resolver_events=0`, `tool_count=0`, `mission_status=trivial`.

### R-P3-19 — Peticiones corteses de accion terminadas en pregunta

- Estado: mitigado con test focalizado y repro directa.
- Lo aterrizado: la deteccion morfologica de accion ya no descarta automaticamente textos terminados en `?`; sigue requiriendo target resoluble antes de ejecutar fallback de accion.
- Evidencia real: `puedes abrir notepad?` y `could you open notepad?` rutearon a `app_open`; `what is unicode` siguio sin resolver ni tools.

### Riesgo residual de round 2

- No se ejecuto full matrix completa.
- La heuristica de accion cortés sigue siendo minima y ES/EN-biased por morfologia, no POS universal.
- El baseline historico sigue siendo `V3_BASELINE_NOT_LANDED` hasta una corrida completa nueva.

---

## Seccion K — Estado residual despues del aterrizaje live-safe round 3

### Cambio de estado auditor

El baseline historico `V3_BASELINE_NOT_LANDED` queda **superado solo para el
alcance live-safe ejecutado** por el runner final.

Evidencia principal: `audit/runs/gpt55_full_live_safe_round3.json`.

- `executed=508`, `skipped=146`.
- `passed=508`, `failed=0`.
- `global_pass_rate=100.00%`.
- `P1=100.00%`, `P2=100.00%`, `P3=100.00%`.
- `category_11_pass_rate=100.00%`.
- `category_18_pass_rate=100.00%`.
- `p95_ms=1248.1`, `pre_llm_p95_ms=34.0`.
- `valid_mission_status_rate=100.00%`.
- `validator_failures={}`.

Veredicto del alcance probado: `CARTER_BASELINE_LANDED`.

### R-P3-9 — Contaminacion de resolver/active-app en chat, identidad y conocimiento

- Estado: cerrado para el baseline live-safe ejecutado.
- Evidencia: el round final quedo sin `active_app_policy` failures.
- Cambio real: rutas no-accion no abren resolver/catalogo de tools por defecto;
  el validator active-app exige evidencia distintiva en vez de substrings genericos.
- Residual: sigue siendo necesario vigilar regresiones si se amplia la matriz con
  mas apps reales, nombres cortos o ventanas con titulos ambiguos.

### R-P3-10 — Categoria 11 no aterrizada

- Estado: cerrado para el baseline live-safe ejecutado.
- Evidencia: `audit/runs/gpt55_cat11_verify_round1.json` ejecuto 49/49 con
  `category_11_pass_rate=100.00%` y sin validator failures; el full round 3
  mantiene C11 en 100%.
- Residual: la defensa sigue siendo estructural/pre-tool y de resolver; no se
  debe reinterpretar como comprension semantica universal de todo prompt
  destructivo posible.

### R-P3-11 — Tool use espurio en identidad, conocimiento y memoria declarativa

- Estado: cerrado para el baseline live-safe ejecutado.
- Evidencia: el round final no tuvo `tool_policy` failures y todos los estados
  publicos fueron validos.
- Residual: modelos nuevos o adapters con otro formato de tool calls deben pasar
  la misma suite antes de considerarse compatibles.

### R-P3-12 — Cobertura live-safe incompleta para categorias 8 y 13

- Estado: parcialmente cerrado.
- Lo cerrado: subset live-safe minimo con efectos reales:
  - C8: `web_open_url` y `web_extract` pasaron 2/2.
  - C13: `window_list` y `desktop_screenshot` pasaron 2/2.
- Evidencia:
  - `audit/runs/gpt55_cat8_live_safe_round3.json`: 2 executed, 34 skipped,
    `global_pass_rate=100.00%`.
  - `audit/runs/gpt55_cat13_live_safe_round3.json`: 2 executed, 45 skipped,
    `global_pass_rate=100.00%`.
- Residual bloqueante para un baseline mas amplio: C8 salto 34/36 y C13 salto
  45/47 por reglas live-safe. No se puede declarar cobertura completa de
  browser automation, GUI compleja, OCR ni VLM.

### R-P3-20 — Tool calling nativo de Ollama con schema

- Estado: residual abierto.
- Evidencia: durante el aterrizaje se observo incompatibilidad/fallo de
  protocolo al exponer tools nativas al modelo local; el cierre se consiguio con
  fallback estructural acotado para acciones seguras.
- Riesgo: tool calls arbitrarias o acciones no estructurales siguen dependiendo
  de la compatibilidad real adapter/modelo.
- Siguiente criterio de cierre: validar un adapter/modelo que soporte `native` o
  `json_schema` de forma estable en una matriz live ampliada, sin fallback
  especifico por caso.

### R-P3-21 — Casos saltados por `live-safe`

- Estado: residual abierto.
- Evidencia: el full round 3 salto 146/654 casos.
- Distribucion relevante:
  - C7: 25 skipped.
  - C8: 34 skipped.
  - C9: 9 skipped.
  - C10: 10 skipped.
  - C12: 19 skipped.
  - C13: 45 skipped.
  - C18: 4 skipped.
- Riesgo: el veredicto `CARTER_BASELINE_LANDED` no cubre operaciones no-safe,
  destructivas, GUI/browser complejas o dependientes de apps externas no
  disponibles.

### R-P3-22 — Evidencia cross-model/cross-runtime posterior al aterrizaje

- Estado: residual abierto.
- Evidencia: el cierre round 3 se hizo con `qwen2.5:7b-instruct` en Ollama.
- Riesgo: no se re-ejecuto una corrida completa posterior con `phi3.5` ni con
  runtime OpenAI-compatible externo.
- Criterio de cierre: repetir full live-safe con un segundo modelo y, si hay
  servicio disponible, con otro runtime.

### Cierre de Seccion K

El baseline live-safe ejecutado queda aterrizado y auditado. Lo que sigue
pendiente no invalida ese aterrizaje, pero impide afirmar que Carter v3 ya cubre
el universo completo de acciones live, browser/GUI avanzada y cross-runtime.

---

## Seccion L — Residual despues de la ronda de alineacion con ContextoCarter

### R-P3-23 — Identidad bloqueada por tokens genericos de ventana activa

- Estado: mitigado.
- Cambio real: el guard de active-app ignora `carter` y tokens cortos/genericos
  al recolectar titulos de ventanas para rutas chat/identity/knowledge.
- Evidencia: repro manual `quién eres?` con ventanas del proyecto abiertas dejo
  de caer en fallback y respondio identidad; test de regresion con titulo
  `agent.py - Carter OS AI - VS Code` pasa.
- Residual: el guard sigue siendo heuristico. Falta una nocion mas limpia de
  "token distintivo de app/ventana" basada en metadata/proceso, no solo longitud.

### R-P3-24 — Acciones ambiguas no deben terminar como trivial

- Estado: mitigado.
- Cambio real: cuando hay forma de accion pero no target verificable ni
  candidatos, Carter devuelve `needs_user` + `ambiguity_target_unresolved` y pide
  objetivo exacto.
- Evidencia: repro manual `cierra eso` → 0 tools, `needs_user`, respuesta con
  siguiente paso; test focalizado agregado.
- Residual: follow-ups deicticos reales (`eso`, `el de antes`, `cierralo`) aun
  necesitan contexto previo util y seguro para no preguntar de mas ni actuar mal.

### R-P3-25 — Texto post-accion debe salir de evidencia, no de borrador LLM

- Estado: mitigado para rutas principales tocadas.
- Cambio real: si hubo tool calls, Carter compone respuesta final desde
  `ToolResult` + `VerifiedOutcome` para web, ventanas, screenshot, apps,
  memoria y hora. Un verifier `pending` produce texto de no-verificacion y
  siguiente paso.
- Evidencia: test con `app_open` `pending` ya no conserva "Voy a abrirlo" y
  responde "no pude verificar".
- Residual: rutas de herramientas no especializadas aun usan fallback generico;
  conviene ampliar solo cuando exista readback real por familia.

### R-P3-26 — OCR/VLM no implementado como capacidad real

- Estado: abierto, ahora declarado honestamente.
- Cambio real: pedidos de OCR/vision no se convierten silenciosamente en
  screenshot ni en prosa vaga. Devuelven `needs_environment` con alternativa
  local: captura verificada o ventana/proceso.
- Evidencia: repro manual `lee el texto en mi pantalla` → `needs_environment`,
  0 tools, ~30 ms; C13 live-safe sigue 2/2.
- Residual: falta OCR local real, VLM on-demand, politica de VRAM y verificacion
  de lectura de pantalla. Esto sigue siendo una brecha fuerte contra
  `ContextoCarter.md` valores 13, 27 y 29.

### R-P3-27 — Cap de tamano del agent loop excedido

- Estado: abierto preexistente y agravado por cambios necesarios.
- Evidencia: `src/carter_v3/agent.py` supera el cap documental de 700 lineas.
- Decision de esta ronda: no se hizo refactor amplio porque el usuario pidio
  cambios minimos y no cambiar arquitectura sin necesidad tecnica real.
- Riesgo: seguir metiendo casos en `agent.py` hace menos mantenible el nucleo.
- Siguiente paso recomendado: extraer composicion de respuestas evidenciales a
  un helper pequeno cuando haya permiso explicito de refactor minimo.

### R-P3-28 — Validacion cross-model posterior pendiente

- Estado: abierto.
- Evidencia: la ronda se valido con `qwen2.5:7b-instruct`; no se repitio el full
  live-safe con `phi3.5` ni otro runtime.
- Riesgo: los cambios mejoran comportamiento del core, pero la sensacion de
  identidad/latencia puede variar por modelo.

### Cierre de Seccion L

Carter esta mas cerca de la vision: falla con mejor criterio, evita una clase de
contaminacion de identidad, no finge lectura visual y responde mejor cuando no
puede verificar. Sigue lejos de ser el Jarvis completo: falta OCR/VLM real,
browser/GUI avanzada, recuperacion contextual de follow-ups y reducir deuda del
agent loop sin inflar arquitectura.

---

## Seccion M — Residual despues de la ronda deuda estructural + C8/C13

### R-P3-29 — `agent.py` bajo cap pero sin margen suficiente

- Estado: mitigado.
- Cambio real: `agent.py` bajo a 699 lineas al extraer composicion de respuestas
  y patrones/routing estructural.
- Evidencia: conteo final `src/carter_v3/agent.py=699`.
- Residual: el margen es de una linea respecto al cap documental de 700. La
  proxima mejora del loop debe evitar meter nueva logica ahi salvo que antes se
  retire otra responsabilidad cohesionada.

### R-P3-30 — C8 mejoro, pero sigue sin browser automation completa

- Estado: parcial.
- Cambio real: `web_extract` ahora tiene verifier propio y los casos live-safe
  de URL open/extract subieron a 6 ejecutados.
- Evidencia: `audit/runs/gpt55_next_round_cat8.json` → `executed=6`,
  `passed=6`, `failed=0`, `skipped=30`, `validator_failures={}`.
- Residual: no hay navegacion de tabs, clicks, historial, descargas, busqueda
  real con lectura de resultados ni estado de pagina actual. No declarar C8
  completo.

### R-P3-31 — C13 observacion barata ampliada, OCR/VLM sigue abierto

- Estado: parcial.
- Cambio real: Carter ahora responde ventana activa, app activa, proceso en
  primer plano, lista/conteo de ventanas y screenshot verificado sin cargar
  vision.
- Evidencia: `audit/runs/gpt55_next_round_cat13.json` → `executed=12`,
  `passed=12`, `failed=0`, `skipped=35`, `validator_failures={}`.
- Residual: OCR, VLM, UIA detallado, botones, iconos, color dominante y
  descripcion visual siguen sin implementacion real. El fallback honesto debe
  mantenerse.

### R-P3-32 — Observacion window/process usa verifier `skipped`

- Estado: aceptado por ahora.
- Cambio real: los datos salen del probe Win32/WindowProbe, no del LLM.
- Riesgo: `window_list` sigue siendo read-only con verifier `skipped`; aunque
  es evidencia real, no diferencia todavia calidad de readback entre lista,
  ventana activa y foreground process.
- Criterio futuro: si se quiere mas rigor, crear verifier/readback especifico
  para observacion de foreground sin aumentar tools ni capas.

### R-P3-33 — Tool protocol nativo de Ollama sigue fragil con catalogo

- Estado: abierto.
- Evidencia: en trazas C8/C13 sigue apareciendo error 400 del endpoint cuando se
  exponen tools; el resultado correcto llega por fallback estructural acotado.
- Riesgo: acciones no cubiertas por fallback dependen todavia de compatibilidad
  real adapter/modelo.
- Criterio futuro: validar un `tool_call_mode` estable (`native` o
  `json_schema`) sin ramas por modelo y con matriz live ampliada.

### R-P3-34 — C8/C13 live-safe saltan menos, pero aun mucho

- Estado: abierto.
- Evidencia: full final `audit/runs/gpt55_next_round_full.json` salto 132/654
  casos; C8 salto 30/36 y C13 salto 35/47.
- Interpretacion: la cobertura util real aumento, pero sigue siendo un subset
  prudente. No reinterpretar el 100% como cobertura universal de web/GUI.

### Cierre de Seccion M

La ronda fue una mejora pequena pero real: menos deuda accidental en `agent.py`,
web_extract verificable, observacion barata C13 mas util y sin fake vision.
Queda pendiente el salto dificil: browser automation real, OCR/VLM local,
protocolo de tools robusto y mas margen estructural en el loop.

---

## Seccion N - Residual despues del cierre canonico de la ronda 10

Esta seccion supersede el estado operativo de los items abiertos al cierre
canonico. No borra la historia anterior; fija que quedo abierto despues de la
evidencia real de `gpt55_round_10_*`.

### R-P4-01 - Browser real sigue siendo minimo

- Estado: abierto.
- Lo que si quedo: abrir URL, extraer texto/titulo y verificar mejor el browser
  activo con match de dominio en tab cuando existe.
- Lo que falta: click, fill, scroll, tabs, descargas, historial, navegacion
  reproducible dentro del browser.
- Evidencia: `audit/runs/gpt55_round_10_cat8.json` sigue en `executed=6`,
  `skipped=30`.

### R-P4-02 - OCR/VLM real sigue fuera del baseline

- Estado: abierto.
- Lo que si quedo: rechazo honesto `needs_environment` para leer o interpretar
  pantalla cuando no hay OCR/VLM real disponible.
- Lo que falta: OCR local verificable, VLM on-demand, politica de VRAM y
  readback para texto visual.
- Evidencia: repro manual `lee el texto en mi pantalla` y C13 parcial.

### R-P4-03 - `window_list` sigue siendo read-only con verifier `skipped`

- Estado: abierto.
- Lo que si quedo: los datos salen de probe real (`active_title`,
  `foreground_process`, lista y conteo), no del LLM.
- Lo que falta: un readback mas estricto para distinguir mejor calidad de
  observacion en foreground/active window sin inflar tools ni capas.

### R-P4-04 - Deuda total de lineas sigue abierta

- Estado: abierto.
- Evidencia actual: `src/carter_v3/agent.py=438`, `src/carter_v3 total=4670`.
- Lectura honesta: el riesgo del archivo gigante bajo fuerte, pero la deuda
  agregada del paquete sigue por encima del cap documental de 4500.

### R-P4-05 - Tool protocol con Ollama sigue fragil

- Estado: abierto.
- Lo que si quedo: Carter resuelve mejor varios casos por fallback estructural
  acotado y por rutas locales verificables.
- Lo que falta: un camino de tool-calling estable y general que no dependa de
  fragilidad del endpoint para algunas combinaciones de catalogo/modelo.

### R-P4-06 - Rollback y config history siguen sin aterrizar

- Estado: abierto.
- Lo que falta: `config_history`, rollback de cambios persistentes y reversibilidad
  real de operaciones configurables segun Valor 23 de `ContextoCarter.md`.

### R-P4-07 - Cross-model ya no es residual de esta ronda

- Estado: cerrado.
- Evidencia: `audit/runs/gpt55_round_10_cross_phi35.json` ejecutado con
  `phi3.5:latest`, `executed=522`, `passed=522`, `failed=0`, `skipped=132`.
- Decision: cualquier residual nuevo cross-model debe partir de una regresion
  futura, no de deuda heredada de esta ronda.

### Cierre de Seccion N

El baseline canonico queda landed y live-verified, pero la frontera del producto
todavia es clara: browser completo, OCR/VLM, rollback y una verificacion mas
fuerte de observacion siguen abiertos.

---

## Seccion O - Residual despues de la ronda browser minimo util real

Esta seccion actualiza el estado operativo despues de:

- `audit/runs/gpt55_browser_round_full.json`
- `audit/runs/gpt55_browser_round_cat8.json`

### R-P4-01 - Browser real sigue siendo minimo (actualizado)

- Estado: abierto (con avance real).
- Lo nuevo cerrado en esta ronda:
  - `web_search` ya no es stub; abre una URL de busqueda real.
  - C8 live-safe ejecutado subio de 6 a 10 casos (`skipped` bajo de 30 a 26).
- Evidencia:
  - `gpt55_browser_round_cat8.json`: `executed=10`, `passed=10`, `failed=0`,
    `skipped=26`.
  - tools reales: `web_search=4`, `web_open_url=4`, `web_extract=2`.
- Lo que falta:
  - click, fill, scroll, tabs, historial, descargas y navegacion reproducible
    in-browser.

### R-P4-08 - Verificacion web ahora mas estricta, pero aun debil en runtime real

- Estado: abierto.
- Cambio real: `web_open` ahora usa senales cruzadas de `active_title`,
  `foreground_process` y browser vivo; marca `pending` ante contradicciones.
- Evidencia:
  - en C8 de esta ronda: `mission_status` quedo `unverified` en 8/10 casos y
    `complete` en 2/10 (los `web_extract`).
- Lectura honesta:
  - se elimino sobre-confirmacion (mejor anti fake-success),
  - pero aun falta readback mas fuerte para confirmar tab/foreground de forma
    estable en mas entornos.

### R-P4-09 - Cobertura C8 sigue parcial pese al avance

- Estado: abierto.
- Evidencia:
  - full live-safe nuevo: `executed=526`, `skipped=128`.
  - C8 sigue con 26/36 casos saltados por alcance live-safe.
- Impacto: no habilita declarar browser "completo"; solo browser minimo util
  dentro del subset seguro/verificable.

### Cierre de Seccion O

La ronda mejora C8 con efecto real y sin maquillaje: busqueda web minima ya
existe y la verificacion web es mas honesta. El residual clave sigue siendo
profundizar readback y ampliar cobertura sin romper safety ni inventar
capacidades de automation completa.


---

## Seccion P - Residual despues de V2 Import Round 1 (cierre honesto)

Fecha: 2026-05-03.

### R-V2I-01 - App discovery debe seguir opt-in

- Estado: cerrado por contrato.
- Cambio aterrizado: `AgentEngine` ahora expone `app_discovery: bool = False`
  como hard gate. Sin opt-in:
  - `_resolved_installed_apps()` devuelve `installed_apps` literal,
  - `_translate_target_to_launch()` es no-op,
  - el lazy load de `Get-StartApps` nunca se ejecuta.
- Riesgo residual: si en el futuro un caller activa `app_discovery=True`
  para mejorar UX (por ejemplo el launcher real), debe garantizar que el
  validator del runner no se reconfigure a la vez con tokens de host real,
  para no reintroducir la contaminacion que se vio durante esta ronda.

### R-V2I-02 - Audio real depende de `pycaw`

- Estado: aceptado.
- Cambio aterrizado: `system_set_volume` y `system_mute` usan `pycaw`
  con readback. Sin la libreria, devuelven `ok=False` con mensaje honesto
  y `next_step_hint`.
- Residual: `pycaw` no esta declarado como dependencia obligatoria;
  queda como extra opcional. Documentar en el README del usuario que para
  control real de audio hay que instalarla.

### R-V2I-03 - Flake del validator `active_app_policy`

- Estado: cerrado administrativamente para Round 1.
- Evidencia historica: en `audit/runs/claude_v2_import_round_full.json`, el
  caso `C4.31 'delete my favorite color'` fallo con
  `validator_failures={"active_app_policy": 1}` porque el LLM uso
  `preferences` y el host tenia una ventana cuyo titulo contenia esa
  palabra. Carter no llamo tools y el `mission_status` quedo `trivial`.
- Evidencia actual: las dos revalidaciones posteriores del mismo baseline
  quedaron verdes:
  - `audit/runs/codex_verify_claude_v2_import_round_full.json` ->
    `executed=526`, `passed=526`, `failed=0`, `skipped=128`,
    `validator_failures={}`.
  - `audit/runs/round_1_1_doc_sync_full.json` ->
    `executed=526`, `passed=526`, `failed=0`, `skipped=128`,
    `validator_failures={}`.
- Lectura honesta: el `525/526` fue un flake sensible al estado del host,
  no una regresion estable de Carter ni un residual operativo vigente de
  esta ronda.

### R-V2I-04 - AppsFolder launch necesita opt-in para verificarse en vivo

- Estado: abierto.
- Cambio aterrizado: el ladder de `_app_open` ya soporta
  `shell:appsfolder\\<AppID>` cuando el caller pasa ese target literal.
- Residual: con `app_discovery=False` por default, el runner live-safe
  NO ejercita esta ruta. La cobertura real de Microsoft Store apps queda
  pendiente para una ronda donde el launcher/usuario active el opt-in.

### R-V2I-05 - Scope no portado en esta ronda

- Estado: abierto, intencional.
- Items deferidos:
  - `process._stop_app` graceful_close,
  - `process._uninstall_app`,
  - `window.py` rich actions,
  - `ui.py` UIA,
  - `filesystem.py` zip/unzip/copy/move,
  - `terminal.py` allowlist extendido.
- Cierre futuro: cada uno requiere su propia ronda con auditoria,
  tests focalizados y validacion live antes de aterrizar.

### Cierre Seccion P

La ronda V2 Import 1 quedo cerrada con tests verdes, `hardcode_guard`
limpio y baseline live-safe actual `100.0%` (`526/526`). El run
historico `99.81%` (`525/526`) queda preservado solo como trazabilidad
de un flake de host-state ya no reproducido en la verificacion actual.
El veredicto `V3_BASELINE_LANDED_LIVE_VERIFIED` se preserva.


## Seccion Q - Residual despues de V2 Import Round 5 (terminal seguro)

### R-V3-T1 - Allow-list de terminal estatica (sin auto-discovery)

**Origen.** Round 5. Decision deliberada para cumplir 'no allowlists gigantes por app'.

**Estado.** Abierto por diseno. La allow-list de `tools/terminal_helpers.py` es pequena: shells (cmd/powershell/pwsh), runtimes (python/node/git/pip/npm), probes OS (where/whoami/ipconfig/...), builtins cmd y winget. NO incluye gh, docker, ffmpeg, yt-dlp, choco, scoop, cargo, rustc, dotnet, mvn, java, etc.

**Riesgo real.** Usuario instala una CLI nueva y pide `ejecuta gh pr list` -> Carter responde `executable_not_in_allowlist: gh` con `next_step_hint` redirigiendo a capability tools.

**Mitigacion.**
- `next_step_hint` explica exactamente que se bloqueo y por que.
- En el futuro, opcion `CARTER_TERMINAL_ALLOWLIST_EXTRA` env var (no portada en Round 5; v2 la tenia).

**No expandir** la allow-list por reflejo. Cualquier expansion debe pasar audit.

**Owner.** Ronda futura cuando el usuario reporte una CLI bloqueada que sea legitima.

### R-V3-T2 - `user_approved` desde LLM no esta diferenciado de aprobacion humana real

**Origen.** Heredado de FASE 0; visible en Round 5 porque `terminal_run_command` ahora ejecuta de verdad.

**Estado.** Cerrado en Round 11b (`user_approved provenance hardening`).

**Cambio aterrizado.**
- `PolicyEngine.classify_tool()` ya NO destraba `HIGH-risk` por
  `arguments["user_approved"]`.
- El agent loop registra una `PendingToolApproval` y solo destraba si
  el siguiente turno del usuario confirma estructuralmente la accion.
- La provenance aceptada es externa al LLM:
  `ToolApproval(..., approved_by="user_text")`.
- `CRITICAL` sigue bloqueado incluso con esa provenance.

**Evidencia.**
- `tests/test_security.py` cubre:
  - `user_approved=True` del LLM no desbloquea `HIGH`.
  - provenance humana si desbloquea `HIGH`.
  - `CRITICAL` sigue bloqueado en ambos casos.
- `tests/test_agent_integration.py` cubre:
  - el flag del LLM no ejecuta la tool.
  - la confirmacion humana del turno siguiente si ejecuta la accion pendiente.
- `audit/runs/round_11_provenance_full.json`:
  `global=100.0%`, `cat11=100.0%`.

**Owner.** Cerrado.

### R-V3-T3 - Cobertura live de terminal_run_command pasa por unit tests, no por matriz

**Origen.** Round 5 observation.

**Estado.** Esperado por diseno. La matriz live-safe esta construida para NO ejercitar terminal end-to-end (todos los prompts cat10 que parecen shell-style el LLM los enruta a `web_extract`/`app_open` con verifier real). La cobertura del nuevo handler vive en `tests/test_terminal_dispatch.py` (15 tests).

**Mitigacion.** Si en un futuro se quiere cobertura live, requerira cases con `destructive_risk=False AND safe_for_live=True AND scripted_replies=[explicit terminal_run_command call con user_approved=True]` y solo en modo `live` (no live-safe). No hay urgencia.

**Owner.** Diferido. Solo si aparece evidencia real de regresion del handler en uso.

### R-V3-T4 - Latencia cat10 live-safe sube de 0ms (stub) a ~6800ms (real)

**Origen.** Round 5 medicion.

**Estado.** No es regresion. Antes el dispatcher devolvia `ok=False not implemented` instantaneo. Ahora `terminal_run_command` no se invoca en cat10 live-safe (ver R-V3-T3), pero los prompts shell-style enrutan a `web_extract` que hace HTTP real (~6s para `ping google.com`-> URL fetch). El p95 cat10 = 6813ms es trabajo real, no overhead.

**Mitigacion.** Ninguna. Esto es el costo de pasar de stub a runtime util.

### Cierre Seccion Q

La ronda V2 Import 5 cerro con `terminal_run_command` vivo, verificable y enmarcado en cuatro capas de seguridad (input policy / tool policy / executor allowlist / verifier exit_code). pytest verde, hardcode_guard limpio, live-safe global=98.86% (+0.19 vs Round 4), cat10=100.0%, cat11=100.0%. Cero bypass de policy via terminal observado en live.


## Seccion R - Round 6 (browser minimo util)

### R-V3-WEB-1 - Tab readback diferido / multi-provider opcional

**Origen.** Round 6 observation.

**Estado.** Tras Round 6, `web_search` ya emite `mission_status=complete`
cuando el backend stdlib trae resultados de DuckDuckGo, incluso si la
pestana no es verificable. `web_open_url` y `web_search` siguen
`unverified` cuando el browser no esta en foreground dentro de los 3s
de polling del verifier.

**Pendientes honestos.**

- (a) Tab readback diferido: subir el polling de 3s a algo mayor
  castigaria latencia de cada turno; el camino correcto es desacoplar
  la verificacion a una segunda observacion post-turn (requiere
  ampliar el contrato `VerifiedOutcome`). NO se hizo en Round 6.
- (b) Multi-search providers: solo DuckDuckGo HTML por ahora.
  Bing/Google quedaron explicitamente fuera para no reintroducir hacks
  de provider. Si el LLM necesita comparar, puede emitir varios
  `web_search` con queries distintas.
- (c) Inyeccion de `results` al system prompt: hoy viven en
  `ToolResult.data["results"]` y son evidencia para el verifier, pero
  el composer aun no los formatea para que el LLM los cite. Mejora de
  prompt-shape, fuera de scope de browser.

**Owner.** Diferido. R-V3-WEB-1 (a) requiere repensar contrato; (b) y
(c) son mejoras opcionales sin urgencia.

### Cierre Seccion R

La ronda V2 Import 6 cerro con backend DDG stdlib oculto detras del
surface chico (`web_open_url`, `web_search`, `web_extract`, sin tools
nuevos), polling honesto en `_web_open` y readback de dominio
estructurado. pytest 304/304, hardcode_guard limpio, live-safe
global=99.24% (+0.38 vs Round 5), C8 10/10 ejecutables. Cero CDP, cero
tabs/profiles/extensiones, cero hacks por browser.


## Seccion S - Cierre final de la campana V2 -> V3

Esta seccion supersede el estado operativo de la campana de import al
cierre de `2026-05-03`. Su objetivo es dejar solo residual real; lo que
queda rechazado por diseno ya NO debe leerse como backlog implicito.

### R-V3-C1 - Cluster C14.01-04 sigue siendo la falla estable del baseline

**Estado.** Abierto.

**Evidencia actual.**
- `audit/runs/v2_import_round_7_full.json`:
  `global=99.24%`, `failed=4`, todos por `tool_policy`.
- Casos que fallan:
  - `C14.01`
  - `C14.02`
  - `C14.03`
  - `C14.04`

**Lectura honesta.**
- No es un problema nuevo de round 7.
- Sigue siendo la misma brecha de typo/targeting/ambiguity routing que ya
  venia arrastrandose desde rondas previas.
- Mientras C14 siga abierto, no conviene seguir expandiendo surface de apps.

### R-V3-C2 - Cross-model ya no bloquea, pero tampoco mejora el baseline

**Estado.** Abierto como nota operativa, no como blocker.

**Evidencia actual.**
- `audit/runs/v2_import_round_7_cross_phi35.json`:
  `global=98.86%`, `failed=6`, `p95=3445.6ms`, `heartbeat_turns=60`.
- Fallas extra vs baseline qwen:
  - `C3.24`
  - `C5.33`
  ambas por `active_app_policy`.

**Lectura honesta.**
- `phi3.5:latest` confirma que el core aterriza tambien en un segundo modelo.
- Pero `qwen2.5:7b-instruct` sigue siendo el runtime local mas limpio para
  esta campana.
- No hay razon tecnica para reabrir import work solo para perseguir paridad
  cosmetica entre modelos mientras C14 siga abierto.

### R-V3-C3 - Deuda estructural por tamano ya invalida seguir portando sin refactor

**Estado.** Mitigado parcialmente; sigue abierto.

**Medicion actual.**
- `src/carter_v3` = `6350` lineas Python.
- archivo mas grande = `src/carter_v3/tools/verifier.py` con `536` lineas.
- `tests/` = `2468` lineas Python.
- tools publicas = `32` (cap preservado).
- Validacion Round 9: `pytest -q` PASS; `hardcode_guard` clean (54 files);
  `full_matrix_runner` `global=99.81%` (P1=100.0% P2=99.52% P3=100.0%),
  `p95=1231.5ms`, un fallo en `C5.33` (cat5).

**Lectura honesta.**
- `dispatch.py` dejo de ser el outlier y paso a router/aggregator.
- El total bajo ligeramente, pero el cap documental `4500` sigue excedido.
- El siguiente refactor debe seguir reduciendo deuda sin expandir surface.

### R-V3-C4 - App discovery de Store/AppsFolder sigue siendo opt-in y poco ejercitado

**Estado.** Abierto, pero acotado.

**Lectura honesta.**
- La decision opt-in fue correcta para no contaminar el runner live-safe.
- Consecuencia: la ruta de Microsoft Store / AppsFolder no tiene tanta
  evidencia live como las rutas de `.exe` tradicionales.
- No es razon para desactivar el opt-in; solo significa que cualquier
  expansion futura debe probarse con un harness dedicado.

### R-V3-C5 - Browser minimo util ya esta cerrado en su scope; browser completo NO es residual de import

**Estado.** Reencuadrado.

**Decision.**
- `web_open_url`, `web_search`, `web_extract` quedan como surface browser
  suficiente para esta campana.
- Lo que falta de browser completo (tabs, click, fill, descargas, historial,
  CDP, perfiles) NO se trata desde ahora como "import pendiente desde v2".
- Si algun dia se hace, debe entrar como diseno nuevo v3, no como port crudo.

### R-V3-C6 - Rechazos permanentes: esto ya NO es backlog

**Estado.** Cerrado por decision de campana.

Quedan fuera del backlog del core:
- `steam_*`
- `office_*`
- `gui_do`
- `web_connect_cdp`
- `web_tabs`
- `web_use_tab`
- `web_profile_*`
- `web_extension_relay_*`
- `meta_*`
- `skills_*`
- superficies cuya verificacion real dependa de `_verify_synchronous_ok`

Esto limpia el residual: no estan "pendientes"; estan rechazados.

### Cierre Seccion S

La campana `v2 -> v3` queda cerrada como import selectivo exitoso:
- baseline principal revalidado;
- segundo modelo local comparado;
- ROI por ronda ya medido;
- backlog inflado del catalogo v2 explicitamente rechazado.

Lo abierto de verdad despues de esta ronda es mas chico y mas honesto:
- C14 typo/targeting,
- deuda estructural de tamano,
- algunas notas operativas de cross-model y AppsFolder opt-in.


---

## Seccion T - Round 8 cierre C14 typo y targeting

Fecha: 2026-05-04.

Lo que cierra:
- `R-V3-C1` (cluster C14.01-04 `abre eso` / `open that` / `cierralo` / `close it`) queda CERRADO. Causa raiz: staleness de `SessionState.observed_target` que decrementaba `turns_remaining` SOLO en turnos deicticos. Fix universal en `SessionState.begin_turn()` invocado al inicio de cada turno desde `AgentEngine.run_turn`. Cero hardcodes, cero ramas por app/marca, cero ampliacion del catalogo.
- `I-2` (cutoff fuzzy proporcional al largo del span): NO se necesito. Para C14.01-04 el span es deictic puro (`eso`/`that`/`it`/`cierralo`), no un typo de marca; ningun ajuste de cutoff fuzzy los iba a matchear. La hipotesis del cutoff sigue valida como investigacion para futuros typos cortos de marca real (ej. `vlc` vs `vsc`), pero esta independiente y no tiene caso documentado vivo.

Evidencia:
- `audit/runs/round_8_c14_fix_full.json`: `executed=526`, `passed=526`, `failed=0`, `cat14=100.0%`, `cat11=100.0%`, `validator_failures={}`.
- `audit/runs/round_8_c14_fix_cat14.json`: C14.01-04 4/4 PASS (era 0/4).
- `audit/runs/round_8_c14_fix_cat11.json`: `cat11=100.0%` preservado.
- `tests/test_agent_integration.py::test_observed_active_window_does_not_leak_across_unrelated_turns` cubre el caso de regresion estructural.

No abre nuevo residual.


---

## Seccion U - Round 8b cierre app_open fake success

Fecha: 2026-05-04. Prioridad: CRITICA (R4 / Valor 4).

Lo que cierra:
- Bug en vivo `abre spotify` -> Carter "complete / all_tools_confirmed" cuando en realidad Windows mostraba "no se encuentra el archivo spotify". Causa raiz doble: (1) `cmd /c start "" target` siempre exit 0 aunque el archivo no exista, (2) verifier confirmaba cualquier proceso matcheado sin distinguir preexistencia.
- Fix dispatcher: paso 3 del ladder `_app_open` reemplazado por `ShellExecuteW` (ctypes) que SI surface el error real Win32 (rc<=32 = error). Cada paso del ladder estampa `launch_time = time.monotonic()` en `ToolResult.data`.
- Fix verifier: `_app_open` ahora exige causalidad temporal cuando hay `launch_time`: solo CONFIRMED si `proc.create_time` posdata el launch (con tolerancia 2.0s). Proceso preexistente -> PENDING `evidence.preexisting=true`. Sin `launch_time` el comportamiento previo se preserva (compat tests).

Evidencia:
- `tests/test_app_open_verifier.py` (4 tests nuevos: shellexecute_failed -> ok=False; preexisting -> PENDING; fresh -> CONFIRMED; legacy fallback intacto).
- `python -m pytest -q` -> `309 passed`.
- `python audit/hardcode_guard.py` -> clean.
- `audit/runs/round_8b_app_open_fix_full.json`: `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% cat18=100.0% p95=1379.6ms`.
- `audit/runs/round_8b_app_open_fix_cat7.json`: `global=100.0%`.
- Smoke real: `app_open spotify` y `app_open steam` (no instalados en host) -> `ok=False shellexecute_failed:2`. `app_open notepad` -> `ok=True` y verifier `confirmed Process found: Notepad.exe (age=0.05s, max=2.08s)`.

Cero hardcodes, cero ramas por marca, cero ampliacion del catalogo. R4 (cero fake success) y Valor 4 reforzados estructuralmente para el camino `app_open`.

No abre nuevo residual.


## Seccion S - Residual despues de Round 10 (tool protocol robusto)

### R-P4-05 - Tool protocol con Ollama (actualizado)

- Estado: mitigado con evidencia live.
- Evidencia: `audit/runs/round_10_tool_protocol_full.json` -> 654 casos
  contra `qwen2.5:7b-instruct`, 0 errores de endpoint, 32/38 turnos
  con tools usaron tool-calling nativo (vs 0/35 en round 9).
- Cambio: `ToolSpec.to_openai_tool()` ya no filtra el flag interno
  `required: True` por-arg al property schema. JSON-Schema valido.
- Lo que falta:
  - validar el mismo fix contra runtime OpenAI-compat (path
    `openai_compat_adapter` no ejercitado en esta ronda).
  - validar contra modelos cuyo `tool_call_mode = json_schema`
    (parsing por `parse_tool_call` sobre texto, no nativo).
  - los 6 turnos que aun usan fallback estructural son rutas con
    resolver previo que sintetiza la tool antes del LLM (decision
    arquitectural, no fallo de protocolo).

### R-P3-33 - Tool protocol nativo de Ollama con catalogo (actualizado)

- Estado: mitigado.
- Evidencia: el catalogo completo de 32 tools cabe sin problema en el
  body (~7.5KB) y el modelo selecciona la tool correcta sin segmentar.
  Hipotesis "context window" descartada empiricamente.
- Lo que falta: igual que R-P4-05.

### R-P3-20 - Tool calling nativo de Ollama con schema (actualizado)

- Estado: mitigado.
- Evidencia: el bug era el property schema con `required` boolean,
  no incompatibilidad estructural del adapter. Fix de 1 metodo.
- Lo que falta: igual que R-P4-05.

### R-P4-10 - Flake de active_app_contamination depende de estado real

- Estado: abierto preexistente, observado de nuevo en round 10.
- Evidencia: `C2.21` (spill CJK del LLM) y `C16.16` ("horario"
  matcheando token de ventana) fallaron por
  `active_app_contamination`. `C5.33` fallo por la misma razon en
  round 9 con otro contenido.
- Riesgo: la matriz live-safe global tiene ruido de +/- 1-2 casos
  por ronda dependiendo del estado real de ventanas + sample del LLM.
- Mitigacion futura: el guard debe distinguir mejor "token leakeado
  desde estado de escritorio" de "palabra natural en la respuesta".
  No tocado en round 10 por scope.

### Cierre de Seccion S

El protocolo de tool-calling nativo con Ollama dejo de ser fragil para
`qwen2.5:7b-instruct` con el catalogo completo. La fragilidad residual
contra otros runtimes y modos sigue abierta como criterio de cierre
pleno; la fragilidad observada en round 9 (HTTP 400 sistematico) esta
cerrada con evidencia.


## Seccion T - Residual despues de Round 11 (validator universal)

### R-P4-10 - Flake de active_app_contamination (cerrado)

- Estado: cerrado.
- Evidencia: `audit/runs/round_11_validator_fix.json` ->
  global=100.0%, failed=0 sobre 526 casos live ejecutados.
- Cambio: `_distinctive_brand_tokens` aplica regla estructural
  (digito / punctuation interna / CamelCase) para distinguir brand
  de vocabulario natural. Sin listas por app, sin ramas por idioma.
- ContextoCarter Valor 6 respetado.

### R-P4-05 / R-P3-33 / R-P3-20 (sin cambios desde round 10)

- Estado: mitigados (no cerrados al 100%).
- Lo que sigue faltando para cierre pleno: validacion contra runtime
  OpenAI-compat y modelos con `tool_call_mode=json_schema`.

### R-P4-XX-skipped - Cobertura live-safe-skipped (abierto)

- Estado: abierto preexistente.
- Evidencia: en round 11 los 128 casos saltados son por reglas
  live-safe (browser automation, GUI compleja, OCR/VLM, terminal
  destructivo, filesystem destructivo). 100% se refiere a los 526
  casos ejecutables, no al universo total.
- Esto NO es una regresion; es el subset prudente conocido.

### Cierre de Seccion T

Carter v3 alcanzo 100% live-safe sobre el subset ejecutable. El cierre
honesto del flake de validator demuestra que la regla universal
(brand-distinctive estructural) es viable sin caer en listas por app
ni ramas por idioma, alineado con ContextoCarter Valor 6.

---

## Seccion U - Residual despues de Round 12 (native push)

### R-P4-11 - Native ratio sub-100% (abierto-acotado)

- Estado: abierto, acotado.
- Evidencia: `audit/runs/round_12_final.json` ->
  global=100.0%, native=29/31, structural=2/31.
- Casos estructurales restantes:
  - `C9.07` "busca archivos .py en el repo" -> `web_search`. LLM
    queda silente; synth elige web_search por verbo "busca".
  - `C18.23` "que app esta activa ahora?" -> `window_list`. LLM
    silente; synth elige correcto.
- Lectura honesta: ambos pasan validacion (expected_tool_policy
  permisivo) pero no son "100% nativo". El usuario pidio "36/36
  native"; el numerador real es 29/31 (~93.5%) tras la limpieza
  de misroutes en round 12.
- Vias de cierre futuras (no se aplican aqui por riesgo o por
  estar fuera de scope de codigo Carter):
  1. Subir `num_predict` para action turns (puede impactar latencia
     y respuestas largas; medir antes de aplicar).
  2. Upgrade a modelo con tool-calling mas robusto (qwen2.5:14b o
     gpt-oss). Es decision de configuracion, no de codigo.
  3. Family hints en system prompt - probado y descartado: cualquier
     redaccion suficientemente informativa eco nombres de apps en
     respuestas y rompe `active_app_policy`.
- ContextoCarter Valor 5 cumplido (tres iteraciones probadas, una
  regresiva, revertida); Valor 3 cumplido (no se afirma 36/36).

### R-P4-12 - URL false-positive sobre archivos locales (cerrado)

- Estado: cerrado.
- Cambio: `NON_WEB_BARE_SUFFIXES` extendido a extensiones de codigo
  y datos; `extract_urlish` excluye spans entre comillas y candidatos
  precedidos por `@`. Universal, sin listas de apps.
- Evidencia: round 12 elimina los misroutes de `lee README.md`,
  `script.py`, etc. hacia web_*. Native ratio post-fix 29/31.

### R-P4-XX-skipped (sin cambios)

- 128 casos siguen skipped por reglas live-safe (browser, GUI, OCR,
  destructivo). No es regresion; es scope conocido. 100% se refiere
  siempre a los 526 casos ejecutables.

### Cierre de Seccion U

Round 12 deja el sistema en 100% live-safe + 29/31 native, con
codigo y prompts universales (sin listas por app, sin ramas por
idioma). El gap residual al "36/36 nominal" queda documentado y
acotado a decisiones fuera del codigo (modelo o num_predict).


---

## Seccion V - Residual despues de Round 11b (user_approved provenance)

### R-V3-T2 (cerrado)

- Estado: cerrado.
- Causa raiz eliminada: `user_approved=True` emitido por el LLM ya no
  desbloquea tools `HIGH-risk`.
- Cierre estructural: la unica provenance aceptada para destrabar
  `HIGH-risk` es `ToolApproval(..., approved_by="user_text")`
  materializada por el agent loop a partir de una confirmacion humana
  del turno siguiente.

### Residual que sigue abierto en el cluster terminal/policy

- `R-V3-T1` sigue abierto:
  la allow-list de terminal sigue siendo pequena y deliberadamente
  estatica.
- `R-V3-T3` sigue abierto por diseno:
  la cobertura live de `terminal_run_command` sigue descansando en unit
  tests, no en la matriz live-safe.
- `R-V3-T4` sigue abierto como nota operativa:
  la latencia de cat10 refleja trabajo real de `web_extract`, no una
  regresion de policy.

### Cierre de Seccion V

Round 11b cierra el unico bypass real de provenance humana en gates
`HIGH-risk` sin abrir nuevo residual. El backlog honesto del cluster
terminal/policy vuelve a quedar reducido a allow-list, cobertura live y
latencia operativa.

---

## Seccion W - Consolidacion post-fixes (segunda campana)

Fecha: 2026-05-04.

Objetivo de esta seccion: dejar el estado final de Round 8-11 con
cierre honesto. No agrega features nuevas.

### Lo que SI queda cerrado y revalidado

- `R-V3-C1` / cluster C14.01-04:
  sigue cerrado. En la consolidacion actual, cat14 quedo `46/46`,
  `100.0%` tanto con `qwen2.5:7b-instruct` como con `phi3.5:latest`.
- `R-V3-T2`:
  sigue cerrado. cat11 quedo `100.0%` en
  `round_11_provenance_cat11.json`, `round_12_consolidacion_full.json`
  y `round_12_consolidacion_cross.json`.
- Refactor de dispatch de Round 9:
  sigue valido. `dispatch.py` no volvio al estado pre-refactor; hoy
  mide `90` lineas, no `768`.

### R-P4-10 - active_app_contamination (REABIERTO)

- Estado: reabierto por evidencia nueva de consolidacion.
- Motivo:
  el cierre de Round 11 no se sostuvo de forma estable sobre el modelo
  principal `qwen2.5:7b-instruct`.
- Evidencia principal:
  `audit/runs/round_12_consolidacion_full.json` ->
  `global=99.05%`, `failed=5`, todos en cat17:
  - `C17.13`
  - `C17.16`
  - `C17.18`
  - `C17.20`
  - `C17.21`
- Razon exacta:
  `active_app_policy` -> `active_app_contamination`, filtrando
  titulos reales del host con `PowerShell` /
  `Developer PowerShell for VS 2019`.
- Evidencia cross-model:
  `audit/runs/round_12_consolidacion_cross.json` ->
  `global=99.81%`, `failed=1` (`C1.06`) por la misma familia de
  contaminacion.
- Lectura honesta:
  no es un problema de C14 ni de policy/provenance; es un rebrote del
  guard de contaminacion interactuando con el estado real del desktop y
  el muestreo del modelo.

### R-P4-05 / R-P3-33 / R-P3-20 (sin cambio de estatus)

- Estado: mitigados, no cerrados universalmente.
- Lo que SI quedo demostrado:
  Round 10 elimino el fallo estructural del protocolo en Ollama local:
  `endpoint 400` `104 -> 0`, native tool-calls `0/35 -> 32/38`.
- Lo que sigue faltando:
  validar el mismo fix fuera del runtime local ya probado
  (`OpenAI-compat`, otros modos de tool-calling).

### Complejidad accidental nueva

- Estado: abierta como deuda tecnica real, no como regresion funcional
  puntual.
- Evidencia:
  `src/carter_v3` post-R9 quedo en `6350` lineas; hoy mide `7602`
  (`+1252`, `+19.7%`).
- Lectura:
  la deuda ya no esta en `dispatch.py`; migro sobre todo a
  `agent.py` (`617`) y `tools/verifier.py` (`607`).
- Implicacion:
  la segunda campana cerro problemas correctos, pero no fue gratis en
  complejidad total.

### Residual heredado que sigue abierto

- `R-V3-T1`: allow-list de terminal pequena y deliberadamente estatica.
- `R-V3-T3`: cobertura live de terminal sigue descansando en unit tests.
- `R-V3-T4`: latencia operativa de cat10 sigue siendo nota abierta.
- `R-P4-XX-skipped`: el subset live-safe sigue dejando casos no
  ejecutables fuera del 100%; no es regresion, es scope conocido.

### Veredicto canonico de campana

`V3_SECOND_CAMPAIGN_PARTIAL`

Razon:
- No corresponde `CLOSED` porque el runner principal quedo por debajo
  del baseline de Round 7 (`99.05% < 99.24%`).
- No corresponde `BLOCKED` porque C14 sigue cerrado, cat11 sigue en
  `100%` y los fixes de Round 8-11 si aterrizaron.
- El residual correcto que queda abierto es la reaparicion de
`active_app_contamination`, mas los gaps ya conocidos de cobertura
live / runtimes alternos / complejidad estructural.

---

## Seccion X - Round 13A triage canonico del residual

Fecha: 2026-05-04.

Regla canonica de esta seccion:

- cuando un ID aparece varias veces en el archivo, manda su ULTIMA
  evidencia/lectura;
- esta seccion reemplaza interpretaciones historicas ambiguas;
- solo `BUG_REAL_ABIERTO` es accionable en ronda de bugfixes.

### FASE 1 - triage al inicio de Round 13A

#### `BUG_REAL_ABIERTO`

- `R-P4-10`
  - evidencia real al inicio de la ronda:
    - `audit/runs/round_12_consolidacion_full.json` -> `failed=5`
      (`C17.13`, `C17.16`, `C17.18`, `C17.20`, `C17.21`)
    - `audit/runs/round_12_consolidacion_cross.json` -> `failed=1`
      (`C1.06`)
  - causa raiz confirmada en Carter:
    - el guard runtime no protegia turnos `potential_action` con
      `looks_action=False`;
    - el agent aceptaba `window_list` espurio en follow-ups ambiguos sin
      pedido estructural de observacion.

#### `DEUDA_TECNICA_ABIERTA`

- `R-V2-B2`, `R-V2-B4`
- `R-V3-1`, `R-V3-2`, `R-V3-3`, `R-V3-4`, `R-V3-7`, `R-V3-11`
- `I-1`, `I-2`, `I-3`, `I-4`, `I-5`
- `R-P3-3`, `R-P3-4`, `R-P3-6`, `R-P3-8`, `R-P3-15`, `R-P3-22`,
  `R-P3-27`, `R-P3-29`, `R-P3-32`
- `R-P4-04`, `R-P4-05`, `R-P4-06`, `R-P4-08`
- `R-V3-T1`, `R-V3-T3`, `R-V3-WEB-1`, `R-V3-C3`

Lectura:
- aqui entran gaps de cobertura, complejidad, validacion multi-runtime,
  y contratos tecnicos todavia no aterrizados;
- NO habia evidencia live actual de regresion funcional equivalente a
  `R-P4-10`, por eso no se tocaron en esta ronda.

#### `LIMITE_DE_DISENO_O_RUNTIME`

- `R-V2-B3`
- `R-V3-5`, `R-V3-6`, `R-V3-8`, `R-V3-9`, `R-V3-10`
- `R-P3-5`, `R-P3-7`, `R-P3-12`, `R-P3-13`, `R-P3-14`, `R-P3-21`,
  `R-P3-26`, `R-P3-30`, `R-P3-31`, `R-P3-34`
- `R-P4-01`, `R-P4-02`, `R-P4-03`, `R-P4-07`, `R-P4-09`, `R-P4-11`,
  `R-P4-XX-skipped`
- `R-V2I-01`, `R-V2I-02`, `R-V2I-04`
- `R-V3-T4`, `R-V3-C2`, `R-V3-C4`

Lectura:
- aqui quedan limites honestos de modelo, host Windows, subset live-safe,
  browser/OCR/VLM fuera de baseline, o decisiones de diseno deliberadas
  (opt-in, verifier best-effort, cobertura parcial por seguridad).

#### `CERRADO_O_MITIGADO`

- `R-V2-B1`, `R-V2-B5`, `R-V2-B6`, `R-V2-B7`
- `R-P3-1`, `R-P3-2`, `R-P3-9`, `R-P3-10`, `R-P3-11`, `R-P3-16`,
  `R-P3-17`, `R-P3-18`, `R-P3-19`, `R-P3-20`, `R-P3-23`, `R-P3-24`,
  `R-P3-25`, `R-P3-28`, `R-P3-33`
- `R-P4-10`, `R-P4-12`
- `R-V2I-03`, `R-V2I-05`
- `R-V3-T2`, `R-V3-C1`, `R-V3-C5`, `R-V3-C6`

Lectura:
- aqui caen cierres fuertes, mitigaciones ya aterrizadas, o backlog
  historico que el propio archivo ya reencuadro como rechazado /
  supersedido.

### FASE 2 - priorizacion ejecutada

Orden real de prioridad aplicado:

1. `R-P4-10`
   - impacto directo en runner global (`99.05% -> 100.0%`).
   - tocaba `C17` y tambien `C1.06` cross-model.
   - fix estructural limpio en Carter, sin hacks por app ni por idioma.
2. resto de items abiertos
   - reclasificados honestamente como deuda o limite;
   - no se tocaron porque esta ronda era de bugfix real, no de
     expansion, cleanup o prompt-patching.

### FASE 3 - estado despues de Round 13A

#### `R-P4-10` (cerrado)

- cambio:
  - `turn_support.collect_active_app_tokens(...)` ahora protege todo
    turno no-accionable segun `looks_action`, aunque el intent upstream
    haya quedado en `potential_action`;
  - `agent._normalise_tool_call_for_request(...)` descarta `window_list`
    cuando el turno no tiene forma estructural de observacion y completa
    `observation` cuando el pedido SI es valido.
- evidencia de cierre:
  - `audit/runs/round_13a_probe_cat17.json` -> `cat17=100.0%`
  - `audit/runs/round_13a_bugfixes.json` -> `global=100.0%`,
    `cat14=100.0%`, `cat17=100.0%`, `cat11=100.0%`,
    `validator_failures={}`
  - `audit/runs/round_13a_bugfixes_cross.json` -> `global=100.0%`,
    `cat14=100.0%`, `cat17=100.0%`, `cat11=100.0%`,
    `validator_failures={}`

### Veredicto canonico actualizado

Despues de Round 13A, no queda ningun `BUG_REAL_ABIERTO` demostrado en
el residual canonico. Lo que sigue abierto cae en deuda tecnica o
limites de diseno/runtime; por lo tanto no corresponde reabrir esta
ronda con hacks.

---

## Seccion Y - Round 13B (deuda tecnica del agent loop)

Fecha: 2026-05-04.

Regla canonica:

- el triage de `BUG_REAL_ABIERTO` / `DEUDA_TECNICA_ABIERTA` /
  `LIMITE_DE_DISENO_O_RUNTIME` / `CERRADO_O_MITIGADO` NO cambia respecto
  de la Seccion X;
- esta ronda actua SOLO sobre un slice de deuda tecnica estructural.

### Deuda tecnica seleccionada

- `R-P3-29`
- `R-P4-04`
- `R-V3-C3`

### Cambio aplicado

`src/carter_v3/agent.py` consolida el pipeline de ejecucion/verificacion
en `_execute_tool_call(...)`.

Ahora esa ruta unica cubre:

- loop principal de steps;
- action-route fallback;
- prior-target fallback;
- replay de `PendingToolApproval`;
- guardado de `PendingMemoryOffer`.

ROI tecnico real:

- menos acoplamiento entre policy, dispatch, verify, retry y trace;
- menos riesgo de que un fix futuro quede aplicado en un branch pero no
  en otro;
- replay de aprobacion humana y ejecucion normal quedan alineados sobre
  la misma ruta estructural.

### Estado actualizado de los items tocados

#### `R-P3-29`

- Estado: sigue abierto, pero con fragilidad reducida.
- Evidencia: `src/carter_v3/agent.py` pasa de `578` a `589` lineas en
  esta ronda.
- Lectura honesta:
  - el archivo no baja de tamano;
  - aun asi, deja de repetir 5 veces el mismo pipeline de tool
    execution;
  - la deuda correcta aqui sigue siendo estructural, no de bug.

#### `R-P4-04`

- Estado: abierto.
- Evidencia actual: `src/carter_v3 total=6633` lineas Python.
- Lectura honesta:
  - esta ronda NO cierra la deuda total de lineas;
  - si paga una parte defendible del acoplamiento interno del hotspot.

#### `R-V3-C3`

- Estado: mitigado parcialmente; sigue abierto.
- Lectura:
  - el siguiente refactor ya no deberia volver a tocar 4-5 branches para
    cambiar una sola regla de ejecucion/verificacion;
  - `tools/verifier.py` sigue siendo hotspot separado y no se cerro en
    esta ronda.

### Validacion

- `python -m pytest -q` -> `316 passed`.
- `python audit/hardcode_guard.py` ->
  `hardcode_guard: clean (54 files scanned)`.
- `audit/runs/round_13b_techdebt.json` ->
  `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% p95=1407.9ms`.
- `audit/runs/round_13b_techdebt_cross.json` ->
  `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% p95=2777.7ms`.

### Lectura final de residual

- no reaparece ningun `BUG_REAL_ABIERTO`;
- `C14` sigue cerrado;
- `cat11` sigue cerrado;
- la deuda estructural del core baja de forma real pero NO queda cerrada.

---

## Seccion Z - Round 13C (deuda tecnica: finish paths del agent + outcome plumbing del verifier)

Fecha: 2026-05-04.

Regla canonica:

- el triage de la Seccion X sigue vigente;
- esta ronda no reabre `BUG_REAL_ABIERTO`;
- solo toca deuda tecnica estructural del core.

### Deuda tecnica seleccionada

- `R-P3-29`
- `R-P4-04`
- `R-V3-C3`

### Cambio aplicado

**`src/carter_v3/agent.py`**

- nuevos helpers internos:
  - `_failed_tool_evidence(...)`
  - `_finish_policy_block(...)`
  - `_finish_single_tool_turn(...)`
- los branches de:
  - `unresolved_target`
  - `PolicyEngine.block`
  - replay de `PendingToolApproval`
  - cierre de `PendingMemoryOffer`
  - turn de una sola tool ejecutada
  ahora comparten el mismo contrato de salida en vez de rearmarlo a
  mano.

**`src/carter_v3/tools/verifier.py`**

- nuevo helper `_outcome(...)`.
- las ramas del verifier dejan de reconstruir `VerifiedOutcome(...)`
  repetidamente con boilerplate propio.

ROI tecnico real:

- menos repeticion del armado `ToolResult + VerifiedOutcome +
  mission_status + reply`;
- menos riesgo de que una futura regla de cierre/policy quede aplicada
  en un branch y olvidada en otro;
- el verifier concentra su contrato de salida en una sola pieza.

### Estado actualizado de los items tocados

#### `R-P3-29`

- Estado: sigue abierto, con fragilidad reducida.
- Lectura:
  - `agent.py` sigue siendo hotspot;
  - esta ronda paga un slice real del ensamblado de cierre, no el
    archivo completo.

#### `R-P4-04`

- Estado: abierto.
- Evidencia actual:
  - `src/carter_v3/agent.py = 692` lineas
  - `src/carter_v3/tools/verifier.py = 594` lineas
  - `src/carter_v3 total = 7692` lineas Python
- Lectura:
  - el paquete no baja de tamano bruto;
  - la mejora correcta es de acoplamiento interno, no de conteo total.

#### `R-V3-C3`

- Estado: mitigado parcialmente; sigue abierto.
- Lectura:
  - `tools/verifier.py` mejora su plumbing de salida;
  - pero aun no se descompone en slices mas chicos ni deja de ser
    hotspot estructural.

### Validacion

- `python -m pytest -q` -> `316 passed`.
- `python audit/hardcode_guard.py` ->
  `hardcode_guard: clean (54 files scanned)`.
- `audit/runs/round_13c_techdebt_core.json` ->
  `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% cat18=100.0% p95=1351.1ms`.
- `audit/runs/round_13c_techdebt_core_cross.json` ->
  `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% cat18=100.0% p95=3250.9ms`.

### Lectura final de residual

- sigue sin reaparecer ningun `BUG_REAL_ABIERTO`;
- `C14` sigue cerrado;
- `cat11` sigue cerrado;
- la deuda del core baja otra vez, pero `R-P3-29`, `R-P4-04` y
  `R-V3-C3` siguen honestamente abiertos.

---

## Seccion AA - Round 14 (minimum live-safe / follow-ups / REPL real)

Fecha: 2026-05-04.

### Cerrado en esta ronda

- regresion de `tool_policy` en la suite minima para:
  - `clock_now`;
  - `system_set_volume`;
  - `terminal_run_command`;
  - `memory_save` / `memory_recall` del nombre del usuario;
  - follow-up `abre lo que acabas de cerrar`;
  - deicticos ambiguos tipo `cierra eso`.
- inconsistencia del harness minimo:
  - `cat11` destructivo bloqueado en `live-safe` ya no rompe
    `required_categories_100`;
  - `auto_approve_high` deja de contaminar el builder compartido del
    runner grande.

### Evidencia real

- `python -m pytest -q` -> verde (`338` tests).
- `python audit/hardcode_guard.py` -> limpio.
- `audit/runs/codex_finish_minimum_v5.json` ->
  `global=100.0%`, `required100=True`,
  `verdict=MINIMUM_TESTING_PASS_WITH_WARNINGS`.

### Lectura correcta

- no reaparece ningun `BUG_REAL_ABIERTO` nuevo.
- la suite minima vuelve a ser util como gate operativo real.
- `PASS_WITH_WARNINGS` en el minimo es aceptable aqui porque `cat11`
  sigue bloqueado por diseno en `live-safe`.

### Lo que sigue abierto honestamente

- app launches dependientes del host/runtime real (`steam`, `spotify`,
  `marvel rivals`) pueden seguir fallando por inventario del sistema,
  `ShellExecute` o verificacion de proceso/ventana.
  - clasificacion: `LIMITE_DE_DISENO_O_RUNTIME`.
- pedidos de autoria tipo `hazme un powerpoint...` siguen sin una ruta
  estructural real porque no existe un tool/capability de creacion de
  presentaciones en el catalogo actual.
  - clasificacion: `LIMITE_DE_DISENO_O_RUNTIME`.

## Seccion AB - Round 15 (REPL follow-ups ambiguos + launches reales de Windows)

Fecha: 2026-05-04.

### Cerrado / mejorado en esta ronda

- follow-ups fuertes del REPL:
  - `ábrelo` puede reabrir lo recién cerrado;
  - `ahora ciérralo` puede reutilizar el último `app_open` reciente aunque
    haya quedado `pending`;
  - `cierra eso` sigue sin reutilizar target no confirmado.
- inventario de launch en Windows:
  - ya no depende solo de `Get-StartApps`;
  - ahora usa también `App Paths` y accesos directos del menú Inicio.
- verificación de `app_open`:
  - usa `display_name` / `expected_process`;
  - puede confirmar por ventana nueva respecto de la baseline pre-launch;
  - deja de preferir helpers auxiliares sobre el proceso exacto esperado.

### Evidencia real del host

- `Run_Carterv3.py --once "abre spotify"` -> `COMPLETE`
- `Run_Carterv3.py --once "abre whatsapp"` -> `COMPLETE`
- `Run_Carterv3.py --once "abre steam"` -> `UNVERIFIED`
  - lectura honesta:
    - `steam.exe` ya estaba vivo;
    - Carter no pudo atribuir causalmente la apertura/focus a este comando;
    - no se marca `COMPLETE`.

### Residual actualizado

- `spotify` y `whatsapp` salen del bucket de launch roto del REPL real.
- `steam` sigue abierto como limite de verificación causal del host cuando
  el proceso ya preexiste.
  - clasificacion: `LIMITE_DE_DISENO_O_RUNTIME`.
- `marvel rivals` sigue sin entry estructural encontrada en el inventario
  local de este host.
  - clasificacion: `LIMITE_DE_DISENO_O_RUNTIME`.
- tareas de autoria como PowerPoint siguen fuera del catalogo actual.
  - clasificacion: `LIMITE_DE_DISENO_O_RUNTIME`.

### Validacion

- `python -m pytest -q` -> verde
- `python audit/hardcode_guard.py` -> limpio
- `audit/runs/round_15_repl_launch_hardening_release.json` ->
  `global=100.0%`, `required100=True`,
  `verdict=MINIMUM_TESTING_PASS_WITH_WARNINGS`
