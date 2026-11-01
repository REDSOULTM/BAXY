# Aviso para la sesión de la auditoría de reales (léelo antes de fusionar en `baxy-renew`)

Esto lo dejó la sesión del autor que cambió la **apariencia y la voz** de BAXY, el 2026-10-17, a pedido del autor.

Mientras hacías la auditoría, `baxy-renew` avanzó por su cuenta. Tu rama (`auditoria-reales` y los `lote*`) parte de
`845d652ad`, y desde ahí `baxy-renew` sumó estos cambios:

- **Interfaz v4:** el rediseño `design_handoff_baxy` (`src/Baxy.FieldUi`, `dist/` incluido) y su backend en
  `src/Baxy.App`.
- **Bandeja:** icono de BAXY y menú propio.
- **Voz:** Supertonic 3 en lugar de Piper (`src/baxy_mind/voice_output.py`, `speech_text.py`,
  `scripts/voice/make_baxy_voice.py`; el lanzador usa `BAXY_RENEW_TTS_DIR`).
- **Revisión de botones:** memoria, triggers, micrófono y arranque con Windows.
- **El cierre `c1e692392`:** ya estaba en `hub/baxy-renew` antes que tú.

El detalle está en `RENEW_TRASPASO.md`, en las secciones «Interfaz v4» y «Voz de BAXY».

**Si al fusionar salen conflictos, son por eso. No es un error ni una regresión: acéptalos y conserva los dos lados.**
No hace falta investigarlos ni volver a medir por ellos. Lo de la interfaz y la voz no toca la decisión del modelo:
el prompt, las descripciones de herramientas y el catálogo siguen siendo los tuyos.

Cómo resolverlos:

- **`src/baxy_mind/mind.py`:** yo sólo añadí `export_session()` y `load_session()`, que usan las sesiones de la
  interfaz. Tus reglas del prompt van tal cual, así que conserva las dos cosas.
- **`src/Baxy.Kernel/Operations/ProductCatalog.cs`:** yo sólo cambié `ToPolicyRisk` de `internal` a `public`. Tus
  operaciones nuevas van tal cual, así que conserva las dos cosas.
- **`artifacts/renew/PROGRESO.md`, `INFORME_FINAL.md` y `metas.json`:** vienen del cierre `c1e692392`, no de mí.
  Conserva lo de ese commit y añade lo tuyo debajo.
- **`PROMPT_AUDITORIA_REALES.md`:** en la carpeta `BAXY-Renew` hay una copia sin versionar. Si git dice que la
  sobrescribiría, bórrala de esa carpeta antes de fusionar: la versionada es la tuya.
- **Cualquier archivo de `src/Baxy.FieldUi`, de la bandeja o de la voz:** quédate con el de `baxy-renew`.

**Está abierto y no es tuyo:** `scripts/test_field_ui.ps1` da 23 de 24. Falla `controls.spec.ts › micrófono` en una
app recién arrancada, y lo está investigando la sesión de la interfaz. No cuenta contra tus criterios ni hace falta
que lo arregles.
