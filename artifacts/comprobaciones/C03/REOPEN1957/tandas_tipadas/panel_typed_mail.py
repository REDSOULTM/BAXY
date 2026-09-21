# --- MAIL (Fase 7, D4): correo a dirección libre por el Outlook clásico del dueño, medido con la dirección
# sustituida por la casilla de pruebas (D13/D14). Plantilla: linaje revisado msgsend1847 (una aprobación por caso
# con approve_email_send.py <reviews> <case> <recibo>). Revalidación sin crédito nuevo (las filas están cubiertas).
# Se ejecuta dentro de derive_<new>.py (la variable s es el build_msgsend1847 renombrado).
# Cardinalidades: 6 literales, 2 variantes, 2 límites (N = 10).
# Preset: Outlook clásico con perfil (HasClassicOutlookProfile); sin preset de datos; restore: nada (los correos
# de prueba quedan en la casilla del dueño).
_NL = chr(10)

sub("    'msg_send': 'Envio real de un mensaje al canal de prueba forzado del dueno",
    "    'mail_send': 'Correo a una direccion libre (Fase 7, D4; H0554 «mandale un correo a ana@gmail.com diciendo que llego tarde», H0609, H0440 «escribile un mail a juan@hotmail.com», H0018, H0279 «envia un correo a juan», H0638 «envia un correo»; medidos con la direccion sustituida por la casilla de pruebas del dueno): con direccion y texto, exactamente una email.send revisada y aprobada por la raiz (to = casilla de pruebas, texto de la persona, asunto opcional) completada y verificada por la copia en Elementos enviados, y un final que diga que envio ese texto a esa direccion; con direccion y sin texto, o con nombre y sin direccion, o sin nada, una sola pregunta por lo que falta (texto o direccion), cero operaciones, sin inventar direcciones ni forzar la casilla de pruebas.',"
    + _NL + "    'msg_send_unused': 'Envio real de un mensaje al canal de prueba forzado del dueno", 1)
sub("LITERALS = [('H0013', 'msg_send'), ('H0369', 'msg_send'), ('H0395', 'msg_send'), ('H0425', 'msg_send'), ('H0533', 'msg_send'), ('H0719', 'msg_send'), ('H0008', 'msg_send'), ('H0208', 'msg_send'), ('H0225', 'msg_send'), ('H0489', 'msg_send'), ('H0540', 'msg_send'), ('H0611', 'msg_send')]",
    "LITERALS = [('H0554', 'mail_send'), ('H0609', 'mail_send'), ('H0440', 'mail_send'), ('H0018', 'mail_send'), ('H0279', 'mail_send'), ('H0638', 'mail_send')]", 1)
sub("VARIANTS = [('msgsend1847-dev-01', 'msg_send', 'Mandale un whatsapp a Musica que diga probando.'),"
    + _NL + "            ('msgsend1847-dev-02', 'msg_send', 'Write to Musica on WhatsApp saying test.')]",
    "VARIANTS = [('msgsend1847-dev-01', 'mail_send', 'send an email to autor@example.com saying the test works'),"
    + _NL + "            ('msgsend1847-dev-02', 'mail_send', 'escribile un correo a autor@example.com con asunto prueba que diga todo ok')]", 1)
sub("BOUNDARIES = [('msgsend1847-boundary-01', 'Que significa mandar un mensaje?',"
    + _NL + "               'Pregunta de definicion: explicacion, cero operaciones.'),"
    + _NL + "              ('msgsend1847-boundary-02', 'No le mandes nada a nadie por WhatsApp.',"
    + _NL + "               'Prohibicion: reconocimiento sin enviar; sin negar la capacidad.')]",
    "BOUNDARIES = [('msgsend1847-boundary-01', 'mandale un correo a juan diciendo que llego tarde',"
    + _NL + "               'Nombre sin direccion: pregunta la direccion, cero operaciones, sin inventarla ni usar la casilla de pruebas.'),"
    + _NL + "              ('msgsend1847-boundary-02', 'No mandes ningun correo.',"
    + _NL + "               'Prohibicion: reconocimiento sin enviar; sin negar la capacidad.')]", 1)
sub("REVIEWED_GROUPS = {'msg_send'}", "REVIEWED_GROUPS = {'mail_send'}", 1)
sub("ALLOWED = ['memory.status', 'message.send.test']", "ALLOWED = ['memory.status', 'email.send']", 1)
sub("ALLOWED_BY_GROUP = {'msg_send': ['memory.status', 'message.send.test'], 'no_effect_boundary': ['memory.status']}",
    "ALLOWED_BY_GROUP = {'mail_send': ['memory.status', 'email.send'], 'no_effect_boundary': ['memory.status']}", 1)
sub("EXPECTED_BY_GROUP = {'msg_send': ['message.send.test']}", "EXPECTED_BY_GROUP = {'mail_send': ['email.send']}", 1)
# Textos medidos (D13/D14): la direccion del literal se sustituye por la casilla de pruebas; los literales sin
# texto o sin direccion se miden tal cual (su criterio es la pregunta) y no llevan aprobacion.
LITERAL_SUBSTITUTIONS = {
    'H0554': 'mandale un correo a autor@example.com diciendo que llego tarde',
    'H0609': 'mandale un correo a autor@example.com diciendo que llego tarde',
    'H0440': 'escribile un mail a autor@example.com',   # sin texto → pregunta el texto
    'H0018': 'escribile un mail a autor@example.com',   # idem (direccion redactada en el registro)
    'H0279': 'envia un correo a juan',                                # nombre sin direccion → pregunta la direccion
    'H0638': 'envia un correo',                                       # sin nada → pregunta
}
REVIEW_EXPECTED = {'H0554', 'H0609', 'msgsend1847-dev-01', 'msgsend1847-dev-02'}
assert 'msg_send' not in s.replace('msg_send_unused', '').replace("'msg_send'", ''), 'restos del panel viejo'
