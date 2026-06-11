"""Refuerzo noES del eval congelado del router (backlog #3, 2026-06-11).

La slice no-ES del holdout tenía 1-8 filas por idioma — sin poder estadístico
para los gates por idioma. Agrega 50 filas curadas A MANO (10 × en/pt/fr/de/it)
con labels por convención del corpus, DEDUPLICADAS contra TODO lo que entrena
el encoder (router_corpus_curated_ft + tool2vec_queries) y contra canarios y
el eval existente — las filas de eval deben ser NO VISTAS.

OJO: agregar filas CAMBIA el benchmark — los números pre/post de esta fecha no
son comparables; re-medir baseline tras correr esto (queda en el log).

Idempotente: si la fuente ya existe en el corpus, no duplica.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.curated.jsonl"
SOURCE = "curated_noes_2026-06-11"

ROWS = [
    # en
    ("turn the volume down to 15", ["audio"]),
    ("skip this track please", ["media"]),
    ("minimize all my windows", ["window"]),
    ("how much disk space is left", ["system"]),
    ("send a whatsapp to my mom saying I arrived", ["whatsapp"]),
    ("what's the weather like in London", ["web", "knowledge"]),
    ("who painted the Mona Lisa", ["web", "knowledge"]),
    ("thanks a lot mate", []),
    ("open the calculator app", ["app"]),
    ("take a screenshot of my screen", ["gui", "vision"]),
    # pt
    ("abaixa o volume para 25", ["audio"]),
    ("pula essa música", ["media"]),
    ("minimiza todas as janelas", ["window"]),
    ("quanto espaço livre tem no disco", ["system"]),
    ("manda um whatsapp pro meu irmão dizendo que cheguei", ["whatsapp"]),
    ("como está o tempo em Lisboa", ["web", "knowledge"]),
    ("quem pintou a Mona Lisa", ["web", "knowledge"]),
    ("valeu, muito obrigado", []),
    ("abre a calculadora", ["app"]),
    ("tira um print da tela", ["gui", "vision"]),
    # fr
    ("baisse le volume à 30", ["audio"]),
    ("passe à la chanson suivante", ["media"]),
    ("réduis toutes les fenêtres", ["window"]),
    ("combien d'espace disque il reste", ["system"]),
    ("envoie un whatsapp à ma mère disant que je suis arrivé", ["whatsapp"]),
    ("quel temps fait-il à Paris", ["web", "knowledge"]),
    ("qui a peint la Joconde", ["web", "knowledge"]),
    ("merci beaucoup c'est gentil", []),
    ("ouvre la calculatrice", ["app"]),
    ("fais une capture d'écran", ["gui", "vision"]),
    # de
    ("stell die Lautstärke auf 35", ["audio"]),
    ("spring zum nächsten Lied", ["media"]),
    ("minimiere alle Fenster", ["window"]),
    ("wie viel Speicherplatz ist frei", ["system"]),
    ("schick eine WhatsApp an Papa dass ich angekommen bin", ["whatsapp"]),
    ("wie ist das Wetter in Berlin", ["web", "knowledge"]),
    ("wer hat die Mona Lisa gemalt", ["web", "knowledge"]),
    ("danke dir, sehr nett", []),
    ("öffne den Taschenrechner", ["app"]),
    ("mach einen Screenshot vom Bildschirm", ["gui", "vision"]),
    # it
    ("abbassa il volume a 40", ["audio"]),
    ("salta questa canzone", ["media"]),
    ("riduci tutte le finestre", ["window"]),
    ("quanto spazio libero c'è sul disco", ["system"]),
    ("manda un whatsapp a mamma che sono arrivato", ["whatsapp"]),
    ("che tempo fa a Roma", ["web", "knowledge"]),
    ("chi ha dipinto la Gioconda", ["web", "knowledge"]),
    ("grazie mille, gentilissimo", []),
    ("apri la calcolatrice", ["app"]),
    ("fai uno screenshot dello schermo", ["gui", "vision"]),
]


def _norm(t: str) -> str:
    return " ".join(t.casefold().split())


def main() -> int:
    seen: set[str] = set()
    for path in (
        EVAL,
        ROOT / "gemma4_agent" / "data" / "router_corpus_curated_ft.jsonl",
        ROOT / "gemma4_agent" / "data" / "tool2vec_queries.jsonl",
        ROOT / "gemma4_agent" / "data" / "router_canaries.jsonl",
    ):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                seen.add(_norm(json.loads(line).get("q") or ""))
            except Exception:
                continue

    existing = EVAL.read_text(encoding="utf-8")
    if SOURCE in existing:
        print("la fuente ya existe en el corpus — no duplico")
        return 0

    added, skipped = [], 0
    for q, expected in ROWS:
        if _norm(q) in seen:
            skipped += 1
            print(f"  DEDUP (ya vista en train/eval): {q!r}")
            continue
        added.append({"q": q, "expected": expected, "source": SOURCE,
                      "label_origin": "hand" if expected else "hand_none"})

    with EVAL.open("a", encoding="utf-8") as f:
        for r in added:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"agregadas {len(added)} filas noES (skip {skipped} por dedup) -> {EVAL.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
