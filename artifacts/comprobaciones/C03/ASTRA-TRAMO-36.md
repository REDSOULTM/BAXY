# Tramo 36 — representación de restricciones y criterio del dueño

2026-09-06. C03 EN_CURSO/ACTIVE, sin bloqueo externo. Rama Goal-c03.
No se editó fuente del producto, cambió modelo/sampler registrado ni ejecutó Full.

La última reiteración del dueño —heredar y contrastar con estado del arte,
documentación, papers y experiencias reproducibles— ya está integrada en
C03_ASTRA_AUTORIDAD.md, sección «Prioridad y método», y en el goal activo.
Abarca todas las piezas relevantes, no solamente el modelo. No duplicar la regla.

## Evidencia y decisión

PRUEBAS_RESTRICCIONES_C03.md conserva las 56 entradas y respuestas literales,
dictámenes y enlaces a los mensajes completos. Se usaron ocho entradas del pool,
consumidas para desarrollo, sin certificar autoría humana ni frescura de aceptación.
Las cuatro sondas terminaron con código 0 y el registro permaneció intacto.

| Corrida | Respuestas | Tiempo | GPU MiB | RAM MiB |
|---|---:|---:|---:|---:|
| astra-constraint-purpose | 16 | 6,81 s | 3497,56 | 2839,57 |
| astra-constraint-scope | 8 | 4,41 s | 3493,56 | 2819,20 |
| astra-constraint-sampling | 24 | 7,45 s | 3493,56 | 2819,09 |
| astra-constraint-scope-data | 8 | 4,66 s | 3493,56 | 2818,98 |

El compositor existente inventa que Spotify está en uso y un modo ahorro anterior;
también devuelve al usuario la tarea de asegurar que el sonido esté activo. La
representación específica de restricción reduce esos problemas. Su variante
determinista de alcance obtiene ocho reconocimientos útiles en los ocho ejemplos.
Eso no acredita detección de restricciones ni integración en BAXY: la sonda recibió
esa interpretación preparada y no ejecutó operaciones ni observó el PC.

**Corrección de evaluación:** no reprobar por sí solos «nunca», una conjugación
torpe o una formulación distinta de primera persona. Conforme al dueño, importan
comprensión, utilidad y verdad. Un reconocimiento de intención no es una lectura
del PC; la permanencia de preferencias exige su propia evidencia si se afirma.
Sí fallan el modo ahorro/Spotify en uso inventados, garantizar que el brillo no
podrá bajar y prometer atención a cada sonido. No se modificaron los verificadores
del producto ni se convirtió esta evaluación posterior en aceptación preregistrada.

Con ese criterio explícito: compositor 4/8, representación inicial 7/8, alcance
8/8, muestreo 23/24, alcance como dato 8/8. No usar la suma 50/56 como tasa de
casos independientes ni porcentaje de C03. El reporte contiene cada dictamen.
Algunos PREREG.method derivados conservaron texto de la primera sonda; stages,
posts y replies documentan las etapas efectivas. La errata queda señalada.

Se reutilizó la investigación oficial específica del tramo33. La búsqueda de
alternativas no añade una comparación local nueva y no justifica otra descarga.
No cambiar de modelo sólo por los reproches de estilo corregidos arriba.
Tampoco promover el muestreo: una semilla añade vigilancia y no demuestra ventaja.

## Reanudación

Integrar una representación de restricción sin observaciones, empezando por
llm._conversation_presentation_shape y la lectura de intención existente. Antes
de editar, comprobar cómo distinguir «no subas el volumen» de una negación social,
«no entiendo» y una petición positiva tras una negación. No convertir todo «no»
inicial en prohibición ni añadir vetos de respuesta por frases. Reutilizar una
sola presentación por responsabilidad; no otra cadena de correcciones.

Después verificar negativos en conversación real con el runtime registrado y
regresar a los pendientes del tramo35: dirección ya especificada, identidad del
dispositivo activo y conocimiento del aire. La fecha y el volumen contextual ya
tienen prueba integrada; no repetir sus diagnósticos sin una regresión concreta.
Siguen pendientes cien frescos, UI final, recuperación/recursos y Full de cierre.

No se alteró el audio en este tramo; la última lectura física sigue siendo la del
tramo35: 100, muted:false. No confundir ausencia de cambios con una lectura nueva.
Las pruebas dueñas y Fast del tramo35 siguen siendo las últimas sobre la fuente.
