"""Publica el GGUF fine-tuneado de Baxy a HuggingFace Hub.

Sube el LLM (Q4_K_M) + el mmproj de visión + el model card a un repo de modelo.
Reproducible: regenera el repo HF desde los artefactos locales en models/E2B/.

USO:
    # 1) login una sola vez (el token queda local, NO en el código):
    #    hf auth login        # pegás un token "write" de huggingface.co/settings/tokens
    # 2) publicar:
    python scripts/publish_model_hf.py
    #    o con repo distinto:
    python scripts/publish_model_hf.py --repo TU_USUARIO/otro-nombre

El token se toma de la sesión de `hf auth login` o de $HF_TOKEN (NUNCA se hardcodea).
Idempotente: re-subir actualiza los archivos (HF versiona por commit).

GOTCHA: archivos multi-GB → huggingface_hub usa Xet/LFS automáticamente. Subida
puede tardar según tu upload (3.4 GB + 1 GB). No cortar a mitad.
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models" / "E2B"
CARD = ROOT / "hf_publish" / "README.md"

# Los 2 artefactos que la gente necesita para correr Baxy (texto + visión).
FILES = [
    ("gemma-4-E2B-it-Q4_K_M.gguf", "gemma-4-E2B-it-Q4_K_M.gguf"),  # (local, remoto)
    ("mmproj-F16.gguf", "mmproj-F16.gguf"),
]

DEFAULT_REPO = "REDSOULTM/baxy-gemma4-E2B-GGUF"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=DEFAULT_REPO, help="repo_id destino (usuario/nombre)")
    ap.add_argument("--private", action="store_true", help="crear el repo como privado")
    ap.add_argument("--dry-run", action="store_true", help="verificar todo sin subir")
    args = ap.parse_args()

    try:
        from huggingface_hub import HfApi, login  # noqa: F401
    except ImportError:
        print("ERROR: falta huggingface_hub -> pip install -U huggingface_hub")
        sys.exit(1)

    # token: de la sesión de `hf auth login` (preferido) o $HF_TOKEN. NUNCA hardcoded.
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    api = HfApi(token=token)  # token=None -> usa la sesión guardada de hf auth login
    try:
        who = api.whoami()
        print(f"[hf] autenticado como: {who.get('name')} (rol {who.get('auth',{}).get('accessToken',{}).get('role','?')})")
    except Exception as e:
        print(f"ERROR: no autenticado. Corré `hf auth login` o exportá HF_TOKEN. ({e})")
        sys.exit(1)

    # validar artefactos locales
    missing = [src for src, _ in FILES if not (MODELS / src).exists()]
    if missing:
        print(f"ERROR: faltan artefactos en {MODELS}: {missing}")
        sys.exit(1)
    if not CARD.exists():
        print(f"ERROR: falta el model card {CARD}")
        sys.exit(1)
    for src, _ in FILES:
        sz = (MODELS / src).stat().st_size / 1e9
        print(f"[ok] {src}: {sz:.2f} GB")

    if args.dry_run:
        print(f"[dry-run] subiría a {args.repo}: model card + {[s for s,_ in FILES]}")
        return

    # crear repo (idempotente)
    api.create_repo(repo_id=args.repo, repo_type="model",
                    private=args.private, exist_ok=True)
    print(f"[hf] repo listo: https://huggingface.co/{args.repo}")

    # model card primero (rápido)
    api.upload_file(path_or_fileobj=str(CARD), path_in_repo="README.md",
                    repo_id=args.repo, repo_type="model",
                    commit_message="model card")
    print("[hf] model card subido")

    # los GGUF (lento)
    for src, dst in FILES:
        print(f"[hf] subiendo {src} ... (puede tardar)")
        api.upload_file(path_or_fileobj=str(MODELS / src), path_in_repo=dst,
                        repo_id=args.repo, repo_type="model",
                        commit_message=f"add {dst}")
        print(f"[hf] OK {dst}")

    print(f"\n  LISTO: https://huggingface.co/{args.repo}")
    print("  Verificá que aparezca el widget 'Use this model' (GGUF auto-detectado).")


if __name__ == "__main__":
    main()
