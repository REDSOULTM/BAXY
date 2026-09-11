# Identidad Shell no demuestra membresía completa de una aplicación

Consulta:2026-09-11. Hipótesis acotada de H0675, sin ejecución ni cambios de producto. **AppResolver no resuelve el fallo de atribuir un máximo de proceso a toda una aplicación.**

System Informer consulta un AppID por PID mediante IApplicationResolver2. Su llamada no devuelve miembros, memoria ni completitud y descarta los indicadores opcionales. La cadena de carga COM inspeccionada no solicita elevación; eso no verifica su acceso efectivo en usuario ordinario en esta máquina. Fuente primaria fijada: [appresolver.c](https://github.com/winsiderss/systeminformer/blob/6c4f0dec4fa0ec098eac03745c0d5a9ac7aff51d/phlib/appresolver.c#L125), [interfaz](https://github.com/winsiderss/systeminformer/blob/6c4f0dec4fa0ec098eac03745c0d5a9ac7aff51d/phlib/include/appresolverp.h#L581), [carga COM](https://github.com/winsiderss/systeminformer/blob/6c4f0dec4fa0ec098eac03745c0d5a9ac7aff51d/phlib/util.c#L9815).

La agrupación de procesos de ese proyecto usa ancestros, nombre/ruta, SID y ventanas; no usa AppResolver para enumerar miembros. Reproduce la heurística ya descartada y admite omisiones en su selección de grupos. [procgrp.c](https://github.com/winsiderss/systeminformer/blob/6c4f0dec4fa0ec098eac03745c0d5a9ac7aff51d/SystemInformer/procgrp.c#L248).

Microsoft documenta IDs explícitos opcionales, IDs internos heurísticos y ventanas de un mismo proceso con IDs distintos. Inferencia limitada: observar igualdad de AppID no prueba una partición completa de la memoria por aplicación. [Application User Model IDs](https://learn.microsoft.com/en-us/windows/win32/shell/appids).

No se incorpora interop privado ni una suma por PID al producto. H0675 sigue abierto bajo su criterio sellado: identificar la aplicación de mayor memoria exige hechos nuevos suficientes para membresía y agregado. No se rebaja a un grupo parcial ni se reabre TaskManager/elevación. Esta revisión no declara imposible cualquier otra solución. Informe detallado y búsqueda histórica acotada: C:/Users/usuario/AppData/Local/BAXY/C03-app-membership819-proposal/FINDING.md; huella en SOURCE.json. No hay petición nueva al dueño.
