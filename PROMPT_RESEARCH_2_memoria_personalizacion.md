# Prompt de investigación 2/8 — Memoria, personalización y entity-grounding del asistente

Copiá esto a Claude (research/web). Tema ESPECÍFICO: cómo el asistente APRENDE y
usa el contexto del usuario (sus apps instaladas, contactos, preferencias, alias)
para ejecutar comandos con precisión. Local, sin cloud. Fuentes 2025-2026.

## 0. Stack y producto
Gemma 4 E4B-it Q4_K_M, llama.cpp b9090, asistente de VOZ local Windows, 100%
offline. STT=Parakeet. El usuario da comandos hablados con nombres propios
(apps, contactos, artistas) que el modelo debe resolver a entidades reales.


## RESTRICCIÓN DURA (innegociable): TODO debe correr en vram4 = E4B-Q4
El perfil DEFAULT es vram4 (Gemma 4 E4B-it Q4_K_M, ~4B cuantizado, GPU
modesta ~4-6 GB, latencia tier-Alexa 4-5 s). RED quiere que vram4 sea capaz
de TODO esto — NO asumir un modelo más grande ni subir de perfil. Ninguna
solución puede inflar VRAM/latencia fuera del budget de vram4 ni meter un 2º
modelo pesado. Lo que necesite 'inteligencia' extra: preferí CÓDIGO
DETERMINISTA + el LLM solo para lo conversacional. Cualquier recomendación
que requiera >4B o más VRAM debe marcarse NO-VIABLE-EN-VRAM4 con una
alternativa que sí entre.

## 1. El problema medido (3 incidentes reales)
- **WhatsApp al contacto equivocado**: pidió "escríbele a mamá" y fue al grupo
  "Música". El agente busca el contacto por GUI y a veces abre el chat errado.
- **STT entity-recall**: nombres propios en inglés mal transcritos (Chrome→crumb,
  Edge→echo). Hay un corrector fonético contra un INVENTARIO (apps/artistas),
  pero el inventario es estático + discovery de apps instaladas.
- **Resolución de apps**: "abre Spotify" debe mapear al ejecutable real.

## 2. Lo que YA tenemos (no recomendar)
- `memory.py`: store key-value simple, se vuelca al system prompt como
  "- clave: valor" (prompt_summary). 6 items pinned típicos.
- `experience.py`: ExperienceMemory SQLite (graba interacciones de la sesión,
  recall por similitud, con recuperación de corrupción y poda).
- `inventory.py`: inventario de apps (static seed universal + discovery de apps
  instaladas vía Get-StartApps) + artistas/contactos. Lo usa el corrector
  fonético del STT y el resolver de apps.
- Corrector fonético (Double Metaphone EN + Spanish Metaphone) contra el inventario.

## 3. Lo que quiero investigado
1. **Arquitectura de memoria de usuario para un asistente local de voz**: ¿cómo
   estructurar la memoria persistente (apps, contactos, alias "mamá"→número,
   preferencias) para que el LLM la use con precisión SIN inflar el prompt? El
   dump key-value actual no escala. ¿Memoria estructurada + retrieval selectivo
   por turno? ¿Qué inyectar siempre vs. recuperar on-demand? Patrones 2025-26
   (MemGPT, mem0, A-MEM, etc.) viables en local con un 4B.
2. **Entity grounding / resolución de nombres propios**: el usuario dice "mamá",
   "Spotify", "Bad Bunny" — ¿cómo resolverlos de forma robusta a la entidad real
   (contacto/app/artista) combinando el inventario + fonética + memoria, ANTES o
   DURANTE el tool-call? ¿Conviene que el LLM reciba candidatos resueltos en el
   prompt en vez de adivinar?
3. **Aprendizaje de alias y correcciones**: si el usuario corrige ("no, mamá es
   este otro número"), ¿cómo persistir ese aprendizaje y aplicarlo después, sin
   degradar a otros usuarios (es multi-usuario universal)?
4. **Selección de qué recordar**: hoy se graba mucho a SQLite. ¿Qué señales valen
   guardar (preferencias estables) vs ruido (one-off)? ¿Cómo evitar el "memory
   poison" (la sesión vieja menciona que test-junk contaminó 52% de la DB)?
5. **Privacidad/local**: todo debe quedar en disco local, sin cloud. Restricción dura.

## 4. Formato
Por punto: diagnóstico, opciones con tabla (precisión de resolución, costo de
prompt/latencia, complejidad, riesgo de overfit a un usuario), fuentes recientes,
veredicto VIABLE local+4B, código/pseudocódigo. Marcá lo que medir. Priorizá 1 y
2 (atacan el bug del contacto equivocado y el entity-recall del STT directamente).
