# Agenda1024 — propuesta dirigida H0121/H0343

Base `d97670dbc761b92c39ec38e0e2f306974238d681`; rama `codex/c03-agenda1024`; worktree `C:/Users/usuario/AppData/Local/BAXY/C03-agenda1024-worktree`. Sólo cambia `src/baxy_mind/effect_intent.py` (+29/−14); no __main__.py, llm.py, catálogo ni fuente canónica.

Hereda `C:/Users/usuario/AppData/Local/BAXY/C03-agenda1023-proposal/DIAGNOSIS.md`, SHA256 `3672e4a5be992285989f4e273c12c9a3ddc133065f6ef64d0458b5cfe4046fa4`. En1021 H0121/request26→arguments27 y H0343/request32→arguments33 conservaron reminder.create, pero terminaron preguntando tiempo y contenido. La gramática de recordatorio sólo temporal requería el sustantivo recordatorio/reminder, de modo que avisame+duración no alcanzaba la aclaración específica de title.

La propuesta extrae SIN modificar el patrón de duración de `_reminder_has_actionable_due` a `_REMINDER_RELATIVE_DURATION` y sustituye el patrón inline por esa referencia. `_time_only_reminder_request` reutiliza esa misma duración para una petición completa de aviso/recordatorio sin título, con verbos ya reconocidos en `_SCHEDULING_BY_ITSELF`, cifras o palabras y cortesía opcional. El caller añade esas cabezas únicamente cuando el cuerpo completo demuestra que sólo se proporcionó tiempo. Reutiliza `ClarificationIntent(("reminder.create",), ("title",))`; no pregunta due_time ni entrega argumentos ejecutables.

El objetivo original no se recorta, traduce ni reconstruye. `__main__.py:5855–5859` continúa entregándolo íntegro a `formulate_explicit_clarification_question`, junto a operaciones/campos faltantes; la ruta de objetivo pendiente permanece existente, incluido `startsNewObjective` bajo su guarda de autoridad. Así no se borra la duración para la continuación ni se convierte en un instante inventado. La conservación efectiva tras recibir el título requiere medir esa continuación en el producto; no se afirma que esté verificada por esta revisión.

Revisión manual del diff: las ramas anteriores de reloj/fecha y sus condiciones permanecen; la nueva rama exige coincidencia completa, excluyendo título ya aportado, negación, condiciones, cita y una segunda acción. El frame no-acción y el filtro de petición directa se mantienen. No introduce nombres de personas, contenidos, cantidades o frases del panel como reglas. No cambia la política temporal ni autoriza una duración inválida a ejecutar: sólo pide el dato ausente; los validadores finales se conservan.

Fuera de alcance: H0011, H0043 y el fallback transversal de llm. Dos literales potenciales, sujetos a criterios y pares; cero adjudicación o crédito. Pruebas, imports, AST, builds, GPU, HTTP y efectos omitidos por instrucción explícita; sólo lectura estática, edición y revisión manual. No commit/push ni adopción.

SHA256:
- Base effect_intent.py: `3bb83dc8f0c8736c86d402d0faf656915044a9089b8b27b9b9a430b36365cade`.
- Propuesta effect_intent.py: `868a2e327e81197093f62510b3d0091987b52b7222d552d72486d63d88929b1b`.
- repair.patch: `b45ff88467f3ea281fb59520687a59bc7b96ad8e5f0f6f507807aa92ea4dd493`.
