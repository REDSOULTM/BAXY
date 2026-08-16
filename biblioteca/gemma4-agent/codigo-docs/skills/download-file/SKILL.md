---
name: download-file
description: Download a file, installer, video, song, or document from the internet to a folder. Confirm the source URL before downloading executables; verify the file actually downloaded (do not assume).
priority: medium
metadata:
  examples:
    - "descargá el instalador de python a una carpeta"
    - "bajá y guardá este archivo de este link"
    - "descargame el pdf de esta página a disco"
    - "descargá la última versión de nodejs"
    - "descargá y guardá este video en mi disco para verlo offline"
    - "download and save the installer file from this page"
    - "baixe e salve este arquivo da internet"
  when_to_use:
    - "el usuario quiere traer un archivo de internet y guardarlo en el disco"
    - "bajar un instalador o documento desde una URL a una carpeta"
  limitations:
    - "no es para buscar un archivo que ya está en el disco de la PC"
    - "no es para encontrar un pdf en el escritorio o en una carpeta local"
    - "no es para extraer o leer el texto de un pdf ya existente"
    - "poner un video en pantalla completa o reproducirlo"
    - "not for searching local files or extracting text from an existing pdf"
requires:
  os: [windows]
---

# Download a file from the internet

Tools: `download` (fetch/hash/signature), `web`/`browser` (resolver URL si solo hay nombre), `filesystem` (confirmar que quedó). Honesty-critical: SÍ — nunca afirmar que algo se descargó sin verificarlo; nunca descargar un ejecutable de fuente no confirmada sin avisar.

Usar cuando: "descargá el instalador de X", "bajá este video/canción/pdf", "descargame el archivo de <link>", "bajá la última versión de <programa>". NO usar para: abrir una página (`browser.open`), buscar info (`web`), instalar juego Steam (skill `install-steam-game`).

## Steps

1. **Resolver URL.** Si hay link directo, usalo. Si solo hay nombre: `web(action="search", query="<programa> official download")`; tomar la URL del sitio **oficial** (python.org, nodejs.org, github releases…). Si no estás seguro de cuál es la oficial, PREGUNTÁ antes de bajar — no adivines dominio.
2. **Confirmar antes de un EJECUTABLE.** Regla dura: si es instalador/ejecutable (.exe/.msi/.bat/.ps1) y la fuente NO es claramente oficial/confiable, confirmar: "Voy a descargar `<nombre>` desde `<url>`. ¿Confirmás la fuente?" Para no-ejecutables (pdf/imagen/video/zip de datos) de un link que el usuario dio explícitamente, podés proceder.
3. **Descargar.** `download(action="fetch", url="<url>", dest="<carpeta destino o Downloads>")`. Default: carpeta Descargas salvo que pida otra.
4. **(Opcional) Verificar integridad.** Si el sitio publica hash/firma y es ejecutable: `download(action="hash", path="<archivo>")` (comparar con hash oficial); `download(action="signature", path="<archivo>")` (si hay firma).
5. **VERIFICAR que quedó (no asumir).** `filesystem(action="list", path="<carpeta destino>")`. Confirmar que existe y size>0. Si no está, NO digas que se descargó — reportá el error real.

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Descargado OK | "Listo, descargué `<nombre>` (`<tamaño>`) en `<carpeta>`." |
| Hash verificado | "Descargado y verificado (hash coincide con el oficial)." |
| Fuente dudosa | "No pude confirmar que `<url>` sea la fuente oficial. ¿Confirmás o preferís otra?" |
| Falló la descarga | "La descarga falló: `<error>`. El archivo no quedó en `<carpeta>`." |
| Solo nombre, sin URL clara | "¿De qué sitio querés bajar `<X>`? No quiero adivinar una fuente." |

## Anti-patterns

- ❌ Adivinar el dominio de descarga de un nombre (puede ser malware).
- ❌ Descargar un .exe de fuente no confirmada sin avisar.
- ❌ Decir "lo descargué" sin verificar con `filesystem.list`.
- ❌ Usar este skill para abrir una página (eso es `browser.open`).
