# MERGE CHECKLIST — `PortandoLoMejor` → review/merge

Documento de handoff para que RED mergee con datos reales en la mano. Generado al
cierre de la sesión de validación final (LLM E2E + flakiness + perf budget).

---

## ✅ Estado de la rama

- **Suite:** ~1113 passed por batches + los nuevos de esta sesión; **1 rojo
  PRE-EXISTENTE ajeno** (CDP/Netflix, ver abajo). 115 archivos de test.
- **Flakiness:** **40 corridas consecutivas (2 batches × 20), 0 fallos, 0 flakies.**
  La superficie de mayor riesgo (concurrencia/threads/timing/random/lifecycle) es
  determinista. Ver `bench/flakiness_hunt.md`.
- **Perf budget:** 3/3 pasan con modelos reales y amplio margen (compaction 2.7ms
  vs 50ms; _system_message 1.06ms vs 5ms; wake ~26% vs <60%). Ver
  `bench/llm_e2e_validation.md` §Fase 3.
- **Commits de la auditoría:** ~28 atómicos (esta sesión: 1 fix de latencia real +
  5 docs/tests de validación). Sin push, sin reescritura de historia.

## ✅ Resultados LLM E2E (server de producción real, build b9090, E4B-Q6)

| métrica | valor | veredicto |
|---------|-------|-----------|
| TTFT (smalltalk/pregunta) | 22–73 ms | ✅ |
| decode sostenido | ~55 tok/s | ✅ |
| turno info E2E ("capital de Francia") | 15.0s → **3.59s** tras fix | ✅ (−76%) |
| turno smalltalk E2E | 1.60 s | ✅ |
| recovery (DB corrupta + server up) | turno OK en 2.50 s | ✅ |

**Bug real encontrado y arreglado por el E2E** (commit a1e0071): el
forced-tool-retry se disparaba en turnos informativos ya respondidos en prosa,
quemando un pass de LLM completo (~11.8s). El mock no lo veía. Es exactamente el
tipo de hallazgo que justificaba la validación E2E.

**Latencia residual conocida (NO bug):** turnos donde el modelo elige pensar +
llamar web/knowledge tardan 4–11s por el thinking budget (512 tok @ ~55 tok/s).
Es comportamiento del modelo + tuning de `thinking_budget`. → decisión de RED.

## 🔵 El rojo pre-existente ajeno (CDP/Netflix)

`test_streaming_profile.py::TestCDPHappyPath::test_cdp_success_marks_played`
falla porque requiere una conexión CDP a un Chrome real (no hay en el entorno de
test). Último commit del archivo: `c54f032`, ANTERIOR a toda la auditoría. NINGÚN
commit de la auditoría tocó streaming/CDP. **NO bloquea el merge** — es un test de
integración ambiental, no un fallo de código.

## 📋 Las 3 decisiones que esperan a RED (1 línea + recomendación)

1. **`_inbox` unbounded** (`questions_for_red` #4): ¿bound duro (32) que rechaza
   con toast, o unbounded? → **Recomiendo dejarlo unbounded** (seguro en el threat
   model real; acotar descartaría turnos de usuario en silencio).
2. **`gemma4_agent/ContextoClaude.md`** (#2): archivo sin trackear que no creé yo.
   → **Recomiendo gitignorearlo** si es scratch (parece serlo, 171KB de contexto).
3. **Thinking budget en turnos info** (nuevo, del E2E): los turnos think+retrieve
   tardan 4–11s. → **Recomiendo evaluar bajar `thinking_budget` del modo info**
   (o aceptar que turnos "profundos" exceden el budget de voz). Medir antes de
   tocar.

(El #5 tracing-ValueError ya se RESOLVIÓ; el #1 boot E2E quedó parcialmente
cubierto — ver "riesgos residuales".)

## 🚀 Pasos de merge sugeridos (RED los corre; yo NO)

```bash
# 1. Confirmar la rama y que el árbol está limpio (salvo .claude/settings.json local)
git -C "/c/Users/usuario/Desktop/ETC/Programacion/Probando Gemma 4" status

# 2. (opcional) Smoke rápido pre-merge — los guardrails, <15s:
PYTHONPATH="$(pwd)" python -m pytest gemma4_agent/test_smoke_overnight.py \
  gemma4_agent/test_architectural_invariants.py \
  gemma4_agent/test_perf_budget.py -q -p no:cacheprovider

# 3. Mergear a main (fast-forward o no-ff según preferencia del equipo):
git checkout main
git merge --no-ff PortandoLoMejor -m "merge: auditoría arq/fiab/latencia (27 bugs+2 perf, guardrails)"

# 4. (post-merge, cuando NO haya un server de prod corriendo) smoke E2E opcional:
#    levantar server frío y medir TTFT/boot, como gate de confianza final.
```

## ⚠️ Riesgos residuales conocidos (honestos)

1. **Cold-boot E2E sin medir:** había un server de producción YA corriendo en
   :8080 (no mío); NO lo maté (CLAUDE.md mand. 6 + round-11 respeta servers
   externos). El tiempo a primera respuesta desde server FRÍO no se midió esta
   sesión. Mitigación: el path está cubierto por tests mockeados + el warmup en
   daemon con deadline. Bajo riesgo.
2. **Latencia variable en turnos think+retrieve (4–11s):** comportamiento del
   modelo, no bug. Tuning de producto pendiente (decisión #3).
3. **`domain_tools.py` (10.5k LOC):** deuda de mantenibilidad conocida, aislada por
   el doble try/except del dispatch. No es riesgo de fiabilidad.
4. **El rojo de CDP:** ambiental, ajeno, no bloquea.

## 🟢 Recomendación de merge

**La rama está LISTA para merge.** El código de la auditoría es verde, atómico,
determinista (40/40 corridas), validado E2E con el modelo real, y protegido por
guardrails (perf budget + invariantes + no-orphan + fuzz). El bug que el E2E
encontró ya está arreglado. Los pendientes son 3 decisiones de producto (no
bloqueantes) + 1 medición opcional de cold-boot.

Si RED quiere confianza total: correr el smoke E2E de cold-boot (paso 4) cuando no
haya server de prod corriendo. Si no: mergear ya — el riesgo residual es bajo y
documentado.

## Procesos al cierre

```
llama-server.exe  PID 7904  (router :8080)   <- EXTERNO, ya corría antes de la sesión
llama-server.exe  PID 37604 (child, ~6.5GB)  <- EXTERNO, el modelo del usuario
node.exe          ninguno
```

**NO maté el llama-server: NO lo arranqué yo** (el manager lo detectó "external"
al inicio y lo respetó, round-11). Matar el modelo cargado del usuario sin
confirmar sería el escenario que CLAUDE.md mand. 6 prohíbe. Si RED quiere que se
cierre, es una orden de 1 línea (`taskkill /F /PID 7904`) — pero no la tomé por mi
cuenta. Ningún proceso fue lanzado por esta sesión que quede colgado.
