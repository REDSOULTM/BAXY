# 395 — conservar el contexto del reintento de chat

394 comparó el mismo reintento y las mismas guardias, con una sola diferencia:
conservar los mensajes anteriores que ya recibió chat. En cinco averías
sintéticas fijadas antes de ejecutar, baseline dio 2/5 útiles y la retención
4/5 estrictamente útiles más un parcial. Recupera Jordan y Casey; mantiene
desconocimiento correcto ante Morgan (tercero) y París sin historial. Álvaro
se recupera, pero el modelo añade «en tu último mensaje», una cronología falsa;
ese caso no se declara plenamente correcto. No hay regresión observada.

Adoptar en `LlmRuntime.chat` únicamente `presentation_history` en la lista de
mensajes del reintento bounded_chat_answer. Es el historial ya acotado, deduplicado
y seleccionado para el primer intento. No usar el historial bruto ni restaurarlo
cuando una definición nueva o un aviso de idioma ya lo han excluido.
Mismos prompts, schema, sampler, presupuesto, validadores y autoridad.

Fortalecer pruebas de guardia existentes para verificar retención de roles y
datos, sin duplicar el pedido actual. Control de cambio de tema: una explicación
de RAM no reincorpora la conversación anterior. Baseline antes de fuente,
dueñas Python y Fast después; Full sólo en cierre. La reparación es de averías,
no acredita aceptación normal ni corrige el compositor privado de 393b.
