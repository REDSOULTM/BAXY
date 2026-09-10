# Presupuesto de composición para inventarios verificados

La frontera compartida de composición reconoce ahora los inventarios de window.resolve que llegan dentro del JSON de situation. Cuando están verificados y han tenido éxito, usa los umbrales densos existentes: ocho entradas o512caracteres de inventario. Los datos y el contrato factual no se modifican. No depende del nombre del modelo ni de una forma de respuesta.

Esto reutiliza el límite existente de10s en la App, nueve para el modelo en GPU. Las respuestas ordinarias conservan5s/4s; CPU mantiene sus dos presupuestos60/130s. La selección no concede éxito a datos no verificados ni garantiza que cualquier lista termine dentro del plazo. El problema medido está en762–763: una lista completa20/24 tardaba4,141s y recibía cuatro, seguida de reintentos.

Validación:136 pruebas dueñas,0 fallos,0 skips;22 controles nuevos, incluidos los límites7/8, tamaños0/1/20/50, identidad larga, verificación fallida o mal tipada, JSON inválido y paso por ModelMessageComposer.CreateFacts. Fast pasó y los pins de fuente permanecieron intactos. Comandos y logs en VALIDATION.json. No Full nuevo en esta adopción sólo C#; el Full final sigue pendiente.

Siguiente: regresión registrada765 de los mismos73 casos completos, con hechos frescos, para comprobar entrega y regresiones. No es una comparación nativa de modelos ni acredita UI/voz o consumo conjunto. Fuente Python760, modelo, sampler y prompt permanecen intactos. Encuesta26cubiertos/716abiertos/0NA; C03 activo.
