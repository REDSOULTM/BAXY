# C03 — prueba de producto300–301 y reapertura302

300 no llegó a ejecutar turnos: el perfil de diagnóstico anidado fue rechazado
por WindowsPrivateStorage.PreparePrivateDataRoot, que exige un hijo directo de
LOCALAPPDATA/BAXY. Se preservó el fallo runtime_not_ready; no se presenta como
fallo del saludo.301 corrigió sólo la ubicación del perfil, sin relajar seguridad.

301 ejecutó tres casos de desarrollo mediante py main.py --conductor, source298/299,
runtime registrado2507, sesiones nuevas entre casos y sin inyección de decisiones.
Modelo/manifest sin cambios. Dos de tres respuestas útiles:

- me llamo emmanuel, dime hola emmanuel → Hola Emmanuel, ¿cómo estás? 😎
- me llamo Albeda → ¡Hola Albeda! ¿En qué puedo ayudarte hoy? 😎
- my favorite city is Lima → Lima (NO útil).

Todos terminaron publicados sin timeout ni fallo de composición, lo que no hace
correcto al tercero. Su primera respuesta bruta inventa «I’ve been there a few
times» y pregunta por un lugar favorito. El retry devuelve sólo «Lima». No aceptar
la primera por ser más larga ni relajar veracidad; tampoco contar la publicación
como respuesta correcta. Revisar payload/contexto y primera transformación exacta
antes de otra regla de palabras. Contraste298 sin historial daba otro borrador;
no son payloads idénticos ni una comparación causal del modelo.

Capturas y perfil completos privados, referencias y adjudicación mínima en
astra-memory-product301. Conductor NO acredita píxeles de UI ni audio físico.
No se pidieron escrituras de memoria. RESULT.json resume operaciones del journal.

302 reabre py main.py sin probe, override ni temporizador para que el dueño use
BAXY. Se verificó proceso y ventana BAXY, y bienvenida compuesta publicada t0.
No se enviaron mensajes del agente a esa nueva instancia. Cuestionario742 sigue
disponible en http://127.0.0.1:63179/ y sus marcas permanecen intocadas.

Validación vigente:1022pass0skip5,65s Python298;1879pass0skip2m25s .NET299;
Fast299 VERDE con build19,33s0warn/error. No nuevo Full ni publicación/promotion.
Los fallos de París, atribución del nombre, conocimiento/memoria contextual, demás
rutas y criterios de aceptación integral mantienen C03 EN_CURSO.
