WhatsApp messaging rule.

TRIGGER: "mandale X a <persona> en wsp/whatsapp", "escribile X a <persona>", "dile X a <persona> por WhatsApp" -> whatsapp(action="send_message", contact="<persona>", text="<message>").
- contact lookup = local contacts store. Not added yet -> tool returns needs_user -> ask for phone, then contacts(action="create", name=, phone="+...") and retry whatsapp.
- phone given directly ("mandale a +54 9 11... '...'") -> pass phone="+54 9 11..." INSTEAD OF contact=.

AUTO-SEND DEFAULT (since 2026-05-15): tool actually SENDS by default. Flow: dispatch deeplink -> wait wait_seconds (1.8s) for chat to load -> focus WhatsApp window -> verify active window title contains "WhatsApp" -> press Enter. If focus check fails (active window != WhatsApp): aborts safely, returns sent=False + abort_reason, chat left open for user to press Enter manually.
- ALWAYS verify sent=True in tool result before claiming delivery.
- sent=True -> "Listo, le mandé X a <persona>".
- sent=False -> "Abrí el chat con <persona> y dejé el mensaje listo, dale Enter para enviarlo" (+ optionally abort_reason if it helps).

auto_send=false WHEN: "prepárame un mensaje para X", "abrime el chat de X" (no message), "escribime un mensaje para X pero no lo mandes", "quiero revisar antes de enviar". -> chat opens, Enter NOT pressed.

PHONE FORMAT: country code REQUIRED (54 AR, 1 USA, 34 ES, 52 MX, 57 CO, etc.). No country code -> returns needs_user. Tool normalizes spaces/dashes/parens automatically -> pass readable like "+54 9 11 1234-5678".
