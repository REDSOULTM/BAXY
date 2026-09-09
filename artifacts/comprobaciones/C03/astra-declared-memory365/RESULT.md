# 365 — nombre declarado y guardado explícito unidos en la ruta privada

NaturalMemoryRequestParser une las dos cláusulas que ya reconoce: declaración
del nombre y solicitud explícita de guardarlo. Acepta ambos órdenes y nombres
compuestos. Extrae el valor literal, selectorname, sensitivitypersonal y
retentionpersistent. Un nombre solo, hipótesis, tercero o cláusula ajena no
aporta autoridad. Negación, datos sensibles y permisos generales se filtran antes.
No otra herramienta, respuesta fija, nombre particular ni cambio de modelo.

Los separadores estructurales permiten encontrar ambas cláusulas, sin absorber
una segunda petición en el valor del nombre. La primera edición falló justo ese
control (Lina y abre Steam) y se corrigió antes de validar; focal.log conserva el
rojo1fail28pass. No ocultarlo ni contarlo como baseline limpio.

- Baseline:5fail6pass0skip582ms.
- Focal corregido:29pass0fail0skip666ms.
- Dueñas:1926pass0fail0skip4m33s.
- Fast:verde, build18,06s0warnings/errors.
- git diff --check de las tres fuentes modificadas:correcto.

Comando dueñas: `dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter 'FullyQualifiedName~MemoryAppFlowTests|FullyQualifiedName~MemoryTurnSessionTests|FullyQualifiedName~NaturalMemoryRequestParserTests|FullyQualifiedName~MemoryOperationProtectionTests|FullyQualifiedName~MissionInputPipelineTests|FullyQualifiedName~MindShellEndToEndTests'`.
Fast: `.\scripts\test_source_quality.ps1`. No Full durante reparación.

Producto366 preparado: mismos10controles364/modelo/perfil nuevo, sólo365 diferente.
La mejora integrada aún requiere esa prueba. El problema de recall con memoria
desactivada pero nombre en contexto, y las preguntas durante confirmación, siguen
pendientes. No promover Qwen3.5 ni cerrar C03 por este cambio.
