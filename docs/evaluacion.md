# Cómo se mide BAXY

Un asistente que actúa sobre el PC no se puede evaluar sólo con texto: hay que mirar qué pasó en el escritorio y si lo
que dijo era verdad. BAXY se mide con bancos de casos, oráculos que leen el estado real de Windows y un juez ciego.

## Los bancos

| Banco | Qué mide | Cómo |
|---|---|---|
| **Decisión** | Si el modelo elige la herramienta y los argumentos correctos | Casos de una petición con sus respuestas aceptables; sin ejecutar (`scripts/renew/bench_decision.py`) |
| **De punta a punta (e2e)** | Si la tarea queda hecha en un Windows real | Cada caso tiene preparación, oráculo y limpieza en PowerShell; BAXY recibe la petición en una conversación nueva (`scripts/renew/bench_e2e.py`) |
| **Falsedades** | Si BAXY dice algo que no hizo o no leyó | Conversaciones leídas por un juez con un criterio escrito (`scripts/renew/bench_falsedades.py`, `artifacts/renew/maximo/CRITERIO_FALSEDADES.md`) |
| **Sesión larga** | Si aguanta 45 a 55 turnos seguidos sin degradarse | Guiones de oficina, juegos y sistema (`scripts/renew/bench_sesion_larga.py`) |
| **Banco ciego** | La comparación final entre dos versiones | Misiones de varios pasos, tres semillas por versión, juez ciego |

Los bancos de **práctica** sirven para desarrollar. Los **sellados** (holdouts) se escriben aparte, se guardan fuera
del repositorio porque parten de peticiones reales, y se miden una sola vez por versión. Antes de medir,
`scripts/renew_check.ps1 -Holdout` comprueba el SHA-256 de cada banco sellado contra
[`artifacts/renew/metas.json`](../artifacts/renew/metas.json), para que nadie pueda ajustarlos a posteriori.

## El juez ciego

- Cada misión del banco ciego produce una conversación y los recibos de cada paso. Un **oráculo** independiente
  comprueba el estado final del escritorio.
- Un juez (Claude, varios en paralelo) lee la conversación **sin saber qué versión la produjo** y la clasifica con un
  criterio escrito y versionado por su SHA-256:
  - **logrado**: la tarea quedó hecha y BAXY lo dijo bien;
  - **límite honesto**: no la hizo y dijo que no podía;
  - **éxito falso**: dijo que la hizo y no la hizo (lo peor que puede pasar);
  - **fallo**: no la hizo y no lo reconoció con claridad.
- Cada misión se corre **tres veces** (tres semillas). La clase de la misión es la de la mayoría; sin mayoría cuenta
  como fallo. **pass^3** cuenta las misiones logradas en las tres corridas.
- Base y candidato se juzgan con el mismo juez y el mismo criterio el mismo día.

## La estadística

Las dos versiones se comparan **por pares, misión a misión**, con la prueba de **McNemar** sobre las misiones que una
logra y la otra no. Así un cambio que gana tres misiones fáciles y pierde tres difíciles no parece una mejora.
Para los bancos grandes de decisión se da el intervalo de confianza del 95 % por remuestreo de casos, y antes se mide
el ruido: cuánto cambia la misma versión entre dos corridas suyas.

## Resultados actuales

**Banco ciego de 160 misiones × 3 semillas**, modelo c3 frente al anterior (c2), misma App
([tabla completa](construccion/modelo-propio/ft/BANCO_CIEGO_C3.md)):

| Métrica | c2 | c3 |
|---|---|---|
| Logradas (mayoría de 3) | 36 | **44** |
| pass^3 | 24 | **38** |
| Límite honesto | 51 | 51 |
| Éxito falso | 11 | 11 |
| Fallo | 62 | 54 |
| Misiones con algún éxito falso en alguna corrida | 25 | **20** |
| Robos de foco | 0 | 0 |
| Primer sonido, mediana | 3,7 s | 4,6 s |

McNemar sobre las logradas: 9 misiones sólo las logra c3, 1 sólo c2; **p = 0,0215**.

El modelo c3 intenta más pasos y por eso logra más, pero su primer sonido llegaba más tarde. El análisis está en
[LENTITUD_C3.md](construccion/modelo-propio/ft/LENTITUD_C3.md): el aviso hablado se descartaba por largo o por
plazo. Con el arreglo, en tres misiones largas en vivo con el mismo modelo, la mediana del primer sonido bajó de
**31,8 s a 4,4 s** y las tres sonaron antes de la respuesta. Son sólo tres misiones: el próximo banco ciego lo
confirmará o no.

## Límites conocidos

- **Éxitos falsos.** 11 de 160 misiones por mayoría. Están sobre todo en tareas de interfaz de varios pasos (por
  ejemplo, «Guardar como» con nombre y carpeta). Es la prioridad del próximo ajuste.
- **Tareas largas de interfaz.** Pulsar un rótulo que no está en pantalla tarda entre 17 y 41 s en fallar, porque la
  visión corre en la CPU.
- **Avisos de seguimiento.** Después del primer aviso puede haber silencios largos mientras corre la visión.
- **Voz en inglés.** La voz propia está configurada en español; una respuesta en inglés se lee con esa voz.
- **Instalación.** Todavía es desde el código fuente; la palabra de activación y el reconocedor exacto del producto
  no están publicados (hay alternativas, ver [instalacion.md](instalacion.md)).

## Reproducir una medición

```powershell
# Banco de decisión sobre un banco propio con el mismo formato
py -3.12 scripts\renew\bench_decision.py --help
# De punta a punta: maneja el escritorio real; córrelo en una máquina o sesión dedicada
py -3.12 scripts\renew\bench_e2e.py --help
```

Los e2e mueven ventanas y escriben archivos en carpetas de prueba: no los ejecutes en un escritorio con trabajo
abierto.
