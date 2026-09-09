# Identidad de salida de audio — C03, 2026-09-06

## Problema demostrado

ASTRA-TRAMO-37 y astra-air-device-followup3: «Dime qué dispositivo de audio está
activo» obtiene volumen/silencio, no identidad. AudioStatusReceipt y AudioStatusResult
no incluían nombre. WindowsCoreAudioPlatform conservaba IMMDevice pero sólo leía
su identificador privado y activaba IAudioEndpointVolume. No bastaba cambiar prosa.

## Herencia y contraste

- biblioteca/gemma4-agent/codigo-docs/prompts/tool_rules/audio.md documenta
  devices y set_default separados de lectura/ajuste de volumen. El código de
  herencia `D:/Perfil/Escritorio/ETC/Programacion/Probando Gemma 4/gemma4_agent/domain_tools/audio_devices.py`,
  funciones de enumeración y `_svv_current_defaults` (líneas203 y siguientes),
  conserva nombres y distingue roles Console/Multimedia/Communications. Usa PnP y
  SoundVolumeView; no se copia su dependencia ni la elección del primer dispositivo.
- [Microsoft: propiedades de dispositivos Core Audio](https://learn.microsoft.com/en-us/windows/win32/coreaudio/device-properties):
  IMMDevice.OpenPropertyStore permite leer propiedades del mismo endpoint. GetValue
  puede devolver S_OK con VT_EMPTY cuando la propiedad no existe; eso no es un nombre.
- [Ficha oficial PKEY_Device_FriendlyName](https://github.com/MicrosoftDocs/win32/blob/docs/desktop-src/CoreAudio/pkey-device-friendlyname.md):
  contiene la etiqueta visible del endpoint, con PROPVARIANT de tipo VT_LPWSTR.
- [Ejemplo de Microsoft, EndpointVolume](https://github.com/microsoft/Windows-classic-samples/blob/main/Samples/Win7Samples/multimedia/audio/EndpointVolume/endpointvolumechanger.cpp):
  muestra la lectura con STGM_READ y GetValue. BAXY no copia la inclusión del ID
  físico en el texto del ejemplo; sólo conserva el nombre visible.
- [Implementación de WebRTC](https://webrtc.googlesource.com/src/+/488eb98616b41d85b03a96fa5b4a0ed12b944c69/modules/audio_device/win/core_audio_utility_win.cc):
  aplica la misma lectura y comprueba tipo/puntero; evidencia de uso en otro producto.
- [Incidencia reproducible en win32metadata](https://github.com/microsoft/win32metadata/issues/339):
  registra la clave GUID a45c254e-df1c-4efd-8020-67d146a850e0, propiedad14. El
  problema histórico de metadatos no obliga a añadir un paquete al proyecto actual.

## Aplicación en BAXY

Reutilizar la gestión COM generada y las leases de WindowsCoreAudioPlatform.
Leer el nombre del mismo IMMDevice que proporciona volumen y silencio, sólo en
GetStatusAsync; las mutaciones no añaden esta lectura. Abrir el property store
en modo0/STGM_READ, validar VT_LPWSTR, copiar la cadena y liberar PROPVARIANT y
la referencia COM también ante fallo. VT_EMPTY o etiqueta vacía no se sustituyen
por nombres inventados. El identificador físico sigue privado; el hash mantiene
la vinculación al endpoint. El alcance sigue siendo la salida predeterminada del
rol Multimedia, no todos los dispositivos con sesiones activas por aplicación.

EndpointName se añade como metadato nullable de audio.status, sin cambiar argumentos
ni añadir una operación. El catálogo describe el nombre y alcance disponibles.
El compositor existente recibe el campo por su proyección general de hechos.
La corrida astra-audio-endpoint-name3 demuestra que el compositor narra el nombre
verificado cuando se pregunta por el dispositivo.

## Validación realizada

138 pruebas de proveedor y 131 de integración pasan sin skips. Publicación del Core
NativeAOT terminada con código 0. La corrida física astra-audio-endpoint-name3 termina
con código 0: tres consultas conocidas, tres respuestas útiles. El hecho observado
es EndpointName = Altavoces (Realtek(R) Audio), nivel 100, muted=false. No se pidieron
mutaciones. Pico atribuido a BAXY: 3497,56 MiB de VRAM; RAM 4608,77 MiB; 58,06 s.
El registro del runtime no cambió. Fast verde, compilación sin errores ni avisos.
Literales y límites en PRUEBAS_IDENTIDAD_AUDIO_Y_CONOCIMIENTO_C03.md.
No es aceptación reservada, prueba de UI con voz ni Full final.
