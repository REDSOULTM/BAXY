# Prompt de investigación 3/8 — Verificación de acciones y recuperación de errores del agente

Copiá esto a Claude (research/web). Tema ESPECÍFICO: cómo el agente CONFIRMA que
una acción de verdad ocurrió, y cómo se RECUPERA cuando una tool falla, sin
mentirle al usuario ("Listo" cuando no pasó nada). Local, voz, 4B. Fuentes 2025-26.

## 0. Stack
Gemma 4 E4B-it Q4_K_M, llama.cpp b9090, asistente de voz local Windows. 65 tools
que ACTÚAN sobre el sistema (abrir apps, controlar GUI, mandar mensajes, media).


## RESTRICCIÓN DURA (innegociable): TODO debe correr en vram4 = E4B-Q4
El perfil DEFAULT es vram4 (Gemma 4 E4B-it Q4_K_M, ~4B cuantizado, GPU
modesta ~4-6 GB, latencia tier-Alexa 4-5 s). RED quiere que vram4 sea capaz
de TODO esto — NO asumir un modelo más grande ni subir de perfil. Ninguna
solución puede inflar VRAM/latencia fuera del budget de vram4 ni meter un 2º
modelo pesado. Lo que necesite 'inteligencia' extra: preferí CÓDIGO
DETERMINISTA + el LLM solo para lo conversacional. Cualquier recomendación
que requiera >4B o más VRAM debe marcarse NO-VIABLE-EN-VRAM4 con una
alternativa que sí entre.

## 1. El problema
Un asistente que actúa sobre el mundo real debe saber si la acción TUVO efecto:
- "abre Steam" → ¿Steam abrió de verdad? (la ventana puede no aparecer)
- "mandá a mamá" → ¿se envió o se mandó al chat equivocado? (bug real)
- El modelo de 4B tiende a decir "Listo, abrí X" por inercia aunque la tool haya
  fallado o no se haya verificado.

## 2. Lo que YA tenemos (no recomendar)
- `verifiers.py`: verificadores POR TOOL (verify_app, verify_window, verify_steam,
  verify_filesystem, verify_audio, verify_terminal, verify_gui, verify_web,
  verify_system...) que devuelven VerifierOutcome (verified/failed/unknown).
- Guards de reply: honestidad (no decir "listo" si no verificó), grounding (claim
  de acción necesita evidencia), promesa-sin-acción, leaked-tool-call.
- Recuperación: context-overflow retry, server-reload recovery, per-mode timeout,
  replan (2+ fallos de tool con plan explícito → 1 LLM call de replan), loop
  detector (corta si repite la misma acción sin avanzar).
- Honesty footer: si un paso quedó sin verificar, lo dice en el reply.

## 3. Lo que quiero investigado
1. **Verificación de efecto de acciones GUI/OS en Windows, robusta**: más allá de
   "la tool devolvió ok", ¿cómo confirmar el EFECTO real (ventana visible y
   enfocada, mensaje enviado, volumen cambiado)? UIA, captura+OCR, eventos del
   SO. ¿Cuál es fiable y barato (<300 ms) para voz? El caso WhatsApp (verificar
   el chat correcto antes de enviar) ya lo atacamos con OCR del header — ¿hay
   algo mejor/más general?
2. **Política de recuperación ante fallo de tool en un 4B**: cuando una tool falla
   o no verifica, ¿cuál es el mejor patrón para que el 4B (a) NO mienta, (b)
   reintente con args corregidos, o (c) pida ayuda al usuario — sin entrar en
   loops? Evidencia 2025-26 (self-correction, reflexion, error-aware agents) que
   funcione en <10B local.
3. **Distinguir "no pude verificar" de "falló"**: hoy hay verified/failed/unknown.
   ¿Cómo comunicar el "unknown" al usuario de forma útil por VOZ sin sonar
   inseguro siempre? (UX de confianza en asistentes de voz).
4. **Self-healing de precondiciones**: el mandato del proyecto es que el código
   garantice precondiciones (app instalada, daemon arriba, foco). ¿Patrones para
   detectar y reparar precondiciones ANTES de actuar, en vez de fallar y recuperar?
5. **Costo de la verificación vs latencia**: verificar cada acción suma latencia.
   ¿Cuándo verificar (acciones irreversibles/de mensajería sí; subir volumen no)?
   Política de verificación selectiva por riesgo.

## 4. Formato
Por punto: diagnóstico, tabla (fiabilidad de detección, latencia añadida, riesgo
de falso-ok/falso-fail), fuentes recientes, veredicto VIABLE Windows+voz+4B,
código. Marcá lo que medir. Priorizá 1 (verificación de efecto) y 2 (recovery).
