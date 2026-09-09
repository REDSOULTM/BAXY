# 354 — operación conservada en el compositor

src/baxy_mind/llm.py:_compose_situation_payload conserva operation cuando la
situación lo aporta como cadena no vacía, sin inferir del pedido ni copiar
argumentos. Mismo orden y campo de la ablación353; primera respuesta, retry y
pasos anidados comparten la función. No se cambió modelo, sampler ni guarda.

- Preparación del test:1 error de colección por el nombre reservado request;
  renombrado a user_text antes de medir, log preservado por separado.
- Baseline real:2 fail / 0 pass / 0 skips,0,57s. El primer request y el retry
  existían, pero el campo operation faltaba en ambos casos.
- Runtime Python registrado, `-m pytest tests/test_turn_policy.py tests/test_compose_contract.py -q -x --tb=short`:1035 pass / 0 fail / 0 skips,5,13s.
- `.\scripts\test_source_quality.ps1`:Fast verde, build3,39s,0warnings/errors.

Producto355 terminado: mismos siete pedidos y overrideQwen3.5 de351, con perfil
nuevo; únicamente354 cambia en fuente.6/7 turnos completos útiles,0silencios;
journal verifica enable, nuevo save y recall. Resultado literal y límites en
astra-memory-product355/RESULT.md. Siguen el veto del saludo solicitado y la
selección de cuenta Windows en contexto personal. No promoción ni Full en reparación.
