# Prompt para GPT-5.5 Codex — Control manos-libres por cámara (complemento de Gemma 4)

> Copiá TODO lo de abajo (desde "ROL") como prompt para Codex, dentro del repo de Gemma 4.

---

## ROL Y OBJETIVO
Sos un ingeniero senior trabajando DENTRO del proyecto **Baxy** (asistente Windows,
Python 3.10, todo OSS/local). Vas a construir un **subsistema NUEVO y AISLADO** de control del
PC **manos-libres por cámara web** (mirada/cabeza + gestos de mano), como **complemento** del
control por voz que ya existe. **REUSÁ lo que ya está; no rearmes nada que el proyecto ya tenga.**

## LEÉ PRIMERO (en el repo)
- `documentacion/IDEA_control_camara_manos_libres.md` — el diseño completo (visión, las 3 capas,
  multi-monitor, gestos, máquina de estados, calibración, gates por fase). **Es tu spec.**
- `documentacion/IDEA_..._.md` §16 "Qué REUSAR" — el mapa de tools del proyecto a reusar.
- `documentacion/AUDITORIA_licencias.md` — qué deps son comercial-OK (el producto se VENDE).

## RESTRICCIONES DURAS (no negociables)
1. **100% DETERMINISTA, SIN LLM en el loop de control.** Mover el cursor y clickear es
   **geometría + máquina de estados**, NO inferencia. El LLM (Gemma 4) entra SOLO bajo pedido
   explícito por voz ("qué ves en mi pantalla" → describe_screen; "avisame cuando entre alguien"
   → el LLM arma el watcher UNA vez, la vigilancia corre determinista). **Nunca** un round-trip
   al LLM por frame.
2. **Licencias comercial-OK.** El producto se VENDE → **solo** Apache/MIT/BSD/CC0. **PROHIBIDO**
   GPL/AGPL/non-commercial. MediaPipe (Apache-2.0) y OpenCV (Apache-2.0) están OK. Antes de sumar
   CUALQUIER lib o modelo, verificá la licencia.
3. **CPU, 0 VRAM extra.** MediaPipe corre en CPU; **no toques** la VRAM del 4B (6GB justos).
   Hilo/proceso aparte. Gate por `gemma4_agent/infra/profiles.py::camera_enabled`.
4. **Local/privado.** El video NO se graba ni se sube; se procesan landmarks en memoria y se
   descartan. Indicador visible de "cámara activa".
5. **Dead-man switch.** Sin mano en la zona de control = SIN acciones (cero clicks fantasma).
   Acciones destructivas (cerrar/borrar) exigen 2º gesto o dwell de confirmación.

## REUSÁ (NO armar de 0) — esto YA existe en el repo
El control de cámara **no reimplementa** clicks, grounding ni visión. Solo aporta *dónde
apuntar* y *qué gesto*; ejecutá con las tools existentes:

```python
from gemma4_agent.agent_core.agent import Gemma4Agent
a = Gemma4Agent()                       # el agente (tiene el registry de tools)
ex = a.tools.execute

ex("gui", {"action": "click", "x": X, "y": Y})                      # click físico en (x,y)
ex("gui", {"action": "click_button", "label": L, "window": W})     # click por label -> CASCADA UIA/OCR + verificación
ex("gui", {"action": "keypress", "keys": "ctrl+w"})                # combos (cerrar pestaña, etc.)
ex("gui", {"action": "scroll", "amount": N})                       # scroll
ex("gui", {"action": "screenshot"})                                # captura
ex("vision", {"action": "describe_screen", "target": "..."})       # L3: "qué ves en mi pantalla" (LLM, bajo pedido)
```
- **Snap-to-elemento** en (x,y): `import uiautomation as auto; ctrl = auto.ControlFromPoint(x,y)`
  (validado en este repo) + `gemma4_agent.tools_pkg.ops_tools.ocr_find_text` (OCR con fix de
  palabra+psm11) para texto/web cuando UIA no expone el control.
- **Verificación antes/después** de un click: `gemma4_agent/computer_use_pkg/gui_verify.py`.
- **Monitores**: `win32api.EnumDisplayMonitors()` (el repo ya usa win32 para rects de ventana).
- **Persistencia/perfil**: patrón de `~/.gemma4/` + `infra/profiles.py`.

## ARQUITECTURA (ver §3-§16 del doc)
Cámara (OpenCV) → MediaPipe Face Mesh + Hands (CPU) → fusión cabeza(+iris) a (x,y) en el
**lienzo virtual** (unión de monitores) + reconocedor de gestos por geometría → **snap-to-
elemento** (UIA/OCR del repo) → **máquina de estados** (IDLE/ARMED/DRAGGING) → ejecutor (las
gui tools de arriba). Filtro one-euro anti-jitter. Calibración por usuario+layout.

## EMPEZÁ POR FASE 0 — POC (no construyas todo de una)
**Objetivo del POC:** validar el piso en hardware real ANTES del sistema completo.
1. `pip install mediapipe opencv-python` (ambos Apache-2.0; confirmá que no jalen deps GPL).
2. Abrí la cámara, corré MediaPipe Hands + Face Mesh, dibujá un overlay que muestre:
   el gesto detectado (puño/pinza/palma/apuntar) y la región a la que apunta la cabeza.
3. **MEDÍ y reportá** en el hardware del usuario (tiene 3 monitores):
   - FPS sostenido del pipeline.
   - Fiabilidad del gesto (matriz de confusión rápida sobre 50 muestras por gesto).
   - Estabilidad de la pose de cabeza (jitter px tras one-euro).
**GATE para seguir:** ≥20 fps sostenido **∧** gesto puño/pinza/abierto ≥95% **∧** jitter de
cabeza acotado. Si no pasa → reportá honesto y ajustá (no avances al build grande).

Luego, fase por fase con los gates del doc (§11): gestos→acción → puntero-cabeza →
calibración+multi-monitor → snap → gestos ricos → integración con el perfil `camera_enabled`.

## ESTRUCTURA DE ARCHIVOS (nueva, aislada)
`gemma4_agent/vision_input/` con: `camera.py, landmarks.py, gestures.py, pointer.py,
calibration.py, monitors.py, snap.py, controller.py, watchers.py` (ver §15.1 del doc). NO
toques el core del agente salvo el flag de perfil y, opcional, un toggle por voz.

## QUÉ NO HACER
- ❌ NO metas el LLM en el loop de control (latencia + alucina clicks). L1/L2 = geometría pura.
- ❌ NO uses ni sumes deps GPL/AGPL/non-commercial (rompe la venta). Verificá CADA lib/modelo.
- ❌ NO reimplementes el click/grounding/visión: reusá las gui/vision tools y la cascada UIA/OCR.
- ❌ NO toques la VRAM del 4B ni el runtime de voz; corré en CPU, hilo aparte, opt-in.
- ❌ NO confíes la precisión a la mirada sola: cabeza (estable) + snap-to-elemento (preciso).

## ENTREGABLE DE ESTA TANDA
El POC de Fase 0 funcionando + un reporte de los números del gate medidos en el hardware del
usuario (3 monitores). Si el gate pasa, seguimos con la Fase 1. Medí, no celebres.
