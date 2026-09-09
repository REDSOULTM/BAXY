# Desarrollo parcial: Qwen8 y composición cortada por plazo GPU

Detenido deliberadamente tras nueve terminales de doce: STOP.json. Exit 15,
344.56 s, 3337.57 MiB GPU atribuida, 6926.84 MiB RAM; registro intacto.
RESULT.stopReason=null pertenece al monitor; STOP.json documenta la interrupción
externa del árbol propio. No es una corrida completa ni un éxito.

1, 2, 4, 6, 8 y 9: composition_failed. 5: filtrado sin final. 3: hora inglesa
fiel. 7: saludo mixed comprensible, pero oferta de café ajena a capacidades.
Dos publicaciones, máximo una respuesta plenamente apta de nueve terminales.

Sampling.jsonl muestra cancelaciones de composición de 4.0 s. El host trata
ngl20 como perfil acelerado completo y entrega 5s de transporte/4s de modelo,
aunque el modelo carga parte en CPU. La medición nativa anterior ya tardaba
6.4–16.3s por composición. No se añade otro veto ni se cambia el corpus: la
siguiente prueba reutiliza presupuestos CPU existentes en el host, con ngl20
real en el sidecar. No certificará C07 ni implicará promoción.
