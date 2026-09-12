# H0567 — autoridad de navegación nominal

Evidencia medida en MUSIC1071/private/run-03, fuente fb4d5c528b64517daf5866efefb90bcdf0798a9e. turns.jsonl conserva «siguiente canción» y session.new. Audit request8: media.control ausente de28 candidatos; raw propone media.status. explicit_contract conserva la lectura equivocada y domain_grounding la retira. No hubo un media.control fallido ni un cambio de estado atribuible al producto.

El matcher media_navigation sí contiene dirección nominal + objeto, pero _is_direct_request no admite la cabeza siguiente/next. La puerta de autoridad retorna antes de alcanzar ese reviewer. La recuperación léxica tampoco lo ofrece, pero no es la única causa: hay una incoherencia concreta entre dos lectores de la misma petición.

Delta mínimo sobre1076: extraer _media_navigation_request del bloque existente y reutilizarlo en _is_direct_request y el reviewer. Se retira el inline sustituido. No se añaden cabezas nominales aisladas, objetos, nombres, ejemplos de catálogo ni otra gramática de dirección; se conserva el matcher completo de1076. Se exige además una cabeza leída por _request_head: el prefijo histórico [^\w]* no puede por sí solo autorizar un texto entre comillas.

Los vetos de negación, cita, futuro, correcciones, dispositivo y conservación de compuestos siguen en sus fronteras existentes; _append sigue comprobando la negación de la ocurrencia. El objeto multimedia y la dirección completos siguen siendo obligatorios. La conexión no lee estado ni sustituye al proveedor; next/previous sólo pueden acreditarse con la cola real y el recibo/postlectura de raíz.

Main ya extrae siguiente + canción como next y no cambia aquí. No se presupone cubierto ningún literal con otro orden gramatical. Caso H0567 y H0351 conservan causas distintas: este delta repara la admisión nominal;1076 anterior repara la flexión pone.

Base1076 SHA7471e20da024b7f99b80ae98ed5b6ea9da5de02221e152dfa8568e2d1c64a6d3. Resultado acumulado1073+1076+revision2 SHAdb79ad14666531dc11ab471eb4a9292a6d3378ceb5e224832d5b6ca39f957001. DIFF sólo contiene esta extensión; sha494eabc2c5dd40e026fc93d494e1a36833e81a84506533045b85a63d427d2277.

Revisión manual sin pruebas, imports, AST, Core, GPU, build, efectos o cambios canónicos/registro. Antecedentes externos intactos. Integración y medición pendientes de raíz; no crédito ni pass prometido.
