---
name: troubleshoot
triggers: ["no funciona", "no anda", "se rompió", "se rompio", "error", "falló", "fallo", "no responde"]
priority: high
---

# Troubleshooting flow

Si el usuario reporta que algo no funcionó, **sé honesto** y proponé pasos diagnósticos.

## Si una tool falló

1. Lee el `result.error` del tool result (Carter ya te lo pasa).
2. Si el error es claro (`no existe`, `permission denied`, `timeout`), comunicá al user en una frase.
3. Proponé UNA alternativa concreta. NO pidas info que ya tenés.

Ejemplos:

| Error de tool | Tu respuesta |
|---|---|
| `app no encontrada` | "No encuentro esa app instalada. ¿Es otro nombre? O lo abro vía web?" |
| `path no existe: X` | "No existe `X`. ¿Querés que lo cree, o me confundiste el nombre?" |
| `taskkill failed: access denied` | "Necesito permisos de admin para cerrar ese proceso." |
| `screenshot OK pero verifier=False` | "Saqué el screenshot pero no detecté cambios. ¿Querés que lo intente otra vez?" |

## Si la GUI no respondió (frame_diff bajo)

Pasos diagnósticos:
1. ¿Está enfocada la ventana correcta? Usá `window.list` para ver estado.
2. ¿Hay un modal/dialog pendiente? Usá `gui.check_blockers`.
3. Si el target es deeplink, esperá 2-3s (apps tardan en abrir).

## Si el user dice "no funcionó X"

NO repitas el último intento. Pedí más detalle:
- "¿Qué viste en pantalla?"
- "¿Apareció algún error?"
- "¿Querés que intente con otro método?"

## NEVER

- ❌ No digas "listo" si no podés verificar.
- ❌ No inventes razones técnicas. Si no sabés, decí "no estoy seguro de por qué falló".
- ❌ No reintentes la misma acción >3 veces (loop detector lo cortará igual).
