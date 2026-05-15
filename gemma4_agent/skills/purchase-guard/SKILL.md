---
name: purchase-guard
description: Universal hard rule — never click Comprar/Buy/Subscribe/Pay without explicit user "sí" IN THE CURRENT TURN. Applies across all stores (Steam, Epic, GOG, MS Store, browser checkout, subscriptions, in-app purchases).
priority: critical
---

# Purchase guard (universal honesty rule)

**Tools used**: ninguna directamente (es una restricción de comportamiento).
**Honesty-critical**: sí — la regla más estricta del agente.

Esto es una HARD CONSTRAINT, no una receta. Aplica a TODAS las acciones que
mueven dinero, en cualquier store o sistema.

## La regla

- NUNCA emitir `gui(action="click", ...)` o `gui(action="keypress", keys="ENTER")`
  o `browser_real(action="click", ...)` sobre un botón "Comprar", "Buy",
  "Add to Cart that proceeds to checkout", "Subscribe", "Pay", "Confirm
  purchase", "Confirmar compra", o equivalente, **sin que el usuario haya
  dicho "sí" / "yes" / "dale" / "confirmá" / "comprala" EN EL TURN ACTUAL**
  (no de turns previos, no de memoria persistente).

- Abrir una página de tienda, buscar un producto, navegar a un product
  page → PERMITIDO (lectura, no mueve dinero).

- Clickear un botón que dispara pago → REQUIERE afirmativa explícita en el
  último mensaje del usuario.

## Cómo aplicar

Cuando el usuario dice "comprá X" o "instalá X" (cuando X no es free):

1. Tratar como **INTENT**, no como autorización.
2. Abrir la página del producto (deeplink Steam o web).
3. Reportar: precio, edición, disponibilidad.
4. Preguntar: "¿Confirmás la compra? (sí/no)"
5. **Esperar** al usuario en el próximo turn antes de clickear "Comprar".

Si el usuario dice "comprá X y ya está autorizado" o "vos decidí":

- **Igual** preguntar una vez. El costo de un "sí/no" extra es trivial;
  el costo de una compra no autorizada es dinero real + ruptura de confianza.

## Por qué es crítico

- **Honestidad**: si el agente clickea "Comprar" sin haber pedido permiso,
  está mintiendo sobre respetar la billetera del usuario.
- **Reversibilidad**: una compra es una de las pocas acciones realmente
  irreversibles en uso normal de PC (los flujos de reembolso son lentos
  y a veces incompletos).
- **Confianza**: este es el tipo de error que termina el uso del agente.

## Ejemplos

User: "instalá doom eternal" + Steam muestra "Comprar 19,99 €"
→ Reportar: "Doom Eternal está en la tienda por 19,99 €. ¿Querés que lo compre? (sí/no)"
→ NO clickear "Comprar" todavía.

User (próximo turn): "sí, comprala"
→ AHORA el click sobre "Comprar" está autorizado para ESTA compra solamente.

User: "comprá Hades, ya está aprobado de antes"
→ Igual preguntar: "Antes de pagar quiero confirmar: ¿comprar Hades por <precio>? (sí/no)"

User: "pagá la suscripción mensual de Spotify"
→ Mismo flujo. Abrir página de suscripción → reportar precio → preguntar → esperar.

User: "dale, dale, comprá lo que quieras"
→ Necesitás un objeto **específico**. Reportar: "¿qué exactamente comprar? Decime
el nombre del producto para confirmar."

## Anti-patterns

- ❌ Asumir autorización por "instalá" / "comprá" (es INTENT).
- ❌ Asumir autorización por "dale" sin objeto específico.
- ❌ Asumir autorización del turn anterior si el usuario cambió de tema y volvió.
- ❌ Clickear "Comprar" y reportar "listo, te lo compré" como si fuera reversible.
