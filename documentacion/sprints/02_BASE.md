# Sprint 02 — Base reproducible

## Cómo trabajas

Modelo: GPT-5.6 Sol, `reasoning.effort: high`. Repositorio:
`C:\Users\usuario\Desktop\ETC\Programacion\BAXY`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Ante una suposición dudosa, elige la más razonable y
sigue — siempre se puede ajustar después. Para sólo si vas a tocar datos
personales del usuario u otros proyectos de la carpeta `Programacion`.

Criterio único: **lo mejor para BAXY como producto final**. Entre dos opciones
que cumplen, gana la más ligera.

Arregla lo que bloquea. Lo que *podría* fallar y nadie ha visto fallar lo anotas
en una línea en `documentacion/APLAZADOS.md` y sigues — el sprint 11 existe para
vaciar esa lista.

No recopiles contexto exhaustivo antes de empezar: lee lo justo para dar el paso
siguiente. Si algo ya está documentado en estos repositorios, decide con eso.

## El resultado que cuenta

La compuerta `.\scripts\test_source_quality.ps1 -Mode Full` pasa entera, y pasa
también en un clon recién hecho de este repositorio.

Eso es todo. Es la base sobre la que se apoyan los ocho sprints siguientes: sin
ella, cada medición posterior se hace sobre un árbol que no se puede reproducir.

## Dónde está hoy

Quince pruebas rojas, todas diagnosticadas. Su causa está publicada en R279 y
R280 — léela antes de empezar, porque la mitad del trabajo ya está hecho:

- **Nueve** comparan un preregistro histórico contra lo que su constructor
  regenera hoy. Como el constructor lee el catálogo vivo, cualquier cambio
  legítimo del catálogo las rompe para siempre. La decisión de disciplina ya está
  tomada y escrita en el §7 de la meta: *un preregistro sellado se audita por la
  integridad de su sello, no por su regeneración desde el árbol presente.*
  Aplícala. Verifica el hash publicado del artefacto; no omitas la prueba.
- **Una** falta un artefacto (`bge_m3_operation_recovery_r160_attested.json`).
- **Una** exige un checkpoint binario que no está en la máquina. Descárgalo.
- **Una** es no determinista: `test_dispatch_crash_exits_while_redirected_stdin_remains_open`
  falla por contención con `process.wait(timeout=3.0)` y pasa 5 de 5 aislada.
  Arréglala quitando la dependencia del reloj de pared, no subiendo el número.
- **Tres** tienen causa propia: recibos de V8, `product_packaging`, y el árbol
  WPF del torneo.

Hay además un defecto de reproducibilidad que conviene cerrar de paso: un test
.NET reescribe un artefacto versionado a partir de un fichero que `.gitignore`
excluye, así que sus números dependen del estado local de la máquina.

## Defectos

Lo que bloquea se arregla de verdad: nada de bajar el umbral que lo detectó,
marcar `skip`/`xfail`, mover a pendientes ni envolverlo en un fallback. Lo que
nadie ha visto ocurrir se anota y se sigue.

## Qué entregas

La compuerta verde, y el registro de lo que cambiaste y por qué. Si algo resulta
irreparable por una causa fuera del código de BAXY, dilo con su evidencia y sigue
con el resto.

## Cuándo has terminado

Cuando la compuerta pasa entera dos veces seguidas sobre un árbol congelado, y
una tercera sobre un clon limpio.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
