---
name: troubleshoot
triggers: ["no funciona", "no anda", "se rompio", "se rompió", "no abre", "no abrio", "no abrió", "no se abre", "no responde", "no carga", "no escucha", "no escuchas", "no me oyes", "no me escuchas", "no escribi", "no escribió", "error", "falla", "falló", "fallo", "no aparece"]
priority: high
---

# Troubleshoot flow

Cuando el usuario dice que algo no funciona, el patrón correcto es DIAGNOSTICAR
antes de actuar. No suponer la causa; medir.

## Decisión 1: ¿qué falla? (clarificar)

Si el usuario dice "no funciona" sin contexto:
- **NO** abrir / cerrar nada todavía.
- **NO** asumir que sabes a qué se refiere.
- Pedir una aclaración corta: "¿qué intentaste hacer y qué pasó?".

Si la sesión venía haciendo algo concreto (en history reciente), entonces sí
asumir que se refiere a eso.

## Flujos por dominio

### Una app no abre

1. ¿La app está instalada? `app(action="search", query="<name>")` lista
   matches con sources (PATH, registry, StartMenu, Steam, Epic).
2. ¿El proceso ya está corriendo? `verify(action="app_opened", name="<name>")`
   chequea tasklist + windows.
3. Si está instalada pero no responde: probar Steam/Epic deeplink antes que
   `app.open` (más directo cuando aplica).
4. Si nada: reportar honestamente "no encontré '<name>' instalado" o
   "el lanzamiento se dispatch pero la ventana no apareció en 2s — puede
   estar cargando, esperá unos segundos".

### El audio no funciona

1. `audio(action="get_volume")` → reportar level + muted state actual.
2. Si muted=True y el user quería oír: `audio(action="mute", state=False)`.
3. Si el problema es device wrong (e.g. salía por HDMI cuando quería headphones):
   `audio_device(action="list")` y proponer cambio. **Requiere SoundVolumeView**
   (helper externo); si no está, reportar `needs_dependency` con install hint.

### El micrófono no escucha

1. `voice(action="status")` → reportar si Vosk + Whisper están cargados.
2. Si voice no está enabled: `voice(action="start")`.
3. Si el problema es device wrong: chequear que `inputDevice` en settings
   apunte al mic correcto. No hay tool nativo para enumerar mics — pedir al
   user que abra Sound Settings de Windows.

### Una ventana específica no responde

1. `window(action="list")` → confirmar que la ventana existe con el título
   esperado.
2. Si existe: `window(action="focus", title="<title>")` para traerla al
   frente. Si focus dispatched pero título no es foreground tras 1s →
   reportar UNVERIFIED ("intenté enfocar pero el sistema tiene otra ventana
   activa").
3. Si NO existe: la app probablemente está corriendo en background. Considerar
   `app(action="close")` + `app(action="open")` como reset.

### Un archivo no aparece donde se esperaba

1. `filesystem(action="list", path="<dir>")` → confirmar el directorio.
2. `filesystem(action="search", root="<dir>", pattern="*<name>*")` con
   budget acotado.
3. Si el path es ambiguo (mayúscula vs minúscula en NTFS: case-insensitive,
   pero el resultado preserva el case original): reportar el path exacto
   encontrado.

### Una tool sigue fallando

Si una tool específica falla 3+ veces en el mismo turn, el loop detector ya
emite `[loop-detector CRITICAL] ...` y aborta. Si no aborta pero claramente
no avanza:

- Probar **otra estrategia**, no la misma tool con args distintos.
- Si la otra tool tampoco anda: reportar honestamente UNVERIFIED al usuario
  y pedir que pruebe manualmente.

## Anti-patrones

- **NO** decir "ya está" / "listo" cuando el verifier reportó
  `confirmed=False` o `confirmed=None`. El footer estructural
  `[N no confirmada(s)]` se concatena automáticamente; el LLM debe alinear su
  texto con eso.
- **NO** repetir la misma `gui(action="click", x=N, y=M)` si la primera no
  produjo cambio visible. Verificar con `gui(action="screenshot")` + vision
  antes de re-clickear.
- **NO** culpar al usuario por errores del agente. Reportar lo medido sin
  juzgar.
