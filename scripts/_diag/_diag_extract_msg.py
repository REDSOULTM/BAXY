import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from gemma4_agent.routing.command_splitter import extract_message_to as E
cases = [
    # (clause, expected: None or (contact, body)) -- '*' = solo chequear contact
    ("manda un mensaje por wsp", None),         # BUG reportado -> None
    ("mandá un wsp", None),                       # pelado, sin dest -> None
    ("manda un mensaje por whatsapp", None),
    ("escribe un mensaje de whatsapp", None),     # pelado 'escribe', sin 'a'
    ("decí hola", None),                          # pelado 'decí' sin 'a' -> None
    ("schick eine nachricht", None),              # de pelado -> None
    ("envoie un message", None),                  # fr pelado -> None
    ("invia un messaggio", None),                 # it pelado -> None
    # --- legítimos: deben SEGUIR extrayendo ---
    ("mandale a juan en discord: nos vemos", ("juan", "nos vemos")),
    ("decile a GordoFriki que llego tarde", ("GordoFriki", "que llego tarde")),
    ("escribe a cbayeah en discord y dile que haces", ("cbayeah", "que haces")),
    ("mandale juan hola", ("juan", "hola")),      # clítico, sin 'a', dest directo
    ("manda a juan un saludo", "*juan"),          # pelado PERO con 'a' -> ok
    ("tell juan hi", ("juan", "hi")),
    ("escribile a mama que ya voy", ("mama", "que ya voy")),
    ("mandá a pedro nos vemos", "*pedro"),        # pelado + 'a' -> ok
    # --- reply-a-último: deben devolver None (los maneja otro flujo) ---
    ("respondele que sí", None),
    ("contestale que ya voy", None),
]
ok = 0
for clause, exp in cases:
    got = E(clause)
    if isinstance(exp, str) and exp.startswith("*"):
        passed = got is not None and got[0].lower() == exp[1:]
    else:
        passed = got == exp
    ok += passed
    print(f"{'OK ' if passed else 'XX '} {clause!r:45} -> {got}   (exp {exp})")
print(f"\n{ok}/{len(cases)} pass")
