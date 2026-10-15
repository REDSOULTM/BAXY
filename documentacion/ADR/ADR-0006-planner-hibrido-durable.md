# ADR-0006 — Planner híbrido, acotado y durable

- Estado: Aceptado
- Fecha: 2026-07-16
- Depende de: ADR-0001, ADR-0005 y el catálogo recuperado en `3db92e1`

## Contexto

Carter mezcló planificación, ejecución y verificación en un loop amplio. El
primer BAXY Python simplificó demasiado y dividió órdenes antes de coordinarlas.
Tool Ecosystem v2 construyó un excelente executor durable, pero el planner padre
nunca llegó a la raíz. BAXY .NET recuperó una autoridad más pequeña y segura,
pero sólo ejecutaba una operación.

El corpus exige hasta 15 operaciones por misión y el estado del arte muestra
que JSON válido no equivale a plan ejecutable, especialmente con tools
irrelevantes, fallos implícitos y horizonte largo.

## Decisión

Adoptar un planner híbrido:

1. La mente propone únicamente un skeleton cerrado y acotado.
2. El catálogo viene del `hello` exacto validado por el shell.
3. Retrieval limita lo visible a 8 familias y 28 operaciones.
4. Dos revisiones independientes del mismo borrador deben coincidir en
   operaciones, dependencias y modo de argumentos; texto e IDs cosméticos no
   forman parte del consenso.
5. Los argumentos literales se extraen aparte y pueden abstenerse.
6. IDs y revisiones derivados de resultados se materializan sólo después de
   verificar dependencias.
7. .NET vuelve a validar DAG, catálogo, schemas y texto seguro.
8. Cada paso entra al `MissionEngine`; el planner no posee autoridad.
9. El estado se cifra y persiste antes de cada posible efecto.
10. Replan automático máximo dos veces y sólo con prueba de que el efecto no
    pudo ocurrir.
11. Un fallo del planner no degrada a una ejecución parcial de una sola tool.

## Invariantes

- Máximo 16 pasos, IDs únicos, dependencias sólo hacia atrás y sin ciclos.
- `memory.*` jamás se expone al planner general.
- El modelo no declara riesgo, confirmación, retry, verifier ni éxito.
- Una confirmación está ligada a la invocación exacta preparada por el core.
- `Pending` con efecto posible detiene la misión y exige reconciliación.
- La observación reinyectada contiene sólo campos permitidos como IDs, estado,
  versión, revisión, hash, URI de recurso y job; nunca texto libre externo.
- Planes terminales se eliminan del outbox sólo después de cerrar su estado.

## Consecuencias

Positivas:

- Recupera composición sin portar el monolito Python v2.
- Mantiene NativeAOT y la política de riesgo como autoridad.
- Sobrevive reinicios sin repetir ciegamente efectos.
- Permite reemplazar el modelo del planner sin cambiar el executor.

Costes:

- Propuesta y dos revisiones aumentan latencia; solicitudes simples, completas
  y de una sola acción usan primero el router determinista.
- La primera versión ejecuta el DAG secuencialmente.
- Algunas misiones válidas se abstendrán cuando no haya evidencia suficiente.
- Las composiciones privadas y gates externos requieren caminos separados.

## Alternativas descartadas

- Loop ReAct abierto: presupuesto y autoridad demasiado amplios.
- CodeAct/shell general: incompatible con catálogo cerrado y seguridad.
- Portar `legacy/tooling` completo: duplica stores, policy y providers.
- Workflow-only: no cubre las 166 formas compuestas observadas.
- LLM con catálogo completo: peor ruido, coste y superficie de ataque.
- Reintentar siempre: duplica efectos cuando el outcome es incierto.
