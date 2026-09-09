# C03 — controles literales UI/voz del tramo45

Desarrollo consumido,fuera de reserva fresca. Ventanas reales de `py main.py`,
modelo registrado,Qwen3-4B-Instruct-2507 Q4_K_M. Hook diagnóstico local en ambas
variantes comparables;no modifica decisiones ni contenido. Voz habilitada.

| Corrida / entrada literal | Respuesta visible literal | Adjudicación |
|---|---|---|
| native-ui45: `hola quien eres` | Hola, soy BAXY. Por ahora no puedo responder porque mi mente no está disponible. | Fallo de utilidad por caída nativa; causa coherente con proceso muerto. visible-failure.png. |
| owned-stream-ui45: `hola quien eres` | Hola, soy BAXY, tu compañero en el PC. ¿En qué puedo ayudarte? 😎 | Útil,identidad coherente; conversación sin operación. visible-greeting.png. |
| owned-stream-ui45: `¿No está silenciado el audio?` | El audio del altavoz (Realtek(R) Audio) está activo y el volumen está en 100. | audio.status verificado,muted=false,level100,endpointRealtek. visible-audio.png. |
| owned-stream-ui45: `dime la hora, no abras Steam` | Son las 23:12. | system.time:UTC2026-09-07T02:12:31.6197611+00:00,offset−180. No abrir Steam. visible-clock.png. |

Saludo inicial idéntico en ambas:«¡Hola! ¿Cómo estás?». El agente introdujo y
envió los tres controles mediante la skill Windows. En native-ui45 set_value
falló;se comprobó el campo y se tecleó una única entrada enviada. En la variante
corregida un intento de escribir la consulta sin recuperar foco no introdujo
texto;se enfocó y se comprobó el literal antes de enviar. No duplicados enviados.

La primera observación scoped-reader-ui45 tenía entrada externa del mismo
saludo y caída similar;no se adjudica allí la respuesta como visible porque no
se capturó. Su screenshot observado de Codex queda excluido de evidencia BAXY.
Los dumps permanecen privados en %LOCALAPPDATA%/CrashDumps;NATIVE_DUMP45.json
contiene rutas/hashes y límites de interpretación. No pruebas100 ni audio
comprendido mediante transcripción física de estas frases.
