"""Enseña al encoder del router que "click/apretá el primer elemento QUE VEAS / de
la lista / en pantalla" es ACCIÓN (computer_use/gui), NO percepción (vision).

Motivo (bug medido 2026-06-07): "En mi pantalla apretá el primer título que veas"
puntuaba vision 0.62 > computer_use 0.52 — las palabras "en mi pantalla" + "que
veas" cargan semántica de percepción aunque la INTENCIÓN sea clickear. El encoder
no tenía ejemplos del patrón acción-sobre-lo-visible, así que lo confundía con
"describí la pantalla". Esto NO es hardcode: alimenta el corpus de embeddings con
ejemplos reales etiquetados para que APRENDA el patrón, universal a cualquier
fraseo/idioma (a diferencia de un regex de verbos por idioma, que es frágil).

Multi-idioma (es/en/pt/fr/de/it). Cada ejemplo combina:
  - un verbo de acción (click/apretar/seleccionar/tocar/presionar...),
  - un selector ordinal/de-lista (el primero, el segundo, el de arriba...),
  - opcionalmente lenguaje de percepción ("que veas", "en pantalla", "de la lista")
para que el encoder aprenda que ESO sigue siendo ACCIÓN.

Salida: append a tool2vec_queries.jsonl (dedup). Reentrenar con router_ft_pipeline.
Rollback: tool2vec_queries.jsonl.bak_pre_clickvisible_2026-06-07.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T2V = ROOT / "gemma4_agent" / "data" / "tool2vec_queries.jsonl"

# (tool, query). Acción de click/selección sobre un elemento VISIBLE. El selector
# ordinal + el lenguaje de "lo que ves/pantalla/lista" es justo lo que confundía
# al encoder con vision. Etiquetados a computer_use (orquesta ver->localizar->click)
# o gui (click directo). Variados en idioma y fraseo a propósito.
EXAMPLES: list[tuple[str, str]] = [
    # --- español (voseo + tuteo) ---
    ("computer_use", "apretá el primer título que veas en pantalla"),
    ("computer_use", "aprieta el primer titulo que veas"),
    ("computer_use", "clickeá el primero que aparezca en la lista"),
    ("computer_use", "hacé click en el primer resultado que veas"),
    ("computer_use", "seleccioná el primer elemento de la pantalla"),
    ("gui", "click en el primer item de la lista"),
    ("gui", "tocá el primer botón que veas"),
    ("computer_use", "presioná el primero de arriba"),
    ("computer_use", "abrí el primer juego que aparezca en pantalla"),
    ("computer_use", "elegí la primera opción que veas"),
    ("gui", "clic en el segundo resultado de la lista"),
    ("computer_use", "apretá el último de la lista que ves"),
    ("computer_use", "dale click al primero que salga"),
    ("gui", "selecciona el primer enlace en pantalla"),
    # --- english ---
    ("computer_use", "click the first title you see on screen"),
    ("computer_use", "tap the first item in the list"),
    ("gui", "click the first result you can see"),
    ("computer_use", "press the first one at the top"),
    ("computer_use", "select the first option on the screen"),
    ("computer_use", "open the first game shown on screen"),
    ("gui", "click the second link in the list"),
    ("computer_use", "click whatever shows up first"),
    # --- português ---
    ("computer_use", "clique no primeiro título que você vê na tela"),
    ("computer_use", "aperte o primeiro item da lista"),
    ("gui", "clique no primeiro resultado que aparecer"),
    # --- français ---
    ("computer_use", "clique sur le premier titre que tu vois à l'écran"),
    ("computer_use", "appuie sur le premier élément de la liste"),
    ("gui", "clique sur le premier résultat que tu vois"),
    # --- deutsch ---
    ("computer_use", "klicke auf den ersten Titel, den du auf dem Bildschirm siehst"),
    ("computer_use", "drücke auf das erste Element in der Liste"),
    # --- italiano ---
    ("computer_use", "clicca sul primo titolo che vedi sullo schermo"),
    ("computer_use", "premi il primo elemento della lista"),
]


def main():
    existing = set()
    if T2V.exists():
        for line in T2V.open(encoding="utf-8"):
            try:
                r = json.loads(line)
                existing.add(str(r.get("q", "")).strip().lower())
            except Exception:
                pass
        bak = T2V.with_suffix(".jsonl.bak_pre_clickvisible_2026-06-07")
        if not bak.exists():
            shutil.copy2(T2V, bak)
            print(f"backup -> {bak.name}")

    new = []
    for tool, q in EXAMPLES:
        if q.strip().lower() in existing:
            continue
        existing.add(q.strip().lower())
        new.append({"tool": tool, "q": q})

    with T2V.open("a", encoding="utf-8") as f:
        for item in new:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"agregados {len(new)} ejemplos click-sobre-visible al corpus del encoder")
    print(f"  corpus total ahora: {sum(1 for _ in T2V.open(encoding='utf-8'))}")
    print("  reentrenar: python scripts/router_ft_pipeline.py")


if __name__ == "__main__":
    main()
