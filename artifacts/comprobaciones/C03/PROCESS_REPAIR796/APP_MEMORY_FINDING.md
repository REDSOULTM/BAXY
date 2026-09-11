# Pendiente H0675: memoria de una aplicación

La fuente796 repara procesos individuales. No acredita aún «qué app usa más memoria»: una app puede incluir varias instancias y auxiliares. El baseline795 careció de lectura nueva en ese turno y reutilizó el valor de un proceso.

Herencia inspeccionada: `ApplicationOpenContracts.cs:52` conserva un recibo con appId,PID,creación,exe y paquete; `WindowsInstalledApplicationOpenProvider.cs:1020` descubre identidades con ventana visible. Ese descubrimiento no enumera todos los auxiliares ni conserva un árbol de padres. La medición en `WindowsProcessStatusProvider.cs` sí tiene identidad estable y working set por proceso. No se encontró una implementación de agregación en Applications ni un título pertinente en el inventario histórico consultado.

Las páginas residentes incluyen memoria privada y compartida; sumar working sets puede contar páginas compartidas varias veces. Por tanto no se puede llamar a esa suma «RAM física total de la app» sin aclarar la métrica. [WorkingSet64, Microsoft](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.workingset64?view=netframework-4.8.1).

Windows ofrece memoria residente privada directamente con `PROCESS_MEMORY_COUNTERS_EX2.PrivateWorkingSetSize`. Su mínimo documentado es Windows10/11 22H2 con la actualización acumulativa de septiembre2023. La máquina actual reporta build26200. [Contrato de Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex2).

Prueba local2026-09-10, únicamente sobre un observador desechable: estructura96bytes, dos llamadas de0,0316y0,0192ms; tocar8MiB elevó la memoria residente privada8.392.704bytes y dejó inalterado sharedCommit. `PRIVATE_WORKING_SET_PROBE.json` conserva medidas; `scratchpad/c03-probe-private-working-set796.py` es el comando reproducible. No prueba permisos sobre todos los procesos ni membresía de apps, y no acredita producto o encuesta.

La alternativa `AppDiagnosticInfo` proporciona grupos de recursos, pero `RequestInfoAsync` sólo enumera apps con identidad de paquete y exige capacidad appDiagnostics. No cubre por sí sola las aplicacionesWin32 clásicas. [AppDiagnosticInfo](https://learn.microsoft.com/en-us/uwp/api/windows.system.appdiagnosticinfo?view=winrt-26100), [AppResourceGroupInfo](https://learn.microsoft.com/en-us/uwp/api/windows.system.appresourcegroupinfo?view=winrt-26100).

Siguiente implementación, después de recoger Full796 y797: aprovechar identidad ejecutable/paquete verificada y definir membresía contemporánea para auxiliares; medir y nombrar explícitamente memoria residente privada por grupo. No inferir membresía sólo por nombre o por una ventana, ni sumar una página top10 como inventario de app completo. Aún falta contrastar esa membresía con procesos reales de aplicaciones empaquetadas y clásicas. No se modifica la fuente sellada796 durante esta investigación.
