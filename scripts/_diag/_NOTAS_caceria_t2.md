# Notas cacería tanda 2 — análisis pre-fix (2026-06-05)

## Juez: 586 OK / 236 BUG / 178 DUDOSO (1000 casos). Clusters en _judge_clusters_1000.txt

## A1 — destructivo catastrófico (CRÍTICO ~28) — ANÁLISIS DE CÓDIGO REAL

Verifiqué `terminal_run` (tools.py:5405): **SÍ tiene `_hard_gate(risk="high")`** para toda
invocación del LLM (salvo `_internal_safe`). O sea: en PROD, `rm -rf /` via terminal.run
pega contra el gate de confirmación y NO ejecuta. El mock (`_diag_hunt_tanda.py:64`)
reemplaza `ToolRegistry.execute` entero -> el gate NUNCA corre en el eval -> el reply
parece que ejecutó. **No puedo juzgar el gate desde esta data; verificar EN VIVO.**

Tools destructivas y su gate (a verificar en vivo, sin mock):
- filesystem.delete -> hard_gate (CC-101) confirmado en tanda 1. PROD gatea.
- terminal.run -> hard_gate risk=high (tools.py:5405). PROD gatea.
- registry.delete -> ¿gate? VERIFICAR.
- system.shutdown / system.format -> ¿gate? VERIFICAR. (1931 format C:->shutdown = routing inversion)
- maintenance.firewall_status (1947/1948 disable firewall->status) = ROUTING: rutea a una
  tool que solo LEE; no desactiva nada. El reply MIENTE ("está desactivado"). Bug de
  HONESTIDAD del reply, no de ejecución.

### Conclusión A1 (a confirmar en vivo):
- La EJECUCIÓN destructiva probablemente está gateada en prod (no es el bug).
- El BUG REAL y verificable-sin-mock es la **mentira del reply**: "Listo, borré todo y
  verifiqué que ya no existe" / "Defender desactivado" / "firewall desactivado" cuando
  (a) la acción estaba gateada o (b) la tool solo leyó. => Guarda de honestidad:
  **claim de acción destructiva/verificación SIN evidencia de ejecución real**.
- Plan: (1) verificar EN VIVO que delete/terminal/registry/shutdown gatean; (2) si gatean,
  el fix es la GUARDA DE HONESTIDAD (no afirmar destrucción/verificación sin evidencia),
  universal y estructural; (3) si alguna NO gatea (registry/shutdown/format), agregar gate.

## Prioridad de fixes (real, descartando mock Bloque D ~140):
1. A1 honestidad destructiva + verificar gates (vivo)        ~28 CRÍTICO
2. A6 conocimiento->vision/web (que _is_howto suprima vision/web) ~22
3. B1 web-loop -> RE-MEDIR (puede estar ya fijo por dedup c84551e) ~22
4. A2 claim de mensaje "hola"/envío inventado                ~16
5. A7 sitio web -> app.open (desviar URL a browser)          ~14
6. A4 tool != claim (generalizar intent_domain_mismatch)     ~12
7. C3 encadenamiento incompleto                              ~12
8. A8 preferencia/dato personal -> acción                    ~10
9. A5 acción opuesta (lock/suspend/activar) + A3 resultado fabricado ~14

## DESCARTAR (Bloque D, ~140): cifras system/IP/PDF/whoami/version = el LLM rellena el
## vacío del mock. Routing correcto, dato fabricado por mock. NO son bugs prod.
## Excepciones menores reales: leak wrapper JSON crudo (1332/1376/1467), IP-privada-
## etiquetada-pública (wording), versión inventada (1884).

## PROGRESO FIXES (2026-06-05, durante tandas)
- A6 conocimiento->vision/web: HECHO (commit 5f68fb5). _INFO_SUPPRESS_TOOLS.
- A7 web->app.open: HECHO (commit 5f68fb5). _is_web_target en planner + divert.
- A1-honestidad destructiva: HECHO (commit 5f68fb5). destructive_claim_without_evidence.
- Techos archivos-dios reconciliados (call-site irreducible).

## PENDIENTE — analizado, requiere cuidado/vivo:
- A2 (~16) msg "hola" inventado: DOS sub-bugs. (1) cu(goal) — el 4B INYECTA
  "y escribile hola" en el goal cuando el user solo pidió "andá al chat" (1131-1182);
  el reply afirma "escribí hola". Fix en la FUENTE (no inyectar send en goal de
  navegación), no en reply-guard (cu sí corrió). (2) whatsapp.send con body=eco del
  comando ("text":"enviá un mensaje a Pedro") + claim "le envié" (1522/1523). En prod
  hay draft-first auto_send=False. -> verificar en vivo si el body-eco y el "le envié"
  persisten con el flujo real; guard "send claim sin body provisto por el user".
- A4 (~12) tool!=claim: generalizar intent_domain_mismatch (hoy solo window<->file)
  a una tabla verbo-afirmado->familia-tool. Cuidado con falsos+.
- A8 (~10) preferencia/dato personal->acción: detector "declaración de preferencia/
  dato" que suprime tools de acción (como how-to/trigger). Clean, hacer.
- A5 (~7) acción opuesta (lock->shutdown, activar->silenciar, cerrar->abrir): routing
  de antónimos. 1390 lock!=shutdown peligroso. 1418 trigger (verificar detector t1).
- C1 charla->comando, C2 tienda equivocada, C3 encadenamiento incompleto, C4 idioma.

## HALLAZGO dedup (t3 análisis): el fix dedup_degenerate_batch YA FUNCIONA
- Los loops de 140 tools (window.maximize×140, run_tests×142) del cluster A2/E1 eran
  EJEMPLOS DE TANDA 1 (IDs <1000, PRE-fix) que el juez citó. NO son de t2/t3.
- t2: 11 loops. t3 (post-fix): solo 4 loops, TODOS multi-pass (passes 5-7), NO
  single-batch degenerado. El per-response dedup mató el caso de batch único.
- Los 4 de t3 (2358/2391/2523/2692) son re-try genuino del 4B across passes; el
  circuit-breaker global los corta honestamente (~30 tools) pero lento (50-72s).
- CONCLUSIÓN: NO generalizar dedup a ciegas (sería over-eng para 4 casos). El dedup
  per-response basta para el batch degenerado. Para los multi-pass: evaluar bajar
  GLOBAL_CIRCUIT_BREAKER o dedup cross-pass — pero solo 4/1000, abortan honesto.
  PRIORIZAR los fixes nuevos de mayor volumen (A5 Jarvis, A1 noise-tokens).

## HALLAZGO (t3, disciplina medir-antes-de-codear):
- A1-noise-token (~22 del juez): SOBRE-CONTADO. En t3 REAL solo 2 casos (1 garble STT
  difícil, 1 leak). Los ~22 eran IDs de tanda 1 (508-543) citados por el juez. El
  _is_low_signal_noise de t1 ya basta. NO extender (sería over-eng).
- Leaks (~8 del juez): en t2+t3 REAL solo 6, y 5 son ENVELOPE DEL MOCK ("contenido es:
  {ok:true,_eval_mock}") = artefacto (en prod el tool da contenido real). Solo 1 leak
  REAL: 2300 "memory{action:<|"|>list<|"|>}" (tokens especiales). Vale extender el
  sanitizer para <|...|> + memory{...} (safety net, leaks siempre son bug). Bajo volumen.
