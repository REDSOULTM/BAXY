# Latido en práctica y sondas de continuación, notebook (2026-10-20)

## Latido: modelo base frente a c2-e1.0, escenas de práctica ×4

Los dos modelos corrieron con la misma copia de la mente y el mismo catálogo (`2a5a0aad5`, `BAXY_AYUDAS=none`). El
base es Qwen3.5-4B Q4_K_M (sha 00fe7986). Solo se usaron ids y categorías de práctica, nada del holdout del ajuste
fino.

| Modelo | sin tocar/pA/pB/pC | Molestas | Silencio | Proponer | Decir | Actuar |
|---|---|---|---|---|---|---|
| base | 31/31/31/30 = 30,75 | 2 | 90/92 | 4/12 | 14/24 | 15/28 |
| c2-e1.0 | 32/33/32/33 = 32,50 | 0 | 92/92 | 8/12 | 14/24 | 16/28 |

- **c2-e1.0 gana:** P008 (proponer apagar de noche, de 0 a 4), P019 (callar, de 2 a 4), P027, P007 y P024.
- **c2-e1.0 pierde:**
  - P020: en una llamada propone pausar la música en vez de pausarla; el base la pausaba 3 de 4 veces.
  - P035: decir de noche, de 1 a 0.
- **Fallan los dos:**
  - P002
  - P012: un aviso que se pidió llega y el modelo calla.
  - P016
  - P023: con un recordatorio vencido, el modelo propone `message.draft`.
- **Lo mismo que en el holdout:** c2-e1.0 propone donde debería actuar o decir, y calla recordatorios y avisos
  pedidos (en el holdout: FE12 y FE17).
- **Conducta nueva:** c2-e1.0 llama a `confirmation.answer` en latidos sin nada pendiente (P026 y P035, 4 de 4
  corridas). El base no lo hace nunca.
- **Ayuda posible, solo con hechos:** decir «no hay ninguna confirmación pendiente» en el mensaje del latido.
  - El riesgo es que cambia la presentación del latido con la que se entrenó.
  - No cubre P020, P023 ni P012: ahí el problema es la decisión, no la falta de un dato.
- **El lote sí mueve el latido, solo por la palanca 8:**
  - La frase va en el prefijo de herramientas, que el latido comparte. Escenas: 32,50 → 31,25 (P024 4→2, P026 2→0,
    P004 4→3).
  - Las ayudas de resultado (1, 2, 3b, 1c) no pueden tocarlo.

## Sondas de continuación (confirmación de lo medido en el PC)

Configuración: `continuacion.py` (`e6c18ce9a`), copias sembradas de `d7a76adf1`, catálogo `lote3.json` y c2-e1.0.

| Palanca | Brazo | s0 | s1 | s2 |
|---|---|---|---|---|
| 2 | base: falsas | 6 | 4 | 6 |
| 2 | ayuda: falsas / honestas | 0 / 3 | 0 / 5 | 0 / 2 |
| 3 | base: dice BAXY-bench | 2 | 2 | 2 |
| 3 | campos solos: dice BAXY-bench | 2 | 2 | 2 |
| 3 | `next` (3b): honestas | 3 | 3 | 3 |
| 1c | base: dice que está en la biblioteca | 1 | 1 | 1 |
| 1c | ayuda: mira con `input_visible_controls` | 1 | 1 | 1 |

Los resultados confirman lo del PC: la 2 lleva las falsedades a 0, la 3b funciona solo con `next` y la 1c hace mirar
siempre.

## `beat_no_pending` (`d16e13bf2`): descartada

Escenas ×4 con la misma copia y el mismo catálogo, intercaladas por celda:

| Brazo | sin tocar/pA/pB/pC | `confirmation.answer` espurias |
|---|---|---|
| `none` | 32/33/32/33 = 32,50 | 4 |
| `beat_no_pending` | 32/31/31/32 = 31,50 | 0 |
| lote | 31/32/32/30 = 31,25 | 4 |
| lote + `beat_no_pending` | 31/31/31/32 = 31,25 | 0 |

- **Lo que logra:** quita las llamadas espurias.
- **Lo que no logra:** no convierte esos latidos en «decir».
  - P026: el modelo pasa a `system.settings.set` 4 de 4 veces y el caso queda en 0/4.
  - P035: queda en silencio.
- **Bajas:** P024 y P034.
- **Molestas:** ninguna en los cuatro brazos.
- **Conclusión:** el PC la revirtió (`d8855558e`) porque no sube las escenas.
