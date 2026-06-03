# Prompt de investigación 5/8 — Aprendizaje proactivo de patrones del usuario (asistente tipo Jarvis)

Copiá esto a Claude (research/web). Tema ESPECÍFICO y de alto valor: que el
asistente OBSERVE el comportamiento del usuario, detecte patrones repetidos y se
OFREZCA a automatizarlos ("veo que siempre cerrás X al prender la PC, ¿te lo
automatizo?"). Local, privado, sin cloud, sin ser molesto. Fuentes 2025-2026.

## 0. Stack y visión
Gemma 4 E4B-it Q4_K_M local, asistente de VOZ Windows. RED quiere un "Jarvis"
que aprenda sus hábitos y lo guíe/anticipe, SIN volverse intrusivo ni petar el
programa. Multi-usuario universal (lo que aprende de un usuario no debe degradar
a otros).

## RESTRICCIÓN DURA (innegociable): TODO debe correr en vram4 = E4B-Q4
El perfil DEFAULT es vram4 (Gemma 4 E4B-it Q4_K_M, ~4B cuantizado, GPU modesta
~4-6 GB, latencia tier-Alexa 4-5 s). RED quiere que vram4 sea capaz de TODO esto
— NO asumir un modelo más grande ni subir de perfil. La solución NO puede:
inflar la VRAM por encima del budget de vram4, agregar un 2º modelo pesado que no
entre, ni subir la latencia por turno fuera del presupuesto. Si algo necesita
"inteligencia", preferí CÓDIGO DETERMINISTA + el LLM solo para conversar la
sugerencia. Cualquier recomendación que requiera >4B o más VRAM debe marcarse
explícitamente como NO-VIABLE-EN-VRAM4 y darse una alternativa que sí entre.

## 1. El caso de uso concreto (de RED)
"Yo siempre cierro tal programa al empezar la PC — el LLM podría ofrecerse a
hacer eso siempre." Generalizando: el asistente debería detectar rutinas
implícitas del usuario (apps que abre/cierra a ciertas horas, secuencias de
comandos repetidas, correcciones que hace) y proponer automatizarlas o asistir.

## 2. Lo que YA tenemos (no recomendar — esto es la base sobre la que construir)
- **Sistema de rutinas con triggers** (`routine_tool`): soporta `manual`, `cron`,
  `once`, `on_app_open`, `on_app_close`, `on_process_start`, `on_process_exit`,
  `on_phrase`. Backend: windows_scheduled_tasks + watcher poll + chat phrase hook.
  O sea: EJECUTAR una rutina automatizada YA está resuelto.
- **ExperienceMemory** (`experience.py`): SQLite que graba interacciones de la
  sesión, recall por similitud, con poda y recuperación de corrupción. (Gotcha
  conocido: test-junk contaminó 52% de la DB una vez — cuidado con qué se graba.)
- **memory.py**: store key-value persistente que se vuelca al system prompt.

LO QUE FALTA (el corazón del pedido): el lazo OBSERVAR → DETECTAR PATRÓN →
SUGERIR. Nada hoy observa "RED cierra X cada arranque" y ofrece automatizarlo.

## 3. Lo que quiero investigado
1. **Detección de patrones de comportamiento en local, barata y privada**: ¿cómo
   registrar y minar eventos del usuario (apps abiertas/cerradas, comandos
   repetidos, horarios) para detectar rutinas implícitas SIN ML pesado ni cloud?
   ¿Frequent-pattern mining (estilo PrefixSpan/secuencias), reglas de asociación,
   conteo simple con umbral? ¿Cuántas repeticiones antes de sugerir? Evidencia de
   asistentes/RPA que aprenden hábitos.
2. **Cuándo y cómo SUGERIR sin ser intrusivo**: el balance proactividad-vs-molestia
   es el problema central de los asistentes proactivos. ¿Qué señales disparan una
   sugerencia (confianza del patrón, momento oportuno)? ¿Cómo ofrecer por VOZ de
   forma no-molesta y que el usuario acepte/rechace/edite? Patrones de UX de
   proactividad (mixed-initiative). Evitar el "Clippy problem".
3. **Conectar el patrón detectado al sistema de rutinas existente**: dado que ya
   tenemos triggers on_app_open/cron/etc., ¿cómo traducir un patrón observado
   ("cierra Discord al abrir un juego") a una propuesta de rutina concreta que el
   usuario confirme con un sí? Diseño del handoff observación→rutina.
4. **El rol del LLM vs reglas deterministas**: ¿el LLM debe hacer la detección de
   patrones (caro, poco fiable en 4B) o solo la PRESENTACIÓN/conversación de la
   sugerencia, dejando la minería a código determinista? Arquitectura recomendada.
5. **Privacidad y multi-usuario**: todo local. ¿Cómo aprender del operador sin
   degradar el comportamiento universal? ¿Perfil de usuario separado de la lógica
   base? Riesgo de over-personalización.
6. **Anti-poison / qué grabar**: dado el incidente de DB contaminada, ¿qué eventos
   valen registrar (señal estable) vs ruido? Política de retención y olvido.

## 4. Formato
Por punto: diagnóstico, opciones con tabla (precisión de detección, intrusividad,
costo, privacidad, complejidad), fuentes recientes (asistentes proactivos, RPA,
pattern mining, mixed-initiative UX), veredicto VIABLE local+4B+voz, código/
pseudocódigo y cómo enganchar al routine_tool existente. Priorizá 1, 2 y 3 (son
el camino directo al "Jarvis que se ofrece a automatizar").
