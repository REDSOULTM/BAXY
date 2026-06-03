# Prompt de investigación 7/8 — Comprensión de comandos: ambigüedad, multi-intent y clarificación en voz (vram4)

Copiá esto a Claude (research/web). Tema ESPECÍFICO: que el asistente entienda
bien comandos de voz ambiguos, con varias intenciones, o incompletos, y pida
aclaración de forma natural cuando hace falta. Fuentes 2025-2026.

## RESTRICCIÓN DURA: TODO en vram4 = Gemma 4 E4B-it Q4_K_M
Default vram4 (4B cuantizado, voz local, latencia 4-5 s). RED quiere que vram4
haga TODO. Nada que requiera >4B o más VRAM/latencia. Lo que no entre → NO-VIABLE
+ alternativa que sí entre en vram4.

## 1. El problema
El input es VOZ transcrita (Parakeet) — informal, con disfluencias, a veces con
varias intenciones ("abrí Spotify y bajá el volumen"), a veces incompleto
("mandale a Juan" sin el mensaje), a veces ambiguo ("ponelo" → ¿qué?). Un 4B
tiende a: ejecutar solo una de varias intenciones, inventar el slot faltante, o
adivinar mal el referente.

## 2. Lo que YA tenemos (no recomendar)
- intent_router (info vs acción por anclas multilingües + gate interrogativo
  léxico zero-ML), abstain_head (gate no-tool), semantic_router (subset de tools).
- Slot-filling parcial: whatsapp pide UN slot faltante (body/contact/channel).
- inherit-tools para continuaciones cortas ("subelo" hereda la tool previa).
- Modos por intención (fast_action/quick_action/deep_action/...).
- parallel_tool_calls (puede emitir varios tool-calls en un turno).

## 3. Lo que quiero investigado
1. **Multi-intent en un comando de voz**: "abrí Spotify y bajá el volumen" son DOS
   acciones. ¿Cómo lograr que un 4B las ejecute AMBAS de forma fiable (parallel
   tool-calls, descomposición en código antes del LLM, o secuencial)? ¿Detectar
   conjunciones/listas barato y rutear como N comandos? Evidencia en SLMs.
2. **Detección de comando incompleto → clarificación**: cuándo falta un slot
   esencial ("mandale a Juan" sin texto), ¿cómo decidir pedir aclaración vs
   inventar? Una sola pregunta corta, en el idioma del usuario, sin trabarse en
   loops de preguntas. UX de clarificación en voz (mixed-initiative).
3. **Resolución de referentes ambiguos/deícticos**: "ponelo", "ese", "el otro",
   "ciérralo" — dependen del contexto previo. ¿Cómo resolver el referente de
   forma fiable en 4B (estado de turno, último objeto mencionado) sin alucinar?
4. **Tolerancia a disfluencias del STT**: "abre, abre a, abre Spotify" (titubeos),
   o transcripción imperfecta. ¿Normalización/limpieza del comando ANTES del LLM
   que mejore el entendimiento sin perder intención? ¿Dónde hacerlo (post-STT)?
5. **Confianza y "no entendí"**: cuando el comando es genuinamente incomprensible,
   ¿cómo responder útil ("no te entendí, ¿querés X o Y?") en vez de ejecutar algo
   al azar? Calibración de confianza sin un 2º modelo.
6. **Comandos compuestos con dependencia** ("buscá un Word y abrilo") — esto se
   cruza con el encadenamiento; acá enfocá la COMPRENSIÓN (entender que son 2
   pasos dependientes) más que la ejecución.

## 4. Formato
Por punto: diagnóstico, tabla (precisión de comprensión, latencia, riesgo de
ejecutar mal), fuentes recientes (NLU para voz, multi-intent, clarification
dialogue, SLMs), veredicto VIABLE vram4, código/pseudocódigo (dónde engancharlo:
post-STT, router, planner). Priorizá 1 y 2 (multi-intent y clarificación).
