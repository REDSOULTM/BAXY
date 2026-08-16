"""Build R16 fusion preserving baseline ASR except dual-ASR pause-safe proof."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT, ROOT / "src", ROOT / "scripts", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_r16_sapi_semantic_fusion_corpus_v2 as builder  # noqa: E402


CORPUS_SCHEMA = "baxy.r16-sapi-semantic-asr-fusion-development.v7"
REPORT_SCHEMA = "baxy.r16-sapi-semantic-asr-fusion-build-development.v7"


def main() -> int:
    arguments = builder.parse_args()
    if arguments.dotnet_root is not None:
        dotnet_root = str(arguments.dotnet_root.resolve(strict=True))
        os.environ["DOTNET_ROOT"] = dotnet_root
        os.environ["DOTNET_ROOT_X64"] = dotnet_root
        os.environ["DOTNET_ROOT(x64)"] = dotnet_root
    core = builder.discover_core(arguments.core)
    operations, applications, games, identities = builder.authenticated_catalog(core)
    report = builder.build(
        parakeet_path=arguments.parakeet,
        whisper_path=arguments.whisper,
        redecode_parakeet_path=arguments.redecode_parakeet,
        redecode_whisper_path=arguments.redecode_whisper,
        output_path=arguments.output,
        report_path=arguments.report,
        available_operations=operations,
        application_names=applications,
        game_catalog=games,
        catalog_identities=identities,
        corpus_schema=CORPUS_SCHEMA,
        report_schema=REPORT_SCHEMA,
        scope="opened_r16_baseline_preserving_pause_safe_redecode_asr_fusion_build",
        supersedes={
            "artifact": "r16_sapi_semantic_asr_fusion_build_v6.v1.json",
            "reason": "v7_preserves_baseline_and_accepts_only_dual_asr_terminal_status_proof",
        },
    )
    print(json.dumps({"rows": report["rows"], "outputSha256": report["outputSha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
