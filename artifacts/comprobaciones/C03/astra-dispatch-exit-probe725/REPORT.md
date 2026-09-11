# Caída posterior al saludo: tres passes y un timeout

La sonda llama al test724 sin cambiar su cuerpo ni sus límites. Una subclase privada de Popen captura información únicamente después de TimeoutExpired. Se programaron hasta cinco intentos con parada en el primer fallo; pasó tres y falló el cuarto.

En el cuarto intento, el plazo vencido es3s. La enumeración inmediatamente posterior encontró únicamente el launcher del entorno virtual(PID25188,4.661.248 bytes RSS,1hilo), sin un intérprete descendiente visible. py-spy devolvió1 porque no encontró una versión de Python. El stderr privado sí conserva `RuntimeError: forced_dispatch_crash`, propagado desde el dispatcher por main.

No hay pila causal de un bloqueo Python. La observación tampoco demuestra que el intérprete hubiese terminado dentro de3s: la enumeración ocurrió después. El siguiente diagnóstico debe conservar su identidad antes del disparador para separar los tiempos de salida del intérprete y del launcher. El source hash del test sigue idéntico; no se ha cambiado producto ni adoptado724. Wrapper exit0, resultado semántico3 pass/1 fail, cero cobertura nueva.
