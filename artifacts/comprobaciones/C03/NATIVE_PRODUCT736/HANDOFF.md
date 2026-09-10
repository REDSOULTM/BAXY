# Handoff — C03 — 2026-09-10 — tramo736

## Objetivo y estado

Completar C03 íntegro; goal activo en rama Goal-c03.736 es diagnóstico, no adopción. Encuesta742/rev1248:26 cubiertos/716 abiertos/0NA. BAXY manual cerrado; no inferencia viva. Sesiones63813/48438 y84322/5502 terminaron; no sondearlas ni relanzar736.

## Resultado que no debe reconstruirse

Nativo699: seis perfiles×50=300 sin BAXY; Qwen práctico40/50, K2high práctico38/50.736: mismo código, adaptadores y binarios App/Core. K2 se cortó por RAM global747,49MiB tras50/73;11 finales correctos,39 fallidos,23 no evaluados. Qwen73/73;48 correctos/25 fallidos (sensibilidad47–50). Mismos50: K211/Qwen35,24 gananciasQwen,0 pérdidas. No resta causal contra699: otro panel; entorno más libre tras cerrar PresentMon/solicitar cierreSteam. REPORT.md, COMPARISON.json, ambos ADJUDICATION.json y PINS.json preservan límites y datos.

## Atribución y errores de interpretación retirados

- H0104: rechazo BAXY de prosa verdadera. Cambiar «Activa está» a «Está activa» no basta: también restringe el sujeto. FOCUS_ATTRIBUTION.json y replay privado.
- H0023/H0103/disk-used-es: catálogo ofrecido y elección nativa correctos; replay del veto de dominio borra las3. `conversation_reply` timeout es posterior; no la primera pérdida. `process` requerido acepta `*`, no es por sí defecto.
- H0207/H0384: marcador IFM ya en HTTP content; origen generación/prompt/parser no aislado. Wire real T1/max4096/high, no T0/max256/false del input previo.
- H0359: selector ya retorna conversation con cifra sin lectura. Guardia posterior entra por __main__6322→1309 y expira; no por llm7750. Guardia real total3K2/14Qwen: sólo se evita dentro de selección nativa, no en todo el producto.
- No reparar guardia antiguo a partir de probes733/734 sin atribución de ruta concreta. No declarar modelo incapaz por puntuación del conjunto.

## Validación y fuentes pendientes

Fast735 pasó completo, Release0warnings/0errors114,47s;6 pruebas Python distintas pass. Fast1 falló sólo3formatos C# de730; se corrigió formato, sin cambiar aserciones. Dueñas730 anteriores83pass/0fail/0skip. Esta continuación sólo añadió herramientas diagnósticas y reportes; sus aserciones y hashes pasaron.

Full5 sigue rojo: .NET4532pass/0fail/1skip; Python11135pass/2fail/3skip +466subtests. Fallan packaging45s y crashsidecar3s originales. No Full6 ni relajación. Fuente705+712+730 sin adoptar; Python de inventario global730 aún no conectado. Detalle en astra-catalog-source712/FULL5_RESULT.json, astra-window-inventory730/OWNER_STATUS.json y HANDOFF_BEFORE729.md.

## Siguiente acción

Aislar la redacción de hechos con los payloads reales de736 y perfiles adecuados por rol, antes de otra campaña integrada. Empezar por `scratchpad/c03-native-product736-hook/sitecustomize.py` y `src/baxy_mind/llm.py` composición: medir modelo antes/después del prompt y validación, sin ampliar plazos ni repetir tandas idénticas. Permanecen23 casos K2 pendientes; no contarlos ni rellenarlos como passes. C03 aún exige generalización742,8rutas/reserva,UI/voz/loopback-AEC separados,recuperación,recursos conjuntos,matriz/continuidad y Full final verde.
