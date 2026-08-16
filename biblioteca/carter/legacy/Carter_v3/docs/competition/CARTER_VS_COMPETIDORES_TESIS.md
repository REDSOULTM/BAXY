# Carter v3 — Análisis Competitivo Honesto
**Fecha:** 2026-05-06  
**Proyecto:** Carter v3 — Asistente Personal Local tipo Jarvis para Windows  
**Nota metodológica:** Carter se evalúa según su especificación completa (ContextoCarter.md), asumiendo implementación terminada con voz y posible cámara. Los competidores se evalúan según su estado real documentado hoy. Este documento busca ser útil para una defensa académica, no para vender el proyecto.

---

## 1. El problema que todos intentan resolver

Todos los proyectos de esta categoría responden a la misma pregunta:

> ¿Cómo hago que un LLM controle mi computadora de forma útil, segura y confiable?

Las respuestas divergen en cinco ejes que definen la arquitectura:

1. **¿Dónde corre el LLM?** — local vs. cloud
2. **¿Cómo ejecuta acciones?** — código libre vs. herramientas declarativas
3. **¿Cómo sabe si la acción funcionó?** — verificación vs. confianza ciega
4. **¿Por dónde habla el usuario?** — voz, texto, mensajería
5. **¿Qué tan universal es?** — Windows específico vs. multiplataforma

Carter toma posiciones claras en los cinco. Algunas son ventajas reales. Otras son apuestas que otros ya ganaron de otra forma.

---

## 2. Los competidores reales

### 2.1 Open Interpreter
**github.com/OpenInterpreter/open-interpreter — 63,400 stars — Activo**

El referente de la categoría. Lanzado en 2023, con años de uso real, comunidad grande y bugs corregidos por miles de usuarios. El LLM genera y ejecuta código Python/Shell directamente en la máquina.

**Lo que hace bien:**
- Años de prueba en condiciones reales por decenas de miles de usuarios
- Flexible: el LLM puede resolver problemas que ninguna herramienta declarativa anticipó
- Soporte para cualquier LLM (Ollama, OpenAI, Claude, etc.)
- El proyecto 01 ya tiene voz funcionando hoy

**Sus limitaciones reales:**
- En Windows requiere WSL2 para funcionar bien — no es nativo
- Ejecución de código libre es potente pero difícil de acotar: el LLM puede generar código que falle silenciosamente
- No tiene verificación formal post-acción: confía en el output del código
- No tiene guardia anti-fake-success documentada
- AGPL-3.0: si distribuyes el software modificado, debes publicar el código

**Comparación honesta con Carter (completo):**

| Dimensión | Open Interpreter | Carter (completo) | Ventaja |
|-----------|-----------------|-------------------|---------|
| Años en producción | 3+ años, miles de usuarios | Nuevo | **Open Interpreter** |
| Windows nativo | ⚠️ WSL recomendado | ✅ nativo | **Carter** |
| Flexibilidad de acción | Alta (código libre) | Media (32 tools) | **Open Interpreter** |
| Verificación post-acción | ❌ confía en output | ✅ readback real por tool | **Carter** |
| Privacidad | ✅ local con Ollama | ✅ local | Empate |
| Voz | ✅ 01 App (funciona hoy) | ✅ capa sobre núcleo | Empate |
| Seguridad pre-LLM | ❌ | ✅ PolicyEngine | **Carter** |
| Comunidad/validación | ✅✅✅ | ❌ (proyecto nuevo) | **Open Interpreter** |

**Veredicto:** Open Interpreter gana en experiencia real y flexibilidad. Carter apuesta por un modelo más controlado y verificable. Ambos enfoques son válidos — son filosofías diferentes, no una siendo objetivamente mejor.

---

### 2.2 OpenClaw (antes Clawdbot / Moltbot)
**openclaw.ai — 369,000 stars — Activo**

El proyecto con más stars de la categoría. Su arquitectura es radicalmente diferente: no es un asistente que vive en tu terminal, sino un agente 24/7 accesible por mensajería (WhatsApp, Telegram, Discord, Slack, 20+ plataformas).

**Lo que hace bien:**
- 369,000 stars — validación masiva de uso real
- Multi-canal: hablas con él por WhatsApp mientras haces otra cosa
- 24/7 autónomo con cron jobs
- Voz en Android y wake word en macOS/iOS ya funcionando

**Sus limitaciones reales:**
- Windows requiere WSL2 — no nativo
- Los mensajes del usuario pasan por plataformas de terceros (WhatsApp, Telegram) — privacidad limitada
- No es un asistente conversacional en el sentido Jarvis — es más un bot de automatización multi-canal
- No tiene verificación formal de acciones documentada
- Tuvo problemas de marca registrada y se renombró dos veces (señal de inestabilidad legal)

**Comparación honesta con Carter (completo):**

| Dimensión | OpenClaw | Carter (completo) | Ventaja |
|-----------|---------|-------------------|---------|
| Comunidad | ✅✅✅ 369k stars | ❌ nuevo | **OpenClaw** |
| Privacidad | ❌ mensajes por terceros | ✅ 100% local | **Carter** |
| Windows nativo | ⚠️ WSL | ✅ | **Carter** |
| Experiencia Jarvis | ❌ es un bot de mensajería | ✅ conversacional | **Carter** |
| Voz integrada | ✅ funciona hoy | ✅ | Empate |
| Verificación acciones | ❌ no documentada | ✅ | **Carter** |
| Autonomía 24/7 | ✅ | ❌ no es su objetivo | **OpenClaw** |

**Veredicto:** OpenClaw y Carter resuelven problemas distintos. OpenClaw es un agente de automatización accesible remotamente. Carter es un asistente personal local conversacional. No compiten directamente — apuntan a usuarios diferentes.

---

### 2.3 Mark XXXIX
**github.com/FatihMakes/Mark-XXXIX — Activo — Creative Commons BY-NC**

El competidor más parecido a Carter en filosofía: Jarvis local con voz, visión de pantalla y control de PC. Es la inspiración más directa del concepto.

**Lo que hace bien:**
- Voz + visión de pantalla funcionando hoy
- Ultra-baja latencia conversacional con Gemini Live
- Control real de PC con terminal y archivos
- Experiencia de usuario pulida y demostrable

**Sus limitaciones reales:**
- **Depende de Google Gemini Live API** — los comandos de voz y contexto de pantalla van a servidores de Google. No es local.
- Requiere conexión a internet para funcionar
- Licencia BY-NC: no comercializable
- Sin PolicyEngine ni seguridad pre-LLM documentada
- Sin verificación formal post-acción

**Comparación honesta con Carter (completo):**

| Dimensión | Mark XXXIX | Carter (completo) | Ventaja |
|-----------|-----------|-------------------|---------|
| Voz + visión HOY | ✅ funciona | ✅ (proyectado) | **Mark XXXIX** |
| Privacidad | ❌ datos a Google | ✅ 100% local | **Carter** |
| Funciona offline | ❌ requiere internet | ✅ | **Carter** |
| Experiencia demostrable | ✅ demos en YouTube | ⚠️ en desarrollo | **Mark XXXIX** |
| Seguridad pre-LLM | ❌ | ✅ | **Carter** |
| Verificación post-acción | ❌ | ✅ | **Carter** |
| Latencia percibida | ✅ muy baja (Gemini) | ⚠️ depende del modelo local | **Mark XXXIX** |

**Veredicto:** Mark XXXIX gana en experiencia demostrable hoy y en latencia percibida (Gemini es más rápido que un modelo local en hardware consumer). Carter gana en privacidad y funcionamiento offline. La elección entre los dos es fundamentalmente una elección entre **velocidad/experiencia vs. privacidad/control**. No hay una respuesta objetiva — depende de qué valora el usuario.

---

### 2.4 InnerZero
**innerzero.com — Activo — Propietario gratuito**

El competidor comercial más directo. Local, basado en Ollama, con 30+ herramientas, memoria persistente y voz. Windows-first.

**Lo que hace bien:**
- Local puro con Ollama — sin cloud
- Windows nativo con detección automática de hardware
- Voz funcionando
- 30+ herramientas integradas
- Gratis, sin suscripción

**Sus limitaciones reales:**
- Código propietario — no auditable, no modificable
- No documenta verificación formal de acciones
- No documenta política de seguridad pre-LLM
- No open source — si el proyecto muere, no hay alternativa

**Comparación honesta con Carter (completo):**

| Dimensión | InnerZero | Carter (completo) | Ventaja |
|-----------|----------|-------------------|---------|
| Local + Ollama | ✅ | ✅ | Empate |
| Windows nativo | ✅ | ✅ | Empate |
| Voz | ✅ hoy | ✅ | Empate |
| Open source | ❌ | ✅ | **Carter** |
| Auditable | ❌ | ✅ hardcode_guard | **Carter** |
| Verificación formal | ❌ no documentada | ✅ | **Carter** |
| Madurez del producto | ✅ producto terminado | ⚠️ en desarrollo | **InnerZero** |

**Veredicto:** InnerZero es hoy la alternativa más parecida a Carter en Windows. La diferencia real es filosófica: InnerZero es un producto cerrado que funciona; Carter es un proyecto académico abierto con garantías arquitectónicas documentadas. Para uso doméstico InnerZero puede ser suficiente. Para investigación o auditoría, Carter es el único que permite verificar qué hace internamente.

---

### 2.5 Agent-S (Simular AI — Estado del arte académico)
**github.com/simular-ai/Agent-S — ICLR 2025 Best Paper**

El líder académico en automatización de computadoras por GUI. Logró 72.6% de accuracy en tareas de 100 pasos en OSWorld — superando el rendimiento humano promedio.

**Lo que hace bien:**
- Rendimiento verificado en benchmarks públicos
- Reconocimiento académico (ICLR 2025)
- Automatización de tareas complejas de múltiples pasos
- Cross-platform

**Sus limitaciones reales:**
- No es un asistente conversacional — es una plataforma de automatización
- Sin voz
- Sin memoria persistente conversacional
- Sin personalidad ni follow-ups
- Interfaz programática, no de usuario final

**Comparación honesta con Carter (completo):**

Agent-S y Carter no compiten directamente. Agent-S resuelve "automatización de GUI de alta precisión". Carter resuelve "asistente personal conversacional con acciones". Son categorías adyacentes, no iguales.

Lo relevante académicamente: Agent-S tiene benchmarks públicos que Carter no tiene. Si el profesor pregunta "¿cómo mides el rendimiento de Carter?", la respuesta es la matriz 18×30 — que es interna, no un benchmark público reproducible por terceros.

---

### 2.6 JARVIS (Microsoft / HuggingGPT)
**github.com/microsoft/JARVIS — 24,700 stars — Archivado**

Sistema de investigación de 2023 que conectaba ChatGPT con modelos de HuggingFace. Ya está archivado — el servicio fue discontinuado por Microsoft. Relevante como referencia histórica y conceptual, no como competidor activo.

---

## 3. Lo que Carter hace distinto — honestamente

Después de la comparación, hay tres cosas que Carter hace de forma genuinamente diferente a todos:

### 3.1 Verificación formal por herramienta (si funciona como especificado)
Carter tiene 14 tipos de verifier distintos con readback real:
- `app_open` verifica que el proceso post-date el lanzamiento (no proceso preexistente)
- `volume_set` lee el volumen real del sistema ±5% tolerancia
- `filesystem_write` verifica hash del archivo
- `web_open_url` verifica URL y título de ventana

**Caveat honesto:** Esta arquitectura es correcta en diseño. Su valor real depende de cuántas veces funciona correctamente en condiciones de uso real con el LLM corriendo. Eso es lo que la fase de validación debe demostrar.

### 3.2 Anti-fake-success como garantía arquitectónica
El `fake_success_guard` bloquea cualquier respuesta que afirme completitud sin evidencia verificadora. Los estados honestos (COMPLETED/UNVERIFIED/PARTIAL) son obligatorios. Ningún competidor documenta esto.

**Caveat honesto:** Un sistema que dice "no puedo confirmar" demasiado frecuentemente también falla al usuario. El balance entre honestidad y utilidad es el reto real.

### 3.3 hardcode_guard como mecanismo de calidad continua
El escáner AST garantiza que el runtime no degenere en hardcodes con el tiempo. Es un mecanismo de mantenimiento, no solo de diseño inicial.

**Caveat honesto:** Esto resuelve un problema de proceso de desarrollo, no necesariamente un problema del usuario final. El usuario final no ve el hardcode_guard — ve si Carter funciona o no.

---

## 4. Donde Carter está genuinamente detrás

Siendo completamente honesto, Carter tiene desventajas reales frente a sus competidores:

| Desventaja | Impacto real |
|-----------|-------------|
| **0 usuarios externos** | Ninguna validación independiente. Los bugs que aparecen con 1,000 usuarios no han aparecido. | 
| **Dependiente de hardware del usuario** | Un modelo local en 8GB de VRAM es notablemente más lento que Gemini. Mark XXXIX gana en latencia percibida. |
| **32 herramientas declarativas vs. código libre** | Open Interpreter puede resolver casos que Carter nunca anticipó. Carter requiere que alguien agregue la herramienta. |
| **Sin benchmarks públicos** | La matriz 18×30 es interna. No es reproducible por un tercero sin acceso al código. |
| **Voz y cámara aún no implementadas** | Los competidores tienen esto funcionando hoy. |
| **Un solo desarrollador** | Dependencia de una persona para mantenimiento y evolución. |

---

## 5. La apuesta real de Carter

Carter no es el mejor asistente de IA para Windows hoy. No puede serlo: está en desarrollo y sin voz todavía.

Lo que Carter propone es una **arquitectura específica** con garantías documentadas:

> Un asistente local puede ser confiable si y solo si: cada acción tiene verificación real con readback específico, el sistema no puede reportar éxito sin evidencia, la intención se clasifica sin depender de vocabulario de idioma, y la seguridad se aplica antes de que el LLM vea el input.

Esa es una hipótesis arquitectónica. La tesis no defiende que Carter sea mejor que Open Interpreter — defiende que ese conjunto de garantías produce un asistente más confiable en el segmento local-Windows-privado que las alternativas existentes.

**Es una propuesta, no un producto terminado compitiendo en el mercado.**

---

## 6. Respuestas preparadas para la defensa

**"Open Interpreter tiene 63,000 stars y lleva 3 años. ¿Por qué Carter?"**

> Open Interpreter es el referente de la categoría y lo reconocemos. Tomamos un enfoque diferente: herramientas declarativas verificables en lugar de código libre. La ventaja es la verificabilidad — cada acción tiene un readback específico y el sistema no puede afirmar completitud sin evidencia. La desventaja es menor flexibilidad. Para el segmento local-Windows-privado con énfasis en confiabilidad, creemos que el enfoque declarativo tiene ventajas. Pero no afirmamos ser mejores que Open Interpreter en general.

**"Mark XXXIX ya tiene voz y visión funcionando."**

> Correcto, y Mark XXXIX es un proyecto más avanzado en experiencia de usuario hoy. La diferencia fundamental es privacidad: Mark XXXIX envía los comandos de voz y el contexto de pantalla a los servidores de Google. Para un asistente que controla el PC del usuario — con acceso a archivos, aplicaciones y sistema — esa es una decisión arquitectónica con consecuencias de privacidad significativas. Carter apuesta por privacidad total aunque eso implique más latencia.

**"¿Cómo sabes que la verificación formal funciona?"**

> La validación completa requiere pruebas con el LLM real corriendo en condiciones reales — eso es precisamente lo que la fase de validación live debe demostrar antes de declarar Carter completo. Lo que tenemos hasta ahora es la arquitectura correcta y 490 tests que validan el comportamiento con un adaptador scripted. La evidencia de funcionamiento real es el paso siguiente, no el pasado.

**"¿Por qué no construiste sobre Open Interpreter en vez de desde cero?"**

> Open Interpreter usa AGPL-3.0, que requiere publicar el código de cualquier derivado distribuido. Para un proyecto académico con potencial de evolución futura, construir desde cero con arquitectura propia da más libertad. Además, el diseño de Carter — especialmente la capa de verificación y el PolicyEngine — requería integración desde la base, no como extensión de otro sistema.

---

## 7. Tabla final honesta

| Proyecto | Privacidad local | Windows nativo | Voz hoy | Verificación formal | Anti-fake-success | Open source | Usuarios reales | Madurez |
|----------|-----------------|----------------|---------|--------------------|--------------------|-------------|----------------|---------|
| **Carter (completo)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ⚠️ En desarrollo |
| Open Interpreter | ✅ | ⚠️ WSL | ✅ (01) | ❌ | ❌ | ✅ | ✅✅✅ | ✅ Maduro |
| OpenClaw | ⚠️ terceros | ⚠️ WSL | ✅ | ❌ | ❌ | ✅ | ✅✅✅ | ✅ Maduro |
| Mark XXXIX | ❌ Google | ✅ | ✅ | ❌ | ❌ | ⚠️ BY-NC | ✅ | ✅ Funcional |
| InnerZero | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ Funcional |
| Agent-S | ✅ | ✅ | ❌ | ⚠️ | — | ✅ | Investigación | ✅ Activo |

---

## 8. Conclusión honesta

Carter es un proyecto académico con una propuesta arquitectónica sólida y diferenciada. No es el asistente de IA más avanzado del mercado — eso sería Open Interpreter o Mark XXXIX. Tampoco es el más popular — eso es OpenClaw por mucho.

Lo que Carter propone es específico y defendible:
- El único asistente local Windows con verificación formal documentada por tipo de acción
- El único con guardia anti-fake-success como garantía arquitectónica
- El único con escáner de calidad continua (hardcode_guard) para prevenir degradación
- El único 100% local en Windows sin depender de WSL ni de APIs externas

**Esa combinación no existe junta en ningún otro proyecto documentado.**

Si eso es suficiente para una tesis depende de los criterios de evaluación. Si la tesis se juzga por novedad arquitectónica y rigor de diseño, Carter tiene argumentos fuertes. Si se juzga por cantidad de usuarios o años en producción, Carter pierde frente a sus competidores más maduros.

Un evaluador honesto reconocería ambas cosas.

---

*Documento generado para defensa académica — 2026-05-06*  
*Carter evaluado según ContextoCarter.md (especificación completa con voz y cámara)*  
*Competidores evaluados según estado real documentado a mayo 2026*
