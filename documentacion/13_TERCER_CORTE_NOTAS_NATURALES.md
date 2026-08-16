# Tercer corte productivo: notas naturales ES/EN/spanglish

Estado del corte: implementado y verificado en `c1c07ff`. Reduce B-004, pero no
lo cierra. No añade voz, conversación general, composición multioperación,
instalador ni aceptación física.

## Alcance exacto

La GUI WPF puede crear, listar, leer, enviar a la papelera y restaurar notas con
gramáticas finitas en español, inglés y spanglish. Ejemplos:

- `anota comprar leche`;
- `create a note called Groceries with buy milk`;
- `show me my trashed notes`;
- `lee la nota Compras`;
- `delete the note called Compras`;
- `restaura la nota Compras de la papelera`.

El parser no ejecuta texto libre. Negaciones, condicionales, bulk, selectores
múltiples, controles, UTF-16 malformado, rutas/archivos y composiciones con
recordatorios quedan fuera. El título y contenido viajan como JSON de datos;
ninguno se convierte en ruta, argumento de proceso o comando.

## Oráculo histórico

La auditoría de `note.manage` separó un denominador limpio de creación de nota
standalone:

- 40 mensajes únicos de `product_1_0`;
- 13 literales distintos;
- 49 ocurrencias de procedencia;
- 40/40 enrutan a `note.create`;
- siete negativos congelados de filesystem, documentación, conversación y
  nota+recordatorio no enrutan en esta slice.

Esta cifra no significa 40/40 de todo `note.manage`. Hay 65 filas de producto
que contienen esa operación y la misión consolidada está contaminada por
archivos, composiciones, requisitos amplios y ruido. Inflar el denominador o
declarar cerrada esa misión sería incorrecto.

## Grounding y replay

Las notas rápidas derivan un título determinista del contenido. Se normaliza
Unicode Form C, se colapsa espacio horizontal y se limita a 120 bytes UTF-8 sin
cortar una runa. Los selectores admiten como máximo 512 bytes.

`note.read` exige una única coincidencia activa exacta, ignorando mayúsculas.
`note.trash` y `note.restore` exigen una única coincidencia exacta entre activas
y papelera. La búsqueda y la mutación ocurren bajo el mismo lock del store. Si
un retry encuentra que la única nota ya alcanzó el estado objetivo, devuelve
ese estado sin incrementar la revisión.

Dos notas con el mismo título producen `note_ambiguous`; ninguna se modifica.
Este comportamiento evita actuar sobre la nota equivocada, pero la GUI todavía
no ofrece shortlist o selección para resolver la ambigüedad. Es un P2 y límite
de producto explícito.

El fault injection interrumpe el completion del journal después de los efectos
de trash y restore. La repetición con la misma identidad mantiene las revisiones
2 y 3, completa el resultado y permite que el intento siguiente sea replay. Las
respuestas mutantes describen estado verificado —en papelera o activa— y no
afirman de nuevo que el retry causó el efecto.

## Frontera y respuesta

El saludo debe contener exactamente una vez las seis capacidades interactivas
usadas por el shell y el riesgo esperado. Una capacidad ausente, duplicada o
con riesgo distinto impide habilitar la entrada. `app.status` solo acepta `{}`
y el core valida al arrancar que ProductCatalog coincida con OperationRegistry.

La proyección de `note.read` presenta título y contenido, no JSON crudo. La
vista se limita a 16.384 caracteres; si excede el límite, declara truncamiento
y conserva una frontera UTF-16 válida.

## Evidencia ejecutada

| Evidencia | Resultado |
|---|---:|
| Oracle creación standalone | 40/40 mensajes únicos |
| Contratos .NET | 23/23 |
| Kernel .NET | 26/26 |
| Provider Windows .NET | 60/60 |
| Integración .NET | 228/228 |
| Total .NET Release | 337/337 |
| Python canónico | 59/59 + 148 subtests |
| Corpus específico | 36/36 + 54 subtests |
| Total conjunto principal | 396/396 |
| Formato/diff | limpio |

El E2E automatizado real atraviesa ViewModel→core→store y completa
create/read/trash/list/restore/list. No muestra JSON, deja el outbox vacío y,
tras cerrar el core, una instancia independiente confirma una nota activa con
contenido exacto y revisión 3.

La auditoría adversarial no encontró P0/P1. Detectó un surrogate UTF-16 aislado
que podía escapar como excepción; se corrigió con rechazo seguro y regresión.
El único hallazgo abierto de la slice es la desambiguación de títulos duplicados.

## Límites

- Las notas y el outbox siguen en texto plano, sin cifrado/HMAC.
- No hay voz, composición general ni memoria completa.
- No existe UX para duplicados ni operación de renombrado.
- El build distribuible del segundo corte no fue regenerado; no es instalador.
- No hay nueva evidencia física de accesibilidad, GPU 4 GB o VM limpia.
- Must 4, 9 y 13 avanzan, pero permanecen pendientes; B-004/B-005/B-006 siguen
  abiertos.
