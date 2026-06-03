import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from gemma4_agent.routing.command_splitter import extract_message_to as E
# El núcleo de accesibilidad: "escribí <texto> en/a <app>". ¿El reply-net lo
# secuestra como mensaje de WhatsApp? (claude code = APP, no persona)
for q in [
    "escribile sigue a claude code",     # caso EXACTO del user
    "escribí sigue en claude code",
    "en claude code escribe quien eres",
    "escribí hola en el bloc de notas",
    "poné reunion a las 5 en notepad",
    "escribile a juan que ya voy",        # ESTE sí es WhatsApp (control)
]:
    print(f"{q!r:42} -> extract_message_to = {E(q)}")
