# Coordinación serial — 2026-09-06

Misma población de 16 turnos. Sin Full concurrente. Fuente Python del primer
tramo intacta; cambia coordinación/plazo de transporte en App. 255 s hasta el
último final según shell-trace. No certifica latencia C07.

**11/16 útiles y fieles; 15/16 publicados.** No habilita aceptación reservada.

| Turno | Veredicto | Motivo |
|---|---|---|
| 1 | Pasa | Saludo en inglés. |
| 2 | Pasa | DNS resuelve nombres a IP. |
| 3 | Pasa | Saludo natural con oferta social. |
| 4 | Pasa | Saludo en inglés. |
| 5 | Pasa | Definición correcta de latencia. |
| 6 | Pasa con defecto | Explica efecto del retraso en comunicación y decisiones; «la retraso» y concordancia deficientes. |
| 7 | Pasa | Caché DNS y finalidad correctas. |
| 8 | Pasa | Menos latencia y consultas repetidas. |
| 9 | Pasa | Túnel cifrado con servidor remoto; no promete anonimato total. |
| 10 | Falla | Pierde el tema VPN; contestación circular y genérica. |
| 11 | Pasa | Proxy como intermediario de tráfico y acceso. |
| 12 | Falla | «Filtrar el acceso a datos directamente desde el origen» no explica la finalidad del intermediario con precisión. |
| 13 | Falla | No distingue router de otros dispositivos: omite encaminamiento entre redes. |
| 14 | Falla | «Mejor ruta en el camino que necesitas» no aporta utilidad de un router de red. |
| 15 | Falla | Agotamiento, sin resultado aritmético. |
| 16 | Pasa | Lima. |

La coordinación recupera publicación y está cubierta por regresión de proceso:
75 pass/0 skips en propietarios de App. La traza aún registra timeouts de
decisión; no se declara resuelta toda disponibilidad. El defecto aritmético existe
también en borradores, así que retirar un veto no lo arregla.

`runtime-props.json` conserva plantilla efectiva y sampler heredado de llama.cpp;
`llama-command.txt`, lanzamiento efectivo. Modelo y runtime registrados sin override.
