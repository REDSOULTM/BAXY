---
name: screenshot-and-analyze
description: Take a screenshot, run vision/OCR on it, report what's visible. Use when user asks "qué ves", "leé la pantalla", "describí lo que aparece", or when an action needs visual verification before/after.
priority: medium
metadata:
  examples:
    - "sacá una captura y describime qué ves ahí"
    - "tomá un screenshot y leeme el texto que aparece"
    - "hacé un pantallazo y contame qué se ve"
    - "take a screenshot and describe what you see"
    - "faça uma captura de tela e me diga o que aparece"
  when_to_use:
    - "el usuario quiere que mires la imagen en pantalla y le cuentes el contenido"
    - "hace falta verificar visualmente qué hay en una ventana"
  limitations:
    - "no es para subir o bajar el brillo de la pantalla"
    - "no es para poner un video en pantalla completa"
    - "no es para imprimir un documento en la impresora"
    - "not for changing screen brightness or printing a document"
requires:
  os: [windows]
---

# Screenshot and analyze

Tools: `gui`, `vision`, `window` (opt). Honesty-critical: SÍ — solo reportar lo que vision/OCR realmente extrajo. Nunca inventar texto que no aparece.

Usar cuando: "qué ves en pantalla", "leé lo que dice", "describí esta ventana", "qué botones hay", "buscá el botón X". O implícitamente cuando otra acción necesita verificación visual (ej. tras un click no verificable con `verify`).

## Steps

1. **Identificar target.** Si menciona una ventana específica: `window(action="focus", title="<query>")` (la trae al frente antes de capturar). Si window NO existe, NO continuar — preguntar qué ventana mirar.
2. **Screenshot.** `gui(action="screenshot", monitor="primary")`. Opciones: `"primary"` (default, solo monitor primario), `"all"` (VirtualScreen multi-monitor), `0`/`1`/etc (índice). El verifier chequea que el PNG existe en disk y tiene >1000 bytes (no es captura vacía). Si `confirmed=False`, NO continuar.
3. **Análisis visual / OCR** (según lo pedido):
   - 3a. **Describir contenido general**: `vision(action="describe_screen", image_path="<path>")` — Gemma 4 multimodal lee y describe. Pasar el `image_path` de `gui.screenshot`.
   - 3b. **Buscar un elemento específico**: `vision(action="find_element", image_path="<path>", target="<descripción>")` — devuelve coordenadas si lo encuentra. Útil antes de un click.
   - 3c. **Solo OCR (texto literal)**: `vision(action="ocr", image_path="<path>")` — devuelve texto plano. NO interpretarlo, solo transcribirlo.
4. **Reportar**: **qué se ve** (descripción de vision o texto OCR); **confianza** (vision puede equivocarse; si la imagen es ambigua o el target no está claro, decirlo); **path del screenshot** (el usuario puede querer verlo).

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Screenshot OK + vision describe contenido | "Veo [descripción]. Captura en `<path>`." |
| Screenshot OK + vision no encuentra target | "Tomé la captura pero no veo '<target>' en pantalla. Path: <path>. ¿Estará en otra ventana o monitor?" |
| Screenshot OK + OCR vacío | "La captura no tiene texto legible. ¿Querés que pruebe con vision (describe) en vez de OCR?" |
| Screenshot file missing tras capture | "La captura falló silenciosamente (no se escribió el PNG). Probablemente captures_dir sin permisos." |
| Window no encontrada | "No veo ventana con título '<query>'. Las visibles son: [list de window.list]." |

## Anti-patterns

- ❌ Inventar texto que OCR no extrajo.
- ❌ Decir "veo X" si vision retornó `confirmed=False`.
- ❌ Reportar coordenadas de `find_element` que no aparecen en el resultado.
- ❌ Tomar screenshot del monitor secundario cuando el usuario hablaba del primario.
- ❌ Hacer screenshot de información sensible (contraseñas, tarjetas) sin advertir.
