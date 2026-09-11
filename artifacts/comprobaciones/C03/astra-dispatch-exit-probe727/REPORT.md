# Medición separada de intérprete y launcher

Esta es una sonda con el prototipo724 retirado, no una ejecución de la aceptación original. Antes del disparador conserva handles de ambos procesos. Marca la escritura con GetSystemTimePreciseAsFileTime y consulta GetProcessTimes/exit code después de esperar. Sólo utiliza ExitTime cuando el handle está señalado: Microsoft documenta que es indefinido para un proceso vivo.

Los cinco intentos terminaron dentro del plazo de la sonda. Los JSON por intento conservan timestamps nativos, códigos y CPU. En el primero, intérprete0,491s y launcher0,532s después del disparador; ambos exit1, prioridad normal32. No se reprodujo el fallo intermitente de725 ni se ha demostrado su causa. La medición no convierte en verde el plazo original de3s desde el lanzamiento, que incluye la precarga.

La fuente exacta de CPython3.12.10 muestra que el launcher configura el venv, duplica std handles, crea el hijo y espera para propagar su código. Por eso la salida de texto heredada no fecha por separado ambos procesos. La receta interna __PYVENV_LAUNCHER__ no se ha aplicado al producto ni se ha declarado equivalente sin medir prefijos/dependencias.

Fuentes: [CPython3.12.10 launcher](https://github.com/python/cpython/blob/v3.12.10/PC/launcher.c), [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes), [reloj UTC preciso](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimepreciseasfiletime). Sin adopción ni cobertura.
