"""Congela las filas E5 de las vistas reales de la pasada r3 para tests/test_cu_v3_semejanza.py.

Entrada: tests/data/cu_semejanza_vistas.json (vistas del journal recortadas por la hora de cada caso, con los
objetivos medidos en r5a/decision.md) y tests/data/cu_etiquetas_fuera_tabla.json (las etiquetas fuera de la tabla
de tests/test_cu_v3_etiquetas.py). Salida: tests/data/cu_semejanza_e5.npy (float16, una fila por texto) y
tests/data/cu_semejanza_e5.json (las claves «query: …» / «passage: …» en el mismo orden). Usa el snapshot fijado del
encoder (router.MODEL_NAME/MODEL_REVISION) sin descargar nada:

    python -X utf8 scripts/cu_semejanza_congelar.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind.router import MODEL_NAME, MODEL_REVISION  # noqa: E402
from baxy_mind.semantic.missions import _LABEL_ALIASES  # noqa: E402

VIEWS = ROOT / "tests" / "data" / "cu_semejanza_vistas.json"
LABELS = ROOT / "tests" / "data" / "cu_etiquetas_fuera_tabla.json"
ROWS = ROOT / "tests" / "data" / "cu_semejanza_e5.npy"
KEYS = ROOT / "tests" / "data" / "cu_semejanza_e5.json"


def main() -> None:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import numpy as np
    from sentence_transformers import SentenceTransformer

    views = json.loads(VIEWS.read_text(encoding="utf-8"))
    queries: list[str] = []
    passages: list[str] = []
    for view in views:
        queries.extend(view["labels"])
        passages.extend(str(control.get("name") or "").strip() for control in view["controls"])
    for group in _LABEL_ALIASES:
        queries.extend(sorted(group))
        passages.extend(sorted(group))
    # Las etiquetas fuera de la tabla y sus contracasos (tests/test_cu_v3_etiquetas.py), sobre las mismas vistas.
    outside = json.loads(LABELS.read_text(encoding="utf-8"))
    queries.extend(row["label"] for row in (*outside["pairs"], *outside["never"]))
    keys = [f"query: {text}" for text in dict.fromkeys(q for q in queries if q)]
    keys += [f"passage: {text}" for text in dict.fromkeys(p for p in passages if p)]
    model = SentenceTransformer(MODEL_NAME, device="cpu", revision=MODEL_REVISION, local_files_only=True)
    rows = model.encode(keys, normalize_embeddings=True, show_progress_bar=False, batch_size=64)
    np.save(ROWS, rows.astype(np.float16))
    KEYS.write_text(json.dumps(keys, ensure_ascii=False, indent=0) + "\n", encoding="utf-8", newline="\n")
    print(len(keys), "filas")


if __name__ == "__main__":
    main()
