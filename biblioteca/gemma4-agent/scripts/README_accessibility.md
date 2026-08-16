# Accesibilidad de apps Chromium/Electron para Baxy

## Qué resuelve

Apps como **Discord, Spotify, Chrome, Edge, Brave, Slack** son Chromium por dentro.
Por defecto **no exponen su árbol de accesibilidad (UI Automation)**, así que el
agente (o un lector de pantalla) no "ve" sus botones por nombre — y tiene que
adivinar por OCR/visión, que es más lento e impreciso.

El flag oficial de Chromium **`--force-renderer-accessibility=complete`** activa ese
árbol. Con él, el agente controla esas apps con `click_button` por UIA (preciso,
rápido, sin OCR ni visión).

## Cómo se aplica (dos capas)

1. **Cuando el AGENTE abre la app** (vos decís "abrí Discord"): ya le pasa el flag
   automáticamente (`app_resolver._ax_launch_target`). No hay que hacer nada.

2. **Cuando la abrís VOS** (clic en el acceso directo): hay que adaptar los
   accesos directos una vez, con este script:

   ```powershell
   # Ver qué haría, sin tocar nada:
   powershell -ExecutionPolicy Bypass -File scripts\enable_app_accessibility.ps1 -WhatIf

   # Aplicar (crea backups *.lnk.gemma4bak de cada acceso directo):
   powershell -ExecutionPolicy Bypass -File scripts\enable_app_accessibility.ps1
   ```

   Después **cerrá y reabrí** las apps (son single-instance: el flag toma efecto en
   el próximo arranque).

## Cómo revertir (si NO lo querés)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\enable_app_accessibility.ps1 -Revert
```

Restaura los accesos directos originales desde los backups `*.lnk.gemma4bak` y los
borra. Volvés al estado previo. (El flag solo cuesta +5-15% de CPU sostenido en esas
apps; si tu máquina es justa o no usás el control por voz de esas apps, revertí.)

## Qué NO toca

- **VS Code**: es tu IDE, no se modifica.
- **WhatsApp y otras UWP**: ya exponen UIA nativo, no necesitan el flag.
- Los accesos directos **no se destruyen**: se guarda un backup de cada uno antes
  de modificarlo.

## Notas

- Discord usa Squirrel (`Update.exe --processStart Discord.exe`): el flag se agrega
  después y Squirrel lo propaga al Discord.exe real.
- Si una app se abre desde un ícono **anclado a la barra de tareas**, ese acceso a
  veces está aparte (`%APPDATA%\...\TaskBar`); re-anclarla desde el acceso directo
  ya adaptado hereda el flag.
- El instalador de la app puede recrear su acceso directo en una actualización; si
  notás que perdió accesibilidad, volvé a correr el script.
