"""MEDICIÓN Fase 6 (speculative N=2): ¿el 4B encadena la SECUENCIA de acciones
GUI en UNA pasada (sin el andamiaje determinista) con fiabilidad >80%? Si sí,
conviene construir speculative multi-action; si no, NO (los rollbacks cuestan
más que el ahorro). El roadmap exige medir ANTES de construir.

Método: misiones canónicas de 2 pasos ("abrí Notepad y escribí <texto>") con el
SPLITTER DETERMINISTA APAGADO (GEMMA4_MULTI_INTENT=0). Así el 4B, solo, debe
encadenar app.open -> gui.type_into en una pasada. Oráculo por estado del SO
(¿el texto quedó en Notepad? UIA).
"""
import os, sys, time
os.environ["GEMMA4_MULTI_INTENT"] = "0"   # APAGAR el splitter determinista
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
sys.path.insert(0, os.path.dirname(__file__))
import gemma4_agent.agent as A
from eval_set import _kill_process, _clear_notepad_session, uia_window_has_text

ag = A.Gemma4Agent()

cases = [
    ("sp_es_0", "abrí el bloc de notas y escribí hola mundo", "hola mundo"),
    ("sp_es_1", "abrí el bloc de notas y escribí prueba dos", "prueba dos"),
    ("sp_es_2", "abrí notepad y escribí buenas tardes", "buenas tardes"),
    ("sp_es_3", "abrí el bloc de notas y escribí reunion manana", "reunion"),
    ("sp_en_0", "open notepad and type hello there", "hello there"),
    ("sp_en_1", "open notepad and write meeting notes", "meeting notes"),
    ("sp_en_2", "open the notepad and type quick test", "quick test"),
    ("sp_pt_0", "abre o bloco de notas e escreva ola mundo", "ola mundo"),
    ("sp_fr_0", "ouvre le bloc-notes et ecris bonjour", "bonjour"),
    ("sp_it_0", "apri il blocco note e scrivi ciao mondo", "ciao mondo"),
    ("sp_es_4", "abri el bloc de notas y escribi informe final", "informe final"),
    ("sp_es_5", "abri notepad y tipea lista de compras", "lista de compras"),
]

first_ok = 0; full_ok = 0; n = 0
for mid, utt, text in cases:
    _kill_process("notepad.exe"); _clear_notepad_session(); time.sleep(0.4)
    res = ag.run_text(utt)
    events = list(getattr(res, "tool_events", []) or [])
    tools = [(getattr(e, "name", None), (getattr(e, "args", {}) or {}).get("action")) for e in events]
    fa = any(t[0] == "app" or (t[0] == "gui" and t[1] in ("type", "type_into")) for t in tools)
    time.sleep(0.6)
    g = bool(uia_window_has_text("notas", text) or uia_window_has_text("notepad", text))
    n += 1
    if fa: first_ok += 1
    if g: full_ok += 1
    print(f"{mid:10} first={fa} full={g} ntools={len(tools)} {tools}")
    ag.clear()

print("\n=== SPECULATIVE (multi-intent OFF, el 4B encadena solo) ===")
print(f"misiones={n}  first_action={first_ok}/{n}  full_sequence={full_ok}/{n}")
if n:
    print(f"first-action acc = {first_ok/n:.0%}   full-sequence acc = {full_ok/n:.0%}")
    print(f"GATE Fase 6 (>80% full-seq para construir): "
          f"{'PASA -> construir' if full_ok/n > 0.8 else 'NO PASA -> NO construir'}")
