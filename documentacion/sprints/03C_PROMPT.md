# Prompt para Grok 4.6 — Goal 03C

Pégalo entero en una sesión nueva, sobre
`C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`, rama `main`.
El goal canónico es [`03C_ALCANCE.md`](03C_ALCANCE.md). Este fichero es
la misma instrucción, lista para pegar.

---

```
Trabajas en C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo, rama main.
Comprueba que estás ahí: `git rev-parse --show-toplevel` termina en "BAXY
Definitivo". En la misma carpeta Programacion hay otro repositorio llamado BAXY a
secas: es el intento anterior, fuente de herencia, NO tu sitio de trabajo.

TU GOAL ES documentacion/sprints/03C_ALCANCE.md. Léelo entero. Es tu única
instrucción de qué hacer. AGENTS.md te dice dónde estás y cómo moverte; la
identidad está en documentacion/00_IDENTIDAD.md. Si un diseño tuyo las
contradice, cambias tú.

DE DÓNDE PARTES (ya medido, no lo vuelvas a descubrir):
- Tres corridas del fresco SHA-256 761c1bc3… : 112, 112 y 110 de 124 (mediana
  112 = 90,3 %). goal03_rec5e2e8/9/10.json. Reconocedor 0, recuperación 0.
- Fuera de catálogo: 21–24/36 abstenciones honestas. El scorer cuenta `acted`
  con intent_operations incluidos: un clarify «¿creo una tarea?» para un taxi
  cuenta. Hoy hay 12–15 acted. El listón es ≤5 de 36. NO relajes el scorer.
- Cobertura 169/158/31 sello dc0a7893…. Compuestos 6/15 y 15/32. VRAM pico
  4026/4096 MiB. Sobrecarga LLM p50 17 ms. p50 de turno 1,50–1,60 s.

QUÉ CIERRA ESTE GOAL (no pases al 04 con esto abierto):
1. ≤5/36 acted fuera de catálogo, tres corridas, SIN bajar la mediana de 112/124.
2. Las 12 filas in-catalog que aún fallan, servidas o con diagnóstico medido.
   Estables (fallan las tres corridas): cmp-01, fs-04, inp-06, net-01, net-10,
   win-01. Los textos están en 03C_ALCANCE.md.
3. Si 112 y el alcance cierran, sigue si puedes subir del 90 %.

Nueve oos acted en las tres corridas — éstas mandan:
ooc-01 taxi → task.create (clarify)
ooc-07 upload youtube → media.play.youtube (clarify)
ooc-17 grabar pantalla en video → capture.active.window (clarify)
ooc-18 vpn → wifi.connect.named (clarify)
ooc-19 clonar disco → filesystem.copy (clarify)
ooc-23 editar video → media.seek.relative
ooc-24 pdf a word → office.document.create (ACTION)
ooc-31 unlock my phone → system.power (clarify)
ooc-33 imprimir 3d → peripheral.print (clarify)
También ooc-22 torrent (action) y ooc-20 regar plantas.

NO REPETIR (APLAZADOS.md): filtrar hojas ungrounded (abre oos), exentar
read_only (red neuronal), pila FunctionGemma, sexto gate léxico, BGE-M3,
MTOP, tool_choice required, unión ranker+E5, reactivar el verificador de
identidad del reconocedor como retirada.

CÓMO: una cosa cada vez, offline sobre la telemetría en disco antes de e2e,
tres corridas para declarar un cambio bueno. Sin subagentes. Commit después
de cada paso medido. No dos mediciones Goal 03 a la vez. Pytest con el venv
viejo BAXY\experiments\mind_router_spike\.venv. Si tocas src/baxy_mind,
repinas wake-validation-program-tree.

Medición:
  py -m experiments.mind_router_spike.run_goal03_comprehension --label <nombre>
  py -m experiments.mind_router_spike.measure_goal03_catalog_coverage --label <nombre>
  py -m experiments.mind_router_spike.run_goal03b_compound_missions --label <nombre>

Lee documentacion/sprints/03C_ALCANCE.md ahora y no pares hasta cumplirlo.
```
