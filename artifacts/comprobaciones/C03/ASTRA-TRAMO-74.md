# C03 — veto de fallos impersonales — tramo74

Hipótesis medida en72/t3: una respuesta fiel al invalid_utf8 real se pierde por
dos vetos de Python: «the operation» se confunde con código y «failed» no cuenta
como fallo. No es un defecto del modelo en ese borrador. Herencia directa:
UserMessagePolicy.LooksLikeFailure (tramo52) ya distingue fallos afirmados de
fallos negados. Se reutiliza ese alcance en Python, sin otro prompt ni modelo.
Se retiran sólo las palabras ordinarias «the operation»/«la operación» del veto
de metatexto. Códigos tipados, schemas, éxito inventado y hechos ausentes siguen
protegidos. No ampliar excepciones a otra prosa sin evidencia.

Rojo:2 fail,1 pass,18 deselected/0,55s, en test_compose_contract con los tres
tests nuevos. Con fuente74:21 pass/0,50s. Tres suites dueñas
test_compose_contract.py, test_c03_request_preservation.py, test_turn_policy.py:
1105 pass/0 skips/5,67s. Se usó Python312 explícito porque py apunta a313 sin pytest.
Fast70202exit0: todas las etapas verdes, Release2,86s,0 avisos/errores.
No Full; no validación de cierre.

files74-veto terminó48789exit0. Misma secuencia10, fixtures y override Qwen3.5
de72; fuente63 + Python74. Registro no se modifica. Criterio: respuesta UTF8
útil publicada, con polaridad/causa correctas; registrar todos los otros fallos.
No selector, catálogo, historial ni prompts cambiados. PREREG fija hashes antes
de ejecutar. Conductor no acredita UI, voz/audio físico ni reserva humana.

Resultado6/10 útiles frente a5/10: t3 publica exactamente el primer borrador
fiel rechazado en72.123,12s,GPU3177,56MiB,RAM6983,55MiB,registro intacto.
PRUEBAS_VETO74.md/TRAMO74_PINS.json fijan fuente, pruebas, resultado y límites.
75 confirmó errores HTTP400 de template en t6/t7/t10; no son fallos semánticos
del modelo en esas peticiones. Modelo sigue sin promover.
