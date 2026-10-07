# Computer use — cobertura, latencia y procedimientos (medido 2026-10-06)

Medido en vivo en el PC del dueño con la App real (`Baxy.exe --conductor`, mismo turno que la UI), Qwen3.5-4B
Q4_K_M + LoRA `full3`, pantalla 1536×864 lógicos al 125 %. Trazas por misión (`BAXY_APP_TRACE`) en
`%LOCALAPPDATA%\BAXY\cu-universal-evidencia\<misión>\trace.jsonl`, fuera del repo. Resultado de cada misión:
`PROGRESO.md`.

## Cobertura por tipo de aplicación

| Tipo | Probado en vivo | Cómo ve el motor la ventana | Estado |
|---|---|---|---|
| Win32 clásico | Panel de control → «Sistema y seguridad» | árbol UIA completo (32 controles) | logrado, 2 pasos, título verificado |
| UWP / WinUI | Calculadora (12×7), Reloj → Cronómetro | árbol UIA dentro de ApplicationFrameHost | logrado; `app.open` de la Calculadora no se verifica (marco UWP) y el motor lo tolera si queda delante |
| Electron | Discord (Enter en un MD; canal de voz) | árbol UIA de Chromium (60 controles) | Enter logrado por el motor; el canal lo resuelve la operación tipada `client.channel.locate` — el 4B no lo encontró pulsando por la lista |
| CEF sin árbol | Steam → Biblioteca | 1 control + líneas OCR | logrado tras 6 arreglos generales: clic OCR de varias palabras, menú abierto por el clic, llegada `page:`, ventana tapada al abrir |
| Navegador de la persona (Opera GX) | ir a la pestaña de YouTube; cerrar todas; HBO Max | pestañas `TabItem` por UIA; categoría «navegador» | pestaña por el motor; cerrar todas y streaming por sus operaciones tipadas |

## Latencia por paso

| Parte | n | p50 | máx | Nota |
|---|---|---|---|---|
| Vista (`input.visible.controls`, UIA + OCR) | 34 | 0,67 s | 1,9 s | la primera de cada misión ≈ 1,1–1,9 s (arranque del worker y OCR completo) |
| Decisión del modelo (`computer.use.step`) | 30 | 2,7 s | 5,2 s | sólo cuando la mente no dicta el paso; ≈ 830 tokens de entrada, ≈ 130 de salida |
| Paso dictado sin modelo | 13 | < 0,02 s | | tecla, escribir, calcular, clic en el control nombrado, pestaña, entrada de menú |
| `input.visible.click` | 12 | 1,2 s | 3,2 s | incluye la postlectura (superficie antes/después) |
| `input.key.press` / `input.text.type` | 5 | 0,67 s | 0,69 s | |
| `app.open` | 3 | 1,0 s | 1,9 s | reutiliza la ventana que ya corre |

Misiones completas del motor: Discord Enter 2,9 s; Calculadora 3,6–3,9 s; pestaña de YouTube 4,9 s; Panel de
control 5,6 s; Steam 9,3 s (una decisión del modelo). El turno visible suma ≈ 1,5–2 s de comprensión y
composición.

## Memoria de procedimientos

| Caso | Aprendiendo | Reproduciendo | Ahorro |
|---|---|---|---|
| Calculadora abierta, «calculá 12×7» | 3 913 ms (modelo 67 ms) | 3 559 ms (modelo 0 ms) | −354 ms (−9 %) |

El ahorro es pequeño porque la mente ya dicta sin modelo los pasos obvios; los procedimientos sólo pesan
cuando el modelo decide (Steam: 4,5 s de modelo por misión). Dos fallos de diseño hallados y corregidos al
medir:
- se aprendía descartando los pasos fallidos (Steam aprendió un clic sin sentido): ahora una misión con un paso
  fallido no se aprende (contrato §5), salvo una apertura UWP que no verifica;
- un procedimiento sin su apertura se reproducía sobre la ventana de delante (la Calculadora habría escrito en
  el editor): ahora sólo se reproduce sobre la ventana de la aplicación (`window.requested`) o cuando el paso
  es abrirla.

## Límites medidos

- El 4B elige mal cuando el destino no está a la vista y hay que buscarlo (Discord: 6 clics por la lista sin
  hallar el canal). Las rutas tipadas del catálogo cubren esos casos; no se cambió el modelo.
- En ventanas sin árbol la llegada se comprueba por texto (`page:`): una página cuyo texto cambie poco tras
  navegar no se daría por alcanzada (falso negativo honesto, nunca falso éxito).
- «cerrá todas las pestañas de <navegador>» actúa sobre el navegador predeterminado (`APLAZADOS.md`).
