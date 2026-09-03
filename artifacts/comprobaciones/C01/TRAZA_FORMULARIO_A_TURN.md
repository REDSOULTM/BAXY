# Traza formulario → `/turn` y divergencias (C01)

## Recorrido público

1. `FieldCenter.tsx` `handleSubmit`: si `armed` (agente listo, draft no vacío,
   adjuntos terminados de subir), `POST /turn` con `{ text, attachments }`.
   Vacía el draft al volver `fetch`, no al admitir.
2. `field-native-bridge.js` intercepta `fetch` y lo envía por
   `baxy.field.v1` al host WebView. No hay HTTP de red: el `/turn` de Vite es
   un proxy de desarrollo, no la API de producto.
3. `FieldUiBridge.OnWebMessageReceived`: descarta cualquier origen que no sea
   `https://baxy.local/index.html`. Luego `HandleHttpAsync` delega en
   `FieldProductChannel`.
4. `FieldProductChannel.HandleTurnAsync`:
   - `FieldBridgeContract.TryAcceptTurn(IsInputEnabled, text)` → 409
     `agent_not_ready` o 400 `invalid_text`.
   - `MissionInputContract.ValidateAndTrim` → 400 `invalid_text` (nulo, UTF-16
     mal formado, >4096). Publica la guía de rechazo en el chat.
   - Emite evento público `admission` (acuse). Esto no es la respuesta final.
   - `MainWindowViewModel.SubmitAsync(MissionInput, token)` →
     `MissionInputPipeline.DispatchAsync` → ejecución real (mente, Core,
     providers, journal, colas, prosa).
   - HTTP `{ ok:true, status:"accepted" }` al terminar `SubmitAsync`. La cola
     de composición puede publicar después. `accepted` ≠ final visible.
5. Proyección pública: `activity` (mensajes), `boot_stage` (progreso),
   `agent`, `state`, `session`. Un socket que se reconecta recibe el estado
   actual, no el histórico.

## Sesión, adjuntos, cancelar, Nueva sesión

| Control | Ruta | Conducta |
|---|---|---|
| Texto | `POST /turn` `{text}` | Canal compartido |
| Adjunto | `POST /upload` | `attachments_not_supported` 501. El array `attachments` de FieldCenter se ignora en `/turn` |
| Cancelar | texto público `cancelar` por `/turn` | No hay verbo HTTP nuevo. `ConfirmationReplyParser` lo interpreta si hay confirmación pendiente |
| Nueva sesión | `POST /sessions/new` | `StartNewUiSession`: limpia `Messages` y saluda; **no** retira `_pendingMindPlan` (defecto C05) |
| Envío ocupado | `IsInputEnabled == false` | 409 `agent_not_ready` |

## Divergencias que C01 cierra o deja documentadas

1. **Dos `SubmitAsync`.** El público exige `CanSend` (draft no vacío) y
   capturaba `MissionInputRejectedException` con guía visible. El interno
   (bridge) exigía `IsInputEnabled` y dejaba burbujear el rechazo. El canal
   ahora valida y publica la guía antes de despachar; el interno sigue
   sirviendo texto ya extraído. Ambos adaptadores llaman al canal.
2. **Bridge vs ViewModel.** El bridge exigía Window+WebView2 y proyectaba
   eventos sólo a sockets. Extraído a `FieldProductChannel` + `IFieldEventSink`.
   El bridge es el adaptador de origen/WebView. El conductor es el adaptador
   sin ventana. Misma admisión, turno y publicación.
3. **`/turn` lee `text`, no `attachments`.** FieldCenter los envía; el producto
   no admite adjuntos (`/upload` 501). El conductor replica esa admisión.
4. **`accepted` no es final.** El conductor espera actividad BAXY pública o
   un terminal honesto (silencio / filtrado / sin final) con timeout.

## Lo que no se toca

Política de origen de WebView, ausencia de API HTTP de red, descomposición
del ViewModel (C02), fallos de prosa/verificación/plan pendiente (C03–C05).
