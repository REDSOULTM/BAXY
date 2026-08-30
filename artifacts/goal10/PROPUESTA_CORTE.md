# Propuesta de corte — Goal 10 en subtareas

Pedido del dueño 2026-08-30: el Goal 10 entero no cabe en un solo
cierre. Parar remakes. Cortar.

El **objetivo** no cambia: BAXY cumple la identidad (es/en/spanglish) y
cada mensaje real in-scope tiene veredicto individual. Lo que se corta
es **la sesión**, no el listón.

## Por qué un solo 10 no cierra

El goal mezcla siete trabajos distintos en una sesión:

1. Campaña testhost 1947 + overlay quirúrgico + familias en mente
2. 808 misiones accionables (tubería real)
3. 2.036 contratos canónicos + holdouts (métrica aparte)
4. Matriz de identidad viva (modos, memoria, voz, arranque)
5. Latencia ABBA vs modelo directo
6. Caminos de error a propósito
7. APLAZADOS / COSTURAS / Full / origin limpio

La evidencia: r120→r132 sobre el mismo criterio (1). In-scope
**1507/217 → 1590/142**. Cada tanda ~2 h. 142 fail in-scope siguen
siendo dueño mente/identidad, no ambiente.

## Corte propuesto (cuatro sesiones)

| Sesión | Cierra cuando | No incluye |
|---|---|---|
| **10.1 Corpus Nivel 1** | 1947 respuestas, in-scope fail = 0 (env y de/fr/it/pt omitidas, no convertidas). Overlay quirúrgico. Una remake tras tests verdes dos veces. | 808, 2036, identidad viva, ABBA, Full |
| **10.2 Misiones** | 808/808 tubería real + 2036 `product_1_0` y holdouts con veredicto individual, publicados aparte de 1947 | testhost 1947, ABBA |
| **10.3 Identidad viva** | Matriz `00_IDENTIDAD.md` decisión a decisión; modos, narración, memoria, privacidad, voz. Reusar r114-d. Deny-power. Sin soak. | corpus 1947 |
| **10.4 Medición y higiene** | Latencia ABBA (p50 ≤+25 ms, IC95 ≤+100 ms), caminos de error, APLAZADOS vacío o clasificado, COSTURAS, Full, `origin/main` al día | reabrir 10.1 si ya está a 0 fail |

El **11** sigue siendo ambiente. El **12** sigue publicando evidencia
de 10.x + 11. No se inventa un 10.5.

## Estado al pausar (10.1 a medias)

- HEAD publicado: `672b022` r132 overlay; in-scope **1590/142**
- Merge SHA `a1b6f273c205a709e76f66738f595c5f4f7810a6e06b07ca556e4c4f08639230`
- LastBoot `2026-08-29 21:12:42` (r130 VOID por reboot)
- r130 no overlay. Nunca `system.power` live.
- WIP sucio no commiteado: `effect_intent.py` + test `abri photoshop`
  sin catálogo. Tests de esa familia **no** verdes dos veces. No
  lanzar remake encima.

## Qué no se toca al cortar

- Corpus congelado 1947/626 y 808/281
- Overlay quirúrgico (no wholesale)
- In-scope = es/en; env → 11; de/fr/it/pt omitidos
- Identidad manda sobre el mapping si chocan; se anota

## Decisión que falta del dueño

Elegir este corte de cuatro o uno más grueso (10.1 corpus / 10.2 resto
del 10 original). Hasta entonces: **cero remakes 1947**.
