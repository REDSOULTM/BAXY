# Decisión: modelo de visión para íconos y ventanas sin árbol (v3, punto 3)

Para el dueño. La decisión es tuya y no bloquea el resto del goal.

## El problema

Steam (CEF) y otras ventanas sin árbol, juegos y lienzos dan ≤ 1 control. Hoy BAXY pulsa ahí
por OCR (texto visible); un botón que es sólo un ícono (engranaje, campana, papelera, «⋯») no
tiene texto y no se puede pulsar. Lo que se puede sacar sin modelo (nombre de respaldo por
HelpText/AutomationId, tooltips por UIA, OCR de tooltips en una pausa tuya, Steam con
`-cef-force-accessibility`) va por separado y no necesita esta decisión.

## Límites

- VRAM total ≤ 3,8 GB. El 4B (Qwen3.5-4B Q4_K_M, 3 ranuras) ya usa ≈ 3,6–3,9 GB. GPU: RTX 3060
  Laptop de 6 GB. En la GPU no cabe nada nuevo.
- CPU: Ryzen 7 5800H (8 núcleos), 15,4 GB de RAM (≈ 3 GB libres con tu sesión abierta).
- Licencia Apache-2.0 o MIT obligatoria. Nada sale de la PC.

## Opciones

| Opción | Tamaño / dónde corre | Latencia | Precisión publicada | Licencia | Veredicto |
|---|---|---|---|---|---|
| **A. El mismo Qwen3.5-4B + su `mmproj` en CPU** | +672 MB en RAM, 0 MB más de VRAM; el texto del modelo sigue en GPU | codificar en CPU (medido con el codificador del 2B, de igual tamaño): **1,3 s** con un recorte de zona (144 tokens), 3,6 s con 364 tokens, 9,5 s con 760, 19,8 s con la ventana entera (1 248); más ≈ 0,5–0,8 s de lectura en GPU (estimado) | **ScreenSpot-Pro 60,3**, OSWorld-Verified 35,6 (ficha oficial del modelo) | Apache-2.0 | **Recomendada** |
| A′. Lo mismo con el `mmproj` en GPU | +≈ 0,7–1 GB de VRAM → ≈ 4,6 GB | < 1 s estimado | igual | Apache-2.0 | Pasa el tope de 3,8 GB: sólo si decides subirlo |
| B. UI-TARS-2B (SFT) | 2B, ≈ 1,5 GB en Q4 + su visión; segundo modelo en RAM/CPU | CPU: decenas de s por captura (estimado: dos modelos de 2B en CPU) | ScreenSpot 82,3 · v2 84,7 · **Pro 27,7** | Apache-2.0 | Peor que A y cuesta más RAM |
| C. UGround-V1-2B | igual que B | igual que B | **Pro 26,6** | Apache-2.0 | Peor que A |
| D. ShowUI-2B | igual que B | igual que B | ScreenSpot 75,1 · **Pro 7,7** | MIT | Descartada por precisión |
| E. OS-Atlas-Base-4B / 7B | 4B / 7B | más lento que B | Pro **3,7** / 18,9 | Apache-2.0 (según su ficha) | Descartada |
| F. GUI-Actor-2B | 2B (base Qwen2-VL) | igual que B | Pro 36,7 · v2 88,6 | revisar (código MIT; base Qwen2-VL Apache) | La mejor de las de 2B, pero bajo A |
| G. OmniParser v2: detector + descripción | detector YOLOv9-E (`icon_detect_v3`, ≈ 58 M) + Florence-2-base fine-tuned (0,23 B); CPU | publicado 0,6 s en A100 y 0,8 s en RTX 4090 con todo; en CPU estimado 3–6 s por pantalla (sin medir) | Pro 39,6 **con GPT-4o** como planificador; sin un modelo grande detrás sólo da cajas y descripciones | `icon_detect_v3` MIT, `icon_caption` MIT; **el `icon_detect` v2 original es AGPL-3.0 → excluido** | Alternativa si A no rinde; necesita además casar la descripción con lo pedido |
| H. Florence-2-base / large | 0,23 B / 0,77 B, CPU | ≈ 1–3 s (sin medir) | sin datos de GUI; no está entrenado en interfaces | MIT | Sólo como descriptor de recortes |
| I. GroundingDINO tiny | 172 M, CPU | ≈ 1–2 s (sin medir) | sin datos de GUI; detecta objetos naturales | Apache-2.0 | Descartada para íconos |
| J. SigLIP 2 (≤ 150 M) para casar recortes con «engranaje», «campana»… | CPU | ≈ 0,1 s por recorte (estimado) | sin datos de GUI | Apache-2.0 | Complemento barato de G o de los candidatos sin modelo |
| Excluidas por licencia | Qwen2.5-VL-3B (Qwen Research, Pro 25,9), SeeClick (licencia Qwen-VL, Pro 1,1), Ferret-UI (Apple, sólo investigación), MobileCLIP2 (pesos con licencia de Apple, no MIT/Apache), UI-TARS-1.5 (sólo hay 7B abierto) | | | | |

Las cifras de ScreenSpot de B–F son de las tablas del artículo de GUI-Actor (arXiv 2506.03143).
Las de A, de la ficha de Qwen3.5-4B. Las de G, de la ficha de OmniParser v2.0.

## Recomendación

**A, con el codificador de imagen en CPU y sólo bajo demanda.** Cero VRAM nueva, misma licencia, el
modelo que ya conoce el resto de BAXY, y en el banco de interfaces el mejor de todos los
candidatos que caben. Cómo se usa:

1. Sólo cuando la cascada UIA → OCR → tooltip no encontró la etiqueta en una ventana sin árbol
   (cero costo en el resto).
2. Primero se manda **un recorte de la zona** que nombra la orden o el plan (rejilla 3×3 de la
   vista: 1,3 s medidos); la ventana entera sólo si el recorte no lo encuentra (≈ 10 s con
   tope de 768 tokens).
3. Respuesta en caja 0–1000 relativa al recorte → rectángulo físico → clic sólo dentro de la
   ventana de la misión, con la regla de pausa del punto 0, la misma confirmación de riesgo
   por etiqueta y prueba de efecto (superficie cambiada y llegada). El resultado se guarda en
   la memoria de procedimientos por firma de pantalla para no volver a mirarlo.
4. La captura nunca sale de la PC: el servidor de visión pasa a ser el `llama-server` local
   (sólo loopback); se quita la posibilidad de un servidor remoto.

Costo: +≈ 0,7 GB de RAM mientras el servidor esté arriba (o cargarlo sólo en misiones), y
reiniciar `llama-server` con `--mmproj … --no-mmproj-offload`, con nueva medición del pico de VRAM
del servidor (debe seguir ≤ 3,8 GB) y de la latencia del texto.

**Lo que necesita de ti:**
- Sí o no a la opción A (RAM +0,7 GB; 1–10 s de CPU sólo en clics a íconos sin texto).
- Si alguna vez aceptas subir el tope de VRAM, A′ baja la latencia a < 1 s.
- Si aceptas arrancar Steam con `-cef-force-accessibility` (reinicia Steam una vez; no toca
  tus datos): puede volver innecesaria la visión en Steam.

## Medición local (CPU, sin GPU, 2026-10-07)

- **Montaje:** `llama-mtmd-cli` b9980 (el que trae el runtime) con `-dev none -ngl 0 --no-mmproj-offload -t 8`; equipo Ryzen 7 5800H.
- **Modelo:** Qwen3.5-2B Q4_K_M con su `mmproj-F16` de 668 MB, que es casi del mismo tamaño que el del 4B (672 MB).
- **Imagen:** sintética de 1536×816 con 14 íconos Segoe Fluent en posiciones conocidas; nada del dueño.
- **Limpieza:** 1,95 GB descargados y ya borrados (`scratchpad/dl`).

| Imagen | Tokens de imagen | Codificación en CPU |
|---|---|---|
| Ventana completa 1536×816 | 1 248 | 19,8 s |
| `--image-max-tokens 768` | 760 | 9,5–9,9 s |
| `--image-max-tokens 384` | 364 | 3,6 s |
| Recorte de una zona (512×272) | 144 | 1,3 s |

- **Precisión del 2B (solo indicativa):** de las 3 preguntas con coordenadas útiles, las 3 cayeron dentro del ícono pedido (engranaje, papelera y descarga). En el resto se quedó razonando dentro del límite de tokens, porque el CLI no permite apagar el razonamiento; el servidor real ya corre con `--reasoning off`.
- **Coordenadas:** Qwen responde en escala relativa 0–1000, no en píxeles.
- **Aviso de llama.cpp:** «Qwen-VL … require at minimum 1024 image tokens … on grounding tasks». Hay que medir la precisión de los recortes.

## Riesgos y pendientes

- Precisión real del 4B en recortes pequeños: llama.cpp avisa que los modelos Qwen-VL quieren ≥ 1 024
  tokens de imagen para ubicar elementos. Hay que medirla en el banco (`s12`, `c17`, `g1` y casos de
  ícono nuevos) antes de activarla.
- llama-server con `--mmproj` y `--lora` a la vez: confirmar en la versión b9980 que el adaptador
  del decisor sigue igual con texto solo.
- La lectura en GPU de 1 248 tokens de imagen está estimada, no medida (la GPU estaba ocupada por tu
  sesión).

## Fuentes

- Ficha de Qwen3.5-4B (Apache-2.0, ScreenSpot-Pro 60,3): https://huggingface.co/Qwen/Qwen3.5-4B
- Tamaños de los GGUF y `mmproj`: https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/tree/main, https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/tree/main y https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/tree/main
- Tablas de ScreenSpot de los demás modelos (GUI-Actor): https://arxiv.org/html/2506.03143
- OmniParser v2.0 (licencias y latencia): https://huggingface.co/microsoft/OmniParser-v2.0
- `WM_GETOBJECT`: https://learn.microsoft.com/en-ie/Windows/Win32/winauto/wm-getobject
- Chromium activa la accesibilidad a demanda: https://github.com/Descolada/UIAutomation/wiki/08.-Common-pitfalls;-tips-and-tricks
- Estado de accesibilidad en CEF: https://opendlang.org/library/arsd.webview.cef_browser_host_t.set_accessibility_state.html
- Depuración remota de Steam y su riesgo: https://wiki.deckbrew.xyz/plugin-dev/cef-debugging y https://docs.steambrew.app/developers/themes/getting-started
- Accesibilidad de Steam (Big Picture / SteamOS): https://steamdeckhq.com/news/steam-deck-beta-client-accessibility-settings/

## Decisión del dueño (2026-10-08, 12:55)

«No podemos pasar de 4 GB de VRAM.» Queda descartada A′ (el codificador de imagen en GPU) y cualquier modelo de
visión que sume VRAM. La única opción compatible con esta decisión es A (codificador en CPU, 0 MB de VRAM extra); su
implementación no forma parte del goal v3.
