# Goal 11 — El ambiente listo

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Acabas cuando los criterios de cierre estén
> marcados, o cuando hayas medido que uno es inalcanzable y publicado la evidencia
> que lo demuestra.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Rama: `main`. Esfuerzo de razonamiento: **`high` de suelo**.

Este goal **no se corre en el PC del Goal 10**. Se lanza en un equipo con el
ambiente de uso real preparado: WhatsApp o Discord en ejecución, Firefox
instalado, visión configurada, Wi‑Fi verificable, controles UIA habilitados,
sesión de streaming autenticada, y política de `system.power` acordada con el
dueño (este Goal 10 dejó el host fail-closed a propósito).

## Qué cobra

Las filas del corpus de 1.947 que el Goal 10 **omitió del recuento de fail**
porque el fallo es del escritorio, no del producto. El veredicto individual
sigue siendo fail en esa corrida: **no se convirtió en pass**. Aquí se
vuelven a ejecutar sobre el ambiente listo.

Inventario r120 (`artifacts/goal10/goal10-in-scope-r120.json`): **216** filas.

| Familia | n | Límite medido en el PC del Goal 10 |
|---|---|---|
| `input.visible.click` | 44 | Control visible ausente o deshabilitado (botón rojo / HWND) |
| `message.send` | 33 | WhatsApp/Discord no está en ejecución |
| `web.search` irrelevante | 23 | El buscador público no devolvió resultados verificables |
| `streaming.play.named` | 22 | Netflix/título no confirmado en esta sesión |
| `vision.describe` | 19 | `BAXY_VISION_ENDPOINT` no configurado |
| `wifi.status` | 16 | Verificación externa de Wi‑Fi falló |
| `package.install.prepare` | 9 | Empaquetado/instalación no disponible aquí |
| `streaming.navigate` | 7 | Sesión de streaming no autenticada |
| `ocr.read` | 7 | OCR / `spa.traineddata` |
| `wifi.connect.named` | 7 | Red nombrada no conectable aquí |
| Firefox no instalado | 6 | `app.open` firefox |
| `window_not_found` | 5 | Ventana ausente en este escritorio |
| `game.launch` | 4 | Juego no instalado |
| WhatsApp cliente | 3 | Receptor resuelto, cliente apagado |
| `system.power` | 2 | Fail-closed (`BAXY_DENY_HOST_POWER_TRANSITION=1`); no reiniciar este PC |
| resto | 2 | `task_not_found`, CDP URL no verificada |

Fuera de alcance de este goal: español e inglés in-scope (eso es el Goal 10) y
otros idiomas (alemán, francés, italiano, portugués, …), que BAXY no promete.

## Criterios de cierre

- [ ] El inventario ambiental del Goal 10 está congelado con `message_id` y
      familia; no se mezclan filas in-scope.
- [ ] En el PC con ambiente listo, cada fila ambiental se reejecuta por el
      pipeline real (mismo testhost / mind / Core). 0 `no responde` ocultos.
- [ ] Las que el ambiente permite pasan con journal + verificación. Las que
      siguen sin ambiente (red caída, título de Netflix inexistente) se
      publican como limitación ambiental con degradado honesto, no como pass.
- [ ] `system.power` se prueba **stubbed o en una máquina de descarte**, nunca
      apagando el puesto de trabajo del agente.
- [ ] Idioma: sólo es/en. El resto no se cuenta.
- [ ] Evidencia en `artifacts/goal11/` con hashes, conteos y el cruce contra
      el inventario r120.

## Qué no hacer

No conviertas un fail ambiental del Goal 10 en pass sin reejecutar. No abras
una segunda validación integral de las 1.947. No reinicies el PC del Goal 10.
