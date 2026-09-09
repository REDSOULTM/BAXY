# 420 — vuelve el corte por RAM sin compilación

Mismos ocho casos y fuente418 que419. El arranque no compiló ni publicó AOT,
pero el margen de RAM libre de768 MiB volvió a disparar el cierre del árbol
diagnóstico. Eliminar trabajadores de build no resolvió la presión de RAM.
Eventos conservados: `{"meta": 1, "runtime": 1, "admission": 2, "event:admission": 2, "event:activity": 6, "event:agent": 4, "event:state": 11, "event:boot_stage": 10, "terminal": 2, "posterior": 2}`. No se interpreta una admisión
como una respuesta útil ni como validación de418. Exit1, manifiesto intacto.
GPU propia máxima3177,5625 MiB; RAM del árbol4730,1171875 MiB;29,297s.
No acredita voz conjunta. Los registros privados y el intento fallido se conservan.

Siguiente experimento421: sólo cambiar la carga del mismo modelo a --no-mmap.
Herencia local:390 midió este mecanismo con9B; su mala calidad no lo promovió
y no se traslada ese modelo. La ayuda del binario exacto b9980 admite --no-mmap.
El reporte upstream https://github.com/ggml-org/llama.cpp/issues/14187 es de
b5662, cerrado sin confirmar: apoya una hipótesis, no demuestra un bug actual.
Mismos límites, casos, perfil aislado nuevo, parámetros y fuente. Si pasa,
comparar RAM y evaluar cada respuesta; no declarar optimización por arrancar.

## Respuestas realmente emitidas

1. Entrada: My name is Jordan. Remember my name.
   Respuesta: Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?
2. Entrada: confirm
   Respuesta: The memory has been saved successfully.

T1 pide confirmar activación privada;T2 tiene memory.enable y memory.save verificados.
Dos respuestas útiles emitidas de los8casos preregistrados; seis no ejecutados.
Corrección del resumen inicial:420 sí alcanzó dos terminales, no cero.

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
  }
]
```
