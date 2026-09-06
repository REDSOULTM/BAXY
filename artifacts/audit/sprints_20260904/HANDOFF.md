# Handoff — revisión de sprints — 2026-09-05 — base 5f572ee

## Objetivo
Replantear C03 y los sprints pendientes para acreditar BAXY funcional con
Granite 4.2 3B, ejecutados por Grok 4.6 con contexto acotado.

## Estado
Hecho: 56 documentos revisados; 38 prompts activos por tramos; diagnóstico
de C03 respaldado por informes de agentes y lectura de las fronteras de código.
Actualizados dos tests documentales; el generador histórico permanece intacto.
Revisión terminada: Full verde en checkout aislado de 5f572ee con cambios propios.
Guardado en el árbol compartido; sin commit/push de esta auditoría.
Sin ejecutar aquí: reparaciones del producto, aceptación C03, UI/voz/hardware.

## Decisiones
- 60–100K objetivo, checkpoint a 100K y corte a 150K: política conservadora,
  no umbral de calidad medido por xAI. El sprint puede reanudarse.
- Un terminal honesto sin respuesta normal útil sigue siendo fallo.
- v16 y disc son desarrollo; no vuelven a ser holdout al cambiar GGUF.
- 11.16 entrega candidato; instalación/hardware/entrega cierran en 12.1–12.3.
- Conservar A/B ya demostrado por Grok; no reiniciar C01/C02 ni su tramo A.

## Archivos y ownership
- Informe: `documentacion/sprints/REVISION_SPRINTS_2026-09-04.md`.
- Contrato: `documentacion/sprints/00_PROTOCOLO_EJECUCION.md`.
- Continuación: `documentacion/sprints/Sprints comprobación/07_REPLANTEAR_C03.md`.
- WIP ajeno intacto: código C03, matriz, estado, CIEN y corridas de Grok.
- Manifiesto exacto de cambios propios: `own-files.json` en esta carpeta.

## Validación
- Tres suites dueñas de documentación: 17 passed, 0 failed.
- Documentación + STT en checkout aislado: 29 passed, 0 failed, 1 skip.
- 56 documentos: 0 enlaces rotos; 38 prompts: protocolo y tramos presentes.
- Full inicial: 8 fallos de contratos documentales antiguos; corregidos,
  sin saltarlos ni cambiar tests de conducta del producto.
- Full posterior: 2 fallos de huella STT por edición accesoria del generador;
  edición retirada. Diff aislado vacío en `src scripts main.py assets.manifest.json`.
- `scripts/test_source_quality.ps1 -Mode Full`: exit 0, gate verde.
  .NET 4033 pass / 0 fail / 1 skip; Python 8790 pass / 0 fail / 11 skips
  ambientales, 433 subtests pass. Build: 0 warnings; Python: 3 warnings de cálculo.
  Log `full-final.log`; hashes y alcance en `validation.json`, en esta carpeta.
- Árbol vivo de Grok: 2 fallos de huella STT siguen pendientes para C03.

## Siguiente acción
Pedir a Grok checkpoint y conservar las corridas activas; después usar C03
actualizado en sesión limpia con ese estado. Reconciliar procesos/resultados
antes de otra corrida; continuar desde el avance demostrado, sin reiniciar A.
