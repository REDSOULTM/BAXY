"""Build R16 fusion with measured ASR-envelope normalization."""

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


CORPUS_SCHEMA = "baxy.r16-sapi-semantic-asr-fusion-development.v6"
REPORT_SCHEMA = "baxy.r16-sapi-semantic-asr-fusion-build-development.v6"


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
        output_path=arguments.output,
        report_path=arguments.report,
        available_operations=operations,
        application_names=applications,
        game_catalog=games,
        catalog_identities=identities,
        corpus_schema=CORPUS_SCHEMA,
        report_schema=REPORT_SCHEMA,
        scope="opened_r16_pause_safe_dual_redecode_normalized_envelope_asr_fusion_build",
        supersedes={
            "artifact": "r16_sapi_semantic_asr_fusion_build_v5.v1.json",
            "reason": "v6_normalizes_the_measured_minute_to_mean_it_asr_envelope",
        },
    )
    print(json.dumps({"rows": report["rows"], "outputSha256": report["outputSha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
