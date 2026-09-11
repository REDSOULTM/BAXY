# El Core conserva un catálogo útil

Una ejecución directa del Core, sin peticiones ni LLM, emitió su saludo en6,796s con PID correcto. Publicó293nombres de aplicaciones, con catálogo verified=true y complete=true. Terminó con exit0 al cerrar stdin. Es la lista filtrada de nombres utilizables; no se confunde con las322entradas crudas comparadas en711.

Este control descarta que el arranque medido aquí se agilice publicando un catálogo vacío/no verificado. No demuestra que las50ejecuciones anteriores tuvieran una lista idéntica, pues aquella sonda no capturaba ese campo.

El primer intento714 tenía mal preparado el directorio privado: usaba una subcarpeta, cuando WindowsPrivateStorage exige un hijo directo de LOCALAPPDATA/BAXY. El Core lo rechazó antes de descubrir aplicaciones. Se conserva el error del ejecutor714 y se corrigió sólo la ruta del conductor715; no se alteró la validación de seguridad del producto.

Datos completos privados y huellas en RESULT.json. Sin cobertura nueva ni aceptación de UI, voz o modelo.
