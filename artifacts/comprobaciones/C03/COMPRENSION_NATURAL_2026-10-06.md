# COMPRENSION_NATURAL_2026-10-06 — Fase 3.5b «comprensión natural», segunda vuelta: cierre

Rama `codex/kiro-goal-c03`. Goal: `GOAL_COMPRENSION_NATURAL_v3_2026-09-28.md` (con las reglas de v2). Decisiones de la
vuelta: D32–D80 en `DECISIONES_COMPRENSION_2026-09-25.md`; mapa de la semántica: `documentacion/SEMANTICA.md`
(sección «Segunda vuelta»). Producto medido: Qwen3.5-4B Q4_K_M (Apache-2.0) + LoRA del decisor `full3`, commit
`99d7d146` (v5f: M42–M179). El FINAL-2 se corrió **una sola vez**, en la App real, el 06-10 de 11:16 a 11:37, por
decisión del dueño (D80) tras seis medidas de DEV-E entre 266 y 268.

**Veredicto: el goal no se cumple.** El FINAL-2 da **67,8 %** con el revisor independiente (meta 85 %) y **83,1 %**
con la puntuación automática (meta 90 %; estricta 82,2 %). Frente al cierre anterior (FINAL del 28-09: 56,9 % revisor,
74,3 % automática) son +10,9 y +8,8 puntos, sobre un conjunto nuevo y más largo. Se cumplen VRAM, latencia, cien,
held-out, guion, reserva, 742 y Full; no se cumplen revisor, automática, inventados, repreguntas ni ⚠.

## 1. Resultado por meta

| meta | valor al cierre | meta | estado |
|---|---|---|---|
| FINAL-2 revisor independiente (App real, 338 turnos) | **67,8 %** (229/338) | ≥ 85 % | no |
| — sueltos / conversación / seguimientos (revisor) | 63,2 % / 70,4 % / 69,7 % | | |
| FINAL-2 automática (D61/D71/D73/D78) | **83,1 %** (281/338; estricta 82,2 %, 278) | ≥ 90 % | no |
| — sueltos / conversación / seguimientos (automática) | 78,4 % / 85,9 % / 79,4 % | | |
| inventados (revisor) | **14** | 0 | no |
| repreguntas de un dato ya dado (revisor) | **12** (3,6 % de los turnos; 10 % en el FINAL del 28-09) | 0 | no |
| ⚠ sin respuesta (error o nada publicado) | **1,2 %** (4/338) | ≤ 1 % | no (por 1 turno) |
| VRAM de BAXY (pico por proceso, FINAL-2) | **3 792 MiB** | ≤ 3 800 MiB | sí |
| latencia de decisión p50 / p90 (FINAL-2) | **1,97 s** / 6,67 s | p50 ≤ 3 s | sí |
| DEV-E (sellado, sólo agregados) | 268 / 266 (v5f); 266–268 en v5c–v5f | ≥ 269/299 | no |
| guion del dueño | 52/60 automático + 5 revisados = **57/60** (v5f) | ≥ 53/60 | sí |
| held-out | **29/30** | ≥ 29/30 | sí |
| cien | **100/100** (v5f) | 100/100 | sí |
| reserva MASSIVE | **94,0 %** (v2; 90,0 % en v1), 0 cambios frente a v5d | ≥ 88 % | sí |
| capa A (registro real) | 0 decisiones distintas frente a v5d | ≥ 96 % | sin cambios |
| 742 | 0 decisiones distintas frente a v5d | sin cambios sin revisar | sí |
| Full (código de v5f) | pytest 23 898 + 39 repetidos con sus datos, Integración 4 091, Kernel 194 | verde | sí |

Notas de medida: la puntuación automática se informa con la capa del dueño (D61: aceptadas y D35; D71 lo hecho con
otras palabras; D73 la pregunta donde el oro acepta preguntar; D78 el aviso a la hora que dio BAXY) y estricta. El
revisor fueron dos agentes independientes con el mismo encargo (`brief/REVISOR_FINAL.md`), cada uno con la mitad del
paquete cortada entre conversaciones; ninguno escribió ni arregló BAXY. ⚠ se cuenta igual para las dos mitades
(error no nulo o nada publicado); además 18 turnos salieron por la ruta de error con una respuesta publicada. Tres
turnos de Netflix fallan porque Netflix no tiene sesión en este PC (decisión correcta, dicho en llano): sin ellos el
revisor daría 232/338 = 68,6 %.

## 2. Qué cambió desde el cierre del 28-09

1. **Medida limpia.** FINAL-2 (338 turnos, sellado, sala limpia) y DEV-C…DEV-I; DEV-E sellado como medidor
   imparcial antes del FINAL-2 (D55). Todo se mide en la App real (`scripts/comprension_window.py`, ventana guardia,
   audio y brillo restaurados, VRAM por proceso), no sólo en la mente.
2. **BAXY ayuda, nunca es un lastre** (dueño, D58). Cada lector y guarda se midió contra el decisor solo; los que
   restaban se estrecharon o se quitaron. Con historial escrito y el saludo delante, el lastre del código casi
   desapareció en G/H/I (0–2 turnos).
3. **Mecanismos M42–M179** (detalle en D36–D80): argumentos y horas en lo que dice la persona; avisos «N antes de» y
   mover el aviso propio; lectores de conversación sobre lo que BAXY acaba de preguntar u ofrecer; búsqueda
   automática sin claves (D32), divisas, horarios de ESPN (D77); límites falsos fuera; una aclaración ya no lleva
   operaciones de efecto (la App respondía «mi mente no está disponible», M177).
4. **VRAM** de ≈ 4 000 a 3 792 MiB (caché KV cuantizada y contexto por hueco 10 240, D41–D43) sin pérdida.
5. **Estabilidad del PC.** Dos apagados el 05-10 (batería crítica bajo carga; controlador de NVIDIA) → guarda
   `power_wait.sh` antes de cada trabajo de GPU; sin más apagados.

Evolución de DEV-E (299 turnos, sellado): 236 (v4j, 02-10) → 256–263 (v4r–v4z) → 265–268 (v5a–v5f). Los conjuntos
iterables en v5f: DEV-H 96,7 %, DEV-D 95,2 %, DEV-I 95,0 %, DEV-G 94,7 %, DEV-F 90,7 %.

## 3. Lo que queda, por causa (FINAL-2, revisor; 109 turnos no-ok)

| causa | turnos (≈) | ejemplo | ¿del modelo base? |
|---|---|---|---|
| no contesta lo pedido o lo dice mal | 18 | «tradúzcamelo al inglés» → parafrasea en español | en parte (redacción del 4B) |
| malinterpreta el pedido o hace otra cosa, erratas tomadas literal | 15 | «hazme una foto en panorámica» → captura de pantalla; «pan lecge» guardado tal cual | mixto |
| hechos de memoria falsos o inventados, sin buscar | 13 | libros inventados de Allan Kardec; «2100 es divisible por 400» | sí (conocimiento del 4B) + falta buscar |
| acción que no se logró o error | 12 | Netflix sin sesión (3, entorno); YouTube que no sonó | no (entorno y proveedores) |
| búsqueda que no entrega nada («No encontré…») | 12 | tienda de zapatos con descuento; aparcamiento | no (fuente de búsqueda) |
| repreguntas y preguntas de más | 14 | «set an alarm for 1105» → «What time…?» | no (argumentos) |
| pierde el contexto o el lugar del seguimiento | 11 | «y en cdmx» → clima de Curicó | mixto |
| dato propio buscado en la web, idioma | 4 | la factura de gas de la persona buscada en la web | no |

Al menos ≈ 70 de los 109 fallos son de mecanismos (argumentos, contexto, búsqueda, entorno), no del modelo base; los
de conocimiento del 4B (≈ 13 más parte de la redacción) piden buscar antes de afirmar o un modelo mejor dentro de 4 GB.

## 4. Pendiente

- **M180** (`opus/m180-subele-no-es-saltar`, sin integrar): «súbele un toque» pasaba de canción; probado sin
  cambios en las 742. Entró después de la decisión de correr el FINAL-2 y no se midió en la App.
- **M176b** («pon algo para dormir» → música): espera la decisión del dueño (invierte una regla de la tanda 4).
- El FINAL-2 ya está usado: otra medida final exige un conjunto nuevo sellado.
- Los fallos del FINAL-2 son ahora material de desarrollo (sus ids y notas en `REVIEW.reviewed.jsonl`).

## 5. Cómo reproducir

- Conjuntos (fuera de git): `%LOCALAPPDATA%\BAXY\comprension-2026-09-25\sets\` (FINAL-2 `0f497ea2…d312`, 338 filas).
- App real: `scratchpad/cn/set_after.sh <tag> <marcador> <regex> <conjunto>` (guarda de energía y GPU, ventana
  guardia, VRAM por proceso, audio y brillo restaurados) → `window/<tag>/RUN.jsonl`.
- Puntuación: `scripts/comprension_eval.py score --set sets/FINAL-2.jsonl --run window/final2-once/RUN.jsonl --audit
  window/final2-once/turn-audit.jsonl --blind --accept sets/ACCEPT-D61.jsonl --d35`.
- Revisión: `scripts/comprension_window.py review` → `window/final2-once/REVIEW.jsonl`; revisado en
  `REVIEW.reviewed.jsonl` (mitades `REVIEW.partA/partB.reviewed.jsonl`).
