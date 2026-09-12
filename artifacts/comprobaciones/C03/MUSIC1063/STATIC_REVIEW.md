# Revisión estática, iteración final 2

Dos owners: src/baxy_mind/effect_intent.py y src/Baxy.Providers.Windows/External/WindowsMediaSessionAdapter.cs. La primera propuesta sólo de intención queda en superseded-intent-only; el DIFF raíz actual contiene ambos cambios.

Intención: se conserva la selección de verbos y el dominio existentes. Sólo reanuda/reanudar/resume deja de depender del adjetivo pausado. No se añade un corpus, alias de aplicación, plantilla por literal ni respuesta visible fija. Las negaciones/citas/condicionales siguen atravesando las guardas de autoridad originales; este diagnóstico no las ejecutó y no afirma nuevos pases. Play/reproduce sin calificador continúa por sus rutas previas de consulta/elección. La materialización de media.control sigue por el extractor action enum existente.

Recibo: se revisaron los dos callers privados de MediaResult. El helper exige sourceAppUserModelId y sólo añade provider si el caller aporta uno. Generic ControlAsync pasa la propiedad del mismo objeto session que recibe el efecto y aporta el postread, sin provider opcional. PlayExactCurrentAsync aporta esa propiedad más provider:"spotify". StatusAsync conserva su resultado actual con sourceAppUserModelId y authority windows_smtc_current_session_read; SeekRelative conserva windows_smtc_timeline_postread. No hay cambio en selección SMTC, acción, permisos, polling, timeout, dispatch, verified o effectObserved. La vía Spotify Web API conserva su propio recibo y su autoridad.

La nueva fuente también se incluirá en generic media.control cuando la sesión sea Spotify: se observa su AUMID en lugar de adjudicar un proveedor fijo a todas las sesiones. No se inventa provider=Microsoft ni provider=Windows; Windows SMTC es autoridad de observación, no marca de la aplicación reproductora. Title/artist y estado son los observados por el postread, no los títulos del fixture escritos en código.

Se compararon fuentes base con el canónico al generar IDENTITY: sin cambios externos en esos owners. No se ejecutaron pruebas, imports, build, Core ni GPU. Esto acredita únicamente preparación y revisión textual del parche; la corrección del producto sigue pendiente de adopción y medición real por raíz.

Integración conjunta con CLOSE1060: sus hunks effect_intent están en el helper de cierre, mientras MUSIC1063 cambia la condición multimedia. Aplicar los DIFF completos por hunks; no copiar una propuesta effect_intent completa encima de la otra, pues ambas parten de cd1b08ab. El compositor de raíz es una tercera costura independiente y no está incluido aquí.
