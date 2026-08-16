# Adaptadores externos: contraste y decisiones (2026-07-16)

## Principio común

La arqueología Carter → dos BAXY mostró el mismo patrón de fallo: activar una
URI, pulsar una tecla o abrir una aplicación se confundía con completar la
misión. El corte actual usa tres fases: resolver una identidad observable,
cruzar una única frontera de efecto y comprobar una postcondición independiente.
Un fallo posterior al efecto conserva `EffectMayHaveOccurred=true` y bloquea
reintentos automáticos.

## Fuentes primarias contrastadas

- Microsoft Graph documenta `POST /me/calendar/events` y exige
  `Calendars.ReadWrite`; Outlook también documenta `AppointmentItem.Save` y
  `GetItemFromID`. BAXY usa la sesión MAPI autenticada de Outlook Desktop y
  relee `EntryID`, asunto y tiempos UTC. También existe un adapter Graph real,
  activado únicamente con `BAXY_GRAPH_ACCESS_TOKEN`, con `transactionId` y
  postlectura del evento; nunca extrae tokens de otras aplicaciones.
  - https://learn.microsoft.com/graph/api/calendar-post-events
  - https://learn.microsoft.com/office/vba/api/outlook.appointmentitem.save
  - https://learn.microsoft.com/dotnet/api/microsoft.office.interop.outlook._namespace.getitemfromid
- Word documenta `SaveAs2`; para evitar modales y procesos huérfanos BAXY crea
  paquetes mínimos ISO 29500 `docx`/`xlsx`, los reabre, valida su XML y sólo
  publica un ID opaco. La cuenta Outlook autenticada se reserva al calendario.
  - https://learn.microsoft.com/office/vba/api/word.saveas2
- CDP publica `Page.navigate`; el adaptador inicia un perfil Edge aislado,
  navega por WebSocket y consulta `location.href` como postlectura. Streaming
  además valida dominio de servicio y rechaza redirecciones a login.
  - https://chromedevtools.github.io/devtools-protocol/1-3/Page/
- Windows Media OCR documenta `RecognizeAsync(SoftwareBitmap)`. BAXY resuelve
  exclusivamente `capture_<uuid>.bmp` dentro del almacén privado y usa un
  language pack instalado. Visión conserva el mismo binding y hash al llamar
  un endpoint HTTPS compatible configurado.
  - https://learn.microsoft.com/uwp/api/windows.media.ocr.ocrengine.recognizeasync
- Spotify mantiene Search y Start/Resume Playback en la API 2026. El adaptador
  soporta Web API con token efímero y, para la sesión Desktop ya autenticada,
  UI Automation sobre un resultado de título exacto más postlectura en la zona
  del reproductor; SMTC sigue disponible para controles corrientes.
  - https://developer.spotify.com/documentation/web-api/references/changes/february-2026
- Valve documenta App IDs y `steam://run/<appid>` en Steamworks, pero no promete
  que aceptar `steam://install/<appid>` equivalga a descarga iniciada. BAXY
  conserva la URI sólo como dispatch y exige transición de `appmanifest` para
  éxito. `librarycache` de la cuenta prueba pertenencia local; progreso sale de
  bytes/flags del manifest; lanzamiento exige proceso nuevo bajo `installdir`.
  Las compras reales siguen prohibidas.
  - https://partner.steamgames.com/doc/API/iSteamApps
  - https://help.steampowered.com/faqs/view/71AB-698D-57EB-178C
- Windows documenta `DeviceInformationPairing.PairAsync` y exige diálogo de
  consentimiento en Desktop. BAXY enumera primero, retiene el ID nativo sólo en
  memoria, deja el consentimiento a Windows y relee `IsPaired`.
  - https://learn.microsoft.com/windows/apps/develop/devices-sensors/pair-devices
- WIA es la plataforma oficial para escáneres; el spooler es autoridad para el
  job de impresión. Ninguna operación declara éxito sólo porque se abrió una
  aplicación asociada.
  - https://learn.microsoft.com/previous-versions/windows/desktop/wia/-wia-startpage
- `netsh wlan` documenta perfiles, connect y disconnect. BAXY nunca exporta
  claves: devuelve IDs opacos, despacha el perfil exacto y relee interfaz y
  perfil conectado. Brillo usa `WmiMonitorBrightnessMethods.WmiSetBrightness`
  y relee cada monitor. Luz nocturna permanece fail-closed porque no existe una
  API pública estable equivalente; no se manipula CloudStore/registro.
  - https://learn.microsoft.com/windows-server/administration/windows-commands/netsh-wlan
  - https://learn.microsoft.com/windows/win32/wmicoreprov/wmimonitorbrightnessmethods

## Fronteras deliberadas

- No se extraen cookies, tokens de navegadores o credenciales de aplicaciones.
- No se elige un dispositivo, impresora, red, canción o juego por “primero de
  la lista” sin una identidad exacta.
- Pairing, impresión, escaneo, Wi‑Fi, ajustes, instalación/cancelación Steam y
  calendario mutante siguen sujetos a riesgo/confirmación del core.
- `night_light` y compras Steam fallan cerradas: completar una familia no
  justifica usar APIs privadas, registro no documentado o dinero real.

## Evidencia física del host

- `external_adapters_gate_v2.json`: **14/14 verificados**, incluidos calendario
  Outlook/MAPI, Office OOXML, CDP, búsqueda, streaming, captura, OCR y selección
  exacta `Billie Jean` en Spotify con postlectura del reproductor.
- `hardware_effects_gate.json`: **7 verificados, 0 fallos, 5 omitidos por no
  existir un objetivo exacto**. Se observó un job real en la Brother
  DCP-T720DW y una captura WIA de 11.923.854 bytes. No había dispositivo
  Bluetooth emparejable, perfil Wi-Fi conectado resoluble, brillo WMI, juego
  poseído/no instalado ni descarga parcial; no se inventaron esos efectos.
- `steam_launch_gate.json`: lanzamiento físico de un AppID instalado, proceso
  nuevo verificado bajo su `installdir` y cierre dirigido únicamente a ese PID.
  Instalación y cancelación conservan pruebas contractuales, pero este host no
  ofreció un juego poseído/no instalado ni una descarga parcial para probarlas.
