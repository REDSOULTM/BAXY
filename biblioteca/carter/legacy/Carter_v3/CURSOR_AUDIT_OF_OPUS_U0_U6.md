# CURSOR_AUDIT_OF_OPUS_U0_U6

Fecha: 2026-05-05  
Commit auditado: `6aae2b0a`  
Contexto obligatorio leido: `../ContextoCarter.md`  
Estado previo: `git status` clean, baseline `pytest=418 passed`, `hardcode_guard=clean`.

## Alcance y metodo

- Se auditaron cambios del commit en: `audit/hardcode_guard.py`, `src/carter_v3/cli/launcher.py`, `src/carter_v3/turn_support.py`, `src/carter_v3/response_composer.py`, `src/carter_v3/agent.py`, `src/carter_v3/tools/dispatch_system.py`, y tests nuevos.
- Esta auditoria no asume que el cierre previo sea valido por declaracion; evalua aporte real a runtime live vs solo tests mock.
- No se modifico codigo de produccion durante esta fase.

## 1) Que cambio exactamente en `6aae2b0a`

- **U0**: endurecimiento de `hardcode_guard` (brands en regex, sufijos semanticos en nombres `*_RE`, helpers `looks_*` prohibidos por intencion).
- **U1**: el launcher CLI conserva `history` y envia `prior_turns` a `run_turn`.
- **U2**: `build_messages()` en `turn_support` renderiza capacidades desde `TOOL_CATALOG` y refuerza identidad/localidad/no fake success.
- **U3**: `response_composer` usa `outcome.evidence["preexisting"]` en `app_open`.
- **U4**: `response_composer` propaga `data["next_step_hint"]` de forma generica.
- **U5**: `agent` traduce `data["missing_dependency"]` a `policy_blocks` con `needs_environment`; `dispatch_system` marca `missing_dependency=pycaw`.
- **U6**: `notify_toast` se narra literal, sin inferir side effects.

## 2) Que partes U0-U6 son correctas y universales

- **U0** correcto: previene clases completas de regresion semantica/hardcode, no un caso puntual.
- **U1** correcto: follow-up context en CLI real, sin ramas por app/frase.
- **U2** correcto: capacidades derivadas del catalogo real; evita negar tools existentes.
- **U3** correcto: usa evidencia estructural del verificador (`preexisting`), no texto del usuario.
- **U4** correcto: plumbing universal de hints para cualquier tool.
- **U5** correcto en idea: normaliza dependencias faltantes como entorno, reusable.
- **U6** correcto: evita fake success por toast textual.

## 3) Que partes podrian ser hardcode indirecto

- No se detectan ramas directas por marcas/apps/frases en cambios U0-U6.
- Riesgo indirecto menor: texto persona en `turn_support` podria driftar a respuestas genericas si no se prueba contra runtime live/modelo concreto.
- Riesgo de semantica por regex persiste fuera de U0 en modulos historicos; U0 ayuda, pero no reemplaza auditoria manual de routing.

## 4) Que partes deben mantenerse

- Mantener **U0-U6 completos** como base.
- Mantener tests anti-hardcode de U0 y behavior tests de U1-U6.
- Mantener estrategia de `TOOL_CATALOG` como fuente unica de capacidad visible al modelo.

## 5) Que partes deben revertirse

- **Ninguna** de U0-U6 requiere revert total segun esta auditoria.
- Si hay ajustes, deben ser de completitud runtime/live, no rollback de arquitectura.

## 6) Que partes necesitan tests adicionales

- Follow-ups reales: `Abriste X?`, `Lo cerraste?`, `Si` sobre pending intents.
- Persona/capacidad: evitar respuestas tipo "soy un asistente sin acceso local".
- No fake-success live cases: alarma/mensajes/volumen sin dependencias.
- Casos de typo y dialogo emocional para evitar deriva LLM generico.
- Guard adicional sobre hardcodes semanticos en nuevos helpers/routing.

## 7) Si hay ramas por frase/app/marca

- En cambios U0-U6: **no** se encontraron ramas tipo `if "steam" in user_text` o equivalentes por marca.
- `turn_support.select_tools()` usa detectores `looks_*` estructurales preexistentes; requiere vigilancia pero no introduce listas de marcas en este commit.

## 8) Si hay regex semanticos

- U0 agrega deteccion de regex semanticos prohibidos (positivo).
- En diffs de U0-U6 no se introducen regex semanticos nuevos para rutear por intencion.

## 9) Si `hardcode_guard` cubre regresiones futuras

- Cubre mejor que antes (brands en patterns, nombres semanticos, helpers `looks_*` prohibidos).
- Aun no es prueba absoluta: puede escaparse logica semantica sin regex/nombre obvio.
- Conclusion: **cobertura fuerte pero no completa**; debe coexistir con tests conductuales y smoke live.

## 10) Si el commit ayuda al runtime real o solo al test mock

- Ayuda real probable en runtime para:
  - follow-ups por `prior_turns`,
  - honestidad `app_open` preexisting,
  - mensajes de dependencia faltante,
  - evitar fake toast success.
- **No prueba cierre live por si solo**: falto smoke real contra Ollama y validacion caso-a-caso del log.

## Veredicto de la auditoria

- `6aae2b0a` aporta base tecnica valida y mayor compliance no-hardcode.
- No autoriza declarar `LIVE_TEXT_CORE_READY` sin:
  - auditoria completa de fallos live del log,
  - matriz 80+ ejecutable,
  - nuevos tests obligatorios,
  - smoke live real documentado.
