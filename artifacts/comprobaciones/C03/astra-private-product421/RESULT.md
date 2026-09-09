# 421 — --no-mmap no resuelve el corte de RAM

Mismo4B/casos/controles/fuente418 que420, con --no-mmap en comando efectivo.
GPU3177,5625MiB; RAMárbol4629,90234375MiB;36,172s; corteRAMlibre<768MiB.
Frente4204730,117MiB, sólo100,215MiB menos; no basta ni demuestra un mínimo.
Cuatro finales antes del corte. No adopción de fuente/configuración ni promoción.
T5 alcanzó la mente y una lectura system.identity incorrecta, sin final;T6–T8 no llegaron. Exit1/manifiesto intacto. Árbol diagnóstico cerrado.

## Respuestas realmente emitidas

1. Entrada: My name is Jordan. Remember my name.
   Respuesta: Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?
2. Entrada: confirm
   Respuesta: The memory has been saved successfully.
3. Entrada: Abre una aplicación.
   Respuesta: ¿Quieres que abra una aplicación?
4. Entrada: What name have you saved in private memory?
   Respuesta: I saved the name Jordan in private memory.

T1 pide confirmar activación privada;T2 tiene memory.enable y memory.save verificados.
T3 pregunta permiso otra vez sin pedir qué aplicación: no útil. T4 recupera Jordan
con sujeto correcto y memory.recall verificado, tras aquella aclaración.3/4 útiles
emitidos;3/8 de los preregistrados,T5 sin final yT6–T8sin ejecutar.418 ejercitado sólo en EN.

Operaciones (sin descifrar ni publicar registros privados):
```json
[
  {
    "operation": "memory.status",
    "verified": true,
    "status": "completed"
  },
  {
    "operation": "memory.save",
    "verified": false,
    "status": "failed"
  },
  {
    "operation": "memory.enable",
    "verified": true,
    "status": "completed"
  },
  {
    "operation": "memory.save",
    "verified": true,
    "status": "completed"
  },
  {
    "operation": "memory.recall",
    "verified": true,
    "status": "completed"
  },
  {
    "operation": "system.identity",
    "verified": true,
    "status": "completed"
  }
]
```

Corrección: HTTP nativo421 incluye «Me llamo Álvaro.» y su composición con
cuenta Windows, aunque capture terminó en T4. No equiparar finales a ejecución.
