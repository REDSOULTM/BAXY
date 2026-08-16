# Diseño: Jarvis PROACTIVO (sugerencia sin turno del usuario)

> **Estado:** ✅ IMPLEMENTADO 2026-06-07 (gateado OFF). Decisión del usuario 2026-06-07.
> Piezas: `memory_pkg/proactive_notifier.py` (toast+voz+anti-molestia),
> `memory_pkg/jarvis_proactive.py` (orquestador disparo-en-vivo + create/reject),
> `ambient_observer.py` (callback `on_app_transition`), `domain_tools/routine.py`
> (`created_by` + list filtrable), cableado en `agent.py`. Tests: `test_jarvis_proactive.py`
> 6/6 + suite Jarvis 61/61. Gates: `GEMMA4_JARVIS_PROACTIVE` **ON por default**
> (toast, no-invasivo; apagar con `=0`); `GEMMA4_JARVIS_PROACTIVE_TTS` OFF (voz,
> opt-in); `GEMMA4_JARVIS_CHAT_OFFER` OFF. Decisión del user 2026-06-07: proactivo
> activo por default (el toast es no-invasivo + anti-molestia + cooldowns).
> **Qué resuelve:** hoy la sugerencia de rutina se ANEXA a una respuesta de Baxy
> (necesita que el user le escriba). El user quiere lo opuesto: estar usando la PC
> NORMAL (sin chatear) y que Baxy, **por iniciativa propia**, le sugiera automatizar
> una rutina que detectó — como el Jarvis de Iron Man.

## Decisiones del usuario (2026-06-07)
- **Canal de aviso:** toast de Windows (siempre) + voz TTS (opcional, p.ej. modo
  manos-libres/accesibilidad).
- **Disparo:** EN EL MOMENTO que se completa el patrón (no por intervalos). Ej: al
  abrir Discord justo después de Steam por 8ª vez → avisa ahí.
- **REVERSIBILIDAD TOTAL (clave, pedido del user):** TODO lo que Jarvis cree debe
  poder apagarse/borrarse fácil si el user ya no lo quiere. Cada rutina creada por
  Jarvis lleva una opción de OFF accesible. Ver sección "Reversibilidad" abajo.
- **Alcance de esta iteración:** diseño escrito. Implementar gateado OFF después.

## Diferencia con lo que YA existe
| Pieza | Hoy | Falta para proactivo |
|---|---|---|
| Observador de fondo (daemon, poll 5s) | ✅ `ambient_observer.py::_loop` | — (es la base) |
| pattern_miner (sano tras fixes) | ✅ | — |
| Oferta + cooldowns (`suggestion_queue`) | ✅ | — (se reusa) |
| TTS (Piper) | ✅ `voice/tts.py` | invocarlo SIN turno |
| **Disparo en vivo al completar patrón** | ❌ | **construir** |
| **Canal de salida proactivo (toast)** | ❌ | **construir** |
| **Resolver el sí/no fuera del chat** | ❌ | **construir** |

## Arquitectura propuesta

### 1. Disparo en vivo — en el `_loop` del observador
Punto de enganche: `ambient_observer.py::_loop` (línea ~195), justo donde detecta
una transición de app (`app && app != self._cur_app`). Ahí, ADEMÁS de registrar el
evento, llamar a un nuevo `_check_live_pattern(app, now)`:

```
# pseudocódigo (NO implementado)
def _check_live_pattern(self, just_opened_app, now):
    if not _proactive_enabled():        # gate GEMMA4_JARVIS_PROACTIVE=0 default OFF
        return
    # ¿el app que se acaba de abrir es el TARGET de un patrón cuyo TRIGGER acaba de pasar?
    recent = self.log.events(since_ms=int((now-120)*1000))   # ventana de 2 min
    if not recent: return
    trigger = _prev_actionable(recent, before=just_opened_app)  # el app/boot anterior
    if trigger is None: return
    # minar SOLO si este par (trigger->just_opened) supera umbrales (reusa pattern_miner)
    cands = mine_simple_patterns(self.log.events(since_ms=30d))
    match = [c for c in cands if c.trigger_key==trigger and c.target_key==just_opened_app]
    if not match: return
    cand = self._queue.next_suggestion(match)   # respeta cooldowns/rechazos (REUSA)
    if cand is None: return
    self._emit_proactive(cand)                  # toast + voz opcional
```

**Por qué acá:** el `_loop` ya tiene el evento fresco y corre en el daemon thread —
no toca el turno de voz (latencia 0 para el chat). El miner ya está acotado a 30d.

### 2. Canal de salida proactivo — `_emit_proactive(cand)`
Nuevo módulo `memory_pkg/proactive_notifier.py` (o método del observer):
- **Toast (siempre):** usar `winsdk` (ya instalado) — `winrt`-based toast nativo, o
  agregar `windows-toasts` (gratis, MIT). Texto: la frase de `pattern_miner.jarvis_phrase(lang,'offer')`.
  El toast lleva 2 botones: **"Sí, automatizá"** / **"No"** (acción → callback).
- **Voz (opcional, gate GEMMA4_JARVIS_PROACTIVE_TTS):** si está ON (modo manos-libres),
  invocar `voice/tts.py::StreamingTTS().speak(frase)` en el bg thread. Cuidar: no
  pisar un TTS de un turno en curso (lock simple).
- **Anti-molestia:** el `suggestion_queue` YA gobierna esto (1/hora, 3/día, cooldown
  30d por rechazo). El disparo en vivo SOLO ofrece si la queue lo libera. + no
  avisar si hay una llamada/pantalla completa activa (chequear foco: si el app en
  foco es Zoom/Meet/juego fullscreen → posponer).

### 3. Resolver el sí/no FUERA del chat
Dos caminos, ambos sin obligar a abrir el chat:
- **Botón del toast:** "Sí" → callback que llama `routine create` directo (reusa
  `_handle_pending_suggestion` o su lógica). "No" → `suggestion_queue.mark_rejected`.
- **Voz (si TTS on):** tras hablar, abrir una mini-ventana de escucha (reusa wake/STT)
  para captar "sí"/"no". Más complejo; iteración 2.
- **Fallback:** si el user ignora el toast, se auto-descarta tras N minutos y la
  queue lo cuenta como "ofrecido" (respeta el rate-limit, no re-spamea).

## Reversibilidad — TODA rutina de Jarvis se puede apagar/borrar (pedido del user)

Principio: nada que Jarvis automatice queda "pegado". El user manda. La buena
noticia: el `routine_tool` YA soporta `list` / `disable` / `enable` / `delete`
(`domain_tools/routine.py:472-492`) — no hay que construir el motor, solo cablearlo
para las rutinas de Jarvis y hacerlo VISIBLE/FÁCIL.

### Qué se agrega
1. **Marca de origen:** las rutinas que crea Jarvis se guardan con un tag
   `created_by="jarvis"` en su metadata (campo nuevo en el `create`), para poder
   listarlas/distinguirlas de las que el user creó a mano.
2. **Nombre claro:** label autogenerado legible, ej. `jarvis: Steam → Discord`, así
   en la lista el user reconoce qué hace cada una.
3. **OFF por rutina (3 formas, todas reusan list/disable/delete existentes):**
   - **Por voz/chat:** "Baxy, apagá la rutina de Discord" / "olvidate de abrir
     Discord con Steam" → resuelve por embeddings al label de la rutina → `disable`
     (o `delete` si dice "borrala"). DISABLE = reversible (queda apagada pero se
     puede re-`enable`); DELETE = la elimina.
   - **Lista para revisar:** "Baxy, qué rutinas tenés / qué automatizaste" →
     `routine list` filtrado por `created_by=jarvis`, mostrando estado on/off de
     cada una.
   - **Botón en el toast de creación:** cuando Jarvis crea la rutina, el toast de
     confirmación incluye un botón **"Deshacer"** (delete inmediato) por si el user
     se arrepiente al toque.
4. **Tri-estado honesto:** `disable` (apagada, recuperable) vs `delete` (borrada).
   El user elige; por default ofrecer DISABLE (menos destructivo, reversible) y
   confirmar antes de DELETE (irreversible = guarda de confirmación, CLAUDE.md).

### Casos de uso de reversibilidad
- **"Ya no quiero esa rutina":** "Baxy, apagá lo de Discord" → disable. Si después
  la querés de nuevo: "reactivá la rutina de Discord" → enable.
- **"Apagá TODO lo que automatizaste":** "Baxy, desactivá todas tus rutinas" →
  disable de todas las `created_by=jarvis`. Reversible.
- **"Borrá esto, no lo quiero más":** "borrá la rutina de X" → confirma ("¿seguro?
  no se puede deshacer") → delete.
- **Me arrepentí al crearla:** botón "Deshacer" en el toast de confirmación.

### Por qué esto respeta el CLAUDE.md
- Reversibilidad como requisito (no lujo). El user puede inspeccionar (list) y
  olvidar (disable/delete) todo lo que Jarvis hizo — igual que el inspect/forget del
  perfil de gustos.
- Confirmar lo irreversible: DELETE pide confirmación; DISABLE no (es recuperable).
- El LLM resuelve "apagá la de Discord" por embeddings al label, no por keywords.

## Gates
- `GEMMA4_JARVIS_PROACTIVE` — disparo en vivo + toast. **ON por default** (user
  2026-06-07; el toast es no-invasivo). Apagar con `GEMMA4_JARVIS_PROACTIVE=0`.
- `GEMMA4_JARVIS_PROACTIVE_TTS=1` — además habla por voz.
- Hereda los gates existentes: `GEMMA4_JARVIS`, `GEMMA4_AMBIENT_OBSERVER`.

## Riesgos / cuidados (CLAUDE.md)
- **No-molestia es la prioridad #1** (el síntoma original era intrusividad). Empezar
  conservador: solo patrones MUY sólidos (los umbrales ya en count=8/0.75), respetar
  cooldowns, NO avisar en fullscreen/llamada.
- **Probar EN VIVO** (regla 3.5): un toast real + un patrón real, ver que aparece y
  que el sí/no funciona. El observador en test NO graba (GEMMA4_DIAG) — para probar
  esto hace falta `GEMMA4_AMBIENT_FORCE=1` + un dir temporal sembrado.
- **Privacidad:** el toast muestra nombres de app (metadata, OK); nada de contenido.
- **Dependencia nueva:** `windows-toasts` (MIT, gratis) — autorizado por CLAUDE.md
  regla 5 (deps gratis). winsdk ya está si se quiere sin dep nueva (más código).
- **Latencia:** el disparo corre en el daemon, NO en el turno de voz → 0 impacto al
  chat. El miner ya está acotado a 30d.

## Plan de implementación (cuando se apruebe)
1. `proactive_notifier.py`: toast (windows-toasts) + speak opcional + anti-molestia.
2. `_check_live_pattern` + `_emit_proactive` en el observer, gateado OFF.
3. Callbacks del toast → routine create / mark_rejected (reusa la lógica del chat).
4. Tests: patrón sembrado → simular transición → assert que emite (mock toast/TTS).
5. EN VIVO: `GEMMA4_JARVIS_PROACTIVE=1`, reproducir una secuencia real, ver el toast.
6. Gate OFF por default; el user lo prende cuando quiera.
