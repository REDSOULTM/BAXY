# Prompt de investigación 4/8 — Gestión de contexto e historial multi-turno en un 4B local

Copiá esto a Claude (research/web). Tema ESPECÍFICO: cómo manejar el historial de
conversación y el contexto entre turnos en un modelo de 4B con ventana de 16K, sin
saturar el contexto ni romper el prefix-cache ni perder coherencia. Fuentes 2025-26.

## 0. Stack
Gemma 4 E4B-it Q4_K_M, llama.cpp b9090, ctx=16384, `--swa-full --cache-reuse 256
--keep -1`, monoslot, asistente de VOZ local. Turnos cortos de comando + a veces
multi-paso. El system prompt base (CORE LEAN) ya pesa ~920 tok; FULL ~2900 tok.


## RESTRICCIÓN DURA (innegociable): TODO debe correr en vram4 = E4B-Q4
El perfil DEFAULT es vram4 (Gemma 4 E4B-it Q4_K_M, ~4B cuantizado, GPU
modesta ~4-6 GB, latencia tier-Alexa 4-5 s). RED quiere que vram4 sea capaz
de TODO esto — NO asumir un modelo más grande ni subir de perfil. Ninguna
solución puede inflar VRAM/latencia fuera del budget de vram4 ni meter un 2º
modelo pesado. Lo que necesite 'inteligencia' extra: preferí CÓDIGO
DETERMINISTA + el LLM solo para lo conversacional. Cualquier recomendación
que requiera >4B o más VRAM debe marcarse NO-VIABLE-EN-VRAM4 con una
alternativa que sí entre.

## 1. El problema medido
- El prompt total mediano es ~7875 tok y CRECE ~3900 tok/turno (user + respuesta
  + tool_results acumulados). En sesiones largas se acerca al límite de 16K.
- El prefill mediano es ~888 ms; cuando el historial crece, sube.
- Hay tensión cache: el `--cache-reuse` reusa el prefijo estable, pero el
  historial nuevo (cola) se reprocesa cada turno.

## 2. Lo que YA tenemos (no recomendar)
- `agent_compaction.py`: compute_context_budget proporcional al ctx; compacta el
  historial (compact_completed_history quita tool_calls/tool messages viejos;
  compact_live_content acorta el contenido del turno).
- inherit-tools: una continuación corta ("subelo") hereda la tool del turno
  previo aunque la compaction haya borrado los tool messages (con TTL).
- microagents: conocimiento de dominio inyectado por trigger del user_text.
- CORE LEAN/FULL por perfil (prompt más corto = más rápido Y más preciso en SLMs,
  citan RAG-MCP arXiv:2505.03275 y EasyTool arXiv:2401.06201).

## 3. Lo que quiero investigado
1. **Qué conservar entre turnos en un asistente de voz de comandos**: ¿el modelo
   necesita historial largo, o casi cada turno es independiente? ¿Cuándo importa
   el contexto previo ("subelo", "ese", "el otro") y cómo detectarlo barato para
   compactar agresivo el resto? Evidencia sobre context-as-router-input.
2. **Compaction/summarization que NO rompa el prefix-cache**: el historial crece
   en la cola y se reprocesa. ¿Rolling summary cada N turnos? ¿Cómo resumir sin
   invalidar el prefijo cacheado ni perder la referencia deíctica? Trade-off
   medible (tokens reprocesados vs coherencia).
3. **Coherencia multi-turno en 4B**: los modelos chicos pierden el hilo en
   conversaciones largas. ¿Patrones para mantener coherencia (resumen estructurado,
   slots de estado, "scratchpad" persistente) sin un 2º modelo? Evidencia <10B.
4. **Manejo de tool_results en el historial**: hoy se compactan/quitan los viejos.
   ¿Cuándo un tool_result viejo importa para el turno actual? ¿Cómo decidir qué
   resultado de tool retener (ej. el path de un search reciente para un open
   posterior) vs descartar?
5. **Límite de 16K y degradación**: ¿qué pasa cerca del límite? ¿Cómo degradar con
   gracia (resumir, no truncar a ciegas) sin romper tool-calling? Política de
   "presión de contexto".

## 4. Formato
Por punto: diagnóstico, tabla (tokens reprocesados, coherencia, latencia, riesgo),
fuentes recientes (gestión de contexto/memoria de trabajo en SLMs y agentes de
voz), veredicto VIABLE 4B+16K+voz, código/pseudocódigo. Marcá lo que medir.
Priorizá 1 y 2 (impacto directo en latencia y coherencia).
