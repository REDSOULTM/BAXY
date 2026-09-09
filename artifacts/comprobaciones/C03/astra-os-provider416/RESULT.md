# 416 — nombre de Windows observado y transportado; pruebas dueñas y Fast verdes

Sustituida la lectura OS RtlGetVersion por Win32_OperatingSystem local mediante
ExternalProcessRunner existente. Lee Caption, Version y ProductType, mantiene
arquitectura nativa. Cinco segundos máximos, cancelación propagada; el runner
oculta y termina el proceso en fallo. JSON inválido, error y timeout producen
fallo sanitizado del scope OS; otros scopes conservan sus mediciones. No caché,
tabla de versiones, respuesta fija, nueva operación ni dependencia añadida.
Se retiraron los constantes y el import nativo que quedaron sin consumidor.

Caption obligatorio viaja por OperatingSystemReading, OperatingSystemStatus y
SystemStatusOperatingSystemResult hasta el JSON verificado. Proveedor valida
longitud/control; Core exige texto normalizado y no vacío. Observación CIM local
en tres procesos: 0,415 / 0,354 / 0,355 segundos, siempre Windows 11 Home Single
Language / 10.0.26200 / workstation. Ver CIM_OBSERVATION.json.

`dotnet test tests/Baxy.Providers.Windows.Tests -c Release --nologo -v:minimal
--filter 'FullyQualifiedName~WindowsOperatingSystemProbeTests|FullyQualifiedName~WindowsSystemStatusProviderTests'`
→ 36 pass / 0 skips, 74 ms. Incluye captions Windows 10/11/Server/localizado,
NT 10.0 compartido, dato inválido, fallo/timeout parcial y cancelación en vuelo.

`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
--filter 'FullyQualifiedName~SystemStatus'` → 193 pass / 0 skips, 6 s.
Incluye contrato, handler, handshake y consumidores de recursos; captions
inválidos no pasan verificación y el resultado conserva el caption del servidor.

`.\scripts\test_source_quality.ps1` → Fast verde completo, build Release 18,76 s,
0 warnings / 0 errors. Fallos previos conservados: CA1826 en un test (corregido
acceso indexado) y saltos CRLF introducidos al editar tres tests (restaurados LF).
La corrección LF no altera su comportamiento; no se repitieron suites por ella.
No Full durante reparación. Fuente previa de audio EndpointName y todo WIP ajeno
se preservan. No modelo promovido ni voz/UI/aceptación certificadas.

Herencia, mecanismo Microsoft y comparación 1/4→4/4 están en
astra-os-caption415/RESULT.md. Siguiente: producto417 conserva los seis turnos411
y añade OS ES, RAM EN y CPU ES. No se da por resuelto antes de leer los finales.
