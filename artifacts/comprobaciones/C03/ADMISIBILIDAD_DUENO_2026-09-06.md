# C03 — confirmación de admisibilidad de tres turnos

En esta tarea01a07974-2a33-7ed3-ba87-2436944e8115 se preguntó al dueño si los
siguientes turnos de Probando Gemma4 los había escrito él o los había lanzado una
prueba automática. Se explicó que el log guarda texto/hora, pero no quién lo
introdujo. Su respuesta literal fue: **«Son turnos validos»**.

- `is Spotify open?` —2026-06-20,17:12:33−04:00, traces.jsonl:26924.
- `open steam` —2026-06-23,01:33:04−04:00, traces.jsonl:30039.
- `open the file explorer` —2026-06-25,19:46:28−04:00 y19:47:56−04:00,
  traces.jsonl:50320/50693; hay más ocurrencias conservadas en el pool.

Decisión: admitir estos tres textos para la selección conforme a la confirmación
expresa del dueño. No extender esa confirmación a todos los742 registros ni
inventar metadatos de autor. La reserva conservará texto literal y contexto de
la ocurrencia elegida. La auditoría45 no detecta exposición a C03, código de
regresión examinado ni recuperación del runtime para estos tres; `open steam`
sí aparece en prueba histórica y corpus curado, y `open the file explorer` en
corpus curado. Eso queda anotado, sin afirmar independencia del preentrenamiento.

El cotejo de fuente y hashes está en el informe privado enlazado desde
RESERVE_PROVENANCE_AUDIT45.json. Esta adjudicación de procedencia no es un
resultado del producto ni acredita todavía la reserva100.
