# Batería776: casos sintéticos con respuestas reales del modelo local

Estos datos son fixtures declarados, no mediciones de hardware ni mensajes humanos de reserva. Compositor e instrucciones de BAXY activos; no comparación de modelos nativos. 46 respuestas cumplen íntegramente; cuatro quedan sin acreditar por causalidad añadida.

## battery776-01

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 0,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Tu notebook no tiene batería. Está completamente descargada.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta. No tiene batería es coloquialmente ambiguo, pero la continuación está completamente descargada fija el sentido de0% y no ausencia física.

## battery776-02

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 0,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** The battery is at 0%.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-03

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 0,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Tu laptop no tiene batería cargada, está en 0%. No está conectado a una fuente de energía.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-04

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 1,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Te queda un 1% de batería y está cargando mientras estás conectado a la toma.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-05

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 1,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** The battery has 1% left and is currently charging while plugged in.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-06

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 1,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Te queda un 1% de batería y está cargando mientras estás conectado a la toma.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-07

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 9,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Te quedan 9 por ciento de batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-08

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 9,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** The battery has 9% left.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-09

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 9,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Te quedan 9 por ciento de batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-10

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 17,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Te quedan 17 por ciento de batería y está cargando mientras estás conectado a la toma.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-11

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 17,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** The battery has 17% left and is currently charging while plugged in.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-12

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 17,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Te quedan 17 por ciento de batería y está cargando porque tienes la toma de corriente conectada.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** FAIL. Los valores y ambos estados booleanos son correctos, pero porque añade una relación causal no explícita en el fixture. Se conserva sin acreditar bajo el criterio from supplied fixture only; no se clasifica como porcentaje o estado de carga equivocado.

## battery776-13

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 31,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Te queda un 31% de batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-14

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 31,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** The battery has 31% left.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-15

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 31,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Te quedan 31 por ciento de batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-16

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 49,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Te queda un 49% de batería y está cargando mientras estás conectado a la toma.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-17

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 49,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** The battery has 49% charge and is currently charging while plugged in.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-18

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 49,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Te queda un 49% de batería y está cargando porque tienes la conexión a la toma de corriente activa.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** FAIL. Los valores y ambos estados booleanos son correctos, pero porque añade una relación causal no explícita en el fixture. Se conserva sin acreditar bajo el criterio from supplied fixture only; no se clasifica como porcentaje o estado de carga equivocado.

## battery776-19

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 67,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Te queda un 67% de batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-20

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 67,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** The battery has 67% charge left.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-21

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 67,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Te queda un 67% de batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-22

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 82,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Te queda un 82 por ciento de batería y está cargando porque tienes la toma de corriente conectada.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** FAIL. Los valores y ambos estados booleanos son correctos, pero porque añade una relación causal no explícita en el fixture. Se conserva sin acreditar bajo el criterio from supplied fixture only; no se clasifica como porcentaje o estado de carga equivocado.

## battery776-23

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 82,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** The battery has 82% charge and is currently charging while plugged in.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-24

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 82,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Te queda un 82% de batería y estás cargando porque tienes la toma de corriente conectada.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** FAIL. Los valores y ambos estados booleanos son correctos, pero porque añade una relación causal no explícita en el fixture. Se conserva sin acreditar bajo el criterio from supplied fixture only; no se clasifica como porcentaje o estado de carga equivocado. Estás cargando no se cuenta como fallo de actor adicional: la elipsis del dispositivo es plausible y el trato en segunda persona ya está aceptado.

## battery776-25

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 99,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Te queda un 99% de batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-26

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 99,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** The battery has 99% charge left.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-27

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 99,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** Te queda un 99% de batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-28

**Entrada:** Dime cuánta batería le queda a mi notebook.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 100,
  "isCharging": false,
  "isAcOnline": true
}
```

**Respuesta:** Te queda una carga del 100%.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-29

**Entrada:** How much battery is left?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 100,
  "isCharging": false,
  "isAcOnline": true
}
```

**Respuesta:** The battery is at 100%.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-30

**Entrada:** Baxy, dime cuánta battery le queda a mi laptop.

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 100,
  "isCharging": false,
  "isAcOnline": true
}
```

**Respuesta:** Te queda una carga del 100%. La batería está conectada a la fuente de alimentación y no está cargando.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-31

**Entrada:** ¿Está cargando la batería?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 17,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Sí, la batería está cargando. Tiene un 17% de carga y está conectada a la toma de corriente.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-32

**Entrada:** Is the battery charging right now?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 17,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Yes, the battery is charging right now.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-33

**Entrada:** Baxy, ¿está cargando la battery ahora?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 17,
  "isCharging": true,
  "isAcOnline": true
}
```

**Respuesta:** Sí, la batería está cargando ahora.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-34

**Entrada:** ¿Está cargando la batería?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 82,
  "isCharging": false,
  "isAcOnline": true
}
```

**Respuesta:** No, la batería no está cargando. Está conectada a la toma de corriente, pero no se está cargando.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-35

**Entrada:** Is the battery charging right now?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 82,
  "isCharging": false,
  "isAcOnline": true
}
```

**Respuesta:** No, the battery is not charging right now. The device is plugged in, but charging is not active.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-36

**Entrada:** Baxy, ¿está cargando la battery ahora?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 82,
  "isCharging": false,
  "isAcOnline": true
}
```

**Respuesta:** No, la batería no está cargando ahora. Está conectada a la toma de corriente, pero no se está cargando. El porcentaje de carga es del 82%.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-37

**Entrada:** ¿Está cargando la batería?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 49,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** No, la batería no está cargando. El porcentaje de carga es del 49%.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-38

**Entrada:** Is the battery charging right now?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 49,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** No, the battery is not charging right now.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-39

**Entrada:** Baxy, ¿está cargando la battery ahora?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 49,
  "isCharging": false,
  "isAcOnline": false
}
```

**Respuesta:** No, la batería no está cargando ahora.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-40

**Entrada:** ¿Está cargando la batería?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 100,
  "isCharging": false,
  "isAcOnline": true
}
```

**Respuesta:** No, la batería no está cargando. Está completamente cargada y no está en proceso de carga.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-41

**Entrada:** Is the battery charging right now?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 100,
  "isCharging": false,
  "isAcOnline": true
}
```

**Respuesta:** No, the battery is not charging right now. The device is plugged in, but it's not in charging mode.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-42

**Entrada:** Baxy, ¿está cargando la battery ahora?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": 100,
  "isCharging": false,
  "isAcOnline": true
}
```

**Respuesta:** No, la batería no está cargando ahora. Está completamente cargada y no está en proceso de carga.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-43

**Entrada:** ¿Cuánta batería tiene este PC?

**Datos sintéticos:**
```json
{
  "isPresent": false,
  "chargePercent": null,
  "isCharging": null,
  "isAcOnline": true
}
```

**Respuesta:** Este PC no tiene batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-44

**Entrada:** How much battery does this computer have?

**Datos sintéticos:**
```json
{
  "isPresent": false,
  "chargePercent": null,
  "isCharging": null,
  "isAcOnline": true
}
```

**Respuesta:** This computer doesn't have a battery.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-45

**Entrada:** Dime cuánta battery tiene este PC.

**Datos sintéticos:**
```json
{
  "isPresent": false,
  "chargePercent": null,
  "isCharging": null,
  "isAcOnline": true
}
```

**Respuesta:** Este PC no tiene batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-46

**Entrada:** ¿Cuánta batería tiene este PC?

**Datos sintéticos:**
```json
{
  "isPresent": false,
  "chargePercent": null,
  "isCharging": null,
  "isAcOnline": false
}
```

**Respuesta:** Este PC no tiene batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-47

**Entrada:** How much battery does this computer have?

**Datos sintéticos:**
```json
{
  "isPresent": false,
  "chargePercent": null,
  "isCharging": null,
  "isAcOnline": false
}
```

**Respuesta:** This computer has no battery.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-48

**Entrada:** Dime cuánta battery tiene este PC.

**Datos sintéticos:**
```json
{
  "isPresent": false,
  "chargePercent": null,
  "isCharging": null,
  "isAcOnline": false
}
```

**Respuesta:** Este PC no tiene batería.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-49

**Entrada:** ¿Qué porcentaje de batería queda?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": null,
  "isCharging": null,
  "isAcOnline": null
}
```

**Respuesta:** No se puede determinar el porcentaje de batería actual.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.

## battery776-50

**Entrada:** What percentage of battery is remaining?

**Datos sintéticos:**
```json
{
  "isPresent": true,
  "chargePercent": null,
  "isCharging": null,
  "isAcOnline": null
}
```

**Respuesta:** I don't know the battery percentage.

**Criterio:** Answer requested percentage/charging state from the supplied fixture only. Absent battery is not zero charge; null measurements remain unknown. Preserve subject, language and every additional claim; do not infer charging from AC.

**Adjudicación:** PASS. Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta. I do not know expresa desconocimiento del asistente, no posesión de hardware, y es válido.
