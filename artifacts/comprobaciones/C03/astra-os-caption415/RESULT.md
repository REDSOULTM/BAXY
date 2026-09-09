# 415 — transportar el nombre observado de Windows: 1/4 → 4/4 útiles

La primera petición y su payload nativo igualan el T5 de producto411, comprobados
offline y durante la ejecución. La única diferencia es observed.os.caption.
El baseline repite Windows 10 para Windows 11 y Server 2022; con Caption distingue
los cuatro sistemas y conserva sus ediciones. Las respuestas ES llaman «versión»
al número de compilación, una imprecisión terminológica; no cambian el número
observado. Ningún silencio, error o violación de recursos. Los controles de
Windows 10 y Server son sintéticos, no observaciones de este PC ni aceptación.

GPU propia máxima: 3171,5625 MiB. RAM del árbol: 3623,171875 MiB. Duración 8,641 s.
Esto mide composición aislada con sus guardas, no voz física ni VRAM conjunta.
Modelo diagnóstico Qwen3.5-4B Q4_K_M; no se promovió el runtime. Modelos cerrados.

Se implementará una lectura CIM local, acotada y cancelable mediante el runner
ya existente. Sustituye la lectura numérica RtlGetVersion por los datos de
Win32_OperatingSystem (Caption, Version, ProductType), con arquitectura del runtime.
No se deduce el nombre comercial desde umbrales de build; no se añade una respuesta
fija ni una nueva operación. Caption forma parte del contrato y del resultado
verificado. Si falla la observación, queda un fallo explícito del scope OS.

Herencia: biblioteca/carter/carter_v5/microagents/windows_commands.md:23–32 no
resuelve este nombre; el runner y CIM ya existen en Providers.Windows/External.
Microsoft documenta Windows 10 y 11 con NT 10.0 y Caption como descripción local:
[OSVERSIONINFOEXW](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/ns-wdm-_osversioninfoexw),
[Win32_OperatingSystem](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem).
Fuentes comprobadas el 2026-09-08; prueba y respuestas completas en replies.jsonl.
