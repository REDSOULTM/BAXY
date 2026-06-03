---
name: troubleshoot
priority: high
examples: ["una app no abre o no responde o se colgó", "algo dejó de funcionar y no sé por qué", "no me responde o se quedó colgado", "esto falla o da error, ayudame a arreglarlo", "an app crashed or stopped responding, help me fix it", "algo parou de funcionar e não sei por quê"]
---

# Troubleshoot flow

Patrón: DIAGNOSTICAR antes de actuar. No suponer la causa; medir.

## Decisión 1: ¿qué falla? (clarificar)
Si dice "no funciona" sin contexto: **NO** abrir/cerrar nada, **NO** asumir a qué se refiere. Pedir aclaración corta: "¿qué intentaste hacer y qué pasó?". Solo si el history reciente venía haciendo algo concreto, asumir que se refiere a eso.

## Flujos por dominio

### Una app no abre
1. ¿Instalada? `app(action="search", query="<name>")` → matches con sources (PATH, registry, StartMenu, Steam, Epic).
2. ¿Ya corriendo? `verify(action="app_opened", name="<name>")` (tasklist + windows).
3. Instalada pero no responde: probar Steam/Epic deeplink antes que `app.open` (más directo).
4. Nada: reportar honesto "no encontré '<name>' instalado", o "el lanzamiento se dispatch pero la ventana no apareció en 2s — puede estar cargando, esperá unos segundos".

### El audio no funciona
1. `audio(action="get_volume")` → reportar level + muted actual.
2. muted=True y quería oír: `audio(action="mute", state=False)`.
3. Device wrong (e.g. salía por HDMI, quería headphones): `audio_device(action="list")` y proponer cambio. Requiere SoundVolumeView; si falta, reportar `needs_dependency` con install hint.

### El micrófono no escucha
1. `voice(action="status")` → reportar si Vosk + Whisper están cargados.
2. voice no enabled: `voice(action="start")`.
3. Device wrong: chequear que `inputDevice` en settings apunte al mic correcto. No hay tool nativo para enumerar mics → pedir al user que abra Sound Settings de Windows.

### Una ventana específica no responde
1. `window(action="list")` → confirmar que existe con el título esperado.
2. Existe: `window(action="focus", title="<title>")`. Si focus dispatched pero el título no es foreground tras 1s → reportar UNVERIFIED ("intenté enfocar pero el sistema tiene otra ventana activa").
3. NO existe: probablemente corre en background. Considerar `app(action="close")` + `app(action="open")` como reset.

### Un archivo no aparece donde se esperaba
1. `filesystem(action="list", path="<dir>")` → confirmar directorio.
2. `filesystem(action="search", root="<dir>", pattern="*<name>*")` con budget acotado.
3. Path ambiguo (NTFS es case-insensitive pero preserva el case original): reportar el path exacto encontrado.

### Una tool sigue fallando
Si una tool falla 3+ veces en el mismo turn, el loop detector emite `[loop-detector CRITICAL] ...` y aborta. Si no aborta pero no avanza: probar **otra estrategia** (no la misma tool con args distintos). Si la otra tampoco anda: reportar UNVERIFIED y pedir que pruebe manualmente.

## Anti-patrones
- **NO** decir "ya está"/"listo" con verifier `confirmed=False`/`None`. El footer `[N no confirmada(s)]` se concatena solo; alineá tu texto con eso.
- **NO** repetir la misma `gui(action="click", x=N, y=M)` si la 1ª no produjo cambio visible. Verificar con `gui(action="screenshot")` + vision antes de re-clickear.
- **NO** culpar al usuario por errores del agente. Reportar lo medido sin juzgar.
