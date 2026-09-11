# H0675 — lanzamiento ordinario de Task Manager

Fecha de consulta: 2026-09-11. Diagnóstico documental terminado en dos iteraciones; ninguna prueba ejecutada.

**Veredicto: mecanismo genérico documentado; aplicación efectiva a Task Manager, lectura UIA y cierre: UNKNOWN.** Hay fundamento primario para una prueba desechable posterior a GPU813. No hay fundamento para afirmar que resolverá el bloqueo ni para cerrar H0675.

## Antecedente heredado

La observación autorizada mostró una tabla agrupada y memoria en pantalla, pero accesibilidad sólo expuso la envoltura de ventana. La raíz comunicó denegación del cierre y posterior cierre manual por el dueño. No se copiaron nombres, cifras, identificadores ni rutas de aplicaciones observadas. Ninguno de esos hechos demuestra por sí solo integridad elevada o la causa del árbol incompleto.

## Hechos documentados

1. Microsoft describe `RunAsInvoker` y el ajuste temporal `__COMPAT_LAYER=RunAsInvoker`. Trata la solicitud del manifiesto como `asInvoker` con `uiAccess=false`; el hijo conserva los privilegios del lanzador. Desde un lanzador elevado sigue elevado; desde uno ordinario no solicita elevación. El ejemplo de Microsoft usa otra utilidad de Windows, no Task Manager. No es un mecanismo para rebajar un proceso ya vivo. [S1]
2. .NET permite preparar el entorno del nuevo proceso mediante `ProcessStartInfo.Environment`, con `UseShellExecute=false`. Ese entorno alcanza al proceso y a sus hijos; no requiere modificar variables globales. La combinación con RunAsInvoker es una propuesta derivada de dos contratos, no un ejemplo de Task Manager publicado por Microsoft. [S2, S1]
3. Windows protege interfaces de mayor integridad frente a clientes ordinarios. Por tanto la diferencia de integridad es una explicación posible del bloqueo, todavía sin medir. Esta propuesta no habilita UIAccess en el cliente ni modifica protecciones. [S3]
4. UIA depende de proveedores que expongan controles y navegación. Sin proveedor apropiado pueden quedar sólo datos básicos del HWND. Igualar integridad no crea proveedores ni garantiza filas, celdas, jerarquía, patrones o exhaustividad de una tabla. [S4]
5. `IUIAutomationWindowPattern::Close` documenta cierre de ventana y resultado HRESULT. La página no garantiza que Task Manager ofrezca ese patrón ni que acepte la solicitud. Cerrar esa ventana no es finalizar una aplicación listada en ella. [S5]

## Inferencias delimitadas

Si el lanzador y el cliente UIA tienen integridad ordinaria, y la nueva instancia de Task Manager respeta RunAsInvoker, desaparece esa diferencia concreta de privilegios. Entonces es razonable volver a comprobar UIA y cierre ordinario. Es una hipótesis comprobable; el documento de Microsoft no promete el resultado en la versión instalada.

El árbol reducido también puede deberse al proveedor, a la vista solicitada, a inicialización o a otra limitación del cliente. La denegación de una operación de cierre no identifica automáticamente UIPI ni demuestra que WindowPattern.Close fuese la operación usada. No convertir ambas observaciones en un diagnóstico causal único.

No se encontró en estas dos iteraciones un contrato primario específico que garantice que Task Manager acepte el lanzamiento, no reutilice otra instancia, mantenga la misma tabla a menor privilegio o exponga UIA completa. Esas propiedades quedan UNKNOWN. Se rechaza afirmar viabilidad demostrada o recomendar elevación como siguiente paso.

## Única prueba propuesta para la raíz después de GPU813

1. Confirmar fin de la exclusión GPU y autorización vigente para el diagnóstico de esta ventana propia. Verificar que no se reutilizará una instancia ajena. Si no puede garantizarse el destino, detener la prueba.
2. Usar un lanzador ya ordinario del usuario, en la misma sesión y escritorio que el cliente UIA. Verificar sus niveles efectivos antes de lanzar; si están elevados o no son verificables, no iniciar. RunAsInvoker no los reduce.
3. Preparar una sola creación desechable del ejecutable de sistema verificado. En su entorno de creación exclusivamente, fijar `__COMPAT_LAYER=RunAsInvoker`; usar `UseShellExecute=false`. No cambiar el entorno global, registro, manifiestos, binarios ni bases de compatibilidad. No lanzar otras apps desde esa instancia, pues sus hijos heredarían el entorno.
4. Registrar recibo de creación e identidad real de la ventana resultante, más integridad/elevación efectivas del destino y cliente mediante lecturas ordinarias autorizadas. No inferirlas de la ausencia de aviso UAC. Si hay rechazo, aviso de elevación, instancia reutilizada, integridad superior o identidad incierta, detener sin aumentar permisos.
5. Hacer una lectura UIA acotada a esa ventana: primero estructura y patrones, incluyendo vista Raw cuando la vista ordinaria sólo muestre la envoltura. Comprobar si existen encabezados, grupos y celdas asociadas; comparar con captura autorizada de esa misma ventana. No activar controles de procesos ni finalizar ninguna aplicación listada. Si sigue opaca, registrar fallo de esta hipótesis, sin inventar filas.
6. Solicitar una vez el cierre ordinario de la propia ventana mediante WindowPattern.Close sólo si está disponible y la identidad sigue vigente; conservar HRESULT y verificar desaparición de esa ventana y salida de la instancia creada. No usar terminación forzada. Si no ofrece cierre o lo deniega, registrar el límite y dejar el cierre manual al dueño.
7. Considerar resultados independientes: lanzamiento ordinario verificado, tabla legible y cierre verificado. Sólo tres resultados positivos admiten continuar con esta vía. Ni siquiera eso prueba el superlativo H0675: siguen pendientes filtros, cobertura, orden, unidades, actualidad y asociación correcta de la tabla según el diseño heredado.

## Referencias primarias

Todas consultadas el 2026-09-11. Citas literales inferiores a 25 palabras por fuente; no se usan respuestas comunitarias.

- S1. Raymond Chen / Microsoft, 2016-11-17. [Is RunAsInvoker a secret, even higher UAC setting?](https://devblogs.microsoft.com/oldnewthing/20161117-00/?p=94735). Cita: “The program simply runs with the same privileges as the code that launched it.”
- S2. Microsoft Learn, .NET 10; fecha de actualización no visible. [ProcessStartInfo.Environment](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.processstartinfo.environment?view=net-10.0). Cita: “Gets the environment variables that apply to this process and its child processes.”
- S3. Microsoft Learn, actualizado 2026-02-19. [Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview). Cita: “UIAccess is not enough for a process to move up through the IL boundary.”
- S4. Microsoft Learn, actualizado 2025-07-14. [UI Automation Providers Overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-providersoverview). Cita: “Without a proxy, such a control is largely opaque to UI Automation”.
- S5. Microsoft Learn, actualizado 2024-02-22. [IUIAutomationWindowPattern::Close](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationwindowpattern-close). Cita: “If this method succeeds, it returns S_OK. Otherwise, it returns an HRESULT error code.”

No se ejecutaron Task Manager, BAXY, inferencia, consultas de procesos, pruebas, builds ni Full. No se modificó el repositorio. Únicos entregables: este diagnóstico y SUMMARY.json. H0675 continúa abierto, sin crédito de producto.
