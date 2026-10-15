# BAXY Renew — notas del notebook (REDNOTE, apoyo)

Rama `renew-nb`. El estado estructurado lo lleva el líder en `metas.json`; aquí van las notas del apoyo.

## 2026-10-15 — arranque

- Notebook: RTX 3060 Laptop 6 GB. GGUF `D:\BAXYRuntime\experiments\models\qwen35-4b-e87f1764\Qwen3.5-4B-Q4_K_M.gguf`,
  llama-server en `D:\BAXYeval\llama`, banco en `D:\BAXYeval\renew_bench`.
- `catalog.configure.json` copiado del PC a `%LOCALAPPDATA%\BAXY\renew\` (sha256 `2d3cf7e2…e693`), porque el banco
  lo lee de ahí.

## Ronda 1 medida (banco de práctica `cases.json`, 90 casos, en el notebook)

| Corrida | Código | Resultado | p50 | p90 |
|---|---|---|---|---|
| `en02v2` (PC) | antes de la ronda 1 | 85/90 | 0,74 s | 1,16 s |
| `r1-nb` (notebook) | `bd6a4ba3` (ronda 1) | 80/90 | 0,80 s | 1,27 s |

- Gana R13 y R61. Pierde R46 («skipea esta song» → `media.status`), R72 y R74 (debían preguntar; actuó), y
  R86/R88/R89/R90: pedidos imposibles (uber, rappi, transferir, llamar por teléfono) que ahora reciben una pregunta en
  vez de «eso no lo hago».
- **El mismo código anterior a la ronda 1** (`7fbf1ce38`, corrida `pre-r1-nb`) da **82/90 en el notebook**, contra
  85/90 en el PC. Fallan R13, R25, R34, R61, R72, R82, R86 y R90.
- **Conclusión:** entre corridas hay ±3 casos de ruido, porque se decide a temperatura 0,2 sin semilla fija. La ronda
  1 (80) no es peor de forma demostrable que la anterior (82) en la misma GPU.
- **Recomendación para el marco:** semilla fija (`seed` en el cuerpo de la petición) o varias corridas por variante
  antes de comparar.

## Falsedades del uso real (2026-10-15 01:45–01:55, PC)

Fuentes: `conversation.v1.jsonl`, la traza `renew/turns.jsonl` y el journal firmado `journal/missions.jsonl` del PC.

**Lo que dice el journal:** todas las acciones de esa sesión se ejecutaron y quedaron verificadas por el proveedor
(app.open Steam, ya abierto; los cuatro cambios de volumen 36→26→16→46→30; Chrome con la búsqueda; YouTube en
Opera GX; Gmail y el clic en «Recibidos»; las dos `browser.navigate` a la tienda de Steam). La ruta `conversation` del
registro no significa «sin herramientas»: es la ruta del texto final que el modelo escribe dentro del bucle.

**Las falsedades reales:**

1. **Negar lo hecho y prometer sin llamar.** Ante «no lo hiciste», el modelo respondió sin herramientas «Tienes
   razón, no lo hice. Lo siento. Voy a abrir Steam y buscar Doom Eternal ahora mismo». Las dos acciones constaban
   como verificadas en el journal.
2. **Repetir una acción ante una queja.** Ante «no lo bajaste mentiroso», volvió a bajar el volumen (26→16).
3. **Una URL inventada y contada como hecho.** Inventó la URL de la tienda con appId 1046000 y luego 281390. El
   proveedor sólo verificó la barra de direcciones, así que «te llevé a la página de Doom Eternal» no estaba
   verificado. Además, el dueño pedía el cliente de Steam, no el navegador.
4. **Un plan pendiente que se traga la orden nueva.** Con la confirmación de `app.close {"windowId":"18titans"}`
   pendiente, «cierra 18titans» y «cierra chrome» no llegaron al modelo. `MindPlanSession` pasó el texto por
   `ConfirmationReplyParser` (regex), vio que no era «sí» y re-publicó la confirmación. La redacción convirtió esos
   hechos en «No puedo cerrar Chrome porque mi última orden pendiente era…». Esto es el arnés de confirmación que el
   dueño decidió reescribir (botones Sí/No; por voz, el modelo interpreta con una herramienta, sin regex).
5. **Tono:** «¡Listo!», «Lo siento» y «¿Te gustaría…?» en casi cada respuesta, contra la identidad (sin disculpas
   ni relleno).

**Causa probable de 1–2:** entre turnos, la mente rearma el historial sólo con el texto de usuario y asistente
(`mind.decide`, `history[-13:]`). Las llamadas y los resultados verificados de los turnos anteriores se pierden, así
que ante «no lo hiciste» el modelo no tiene la evidencia y le da la razón a la persona. Arreglo candidato
(protocolo): conservar en la conversación de la mente los mensajes `tool_calls` y `role:"tool"` de los turnos
recientes. Investigación en curso (BFCL multiturno, documentación de Qwen y OpenAI, plantilla de Qwen3.5).

**El arreglo espera a que el líder selle los holdouts:** ajustar el prompt o el protocolo antes del sello
contaminaría el marco.
