# Handoff — auditoría de Goals 01–10 — 2026-09-03 — b2505da

## Objetivo y estado
Contrastar cierres 01–09 con el producto público y juzgar preparación para 10.
Diagnóstico demostrado; sin implementación. Informe principal:
`documentacion/AUDITORIA_GOALS_01_10_2026-09-03.md`.
Diagnóstico terminado. Full con BAXY cerrado: estática/build y .NET
3978 pass / 0 fail / 1 skip; Python **8788 pass / 4 fail / 3 skips**.
Full exit 1. Repetición sólo de los cuatro fallos: 1 pass / 3 fail en 17,21 s.

## Evidencia que no se debe reconstruir
- `ui-turns.json`: seis entradas reales en la casilla, tres últimas encadenadas.
- `core-observations.json`: hora completed/verified narrada como fallo;
  Calculadora apareció, pero app.open verification_failed con efecto incierto.
- `shell-trace.jsonl`, `turn-audit.jsonl`: chiste, red y petición tras Nueva
  sesión no llegaron a decisión ni Core: los interceptó el plan pendiente.
- `public-ui-final.png`: «Listo, audio está abierto.» sin las lecturas pedidas.

## Decisiones y límites
No se aplicaron arreglos ni se rebajaron criterios. No inferir una tasa general
de acierto de seis turnos encadenados. No se conoce la rama exacta que falló en
el verificador de Calculadora ni el primer rechazo de composición de la hora.
El runtime cargaba `BAXY Definitivo/src`, confirmado en su manifiesto.
No se borró el estado durable incierto de la prueba. La app/Core lanzados por la
auditoría se cerraron para Full; Calculadora quedó abierta.
`tests/test_wakeword_runtime_resources.py` era untracked preexistente: no tocar.

## Comandos y validación
`git fetch origin` + `git merge --ff-only origin/main`: ya actualizado;
HEAD y origin/main b2505da8f15820f94e47d874a66e26a927ea2e9a. No push.
`py main.py`: arranque real; un reinicio intermedio chocó con WebView2, retry abrió.
`scripts/test_source_quality.ps1 -Mode Full`: intento inicial interrumpido por
sincronización; segundo bloqueado por Core abierto (MSB3027/MSB3021); tercero
en `source-quality-full.txt`, exit 1. Logs completos y repetición preservados
en esta carpeta. Los skips no son pass; NUnit Explicit queda fuera de totales.
No se ejecutó nueva campaña acústica ni certificación instalada.

## Clasificación del rojo
STT produjo «open up pad please» en lugar de notepad: pasó al repetir aislado.
Dos tests versionados de evaluadores STT fallan por sello: los 396 archivos son
idénticos a HEAD. Usar en memoria la versión 192051f de sólo
`scripts/goal095_09512_integrate.py` reproduce el hash esperado. Diagnóstico
en `program-tree-diagnostic.json`; no reseñar como cambios locales ni alterar
expectativas a ciegas. La cuarta prueba, untracked preexistente, exige compartir
objeto SessionOptions; su fallo de identidad no prueba spinning elevado.

## Siguiente acción recomendada
Al autorizar una reparación, empezar en `src/Baxy.App/ModelMessageComposer.cs`
por la pérdida de hechos del resultado verificado. Usar el contrato real de
`system.time`, no el localTime artificial de la muestra Goal 06. Después,
separar `_pendingMindPlan` de los objetivos nuevos en MainWindowViewModel.
