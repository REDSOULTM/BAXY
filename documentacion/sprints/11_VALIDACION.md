# Goal 11 — Validación, deuda y cierre

> **Mapa: no se lanza entero.** Se ejecuta en `11.1`–`11.16`, una sesión nueva
> por fichero, con Grok 4.6 High y techo operativo de 500k tokens.

## Continuidad lógica

El Goal 10 demuestra uso diario y aceptación de los mensajes reales. El Goal 11
cumple la función que tenía desde el plan original: buscar lo que todavía puede
romperse, cobrar la deuda aplazada, repetir todas las barras juntas, retirar lo que
sobra y publicar el cierre.

También absorbe correctamente el anillo de 2.036 contratos que el intento fallido
metió entero en el 10. No se ejecutan todos como mensajes: 218 son misiones, 2 son
conversaciones, 1.421 son requisitos, 290 son instrucciones de ingeniería y el
resto son fallos, restricciones, preferencias o seguridad. Cada clase recibe su
oráculo correcto.

## Orden

| Goal | Misión | Cierre local |
|---|---|---|
| 11.1 | Congelar cola de cierre | 2.036 + APLAZADOS asignados sin solapes |
| 11.2 | Contratos runtime | 218 misiones + 2 conversaciones |
| 11.3–11.8 | Requisitos A–F | 1.421 requisitos, ≤240 por sesión |
| 11.9–11.10 | Contratos no-runtime A–B | ingeniería, fallos, no-acción, preferencias y seguridad |
| 11.11 | Errores de mente/kernel | inválido, timeout, autorización, duplicación |
| 11.12 | Errores de providers/estado | mentira, disco, proceso, persistencia, UI/voz |
| 11.13 | Regresión Goals 01–06 | herencia a voz visible |
| 11.14 | Regresión Goals 07–10 | misiones a uso diario |
| 11.15 | Higiene e identidad | APLAZADOS vacío, COSTURAS, código/documentación |
| 11.16 | Full y cierre | árbol único, verde, publicado y documento final |

Los hallazgos de `APLAZADOS.md` se reparten por ownership en 11.1 y se resuelven
durante 11.2–11.12. 11.15 no recibe una montaña sin clasificar: sólo comprueba que
la cola quedó vacía y retira duplicación/código muerto.

## Ambiente

Una misión in-scope que no puede ejecutarse por falta de app, cuenta, contenido,
permiso o dispositivo hace fallar su sesión. Se publica cómo preparar el PC y se
repite el mismo goal. No se cierra el producto convirtiendo ambiente en pass. Lo
expresamente diferido por `00_ALCANCE_DESARROLLO_VS_PRODUCTO.md` se informa como
alcance futuro, nunca como capacidad certificada.

## Criterios agregados

- [ ] 2.036/2.036 contratos con oráculo adecuado y veredicto individual.
- [ ] `APLAZADOS.md` vacío por resolución, descarte medido o salida formal del
      alcance; ninguna entrada se pierde por reescritura del ledger.
- [ ] Caminos de error provocados sin afirmación falsa, acción doble ni constante.
- [ ] Regresión completa de Goals 01–10 sobre el mismo commit.
- [ ] Identidad y `03_COSTURAS.md` completas; cero código muerto, duplicaciones o
      banderas que conserven versiones sustituidas.
- [ ] Full verde, documento de cierre y origin al día.

Protocolo: [`11_PROTOCOLO_GROK46.md`](11_PROTOCOLO_GROK46.md).
