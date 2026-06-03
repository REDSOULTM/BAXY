# Computer Use Capability Layers

Objetivo: ampliar compatibilidad por capas sin prometer control perfecto sobre
apps arbitrarias. El agente debe preferir superficies estructuradas, verificar
cada accion relevante y fallar honesto cuando una app no expone API/UIA/AX util.

## Orden De Capas

1. App/API specialist
   - Usar adaptadores de dominio cuando existen: navegador estructurado,
     Discord, launchers, mensajeria, archivos, etc.
   - El adaptador debe exponer operaciones cerradas y verificador propio.

2. Browser protocol
   - Para navegadores Chromium visibles, preferir CDP/browser_real: DOM,
     accessibility tree, texto de pagina, navegacion y acciones por selector o
     nodo accesible.
   - No usar coordenadas si hay DOM/accessibility tree disponible.

3. UI Automation
   - Para apps Windows nativas, usar UIA Control Patterns: Invoke, Value,
     Toggle, Selection, Scroll.
   - UIA parcial/degradada no es exito; pasa a OCR/vision y exige verificacion.
   - Si un campo no expone ValuePattern, UIA no debe caer a SendKeys oculto.
     Debe devolver error verificable para que el ejecutor decida el fallback.

4. OCR
   - Usar OCR para localizar texto visible cuando API/UIA no exponen controles
     utiles. OCR es localizador, no verificador suficiente por si solo.
   - OCR solo se ofrece como capa si Tesseract esta disponible en PATH.

5. Vision fallback
   - Vision se usa como ultimo recurso para interpretar pantalla o confirmar
     estado visual. Clicks visuales deben tener verificacion posterior.
   - Vision solo se ofrece si el registry expone la tool `vision`.

6. Honest fail
   - Si ninguna capa puede verificar el resultado, responder que se intento y no
     se pudo verificar. No decir "listo" ni pedir al usuario que revise/clickee
     en movilidad/no_vidente.

## Contratos De Calidad

- Ninguna accion de escritura debe considerarse completa sin verificador
  estructural, textual o visual.
- `capabilities_before`, `capability_family` y `capability_policy` deben quedar
  en cada paso trazado.
- No hay clicks de pixel "a ciegas": `allow_blind_pixel_click` debe permanecer
  en false.
- No se escribe texto despues de un click no verificado.
- `type` usa la ruta verificable `type_into`; si no se verifica, no se envia.
- Las evals por tiers deben correr en dry-run por defecto. Los tests live de GUI
  requieren perfil descartable y opt-in explicito.

## Fuentes

- Microsoft UI Automation Control Patterns:
  https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-control-patterns-overview
- Chrome DevTools Protocol Accessibility domain:
  https://chromedevtools.github.io/devtools-protocol/tot/Accessibility/
- W3C WebDriver BiDi:
  https://www.w3.org/TR/webdriver-bidi/
- OSWorld benchmark:
  https://arxiv.org/abs/2404.07972
- OSUniverse benchmark:
  https://arxiv.org/abs/2505.03570
