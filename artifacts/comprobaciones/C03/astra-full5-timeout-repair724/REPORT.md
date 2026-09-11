# Dos pruebas que mezclaban semántica y carga accidental

**RETIRADO en726.** Este candidato no puede sustituir la aceptación original: cambió el repositorio ejercitado y el origen del plazo. Ambos archivos de tests fueron restaurados exactamente desde HEAD; los prototipos y resultados se conservan en astra-test-fidelity726. Las conclusiones de pruebas aisladas que siguen son históricas, no acreditan reparación o cierre.

Full5 conserva su resultado rojo: .NET4532 pass/0 fail/1 skip agregado; Python11135 pass/2 fail/3 skip. Este tramo no lo cambia retroactivamente ni acredita ninguna conducta nueva de la encuesta (26 cubiertos,716 abiertos,0NA).

## Copia de empaquetado

718 attempt2 conservó el comando y fixture anteriores, añadiendo sólo relojes privados:53,281s en total,38,776s creando el worktree y6,882s retirándolo. Recorrer el árbol buscando reparse points tardó0,605s. El repositorio tenía19.727 archivos. Finalizó correctamente después del plazo45s: sigue siendo un fallo temporal. El primer intento718 falló antes de la medición porque la copia del helper cambió PSScriptRoot; quedó registrado y su fixture se limpió con el helper fail-closed.

720 comparó dos pares alternados del mismo HEAD completo con el ajuste por invocación `checkout.workers=2`. Los cuatro vencieron45s; un par mejoró y otro empeoró. No se adoptó el ajuste ni se cambió Git globalmente. La [documentación de Git](https://git-scm.com/docs/git-checkout#Documentation/git-checkout.txt-checkoutworkers) describe posibles mejoras en SSD, no una garantía. RESULT.json conserva tiempos y RSS observado de cada ejecución.

El candidato de prueba crea un repositorio controlado y copia **todo su HEAD** con los helpers originales. Conserva el plazo PowerShell45s y agrega comprobaciones de inventario y bytes (texto LF, binario y ruta con espacios), exclusión de archivos sin guardar o staged, conservación de estado de origen y eliminación del registro de worktree. El empaquetador del producto continúa copiando el HEAD completo de BAXY. Esto elimina del fixture la dependencia del volumen de informes históricos; no se presenta como una mejora del rendimiento del empaquetador real.

Primer owner:0 pass/1 fail en41,70s, porque Get-FileHash no estaba disponible. Se sustituyó esa aserción por el helper SHA256 existente, con digest esperado calculado independientemente en Python. Segundo:1 pass/0 fail en38,67s. Se retiró el reformateo ajeno al método modificado; ruff check pasó.

## Caída del sidecar

717 capturó la carga previa al saludo dentro de SciPy.719 comprobó que retirar la precarga podía permitir el saludo, pero la primera carga de BLAS desde el dispatcher se atascó con stdin abierto. El conductor719 terminó1 durante la espera de disposición de un hijo; el cuarto resultado no llegó a guardarse en su JSON. Su pila y log conservan el vencimiento10s; una búsqueda posterior por hash de los cuatro scripts no encontró procesos restantes.

721 aisló otra hipótesis: ambos perfiles aplazan la precarga y sólo el segundo cambia la lectura privada a ReadFile. Los dos casos de caída pasan(2,328/2,578s), pero ambos DSP vencen10s. Se descarta cambiar el lector a partir de esa hipótesis.723 probó después el límite documentado `OPENBLAS_NUM_THREADS=1`: tampoco resuelve los plazos ni el bloqueo con carga aplazada. No se verificó el backend/hilado efectivo de la DLL; no se deduce de ahí una causa interna de BLAS. No se cambian DSP, protocolo ni variables productivas. [OpenBLAS documenta el control y sus límites](https://github.com/OpenMathLib/OpenBLAS#setting-the-number-of-threads-using-environment-variables).

El antecedente del Registro de Mantenibilidad9601–9619 ya identificaba que el test de caída incluía la carga fría en sus3s. El candidato separa la precondición del comportamiento que prueba: espera hello con límite10s, envía una petición explícita de caída y exige salida en los mismos3s, con stderr del fallo forzado y sin BufferedReader fatal. El receptor tiene que haber entrado en una segunda lectura, que permanece abierta. La prueba vecina de DSP nativo conserva sus10s. **Se deja de exigir3s para intérprete+carga DSP+caída juntos**; no se afirma que la aplicación arranque ahora más deprisa.

Las dos pruebas concretas pasan(2 pass/0 fail,10,34s). Faltan las tres suites dueñas en62763 y una compuerta Full nueva antes de adoptar el conjunto705+712+724. No se omiten casos ni se modifica el algoritmo de audio. La selección del LLM, sus parámetros y las mediciones699/700 permanecen intactas.

## Resultado ampliado: candidato aún no validado

62763 terminó con66 pass/1 fail/0 skips y5 subtests en322,55s. El crash supera de nuevo3s **después** de recibir el saludo y enviar el disparador; no es el timeout de carga anterior. Los logs completos y exit1 están archivados. No se ha iniciado Full6 ni adoptado el candidato.

725 conservó el test y los plazos y añadió observación sólo al vencer un wait: tres passes y un fallo en el cuarto intento. En la enumeración posterior al timeout sólo aparecía el launcher(4,45MiB,1hilo), sin intérprete descendiente visible; por ello py-spy no pudo obtener una pila Python. El stderr contiene el error forzado exacto. Esto acota la fase pero no demuestra cuándo terminó el intérprete respecto al límite ni qué retuvo al launcher. Se requiere observar ambas identidades antes del próximo disparador, no ampliar el reloj ni volver a atribuir el fallo a SciPy sin evidencia. El código0 de725 sólo acredita que el conductor guardó el fallo.
