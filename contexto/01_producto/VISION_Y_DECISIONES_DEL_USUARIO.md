# Visión y decisiones del usuario

- BAXY es un asistente local para Windows que recibe voz o texto, comprende la
  misión, actúa, verifica y cuenta brevemente qué hizo.
- Debe sentirse como un Jarvis local: rápido en tareas simples, amigable,
  directo, emocional y adaptable.
- El alcance lingüístico funcional de BAXY 1.0 es español, inglés y spanglish,
  incluido el code-switch natural y los errores de STT cuya intención
  pertenezca a esos idiomas. Las lenguas inequívocamente ajenas se conservan
  solo como trazabilidad histórica y no suman cobertura de producto.
- La etiqueta derivada `language` es heurística: `other` no significa por sí
  sola fuera de alcance, porque órdenes cortas de los idiomas objetivo pueden
  caer en esa categoría. La decisión de alcance es semántica y auditada.
- La conversación es el producto. JSON, comandos, IDs y trazas quedan en
  diagnóstico privado opt-in.
- No se diseña una tool por frase ni se exponen cientos de tools planas. Se
  componen primitivas tipadas y verificables.
- Solo se declara éxito después de observar el estado físico.
- Se confirma únicamente ante dinero, privacidad, seguridad, pérdida de trabajo
  o irreversibilidad real; una orden clara autoriza acciones ordinarias.
- La memoria es local, privada, inspeccionable, corregible y borrable.
- Se conserva la identidad visual de la GUI archivada, aunque su tecnología
  puede cambiar si el torneo lo demuestra.
- El perfil base apunta a equipos Windows con 4 GB de VRAM y aproximadamente
  3 GB cuando sea viable, sin afirmar validación física no realizada.
- `legacy/` es referencia de solo lectura.
- El corpus histórico completo congelado es el alcance de evidencia y
  procedencia de 1.0. Su compromiso de aceptación funcional se limita a
  español, inglés y spanglish; los casos inequívocamente escritos en otras
  lenguas son `trace-only`, no backlog ni cobertura requerida.

Procedencia: `BAXY_GPT56_ULTRA_PROMPT.md`, solicitud adjunta y aclaración de
alcance del 2026-07-14, `documentacion/01_CONTRATO_PRODUCTO.md` y revisión
semántica v2 del corpus. Confianza: decisión directa del usuario.
