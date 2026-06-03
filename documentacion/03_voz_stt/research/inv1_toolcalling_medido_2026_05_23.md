# Inv 1 (tool-calling) — MEDIDO en vram4 (2026-05-23)

## Sampling dual greedy (palanca 1, APLICADO)
Smoke E2E (apps+audio, thinking ON = camino de prod):
| | greedy OFF | greedy ON |
|---|---|---|
| tool-call | 12/12 | 12/12 |
| apps avg | 5.2s | 4.6s |
| audio avg | 3.8s | 3.1s |
-> greedy NO degrada y BAJA latencia ~15-18%. Se queda (default ON, gate
   GEMMA4_GREEDY_TOOLCALL=0).

## A/B clave: ¿el greedy cura el 2/6 SIN thinking?
SIN thinking, system prompt simple + tools claras:
  greedy OFF: 6/6 | greedy ON: 6/6
HALLAZGO HONESTO: el "2/6 sin thinking" NO se reproduce con comandos crisp +
tools claras. El 2/6 medido antes venía de un escenario más complejo (system
FULL 65 tools / comandos ambiguos / contexto completo del agente). Con el setup
real del smoke, sin thinking ya da 6/6. La premisa de la investigación (greedy
cura 2/6) NO aplica acá — pero el greedy igual SE JUSTIFICA por la latencia.

## Prefill <|tool_call|> + few-shot (palancas 2 y 3): NO IMPLEMENTADAS
La investigación las marcó "lift HIPOTÉTICO". Como sin thinking ya damos 6/6 en
el setup medido, no hay problema que resuelvan -> serían complejidad + riesgo
(prefill mal hecho ROMPE el tool-call) sin beneficio medible. DESCARTADAS salvo
que aparezca un escenario real con tasa <6/6 sostenida. (CLAUDE.md: no agregar lo
que no mejora un número.)

## Veredicto inv1: sampling greedy aplicado (gana latencia); prefill/few-shot
descartados por falta de problema medible. Pendiente re-medir si el 2/6 aparece
en prod con el prompt completo.
