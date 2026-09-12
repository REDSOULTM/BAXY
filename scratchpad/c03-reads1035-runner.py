"""Deriva el runner de READS1035 del de CLOCK1034: sin controles cubiertos, sólo lectura."""
from __future__ import annotations

import hashlib
import pathlib

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
SOURCE = BASE / "C03-clock1034-proposal/runner.py"
TARGET = BASE / "C03-reads1035-proposal/runner.py"

OLD_IDS = ("['H0126', 'H0223', 'H0449', 'H0450', 'H0498', 'H0586', 'H0600', 'H0602', 'H0700', "
           "'H0727']")
NEW_IDS = "['H0224', 'H0543', 'H0104', 'H0511']"

OLD_COUNTS = ("{'cases': 22, 'historical_positive_open': 10, 'covered_regression_controls': 2, "
              "'failed_variant_reexecutions': 0, "
              "'original_development_variants': 6, 'boundaries': 4, 'wire_lines': 44, "
              "'controls': 22, 'session_new': 22, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 22, 'maximum_turn_admissions': 22, "
              "'maximum_reportable_terminals': 22, 'case_final_terminals': 22, "
              "'maximum_internal_confirmations': 0}")
NEW_COUNTS = ("{'cases': 12, 'historical_positive_open': 4, 'covered_regression_controls': 0, "
              "'failed_variant_reexecutions': 0, "
              "'original_development_variants': 6, 'boundaries': 2, 'wire_lines': 24, "
              "'controls': 12, 'session_new': 12, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 12, 'maximum_turn_admissions': 12, "
              "'maximum_reportable_terminals': 12, 'case_final_terminals': 12, "
              "'maximum_internal_confirmations': 0}")

# Sin controles cubiertos, la comprobación de controles se reduce a exigir que no haya ninguno
# declarado y que la regla de no acreditar dos veces siga escrita.
OLD_CONTROL = """    controls_declared = case_map['regression_control_case_ids']
    require(controls_declared == seal['regression_control_case_ids'] == ['H0180', 'H0499'],
            'regression control identity changed')
    require(case_map['regression_controls_never_credit_twice'] is True, 'control credit rule changed')
    require(not set(controls_declared) & set(case_map['historical_case_ids']),
            'a regression control cannot also be a credit candidate')
    for case_id in controls_declared:
        require(registry_by_id[case_id]['verification_status'] == 'covered',
                'regression control is no longer a covered row')
        require(case_map['regression_control_rows'][case_id]['literal']
                == registry_by_id[case_id]['literal'], 'control literal changed')
"""
NEW_CONTROL = """    require(case_map['regression_control_case_ids'] == seal['regression_control_case_ids'] == [],
            'this batch declares no covered regression control')
    require(case_map['regression_control_rows'] == {}, 'control rows declared without controls')
    require(case_map['regression_controls_never_credit_twice'] is True, 'control credit rule changed')
"""


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    replacements = [
        ('"""External clock1034 launcher;', '"""External reads1035 launcher;'),
        ("PRIVATE = BASE / 'C03-clock1034-private'", "PRIVATE = BASE / 'C03-reads1035-private'"),
        ("PANEL = BASE / 'C03-clock1034-proposal'", "PANEL = BASE / 'C03-reads1035-proposal'"),
        ("PROFILE = BASE / 'C03-clock1034-profile'", "PROFILE = BASE / 'C03-reads1035-profile'"),
        ("PUBLIC = ROOT / 'artifacts/comprobaciones/C03/CLOCK1034'",
         "PUBLIC = ROOT / 'artifacts/comprobaciones/C03/READS1035'"),
        ("SEAL_SHA = 'a2aac18ebef111424a5ba98c49965ccce18c6ff09020fe4f376b26a44439bc01'",
         "SEAL_SHA = 'e9ba4fcab5dbe064e0e65133754071b40371d1ab6a63ba78dd820add4e24d22e'"),
        ("REGISTRY_SEALED_SHA = '18c2e349485b0b7c413a10b58e46fa2458a9ff7694589d983009b29508475cfd'",
         "REGISTRY_SEALED_SHA = '58986cb8b2b42a6d70f6648ea0e66b9a7b7e948b784963316683fb6b3f8671f7'"),
        ("'wrong clock1034 panel seal'", "'wrong reads1035 panel seal'"),
        ("seal['schema'] == 'clock1034-directed-material-seal-v1'",
         "seal['schema'] == 'reads1035-directed-material-seal-v1'"),
        ("case_map['schema'] == 'clock1034-case-map-v1'",
         "case_map['schema'] == 'reads1035-case-map-v1'"),
        (f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {OLD_IDS}, 'selected IDs changed')",
         f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {NEW_IDS}, 'selected IDs changed')"),
        (f"require(set(case_map['selected_registry_rows']) == set({OLD_IDS}), 'selected material missing')",
         f"require(set(case_map['selected_registry_rows']) == set({NEW_IDS}), 'selected material missing')"),
        (OLD_CONTROL, NEW_CONTROL),
        (f"require(seal['counts'] == {OLD_COUNTS}, 'panel counts')",
         f"require(seal['counts'] == {NEW_COUNTS}, 'panel counts')"),
        ("require(len(panel) == len(entries) == 22 and len({case['case_id'] for case in panel}) == 22, 'expected 22 unique cases')",
         "require(len(panel) == len(entries) == 12 and len({case['case_id'] for case in panel}) == 12, 'expected 12 unique cases')"),
        ("require(len(wire) == len(positions) == 44, 'expected 44 wire lines')",
         "require(len(wire) == len(positions) == 24, 'expected 24 wire lines')"),
        ("['historical_literal'] * 10 + ['covered_regression_control'] * 2 "
         "+ ['original_development_variant'] * 6 + ['original_boundary'] * 4",
         "['historical_literal'] * 4 + ['original_development_variant'] * 6 "
         "+ ['original_boundary'] * 2"),
        ("candidate['schema'] == 'c03-clock1034-root-manifest-v1'",
         "candidate['schema'] == 'c03-reads1035-root-manifest-v1'"),
        ("'case_count': 22, 'limits': LIMITS", "'case_count': 12, 'limits': LIMITS"),
        ("'session': 'one product run; 22 sealed session.new controls each preceding its original turn',",
         "'session': 'one product run; 12 sealed session.new controls each preceding its original turn',"),
        ("'wire_lines': 44, 'turns': 22, 'controls': 22,", "'wire_lines': 24, 'turns': 12, 'controls': 12,"),
        ("if not ok or len(controls) > 22 or len(controls) != len(terminals) + 1:",
         "if not ok or len(controls) > 12 or len(controls) != len(terminals) + 1:"),
        ("if len(turn_admissions) > 22 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:",
         "if len(turn_admissions) > 12 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:"),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise SystemExit(f"expected exactly one occurrence of: {old[:90]!r} "
                             f"(found {text.count(old)})")
        text = text.replace(old, new)
    for stale in ("C03-clock1034", "clock1034-directed", "clock1034-case-map",
                  "c03-clock1034-root-manifest"):
        if stale in text:
            raise SystemExit(f"stale reference to {stale} left in the derived runner")
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"runner: {TARGET}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
