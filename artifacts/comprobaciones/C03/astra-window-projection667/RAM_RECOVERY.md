# Memoria disponible recuperada — 2026-09-09

El dueño autorizó cerrar aplicaciones para liberar RAM. Se preservó VS Code: su ventana mostraba otra tarea del dueño ejecutándose. También se preservaron ChatGPT, Opera y Chrome. No se volvió a intentar la acción sobre Opera bloqueada por Computer Use.

Steam salió mediante su comando `steam.exe -shutdown`. Discord se terminó después de observarlo sin llamada activa. WhatsApp se cerró y se terminaron su proceso raíz y sus ocho descendientes WebView identificados por parentesco; todos terminaron. La comprobación posterior por psutil confirmó ausencia de steam.exe, steamwebhelper.exe, Discord.exe y WhatsApp.Root.exe. BAXY y llama-server también permanecen ausentes.

Muestras del sistema (GiB, no suma de RSS): antes de los cierres 14,237 usados / 1,167 disponibles; después 12,528 usados / 2,876 disponibles, de 15,404 totales. Diferencia observada: 1,709 GiB disponibles adicionales. Son muestras puntuales; no una medición del consumo propio de BAXY ni una garantía de memoria futura.

Candidata667 sigue sin adoptar y sin nueva inferencia. Conserva439 pruebas focales verdes; falta comprobar la proyección semántica precisa con el modelo y el producto antes de promoverla. Encuesta26 cubiertos/716 abiertos/0NA; C03 sigue activo.
