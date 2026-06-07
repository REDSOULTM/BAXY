"""Mide BUG A (turno 7): "escríbele a Juan que voy en un momento en Discord".

ANTES del fix: extract_app_action matchea -> parse_type_action mete "a Juan que
voy en un momento" como payload de tecleo en Discord. extract_message_to (que
separa bien) nunca se llama.

Verifica: (1) extract_message_to separa contacto/cuerpo, (2) el cuerpo NO debe
arrastrar "en Discord" (bug secundario), (3) casos de tecleo legítimo NO deben
ser tratados como mensajería (anti-regresión del fix1).

Uso: python scripts/_diag/_diag_bugA_messaging.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gemma4_agent.routing.command_splitter import (
    extract_app_action,
    extract_message_to,
    parse_type_action,
)

print("=== CASO REAL DEL LOG (turno 7) ===")
real = "escríbele a Juan que voy en un momento en Discord"
print(f"  input: {real!r}")
print(f"  extract_app_action  -> {extract_app_action(real)}")
print(f"  parse_type_action   -> {parse_type_action(real)}")
print(f"  extract_message_to  -> {extract_message_to(real)}")
print("  (esperado tras fix: msg=('Juan','que voy en un momento'), SIN 'en Discord')")

print("\n=== MENSAJERÍA: deben dar (contacto, cuerpo-limpio) ===")
msg_cases = [
    ("escríbele a Juan que voy en un momento en Discord", "Juan", "voy en un momento"),
    ("mandale a juan en discord: nos vemos", "juan", "nos vemos"),
    ("decile a GordoFriki que llego tarde", "GordoFriki", "llego tarde"),
    ("escribile a Ana en WhatsApp que ya salgo", "Ana", "ya salgo"),
]
for text, c_exp, b_exp in msg_cases:
    res = extract_message_to(text)
    ok_c = res and res[0].lower() == c_exp.lower()
    ok_b = res and b_exp.lower() in res[1].lower() and "discord" not in res[1].lower() and "whatsapp" not in res[1].lower()
    print(f"  [{'OK' if (ok_c and ok_b) else 'XX'}] {text!r}\n        -> {res}  (exp contacto={c_exp}, cuerpo~{b_exp}, sin app)")

print("\n=== TECLEO LEGÍTIMO: NO debe parsear como mensajería (None) ===")
type_cases = [
    "escribí 2+2 en la calculadora",
    "escribí hola mundo en el bloc de notas",
    "en notepad escribí la lista de compras",
    "apretá el 5 en la calculadora",
]
for text in type_cases:
    res = extract_message_to(text)
    print(f"  [{'OK' if res is None else 'XX'}] {text!r} -> message_to={res} (debe ser None)")

# RIESGO del Fix2: pelar "_MSG_APP_TAIL" del body podría comerse un mensaje que
# LEGÍTIMAMENTE termina en "en <palabra>" (ej "te espero en casa"). Medimos qué
# pasaría aplicando el regex al body.
import re as _re
from gemma4_agent.routing.command_splitter import _MSG_APP_TAIL
print("\n=== RIESGO Fix2: ¿el pelado de 'en <app>' rompe mensajes con 'en <lugar>' final? ===")
risky_bodies = [
    "que voy en un momento en Discord",   # bug real: debe quedar "que voy en un momento"
    "te espero en casa",                  # legítimo: NO debe perder "en casa"
    "nos vemos en el bar",                # legítimo
    "llego en 10",                        # legítimo (en 10)
    "ya salgo",                           # sin 'en'
]
for b in risky_bodies:
    peeled = _MSG_APP_TAIL.sub("", b).strip(" ,:")
    changed = peeled != b
    print(f"  {b!r:45} -> {peeled!r}  {'(CAMBIÓ)' if changed else ''}")

print("\n\n========== DESPUÉS DEL FIX ==========")
print("\n=== Fix2: extract_message_to ya NO arrastra 'en <app>' en el body ===")
post_cases = [
    ("escríbele a Juan que voy en un momento en Discord", "Juan", "voy en un momento", "Discord"),
    ("escribile a Ana en WhatsApp que ya salgo", "Ana", "ya salgo", "WhatsApp"),
    ("decile a Juan que te espero en casa", "Juan", "en casa", None),   # 'en casa' NO es app -> se preserva
]
for text, c_exp, b_must, app_no in post_cases:
    res = extract_message_to(text)
    ok = res and res[0].lower() == c_exp.lower() and b_must.lower() in res[1].lower() \
        and (app_no is None or app_no.lower() not in res[1].lower())
    print(f"  [{'OK' if ok else 'XX'}] {text!r}\n        -> {res}")

print("\n=== Fix1+3: routing de decisión (_looks_like_whatsapp) ===")
from gemma4_agent.routing.planner import _looks_like_whatsapp
route_cases = [
    ("escríbele a Juan que voy en un momento en Discord", False, "Discord -> computer_use(goal)"),
    ("escribile a Ana en WhatsApp que ya salgo", True, "WhatsApp -> reply-net"),
    ("mandale a mama que llego tarde", True, "sin app -> WhatsApp (default)"),
    ("decile a Pedro en Telegram que ok", False, "Telegram -> computer_use"),
    ("escribile a Juan en Slack que reviso el PR", False, "Slack -> computer_use"),
]
for text, exp_wa, why in route_cases:
    got = _looks_like_whatsapp(text)
    print(f"  [{'OK' if got == exp_wa else 'XX'}] wa={got!s:5} (esp {exp_wa!s:5}) | {why}  <- {text!r}")
