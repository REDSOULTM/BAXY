# 356 — el saludo solicitado atraviesa ambas comprobaciones de eco

351/355 generaron Hola Emmanuel para dime hola emmanuel. La App descartaba el
borrador correcto como restates_request. El compositor Python contenía la misma
comparación: descartó Hola Lina como extra_claim incluso al recuperar un borrador
con un nombre ajeno. Se ajusta esa comparación en ambos dueños, sin cambiar modelo,
prompts, respuestas generadas, lectura global de saludos ni las demás guardas.

El resto de una petición tras dime/decime/tell me puede coincidir con el saludo
pedido. Una petición informativa copiada, incluso tras hola, conserva el veto.
No se incorporan nombres particulares ni prosa visible fija.

- Baseline App: 4 fallos, 4 pass, 0 skips; cuatro saludos válidos rechazados.
- Focal App: 8 pass, 0 fallos, 0 skips, 1 s, política y publicación real.
- Focal Python: 9 pass, 0 fallos, 0 skips, 0,43 s, incluido retry.
- Dueñas Python: 1044 pass, 0 fallos, 0 skips, 5,14 s.
- Dueñas App: 225 pass, 0 fallos, 0 skips, 15 s.
- Fast: verde; build18,00s, 0 advertencias y 0 errores. No Full durante reparación.

Comandos: runtime Python -m pytest tests/test_turn_policy.py
tests/test_compose_contract.py -q -x --tb=short; dotnet test
tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter
FullyQualifiedName~C03FactPreservationTests|FullyQualifiedName~Goal06VisibleVoiceTests|FullyQualifiedName~PlannerAppBoundaryTests|FullyQualifiedName~VoiceFeedbackTests;
.\scripts\test_source_quality.ps1.

El baseline App inicial con un stub que eludía Python está conservado y explicado
en PREREG.md: baseline-wrong-owner.log no es la referencia correcta de App.
El rechazo Python de Hola Lina, abrí Spotify por unmentioned_name comprueba ese
borrador, no un detector semántico completo de afirmaciones de efectos.

Siguiente: producto357, mismos siete pedidos/modelo/perfil aislado355; comprobar
saludo publicado, cada mensaje y journal. No aceptación humana fresca, UI gráfica,
voz física ni promoción de Qwen3.5. C03 íntegro sigue abierto.
