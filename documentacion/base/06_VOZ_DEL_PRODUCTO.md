# Goal 06 — la voz del producto

**Abierto el 2026-08-23. No cerrado.** Este documento se escribe a medida que
avanza; hoy sólo contiene la medida de partida.

> **El estado en una línea:** la prosa que la persona lee hoy **no la formula el
> modelo**: sale de **255 literales fijos** repartidos en 21 ficheros, y el 48 %
> vive en un único `switch` de 964 líneas.

## 1. La medida de partida

| Qué | Ruta |
|---|---|
| Censo reproducible | [`scripts/censo_voz_visible.py`](../../scripts/censo_voz_visible.py) |
| Corrida r0 (2026-08-23) | `artifacts/development/goal06_censo_voz_r0.json` |

```
py -3.12 scripts/censo_voz_visible.py artifacts/development/goal06_censo_voz_r0.json
prosa visible fija: 255 literales en 21 ficheros
```

| Literales | Fichero | Qué es |
|---:|---|---|
| 123 | `src/Baxy.Core/Operations/ProductOperationNarrator.cs` | El `switch` por operación: «Listo, cerré la ventana.» |
| 54 | `src/Baxy.App/MainWindowViewModel.cs` | Negativas, errores y saludo |
| 15 | `src/Baxy.App/PrivateOperationNarration.cs` | Narración de operaciones privadas |
| 13 | `src/Baxy.App/FieldBridgeContract.cs` | Señales de progreso hacia la interfaz |
| 10 | `src/Baxy.Core/Operations/SystemStatusNarration.cs` | Estado del sistema |
| 6 | `src/Baxy.App/MissionNarration.cs` | Resumen de misión |
| 6 | `src/Baxy.Kernel/Operations/IOperationResponseNarrator.cs` | Narrador por defecto |
| 5 | `src/Baxy.App/OperationResponseProjection.cs` | Proyección por estado |
| 5+3 | `src/baxy_mind/__main__.py`, `voice.py`, `asr_fusion.py`, `turn_evidence.py` | Sidecar |
| 12 | Otros 8 ficheros | Una o dos cada uno |

**Qué no cuenta y por qué.** El prompt (`llm.py`, 57 literales) es donde el goal
06 **quiere** que viva el texto: «cambiar el carácter tiene que ser editar un
texto». Los corpus de entrada (`router_bank_sources.py`, `public_turn_corpus.py`,
53 literales) y los `*Parser*.cs` leen al usuario, no le hablan. El censo los
excluye por nombre y lo dice en su cabecera.

## 2. Dónde está el problema de verdad

`ProductOperationNarrator.cs` es un `switch` de **964 líneas** sobre el nombre de
la operación. Cada rama devuelve una frase escrita a mano:

```csharp
"app.close" => "Listo, cerré la ventana.",
"app.status" => "BAXY está listo.",
"audio.microphone.mute" => "Listo, verifiqué el estado de silencio del micrófono predeterminado.",
```

Es exactamente lo que el goal prohíbe, y además explica dos defectos que ya se
habían visto por separado:

- **No responde en el idioma en que se le habló.** La rama es la misma para
  «close Spotify» que para «cierra Spotify».
- **La frase no depende de lo observado.** El goal 05 dejó una verificación que
  observa el estado real; el narrador la ignora y dice siempre la misma frase.

## 3. Las constantes que otros goals ya habían tocado

- `HonestyCorrection.NonAssertingInProgress` = `"Estoy entendiendo tu petición."`
  La publica `FieldBridgeContract` como señal de progreso. Es el «un momento…»
  invariable que el objetivo nombra literalmente.
- `FieldBridgeContract` tiene cuatro más de la misma familia («Estoy preparando
  todo para empezar.», «Estoy realizando la acción que pediste.»).
- `MainWindowViewModel.cs:261` y `:1473` saludan con **«Estoy lista para
  ayudarte»**. BAXY es un «él» por `00_IDENTIDAD.md`: la constante además
  contradice la identidad.

## 4. Lo que falta (ningún criterio de cierre marcado)

- [ ] Cien respuestas seguidas leídas a mano.
- [ ] Cero palabras inventadas, con la causa resuelta y medida.
- [ ] Cero constantes en pantalla, caminos feos incluidos.
- [ ] La narración de accesibilidad por la misma ruta de prosa.
- [ ] La personalidad en el prompt, editable como texto.
- [ ] Publicado: `git rev-list --count origin/main..main` en 0.
