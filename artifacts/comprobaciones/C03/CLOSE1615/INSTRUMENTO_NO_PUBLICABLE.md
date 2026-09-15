# CLOSE1615 — adjudicada, no publicable por su instrumento sellado

Fecha: 2026-09-15. Candidato BUILD1613 (mismos binarios, sin cambio de fuente). Panel sellado de 7 casos: 3 literales de «Cerrar aplicaciones y ventanas» (H0546 «cierra whatsapp», H0693 «cierra discord», H0112 «Necesito que cierres whatsapp»), 2 variantes y 2 límites. Los cinco casos con fixture debían cerrar, con turno revisado y una aprobación raíz exacta, el cliente WhatsApp/Discord del dueño abierto por la raíz como fixture propio (autorización del dueño 2026-09-13/16).

## Qué ocurrió

1. El runner sellado rehusó los cinco casos con fixture antes de admitirlos: su paso `observe` exige la ausencia de los clientes de mensajería (WhatsApp.Root.exe, Discord.exe) y su paso `execute` declara «a messaging client is never a root fixture». Ese invariante —que impide que el producto envíe jamás un mensaje real durante un caso— lo repiten el adjudicador (`clients_absent is True`) y el publicador (`clients_absent_before`). La raíz lo conserva en vez de debilitarlo para un panel de cierre: las ventanas del fixture se cerraron por la raíz y no se envió ningún mensaje. No existe segmento de ejecución para esos casos, así que no reciben veredicto.
2. Los dos límites se ejecutaron y aprobaron (cero operaciones): «¿Qué es una ventana?» explicado; «No cierres WhatsApp, lo estoy usando.» reconocido.
3. La adjudicación se aplicó (ROOT_ADJUDICATION.json, REGISTRY_UPDATE.json: 0 créditos, registro sin cambio, 551/742). El publicador sellado (`root_publish_from_adjudication.py`) rechazó la publicación con `Invalid adjudicated indices`: su cota de índices quedó en `0<=i<6` (heredada del panel de seis casos de APPS1611 y no redimensionada por la raíz en APPS1613 ni aquí), y el límite aprobado tiene índice 6. Defecto de derivación de la raíz, no del producto.

## Decisión de raíz

El instrumento sellado no se modifica después del sellado. CLOSE1615 queda adjudicada sin publicación de casos: **0 créditos**, registro sin cambio. Las filas H0546, H0693 y H0112 quedan condicionadas a una decisión de instrumento del dueño: admitir como fixture raíz una ventana de cliente de mensajería con el transporte limitado a window.resolve/app.close (sin operación de mensajería posible), o dejarlas abiertas. La cota del publicador se corrige en la derivación de la próxima tanda.

Sin pruebas por instrucción expresa del dueño.
