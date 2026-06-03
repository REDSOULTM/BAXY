# Prompt de investigación 6/8 — Estabilidad y degradación con gracia (no petar el programa) en vram4

Copiá esto a Claude (research/web). Tema ESPECÍFICO: que el asistente NUNCA pete
ni se cuelgue, y degrade con gracia bajo presión de recursos, en el perfil más
ajustado (vram4). RED: "no quiero petar el programa". Fuentes 2025-2026.

## RESTRICCIÓN DURA: TODO en vram4 = Gemma 4 E4B-it Q4_K_M
Default = vram4 (4B cuantizado, GPU modesta ~4-6 GB, voz local Windows, llama.cpp
b9090 monoslot, ctx 16384). RED quiere que vram4 sea CAPAZ DE TODO sin petar. Las
soluciones no pueden inflar VRAM/latencia fuera del budget de vram4 ni asumir
modelo más grande. Lo que no entre en vram4 → marcar NO-VIABLE + alternativa.

## 1. El problema
El asistente actúa sobre el SO real (abre apps, controla GUI, GPU compartida con
el LLM). Riesgos de crash/cuelgue medidos o conocidos en el proyecto:
- OOM de VRAM (LLM + visión lazy + KV cache cerca del límite en 4-6 GB).
- ONNX Runtime clava la CPU al 100% sin throttle (congeló Windows en evals).
- Tools que matan procesos del usuario sin avisar (pasó: mató un juego/LLM).
- Residuos de torch (torchcodec/torchvision) que rompen el router en silencio.
- Llamadas al LLM que cuelgan (timeout) y bloquean el turno.

## 2. Lo que YA tenemos (no recomendar)
- Per-mode LLM timeout (un turno no bloquea 24 min), server-reload recovery,
  context-overflow retry, loop detector, dispatch try/except por tool.
- vram_calculator.py predice VRAM sin GPU (validado al MiB); perfiles por VRAM.
- _ort_throttle.py para ONNX (2 threads, sin spinning, afinidad).
- Hard-gate de compra + confirmación antes de matar procesos pesados.

## 3. Lo que quiero investigado
1. **Gestión de presión de VRAM en 4-6 GB con LLM+visión+KV en una sola GPU**:
   ¿cómo detectar OOM ANTES de que pase y degradar (bajar ctx, descargar visión,
   liberar KV) sin matar el turno? ¿Señales tempranas, watchdog de VRAM, fallback
   automático a un ctx menor? Patrones para llama.cpp.
2. **Aislamiento de fallos de tools**: una tool que cuelga/crashea NO debe tumbar
   el agente ni la GUI. ¿Sandbox/timeout/proceso separado por tool de riesgo?
   ¿Cómo recuperar el turno y avisar al usuario? Costo en latencia.
3. **Health-checks y auto-reparación de precondiciones del runtime**: detectar al
   arranque (y periódicamente) si el router está sano, el server vivo, deps
   incompatibles (torchcodec/torchvision), y repararlo o avisar fuerte en vez de
   degradar mudo. Diseño de un "self-check" liviano.
4. **Degradación con gracia bajo carga**: si la GPU está saturada (el user abrió
   un juego pesado), ¿cómo seguir respondiendo (CPU-only fallback, cola, avisar)
   en vez de petar? Política de back-pressure para un asistente de voz.
5. **No matar recursos del usuario**: reforzar la garantía de que el agente nunca
   mate procesos/cierre apps sin confirmación, incluso en rutinas automatizadas.
   ¿Lista blanca/negra, gate por riesgo, dry-run?
6. **Observabilidad para diagnosticar cuelgues**: ¿qué loguear (sin ruido) para
   reproducir un crash después? Tracing liviano.

## 4. Formato
Por punto: diagnóstico, tabla (riesgo de crash mitigado, latencia/VRAM añadida,
complejidad), fuentes recientes (reliability de agentes locales, llama.cpp OOM,
watchdogs), veredicto VIABLE vram4, código. Priorizá 1, 2 y 3 (los que más
previenen el "petar el programa").
