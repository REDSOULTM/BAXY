"""Account for every runtime case while excluding non ES/EN/Spanglish backlog."""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / "artifacts" / "historical_exhaustive"
CASES = LEDGER / "all_executable_cases.jsonl"
OUTPUT = LEDGER / "runtime_language_scope.jsonl"
SUMMARY = LEDGER / "runtime_language_scope_summary.json"
CURATED_NON_TARGET = REPO / "scripts" / "data" / "non_target_language_case_ids.txt"

# Exact manual audit of the remaining non-target-language replay failures.
# Keeping identities (instead of heuristics) makes the acceptance boundary stable.
OUT_OF_SCOPE_LANGUAGE = frozenset("""
case_100b35d313dcd649cfec6a8b case_22410ee4699843ff05416bd0
case_31ad359ffe3a4c0a03603007 case_3417a93e36cb106c2ca61cbc
case_3eb90133cdd0e7979e4eb981 case_44180a076a2c68ce0614d73e
case_4b7f1afb4d50982180cb284c case_65628f8970931532a2e79b74
case_79adcfd2ccb3f50044bf1115 case_7f8e159367f27c864312b5d4
case_8554126cf706afb692d8e69e case_87138ab5a8c8ac760583fbad
case_888a9bd2edcd5a5b473e2e21 case_8b272066c8a48bcbb253aacf
case_8d555601699c5def845faacd case_8e942e8b95f57270ed2f55c5
case_8f5b4aaee7bff954f33c4779 case_915c630963ecfa8eb355e835
case_933e24ae337181941a077740 case_93f2675a782e60385fe7797a
case_9b1f945dc32f9a3f7a3272e5 case_a023c6ed200f054e5dd01c63
case_a2f35906bbe96cfca5b9b4f4 case_a92a8d8a447393c7b958dba5
case_acdc8b617521bbbae08f555b case_ae74323a21f147f5d1f11753
case_b1407c796d56f8ef24751cfc case_b46a56ba963d2bd9ce001840
case_b961bd3b15243ba078df400f case_bcbf5ff71b4b50be0254b687
case_bd8345989e546c22cb72bae4 case_c1918702521cace56b56f30c
case_c2fe6407aabb27cd63e28444 case_c4deca21239c8b44530b2cad
case_c6a5d096c397dfb6f80f2d19 case_c999e5f41792329b86830e73
case_cf3036bf841133720ce5b7f1 case_d156463cb2acd743983766cb
case_d6c165ecb23ad22350d8474e case_da49eaf697d55c68999e79d2
case_dae563f677db36fddb84028e case_dafc8897c4ddf2a0b7ed062a
case_dc5624a2deac841f9ed4c6d7 case_dcad98696108fba3b2efe8df
case_ddbc6bcb0b660dcd38727b0f case_dfb99a3741ef871bd113c95b
case_e84d7452f24d2035714dfb5f case_efd57982aea50caab20e1625
case_f1a93f4b301703f4bd85b830 case_f284eae05328b827a19cc83b
case_f4d0f0ddf85ce20b348020d7 case_f75094072899f1000c3529cb
case_f8c43ef928899c54372263b5 case_fa037d07f60c45c60f0135db
case_fa884869ca5f7fc8104859df case_fb138bad6c07d0b7074be32a
case_fc8d52455975c64fee7f98f3 case_ffd6f4bc7a8511e4c8c7762f
case_6930fea79017ab305a4a4c17 case_0eaf30d6ce26a72a6710824d
case_3cbbc9faa466f8ccb1aecb51
case_41fb2f364885a04709d6298f case_67f6550b149baa63bc2125c9
case_73231af36cd68ee2a2f43ac9 case_7cfdc71425479d06c0e91ef7
case_a6f1f8971550018dddbb34aa case_e1d54cc2553f64e0504fa29c
case_fcddfe58a8dbcbc426527f13 case_b549fcfa79c07e67a5ade6ea
case_05151dd133ea75b86b758ee6 case_56159ec7fe9152a898657d2e
case_5e331a4004aef2ddb5641455 case_674db4d11d8a7bfee52c00d9
case_e0b650e05c8d052525ef8bb2 case_e0d4cbfad63c12f4f72cf1f8
case_e5bdc386599bbf4f6eee39c5
case_1a6e7c5eec5ce448562dd4c3 case_3e99ebaea1bac6f74e0d11fc
case_6fbb344fb3bb81218c34be57 case_93656c923d2734e72161769e
case_cf89b3d580632e0d5d604fcb
""".split())


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def read_curated_non_target(path: Path) -> frozenset[str]:
    """Read the versioned high-confidence language audit.

    The identities were reviewed with a six-language detector and only retained
    when French, German, Italian or Portuguese won with confidence >= .75,
    margin >= .30 and at least 12 source characters. Ambiguous short commands
    deliberately remain in the ES/EN/Spanglish acceptance scope.
    """
    identities = frozenset(
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )
    if any(not identity.startswith("case_") for identity in identities):
        raise RuntimeError("curated language scope contains an invalid case identity")
    return identities


def confident_non_target_pattern(text: str) -> str | None:
    """Return a reviewed non-target language rule, never a broad detector guess."""

    folded = "".join(
        character for character in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(character)
    )
    folded = " ".join(folded.split()).strip(" ?!.,")
    if re.fullmatch(
        r"(?:por favor )?(?:pode|poderia|consegue) "
        r"(?:abrir|fechar|pausar|continuar) (?:o |a )?.+",
        folded,
    ):
        return "reviewed_portuguese_modal_command"
    if re.fullmatch(r"(?:abre|fecha|feche) o [a-z0-9][a-z0-9 ._-]{0,80}", folded):
        return "reviewed_portuguese_definite_article_command"
    if re.fullmatch(r"fazer (?:o |a )?[a-z0-9][a-z0-9 ._-]{0,80} agora", folded):
        return "reviewed_portuguese_infinitive_command"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=SUMMARY)
    args = parser.parse_args()
    cases = [case for case in read_jsonl(args.cases) if any(
        str(value).startswith("runtime_") for value in case.get("provenance_classes") or ())]
    known = {case["case_id"] for case in cases}
    curated = read_curated_non_target(CURATED_NON_TARGET)
    excluded_ids = OUT_OF_SCOPE_LANGUAGE.union(curated)
    unknown = excluded_ids.difference(known)
    if unknown:
        raise RuntimeError(f"language scope refers to {len(unknown)} unknown cases")
    rows = []
    for case in cases:
        case_id = case["case_id"]
        semantic_non_target = confident_non_target_pattern(str(case.get("text_literal") or ""))
        excluded = case_id in excluded_ids or semantic_non_target is not None
        basis = (
            "manual_non_es_en_spanglish_audit"
            if case_id in OUT_OF_SCOPE_LANGUAGE
            else "high_confidence_non_target_language_audit"
            if case_id in curated
            else semantic_non_target
            if semantic_non_target is not None
            else "conservative_target_unless_confidently_excluded"
        )
        rows.append({
            "case_id": case_id,
            "text_sha256": case["text_sha256"],
            "scope": "out_of_scope_language" if excluded else "target",
            "basis": basis,
            "runtime_occurrence_count": case["occurrence_count"],
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(temporary, args.output)
    counts = Counter(row["scope"] for row in rows)
    summary = {
        "schema_version": 1,
        "policy": "acceptance_backlog_is_es_en_spanglish_only",
        "unique_runtime_cases": len(rows),
        "scope_counts": dict(sorted(counts.items())),
        "basis_counts": dict(sorted(Counter(row["basis"] for row in rows).items())),
        "runtime_occurrence_counts": {
            scope: sum(row["runtime_occurrence_count"] for row in rows if row["scope"] == scope)
            for scope in sorted(counts)
        },
        "all_cases_accounted": len(rows) == len(known),
    }
    args.summary_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
