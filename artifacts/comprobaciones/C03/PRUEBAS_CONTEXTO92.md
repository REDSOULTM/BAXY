# C03 — recuperación de contexto92 — 4/4 útiles

La búsqueda vacía se explica y el porqué en inglés conserva la misma causa. Lectura real y reloj recuperan en el mismo proceso.94668exit0;64,08s; GPU3177,5625MiB;RAM5970,09765625MiB;registro intacto. 1152pytest pass/0skips/5,49s;182integración pass/0skips/15s; Fast16945exit0,Release15,01s,0 avisos/errores. ASTRA-TRAMO-92.md detalla herencia, cambios y fallos de implementación detectados/corregidos por pruebas.

Fuente86+92; Qwen3.5 override sin promoción. El primer chat aún añade una falsa limitación del catálogo; se rechaza correctamente. La recuperación ahora recibe previousResponse, produce causa fiel y no ejecuta una nueva lectura. No se añade exención para códigos extra: sólo vocabulario literal del usuario previo. No aceptación UI/voz/audio/reserva humana ni Full.

## t1 — útil

Entrada: Lee el archivo "c03-ausente.txt" del sandbox.

Final literal: No se encontró el archivo "c03-ausente.txt" en el sandbox.

Progreso publicado: []

Borrador (sin veto Python): No se encontró el archivo "c03-ausente.txt" en el sandbox.

```json
{
  "outcome": "failed",
  "completedStepsInOrder": [
    {
      "operation": "filesystem.search",
      "resultAtThisStep": {
        "readOnly": true,
        "seen": {
          "entries": [],
          "count": 0
        }
      }
    }
  ],
  "reason": {
    "outcome": "failed",
    "cause": "file search no matches"
  }
}
```

## t2 — útil

Entrada: Why couldn't you read that file?

Final literal: The file "c03-ausente.txt" wasn't found in the sandbox.

Progreso publicado: []

Borrador (sin veto Python): The file "c03-ausente.txt" wasn't found in the sandbox.

```json
{
  "kind": "conversation",
  "previousResponse": "No se encontró el archivo \"c03-ausente.txt\" en el sandbox."
}
```

## t3 — útil

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final literal: He leído el archivo "c03-lectura.txt" y su contenido es: "Lectura técnica C03: el color de control es turquesa."

Progreso publicado: []

Borrador (sin veto Python): He leído el archivo "c03-lectura.txt" y su contenido es: "Lectura técnica C03: el color de control es turquesa."

```json
{
  "kind": "status",
  "completedRequest": "Lee el contenido del archivo \"c03-lectura.txt\" del sandbox.",
  "outcome": "completed",
  "completedStepsInOrder": [
    {
      "operation": "filesystem.search",
      "resultAtThisStep": {
        "readOnly": true,
        "seen": {
          "entries": [
            {
              "resourceId": "fs_4b78d685afb043dc8c9d52622bd45348",
              "name": "c03-lectura.txt",
              "kind": "file",
              "size": 55,
              "lastWriteUtc": "2026-09-07T07:51:03.8957716+00:00"
            }
          ],
          "count": 1
        }
      }
    },
    {
      "operation": "filesystem.read.text",
      "resultAtThisStep": {
        "readOnly": true,
        "seen": {
          "resourceId": "fs_4b78d685afb043dc8c9d52622bd45348",
          "text": "Lectura técnica C03: el color de control es turquesa.\n",
          "utf8Bytes": 55
        }
      }
    }
  ]
}
```

## t4 — útil

Entrada: Dime la hora.

Final literal: Son las 04:52.

Progreso publicado: []

Borrador (sin veto Python): Son las 04:52.

```json
{
  "clock": "04:52"
}
```
