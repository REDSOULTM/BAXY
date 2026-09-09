# C03 — checkpoint267 — EN_CURSO

Goal-c03; main preservada. Último cambio267: llm.compose_user_message deja de
promover facts.context a situation.previousResponse. La misma prosa anterior
viaja como JSON previous_dialogue_for_references_only fuera de situation,
incluidos los tres intentos; sin nuevo system, sampler ni validador de frases.
PROCEDENCIA_COMPOSITOR267.md; astra-compose-provenance267/before y after.

HTTP9 de UI263 decía «Ya he abierto Steam.» sin operación nueva. Su system
presentaba situation como evidencia, pero ésta contenía la respuesta anterior.
PAYLOAD_COMPARISON.json: petición, system, roles y parámetros idénticos;
sólo se separa el contexto de los hechos. Es captura antes de HTTP, NO inferencia.
La frase falsa aún pasa compose_visible_defect. C# ClaimsUnverifiedSuccess
también la dejó pasar. No afirmar resuelto el fallo público ni ocultarlo con
una frase especial; pendiente comparación nativa y frontera de publicación.

267: pytest test_compose_contract/test_llm_transport/test_turn_policy:999pass,
0skip,6,00s; cinco controles nuevos/actualizados fallaban antes. Ruff verde.
266: lector separa afirmación seguida de petición usando cabezas existentes
y morfología negativa; resolver app usa normalización compartida. «Si, abre
steam» pasa de falso compuesto2 a app.open/Steam; catálogo-unavailable eraNone.
2597pass/0skip,54,36s y ruff. Ninguno de266/267 tiene aún prueba modelo/UI/Fast.
Último Fast anterior262 verde; no se repite Full durante reparación.

Instancia264 pertenece al dueño: PID84328/createTime1788820609.3516054,
launcher100540, ventana397256; proceso revalidado al cerrar267: True.
NO cerrar/reiniciar ni inyectar pruebas; sin watchdog ni cierre automático.
NO leer ahora sus mensajes nuevos: el dueño pidió guardarlos para corregir
DESPUÉS. Traces privadas C03-owner264-private; perfil real dev-mente-v2.
No se usó su servidor de inferencia ni cambió volumen. Tests267 terminaron
exit0; no medición propia en curso. Registro13b971… intacto, overrideQwen3.5.

Siguiente268: seguir con HTTP263 y diagnósticos de causa anteriores, sin tocar
264. La frase «Tengo en mente que abras steam» pierde app.open en shortlist28;
dos selecciones nativas sin tools. Resolver recuperación de operación/identidad
y admisión de afirmaciones. Capacidades263: lista incompleta/length, timeout,
extra_claim, UI Response error; también sigue pendiente. Paquetes267 listos
para comparación nativa cuando no interfiera con las pruebas del dueño.
Reutilizar investigación formato/modelo y catalog67, no otro barrido genérico.

Conservar PRUEBAS_UI263/TRAMO263 y LECTURA_AFIRMACION265_266/TRAMO265_266.
UI263 Steam simple y recuperación verificados con Core. Recursos260 conjuntos
UI/LLM/captura/AEC/Piper:3516,66MiBGPU/4822,60MiBRAM, sin ASR humano;
263:3504,71MiBGPU/5624,86MiBRAM, sin captura. Wake no certificado.

Alcance íntegro pendiente: ocho rutas útiles,100/100humanos frescos aún sin
congelar (742únicos/239revisados, tres ingleses admitidos), averías/recuperación,
UI/voz/ASR/recursos finales, perfil/runtime/instalación, continuidad C04–C09,
Full verde y publicación fuera main. C03 activo, sin bloqueo externo.
