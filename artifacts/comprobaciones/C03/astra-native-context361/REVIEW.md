# 361 — los roles nativos reparan la primera divergencia

Oncepayloads con el mismo contenido, modeloQwen3.5, instrucciones, funciones y
sampling. Sólo cambia la representación: JSON con diálogo citado frente a los
roles user/assistant propios del template. No fuente ni efectos ejecutados.

| Control | JSON | Roles nativos |
|---|---|---|
| quien soy con nombre declarado | Sin lectura | Sin lectura |
| cuentaWindows explícita | identity | identity |
| quien soy fresco, criterio heredado | identity | identity |
| identidad del asistente | Sin lectura | Sin lectura |
| ambas identidades, variante sintética | Sin lectura | Sin lectura |
| Jordan en inglés | Sin lectura | Sin lectura |
| hermana Olivia | Sin lectura | Sin lectura |
| ventana activa | window.active | window.active |
|36013 Yo soy el | filesystem.write.text, incorrecto | Sin lectura |
|36029 ambas identidades, primario | Sin lectura | Sin lectura |
|36031 ambas identidades, sondeo secundario | identity, incorrecto | Sin lectura |

Selección9/11→11/11. El control sintético de ambas identidades que falló358 ahora
pasa también en referencia, pese a payload/sampling iguales: existe variabilidad
entre corridas; no presentar el seed como garantía de salida idéntica. Las dos
divergencias reales36013/31 sí se reproducen y desaparecen en la alternativa.
Texto literal por respuesta en replies.jsonl, objetos completos en archivo privado.

GPU3175,56MiB, RAM4599,84MiB,18,34s; aislado sin voz/UI, no mínimo. Manifest intacto.
La mejora justifica probar el adaptador nativo en fuente y productoQwen3.5, no
promover automáticamente el modelo.316 con2507 y otro contexto había rechazado
roles nativos: no se afirma retrocompatibilidad ni mejora de ese candidato.
No añadir una rama por nombre de modelo para sostener formatos rivales sin una
necesidad de producto; el candidato final debe demostrar sus rutas y recursos.

La fuente359 sola queda descartada como solución integrada por360.362 debe
conservar roles y límites del mismo contexto y reemplazar el envoltorioJSON,
sin una nueva instrucción, descriptor, cuota de historial ni respuesta fija.
