import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from gemma4_agent.routing.command_splitter import extract_app_action as A
# (frase, debe_disparar). verify_app=True cuenta como "dispara" (pendiente OS-check)
FIRE = [
    "escribí sigue en claude code",
    "en claude code escribí quién eres",
    "escribí hola mundo en el bloc de notas",
    "poné reunión a las 5 en notepad",
    "type hello world in notepad",
    "andá a Claude Code y escribí continuá",
    "escribí gracias en Discord",
    "abrí Discord y mandá hola",
    "sacá un screenshot",
    "captura de pantalla",
    "andá a notepad y escribí mi nombre",
    "clickeá en guardar en el word",
]
NOFIRE = [
    "qué hora es",
    "gracias",
    "hola",
    "mandale a juan que ya voy",          # whatsapp
    "anotá la reunión en mi lista",       # notes (anotá no es act-verb)
    "recordame comprar pan mañana",       # reminder
    "subí el volumen",                    # audio
    "buscá noticias de hoy",              # web
    "abrí spotify",                       # app.open simple (nav sin acción)
    "reproducí algo en spotify",          # media
    "qué tengo en la agenda",             # query
    "cómo está el clima",                 # web
]
def fires(q):
    r = A(q)
    return r is not None
tp = sum(fires(q) for q in FIRE); fn = len(FIRE) - tp
fp = sum(fires(q) for q in NOFIRE); tn = len(NOFIRE) - fp
print("== DEBE disparar ==")
for q in FIRE:
    r = A(q); tag = f"{r['pattern']}{'(verify)' if r and r['verify_app'] else ''}" if r else "MISS"
    print(f"  {'OK ' if r else 'XX '} {q!r:42} -> {tag}  app={r['app_hint'] if r else None!r}")
print("== NO debe disparar ==")
for q in NOFIRE:
    r = A(q)
    print(f"  {'XX ' if r else 'OK '} {q!r:42} -> {r['pattern'] if r else 'None'}{'(verify_app->OS-check salva)' if r and r['verify_app'] else ''}")
print(f"\nrecall={tp}/{len(FIRE)}  precision-grammar: FP={fp}/{len(NOFIRE)} (los verify_app los filtra el OS-check)")
