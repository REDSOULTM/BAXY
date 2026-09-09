# 425 — perfil de RAM incorporado; owners y Fast verdes

LlmRuntime._server_command fija --cache-ram0 y añade --no-mmap con GPU.
CPU-only conserva mmap. Se retira la dependencia de flags inyectados por el
diagnóstico; sin nueva configuración de usuario, capa ni modelo. Contexto,
precisión KV, pesos,slots,sampler e historia se conservan. Evidencia423/424.

La extensión del contrato de perfil GPU falla antes del cambio por ausencia
de cache-ram. El filtro baseline no seleccionó CPU(no se atribuye un rojo CPU).
Después: pytest tests/test_planner.py -q -k 'slots or cpu' →6pass,0skips,0,63s.
pytest tests/test_planner.py tests/test_llm_transport.py tests/test_compose_contract.py
-q --tb=short →293pass+121subtests,0skips,2,34s.
scripts/test_source_quality.ps1 →Fast verde completo,build4,11s,0warnings/errors.
NoFull ni nueva certificación CPU/UI/voz. Servidores de ambosSDK cerrados después.

426 usa el código de producción con observador HTTP/commandline/log y mismos
8casos de desarrollo. El hook no añade cache-ram ni no-mmap: debe venir del
comando real. Fuente nueva425 invalida cualquier afirmación de gate final sobre
fuentes anteriores; repetir final runtime/Full sólo cuando C03 esté reparado.
Modelo registrado2507 intacto;4B3.5 sigue diagnóstico,no promoción.
