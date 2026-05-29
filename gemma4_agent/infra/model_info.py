"""Parse a GGUF filename and live llama-server state into a ModelInfo dict.

This is the single source of truth for the model header in the Field UI. The
header MUST always reflect the real loaded model — no hardcoding. If a field
cannot be parsed, the value is the literal string "unknown" and the UI will
render it as-is (dim, but not blank).

The parser is deliberately permissive: real GGUF filenames are inconsistent
(Unsloth's UD- prefix, MoE A4B suffix, MatFormer E4B variants, etc.) and we
need to extract sensible defaults from whatever the user has on disk.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelInfo:
    family: str
    params: str
    runtime: str
    quant: str
    size_bytes: int
    name_full: str
    context_size: int
    mmproj: bool


# family: leading lowercase letters + first digit run, e.g. "gemma-4-..." → ("gemma", "4")
_FAMILY_RE = re.compile(r"^([a-z]+)-?(\d+)", re.I)

# params: matches "4B", "E4B" (MatFormer), "26B" (Gemma3n MoE), "7.2b", etc.
# the leading "E" prefix in MatFormer codes (E4B → 4b) is stripped after capture.
_PARAMS_RE = re.compile(r"\b([eE]?\d+\.?\d*)[bB]\b")

# quantization: tries the long forms first so "IQ2_M" wins over a partial "Q2_M".
# the optional "UD-" prefix (Unsloth Dynamic) is consumed but not emitted —
# users think in terms of the base quant, not the toolchain that produced it.
_QUANT_RE = re.compile(
    r"(?:UD-)?("
    r"IQ\d_[A-Z0-9_]+"      # IQ2_M, IQ4_XS, IQ3_S, …
    r"|Q\d_[A-Z0-9_]+"      # Q4_K_M, Q5_K_S, Q6_K, …
    r"|F16|F32|BF16"        # full-precision tags
    r")",
    re.I,
)


def parse_gguf_name(gguf_path: str) -> dict[str, str]:
    """Parse a GGUF filename into family / params / quant / name_full.

    Returns lowercase strings (except name_full, which preserves original casing
    for tooltips). Fields that cannot be parsed return the literal "unknown".
    """
    name = Path(gguf_path).stem  # without .gguf

    fam_match = _FAMILY_RE.match(name)
    family = f"{fam_match.group(1).lower()} {fam_match.group(2)}" if fam_match else "unknown"

    # params: prefer the FIRST parseable B-suffix token, after stripping a leading "E"
    # (MatFormer-style E4B → 4b). Skip the family-version number itself.
    params = "unknown"
    for m in _PARAMS_RE.finditer(name):
        raw = m.group(1).lower()
        if raw.startswith("e"):
            raw = raw[1:]  # E4 → 4
        if raw:
            params = f"{raw}b"
            break

    q_match = _QUANT_RE.search(name)
    quant = q_match.group(1).lower().replace("-", "_") if q_match else "unknown"

    return {
        "family": family,
        "params": params,
        "quant": quant,
        "name_full": name,
    }


def build_model_info(
    gguf_path: str,
    server_url: str,
    mmproj_path: str | None,
    ctx_size: int,
) -> ModelInfo:
    """Bundle parsed filename + on-disk size + runtime origin into ModelInfo."""
    parsed = parse_gguf_name(gguf_path)
    size = os.path.getsize(gguf_path) if os.path.exists(gguf_path) else 0
    runtime = "local" if ("127.0.0.1" in server_url or "localhost" in server_url) else "remote"
    return ModelInfo(
        family=parsed["family"],
        params=parsed["params"],
        runtime=runtime,
        quant=parsed["quant"],
        size_bytes=size,
        name_full=parsed["name_full"],
        context_size=ctx_size,
        mmproj=bool(mmproj_path),
    )


# ---------------------------------------------------------------------------
# 1.9 — Feature-flag de cuantizaciones experimentales en Gemma 4.
#
# Item I1 + Bloque A3 del informe de optimizacion externa. Unsloth retiro
# MXFP4 de sus quants base (Q2_K_XL, Q3_K_XL, Q4_K_XL) por degradacion en
# tensores criticos (attn_gate, attn_q, ssm_alpha/beta). El usuario del repo
# YA tiene gemma-4-26B-A4B-it-MXFP4_MOE.gguf bajado; no queremos prohibirlo
# pero si avisar cuando lo carga.
# ---------------------------------------------------------------------------

# Patrones de cuantizaciones experimentales / desaconsejadas. Substring
# matching (case-insensitive). MXFP4_MOE es el caso primario.
EXPERIMENTAL_QUANT_PATTERNS: tuple[str, ...] = (
    "mxfp4_moe",  # pure MXFP4 MoE; calidad inferior a UD-Q4_K_XL segun Unsloth
    "mxfp4",      # otros builds MXFP4 (excluyendo pure MXFP4_MOE arriba)
)


def is_experimental_quant(gguf_path: str | Path) -> tuple[bool, str | None]:
    """Detecta si el GGUF usa una cuantizacion marcada como experimental.

    Returns (flagged, pattern_matched). Si no hay match: (False, None).
    El caller decide que hacer (warning, gate, etc).
    """
    name = Path(str(gguf_path)).name.casefold()
    for pat in EXPERIMENTAL_QUANT_PATTERNS:
        if pat in name:
            return True, pat
    return False, None


def mock_model_info() -> ModelInfo:
    """Return a deterministic placeholder used when the agent runs in dry-run.

    The UI renders this dim and adds a MOCK badge next to the logomark, so
    users can tell at a glance that the model is not real.
    """
    return ModelInfo(
        family="unknown",
        params="unknown",
        runtime="mock",
        quant="unknown",
        size_bytes=0,
        name_full="(no model loaded)",
        context_size=0,
        mmproj=False,
    )
