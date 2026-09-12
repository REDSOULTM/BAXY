# Diagnóstico 1028 — tres causas transversales, cada una con su primera transformación incorrecta

De los 17 fallos de la tanda, 14 caen en tres clases. Ninguna es un defecto del compositor de prosa:
en los tres casos el compositor es **fiel al payload que recibe**, y el payload ya viene mal. La
evidencia son las situaciones y payloads reales de `C03-system1028-private/run/compose-audit.jsonl`.

## Causa A — una lectura que sí está en el catálogo se clasifica fuera de catálogo

H0146 «cuánto espacio queda en C» y dev-05 «¿El equipo está enchufado y cargando en este momento?»
recibieron esta situación:

```json
{"kind":"failure","polarity":"failure","cause":"out_of_catalog"}
```

El compositor hizo lo correcto con eso: dijo que está fuera de lo que hace. El defecto está **antes**.
En `src/baxy_mind/__main__.py:6638-6655`, esa situación se construye cuando
`presentation_conversation_kind == "unsupported"` y `catalog_unavailable_decision is not None`, es
decir cuando **la decisión** declaró que el catálogo no cubre la petición. Y sí lo cubre:
`system.status` tiene los scopes `disk` y `battery`, y en la **misma tanda** H0442 y dev-01/dev-02
leyeron el disco y H0037 leyó el estado de batería. No es un veto determinista con un regex que se
pueda corregir en una línea: es la clasificación de la decisión, que acierta con «cuánto espacio libre
tengo en disco» y falla con «cuánto espacio queda en C».

Esto es exactamente el defecto que C03 llama convertir un éxito real en imposibilidad. Seis casos de
la tanda lo comparten: H0146, dev-05, dev-08, dev-09, dev-10 y boundary-03.

## Causa B — la mitad temporal de una petición compuesta se pierde y luego se inventa

H0106 «Muestra la fecha actual y el uso de RAM del sistema» recibió sólo esto:

```json
{"kind":"operation","operation":"system.status","polarity":"success","verified":true,
 "observed":{"scope":"memory","memory":{"totalBytes":34110304256,"availableBytes":10621480960,
 "installedBytes":34359738368}}}
```

Sin `system.time`. La decisión resolvió una sola operación para una petición de dos mitades. Y
entonces ocurre el segundo defecto, el grave: sin fecha en el payload, la respuesta publicada
**fabricó** una, «Hoy es 5 de abril de 2025», cuando la fecha real del sistema era el 12 de
septiembre de 2026. El compositor no tenía el dato y el texto lo invento igualmente.

Las dos variantes de la misma conducta muestran la otra salida del mismo agujero: dev-09 y dev-10
declararon la hora «no disponible en la situación proporcionada» y entregaron sólo la otra mitad.
Es más honesto que inventar, pero sigue siendo falso: `system.time` existe y la categoría de reloj
tiene casos cubiertos.

Las dos mitades del defecto son separables y conviene tratarlas en ese orden: primero que la decisión
conserve las dos operaciones de una petición compuesta; después, que un payload incompleto **no**
pueda producir un dato inventado, que es garantía de honestidad y no de comprensión.

## Causa C — el scope `summary` se elige para una pregunta que nombra un scope concreto

dev-08 «Read the current GPU utilization on this machine» recibió `scope: "summary"`, cuyo contenido
real fue:

```json
{"cpu":{...},"memory":{...},"disk":{...},"battery":{"isPresent":false,"isAcOnline":true},"os":{...},
 "uptimeSeconds":29932,"failures":[]}
```

`summary` no incluye GPU. El payload era correcto y completo para lo que se pidió al provider; lo que
falló fue elegir `summary` en vez de `gpu_usage`. La respuesta —«I don't have access to GPU
utilization data in the current situation»— es fiel al payload y falsa sobre el producto: H0114 y
dev-07, en la misma tanda y en español, obtuvieron la cifra con el scope correcto.

Detalle que refuerza el diagnóstico: ese mismo `summary` traía `battery.isPresent:false` y
`isAcOnline:true`, o sea el dato que las dos variantes de batería declararon imposible por la causa A.
El producto tenía la información en la mano en tres turnos distintos y la negó en dos.

## Asimetría de idioma, anotada sin conclusión

En las tres causas la variante inglesa fue la que falló cuando la española acertó: gpu_usage
(dev-07 pass / dev-08 fail), os_version_with_memory al revés (dev-03 ES fail / dev-04 EN pass),
battery (ambas fail). No hay patrón limpio y con seis pares no se puede afirmar un sesgo de idioma.
Se anota como observación, no como causa, y no se abre una campaña por ello.

## Lo que necesita la tanda de reparación

Subconjunto exacto, no panel entero: los 10 literales que fallaron en 1028 con causa, más controles
que separen las tres causas y protejan lo que ya funciona.

- **Controles de no regresión, obligatorios:** H0442, H0539, H0655, H0422, H0037 y H0114 volvieron a
  cumplir aquí; si la reparación toca la decisión, tienen que seguir cumpliendo. Los cuatro
  acreditados no se re-acreditan, se vigilan.
- **Causa A:** el mismo literal que falló y su gemelo que acertó en la misma conducta, para demostrar
  que la clasificación deja de depender de la formulación.
- **Causa B:** una petición compuesta con las dos mitades disponibles, y una con una mitad
  genuinamente indisponible, para comprobar que la segunda dice qué falta en vez de inventarlo.
- **Causa C:** una pregunta que nombra GPU y otra que pide un resumen, para comprobar que el scope se
  elige por lo que se nombra.

No se propone infraestructura nueva: las tres causas están dentro de mecanismos que ya existen y
funcionaron en esta misma tanda. Nada de esto se integra ni se declara reparado sin medirlo.
