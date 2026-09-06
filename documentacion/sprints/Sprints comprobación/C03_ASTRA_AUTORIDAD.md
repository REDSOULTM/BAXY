# C03 — encargo para GPT-6 Astra con autoridad plena

Escrito el 2026-09-06 para el traspaso a otro PC. Sustituye a los encargos de
relevo anteriores de C03 en lo que respecta al agente entrante. No modifica el
objetivo de [C03_RESPUESTA_VERAZ.md](C03_RESPUESTA_VERAZ.md) ni el
[contrato de campaña](01_CONTRATO_DE_CAMPANA.md).

Diferencia con los relevos anteriores: aquellos ataban al agente a conservar el
trabajo demostrado y le prohibían vías concretas. Éste le da permiso total y le
entrega las mediciones ya pagadas como datos refutables, no como órdenes. El
dueño lo decidió así de forma expresa.

Base de la forma del encargo: guía oficial de OpenAI para GPT-6 Astra
(iniciativa y seguimiento, prioridad de instrucciones explícita, delegación en
subagentes, verificación proporcionada) y la guía de Codex para tareas de
horizonte largo (memoria durable en markdown, tramos con criterio de aceptación
y comando de validación, reparar antes de seguir).

- <https://developers.openai.com/api/docs/guides/latest-model>
- <https://developers.openai.com/blog/run-long-horizon-tasks-with-codex>
- <https://developers.openai.com/api/docs/models/gpt-6-astra>

---

## Encargo

Eres el responsable de BAXY Definitivo. Trabaja con reasoning effort alto.

### Objetivo

BAXY debe responder a lo que se le pide: con sentido, con hechos verdaderos,
con voz propia y en el idioma correcto, incluidas las rutas de error. Hoy no lo
hace de forma fiable. El goal formal se llama C03 y su texto está en
`documentacion/sprints/Sprints comprobación/C03_RESPUESTA_VERAZ.md`, pero el
objetivo real es el producto, no aprobar un documento.

Después de C03 quedan C04–C09, 10.7–10.18, 11.1–11.16 y 12.1–12.3 hasta el
producto instalado. Ver `documentacion/sprints/MAPA_COMPLETO_2026-09-05.md`.
Deja C03 de forma que los siguientes no hereden el mismo atasco.

### Autoridad

Tienes permiso total sobre este repositorio. Puedes reorganizar la
arquitectura, mover o borrar módulos, reescribir componentes enteros, cambiar
el modelo local, rehacer la suite de pruebas, y reescribir o fusionar los
propios documentos de sprint si su planteamiento es el problema.

No necesitas pedir permiso para decidir cómo se hace el trabajo. Decide y
ejecuta. Si algo está mal planteado, replantéalo y di por qué.

Lo único que sí se consulta antes de hacerlo: publicar en `main`, borrar
evidencia de corridas anteriores, o cambiar el modelo local del producto.

Trabaja en la rama `Goal-c03` (`main` intacto) o crea la que prefieras. Puedes
delegar en subagentes y paralelizar siempre que sirva; hazlo de forma proactiva,
no como último recurso.

### Contexto que ahorra días

Antes de decidir el enfoque, lee estos cuatro. No para obedecerlos: para no
pagar dos veces el mismo experimento.

| Archivo | Qué aporta |
|---|---|
| `artifacts/comprobaciones/C03/CHECKPOINT.md` | estado y candidato actual |
| `artifacts/comprobaciones/C03/HANDOFF_OPUS_METODO.md` | detalle de la última sesión |
| `artifacts/comprobaciones/C03/SEGUIMIENTOS.md` | causa raíz del contexto perdido |
| `artifacts/audit/regresiones_20260822_20260905/INFORME.md` | qué se rompió y cuándo |

Cuatro hipótesis ya se midieron y empeoraron el resultado, con población
controlada: turno anterior como contexto (`panel-opus-4/-5`); muestreo 0.2/0.9
(agotamientos 1 → 7); forzar la ruta contextual en elípticas (`seguimiento-3`);
prohibir la definición en un seguimiento (de 9 en tema a 6). Están revertidas.
Se puede volver a probar cualquiera con una razón nueva — sabiendo que ya
costaron una sesión cada una.

Dos hechos más que la evidencia demuestra:

1. Hubo una regresión real anterior a C03: el Goal 06 (23-ago, `046f034`) retiró
   la conversión de hora local y dejó de exigir que ese dato sobreviviera a la
   redacción. El dueño recuerda que BAXY funcionaba mejor hace dos semanas y esa
   memoria tiene respaldo parcial. Snapshots en
   `artifacts/audit/regresiones_20260822_20260905/snapshots/`.
2. El intento de conseguir buenas respuestas acumulando filtros de cadena
   literal llegó a 26 comprobaciones en el clasificador de `llm.py` y no cerró
   nada. Volver a esa vía exige una razón que ese historial no tenga.

### Entorno

Este PC puede no tener Granite descargado: el GGUF (2,09 GB) no viaja por git.
Compruébalo al arrancar y dilo. Sin él funcionan pytest, .NET y el censo; los
paneles y las corridas de cien turnos, no.

Intérprete para pruebas Python:
`%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe`
Con el Python del sistema fallan 20 pruebas por dependencias ausentes.

Modelo local actual: Granite 4.2 3B Q4_K_M (gguf `e0406663`), sobre llama.cpp
`b9980`. Se puede evaluar cambiarlo; se consulta antes de hacerlo efectivo.

### Prioridad de instrucciones

1. Que BAXY funcione de verdad para quien lo usa.
2. Honestidad del producto: nunca un hecho inventado, nunca un éxito falso,
   nunca un silencio disfrazado de normalidad. Un error honesto y recuperable
   es aceptable como conducta; no como resultado final de una petición normal.
3. Lo que el dueño diga en conversación.
4. Los documentos de sprint. Si uno contradice lo anterior, el documento cede;
   reescríbelo y deja dicho qué cambiaste.

### Método

Elige tu método. Sólo tres exigencias, y son por el límite de contexto, no por
desconfianza:

- Mantén un registro vivo en `artifacts/comprobaciones/C03/CHECKPOINT.md`: en
  qué vas, qué decidiste y por qué, qué falta. Actualízalo al cerrar cada tramo
  y antes de compactar. Es lo que permite que otra sesión te releve.
- Trabaja en tramos que quepan en una vuelta, cada uno con su criterio de
  aceptación y su comando de validación. Si una validación falla, repárala antes
  de seguir.
- Mide antes/después sobre los mismos casos. Una corrida nueva sin hipótesis
  nueva no es evidencia.

Prueba lo que lo merece. No escribas tests para cambios reversibles y de bajo
impacto; sí para cualquier conducta que ya se rompió una vez.

### Verificación y cierre

C03 está hecho cuando: cien turnos frescos, en español, inglés y spanglish,
repartidos entre bienvenida, conversación, aclaraciones, confirmaciones,
progreso, resultados, errores y resumen — leídos y adjudicados — dan respuestas
útiles y fieles a lo pedido, sin hechos ni palabras inventadas, sin plantillas,
sin fugas del contrato interno y sin silencios; los errores conservan su causa;
Full pasa sobre el candidato final; y el trabajo está publicado.

Cuenta aciertos, no publicaciones. En `panel-opus-13` se publicaron 75 de 78 y
sólo ~75 % respondían a lo pedido. «Publicado» no es «correcto».

Si un fallo bloquea C03, repáralo aunque toque componentes que otro goal también
validará. Reetiquetarlo a C05/C06 no lo cierra.

### Cómo se informa

Prosa clara, párrafos con una idea cada uno. Sin muletillas de informe, sin
listas de viñetas para todo, sin avisos ni descargos no pedidos. Qué hiciste,
qué mediste y qué decidiste.

### Cuándo paras

Paras cuando C03 cumple lo de arriba con evidencia, o cuando llegas a un bloqueo
real que no puedes resolver — y entonces lo dejas escrito con su reanudación, en
EN_CURSO. Quedarse sin contexto o sin cuota no cierra el goal ni rebaja un
criterio.

Implementa. No entregues un plan ni otro informe de diagnóstico.
