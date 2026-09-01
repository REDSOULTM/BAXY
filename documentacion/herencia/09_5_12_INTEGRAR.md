# Goal 09.5.12 — Integrar herencia y replanificar 10–11

Cerrado 2026-08-31. Fuente de verdad machine-readable:
[`../../artifacts/goal095/synthesis/09.5.12_integrar_y_replanificar.v1.json`](../../artifacts/goal095/synthesis/09.5.12_integrar_y_replanificar.v1.json).
Ledger: [`../../artifacts/goal095/ledger/integrate-09.5.12.json`](../../artifacts/goal095/ledger/integrate-09.5.12.json).

Siguiente prompt humano:
[`../sprints/10.0_BASE_VERDE.md`](../sprints/10.0_BASE_VERDE.md).
No remite a 09.5.12 ni a 09.5.11C.

## Cobertura

100 % del manifiesto (28373 archivos; cubiertos 28373). Faltantes 0, solapes 0. Ledgers: 19850 files con terminales permitidos.

## Cuatro clases

- Herencia previa: Goal 01 (2026-08-16).
- Delta nuevo: manifiesto 09.5.1 y fuentes dispersas declaradas.
- Piezas trasplantadas: cero lotes (`conservar_actual`).
- Rechazos: `functiongemma-270m-ft`, `qwen-vl`, `ollama-runtime`, `auto_approve`, `soak-24h-as-requirement`, `gemma-native-audio`.

## 10.x / 11.x

Cero prompts o slices nuevos. Delta 09.5 va a checkpoints internos. Barras intactas: 200 turnos, 1.947/808, 2.036 contratos, ambiente, Identidad, Full. Ventana <500k. Sólo ES/EN/spanglish.

Extensión posterior aprobada por el dueño: `10.2.5_RECURSOS_EN_REPOSO.md`
se insertó entre 10.2 y 10.3 al demostrarse consumo no atribuido por el cierre
original. No reabre ni altera las decisiones históricas 09.5.

`00_ORDEN_DESDE_09_5.md` conserva 36 ficheros de producto en orden, 10.0 primero.

## Reproducibilidad

`.\scripts\test_source_quality.ps1 -Mode Full` → source_quality_gate_passed: mode=Full; python 8760 passed, 10 skipped (ambient); Integration 2828 pass, 1 skip opt-in; EXIT=0
