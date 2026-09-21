# --- MSGANY: REOPEN1993 grupo E — destinatario sin cliente → se busca en los clientes y se envía si es único.
# Plantilla: linaje revisado msgsend1847 (turnos revisados; una aprobación por caso; driver msgsend_case.sh con
# el revisor approve_message_send_any.py <reviews> <case> <destino esperado> <recibo>).
# Se ejecuta dentro de derive_<new>.py (la variable s es el build_msgsend1847 renombrado).
# Cardinalidades: 6 literales, 2 variantes, 2 límites (N = 10). Literales medidos con el destinatario sustituido
# por el chat de prueba (D13): «Música» (WhatsApp) para H0019/H0408/H0198/H0231/H0536 (ya lo nombran) y «Ron92»
# (Discord) para H0024 «escribile a Lucas…» → «escribile a Ron92 que llego tarde» (literal_measured anotado).
# Preset: borrar <perfil>/messaging/recipient-channels.v1.json antes de cada caso (la asociación se aprende en el caso).
import subprocess as _sp
_NL = chr(10)

sub("    'msg_send': 'Envio real de un mensaje al canal de prueba forzado del dueno",
    "    'msg_any': 'Mensaje a un destinatario con nombre y sin cliente nombrado (REOPEN1993 grupo E; H0019 «mandale a Música que ya voy», H0408 «Manda un mensaje a Música que dija hola», H0198/H0231/H0536 «mandale/enviale al grupo Musica: …», H0024 «escribile a Lucas que llego tarde», medido con Ron92): exactamente una message.recipient.resolve{channel: any} completada y verificada que encuentra el chat en un solo cliente (Música en WhatsApp, Ron92 en Discord) y una message.send revisada y aprobada por la raiz (recipientId de esa resolución, texto de la persona) completada y verificada por OCR, sin preguntar el cliente, y un final que diga que envio ese texto a ese chat por ese cliente; el cliente queda recordado para ese nombre; cero operaciones fuera de la lista.',"
    + _NL + "    'msg_send_unused': 'Envio real de un mensaje al canal de prueba forzado del dueno", 1)
sub("LITERALS = [('H0013', 'msg_send'), ('H0369', 'msg_send'), ('H0395', 'msg_send'), ('H0425', 'msg_send'), ('H0533', 'msg_send'), ('H0719', 'msg_send'), ('H0008', 'msg_send'), ('H0208', 'msg_send'), ('H0225', 'msg_send'), ('H0489', 'msg_send'), ('H0540', 'msg_send'), ('H0611', 'msg_send')]",
    "LITERALS = [('H0019', 'msg_any'), ('H0408', 'msg_any'), ('H0198', 'msg_any'), ('H0231', 'msg_any'), ('H0536', 'msg_any'), ('H0024', 'msg_any')]", 1)
sub("VARIANTS = [('msgsend1847-dev-01', 'msg_send', 'Mandale un whatsapp a Musica que diga probando.'),"
    + _NL + "            ('msgsend1847-dev-02', 'msg_send', 'Write to Musica on WhatsApp saying test.')]",
    "VARIANTS = [('msgsend1847-dev-01', 'msg_any', 'avisale a Música que ya estoy llegando'),"
    + _NL + "            ('msgsend1847-dev-02', 'msg_any', 'text Ron92 that the test works')]", 1)
sub("BOUNDARIES = [('msgsend1847-boundary-01', 'Que significa mandar un mensaje?',"
    + _NL + "               'Pregunta de definicion: explicacion, cero operaciones.'),"
    + _NL + "              ('msgsend1847-boundary-02', 'No le mandes nada a nadie por WhatsApp.',"
    + _NL + "               'Prohibicion: reconocimiento sin enviar; sin negar la capacidad.')]",
    "BOUNDARIES = [('msgsend1847-boundary-01', 'mandale a Zebulón que ya voy',"
    + _NL + "               'Destinatario que no esta en ningun cliente: la resolucion any falla (recipient_not_found_in_clients), nada se envia, el final lo dice y ofrece elegir el cliente.'),"
    + _NL + "              ('msgsend1847-boundary-02', 'No le mandes nada a nadie.',"
    + _NL + "               'Prohibicion: reconocimiento sin enviar; sin negar la capacidad.')]", 1)
sub("REVIEWED_GROUPS = {'msg_send'}", "REVIEWED_GROUPS = {'msg_any'}", 1)
sub("ALLOWED = ['memory.status', 'message.send.test']", "ALLOWED = ['memory.status', 'message.recipient.resolve', 'message.send']", 1)
sub("ALLOWED_BY_GROUP = {'msg_send': ['memory.status', 'message.send.test'], 'no_effect_boundary': ['memory.status']}",
    "ALLOWED_BY_GROUP = {'msg_any': ['memory.status', 'message.recipient.resolve', 'message.send'], 'no_effect_boundary': ['memory.status', 'message.recipient.resolve']}", 1)
sub("EXPECTED_BY_GROUP = {'msg_send': ['message.send.test']}", "EXPECTED_BY_GROUP = {'msg_any': ['message.recipient.resolve', 'message.send']}", 1)
# H0024 se mide sustituido: el registro conserva el literal; el texto del caso lleva Ron92 (D13).
LITERAL_SUBSTITUTIONS = {'H0024': 'escribile a Ron92 que llego tarde'}
EXPECTED_RECIPIENT = {'H0019': 'Música', 'H0408': 'Música', 'H0198': 'Musica', 'H0231': 'Musica', 'H0536': 'Musica', 'H0024': 'Ron92',
                      'msgsend1847-dev-01': 'Música', 'msgsend1847-dev-02': 'Ron92'}
# NOTA para el derive: las cardinalidades (12+2+2 → 6+2+2), los pares de transporte (allowed_operations con el par
# resolve/send y maximum_confirmations 1 por caso revisado) y el inventario se ajustan como en panel_1999.py; el
# aprobador de cada caso es approve_message_send_any.py con EXPECTED_RECIPIENT[case]; el boundary-01 (resolve any que
# falla) no necesita aprobación.
assert 'msg_send' not in s.replace('msg_send_unused', '').replace("'msg_send'", ''), 'restos del panel viejo'
