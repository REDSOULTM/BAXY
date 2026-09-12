"""Deriva el runner de CLOCK1034 del de REPAIR1033, sin tocar guardas heredadas.

Cambian rutas, sello, registro, conteos, case_id y controles. El entorno declarado es distinto: esta
tanda es de sólo lectura, así que no exige apps abiertas ni cerradas; conserva la negativa a arrancar con
un flyout del sistema en primer plano, porque no cuesta nada y protege la medición.
"""
from __future__ import annotations

import hashlib
import pathlib

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
SOURCE = BASE / "C03-repair1033-proposal/runner.py"
TARGET = BASE / "C03-clock1034-proposal/runner.py"

OLD_IDS = "['H0015', 'H0055', 'H0134', 'H0136', 'H0391', 'H0418', 'H0653', 'H0575']"
NEW_IDS = ("['H0126', 'H0223', 'H0449', 'H0450', 'H0498', 'H0586', 'H0600', 'H0602', 'H0700', "
           "'H0727']")

OLD_COUNTS = ("{'cases': 19, 'historical_positive_open': 8, 'covered_regression_controls': 5, "
              "'failed_variant_reexecutions': 0, "
              "'original_development_variants': 4, 'boundaries': 2, 'wire_lines': 38, "
              "'controls': 19, 'session_new': 19, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 19, 'maximum_turn_admissions': 19, "
              "'maximum_reportable_terminals': 19, 'case_final_terminals': 19, "
              "'maximum_internal_confirmations': 0}")
NEW_COUNTS = ("{'cases': 22, 'historical_positive_open': 10, 'covered_regression_controls': 2, "
              "'failed_variant_reexecutions': 0, "
              "'original_development_variants': 6, 'boundaries': 4, 'wire_lines': 44, "
              "'controls': 22, 'session_new': 22, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 22, 'maximum_turn_admissions': 22, "
              "'maximum_reportable_terminals': 22, 'case_final_terminals': 22, "
              "'maximum_internal_confirmations': 0}")

NEW_ENVIRONMENT = '''def declared_environment():
    """A read-only batch declares no application state; the foreground guard stays."""

    import ctypes

    seal = read(PANEL / 'SEAL.json')
    declared = seal['declared_environment']
    require(declared['read_only_batch'] is True, 'declared read-only batch changed')
    require(declared['no_application_effect'] is True, 'declared effect scope changed')
    require(declared['no_system_flyout_in_foreground'] is True, 'foreground condition removed')

    user32 = ctypes.windll.user32
    handle = user32.GetForegroundWindow()
    owner = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
    name = ''
    if owner.value:
        try:
            name = psutil.Process(owner.value).name().lower()
        except psutil.Error:
            name = 'unknown'
    require(name not in {'logonui.exe', 'lockapp.exe', 'unknown'},
            f'the session is not an ordinary interactive desktop: {name}')
    return [name]
'''


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("def declared_environment():")
    end = text.index("def preflight(")
    environment_block = text[start:end]
    replacements = [
        ('"""External repair1033 launcher;', '"""External clock1034 launcher;'),
        ("PRIVATE = BASE / 'C03-repair1033-private'", "PRIVATE = BASE / 'C03-clock1034-private'"),
        ("PANEL = BASE / 'C03-repair1033-proposal'", "PANEL = BASE / 'C03-clock1034-proposal'"),
        ("PROFILE = BASE / 'C03-repair1033-profile'", "PROFILE = BASE / 'C03-clock1034-profile'"),
        ("PUBLIC = ROOT / 'artifacts/comprobaciones/C03/REPAIR1033'",
         "PUBLIC = ROOT / 'artifacts/comprobaciones/C03/CLOCK1034'"),
        ("SEAL_SHA = 'c146ea30cd56e01137cab5d16eacceca092f960658e4c33db0487ec3deb18e42'",
         "SEAL_SHA = 'a2aac18ebef111424a5ba98c49965ccce18c6ff09020fe4f376b26a44439bc01'"),
        ("REGISTRY_SEALED_SHA = 'e9622300757b30a26fca21d84fbbde8afc85b5cec73aea1be03c9f600ef10ee3'",
         "REGISTRY_SEALED_SHA = '18c2e349485b0b7c413a10b58e46fa2458a9ff7694589d983009b29508475cfd'"),
        ("'wrong repair1033 panel seal'", "'wrong clock1034 panel seal'"),
        ("seal['schema'] == 'repair1033-directed-material-seal-v1'",
         "seal['schema'] == 'clock1034-directed-material-seal-v1'"),
        ("case_map['schema'] == 'repair1033-case-map-v1'",
         "case_map['schema'] == 'clock1034-case-map-v1'"),
        (f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {OLD_IDS}, 'selected IDs changed')",
         f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {NEW_IDS}, 'selected IDs changed')"),
        (f"require(set(case_map['selected_registry_rows']) == set({OLD_IDS}), 'selected material missing')",
         f"require(set(case_map['selected_registry_rows']) == set({NEW_IDS}), 'selected material missing')"),
        ("== ['H0085', 'H0315', 'H0317', 'H0251', 'H0706'],", "== ['H0180', 'H0499'],"),
        (f"require(seal['counts'] == {OLD_COUNTS}, 'panel counts')",
         f"require(seal['counts'] == {NEW_COUNTS}, 'panel counts')"),
        ("require(len(panel) == len(entries) == 19 and len({case['case_id'] for case in panel}) == 19, 'expected 19 unique cases')",
         "require(len(panel) == len(entries) == 22 and len({case['case_id'] for case in panel}) == 22, 'expected 22 unique cases')"),
        ("require(len(wire) == len(positions) == 38, 'expected 38 wire lines')",
         "require(len(wire) == len(positions) == 44, 'expected 44 wire lines')"),
        ("['historical_literal'] * 8 + ['covered_regression_control'] * 5 "
         "+ ['original_development_variant'] * 4 + ['original_boundary'] * 2",
         "['historical_literal'] * 10 + ['covered_regression_control'] * 2 "
         "+ ['original_development_variant'] * 6 + ['original_boundary'] * 4"),
        ("candidate['schema'] == 'c03-repair1033-root-manifest-v1'",
         "candidate['schema'] == 'c03-clock1034-root-manifest-v1'"),
        ("'case_count': 19, 'limits': LIMITS", "'case_count': 22, 'limits': LIMITS"),
        ("'session': 'one product run; 19 sealed session.new controls each preceding its original turn',",
         "'session': 'one product run; 22 sealed session.new controls each preceding its original turn',"),
        ("'wire_lines': 38, 'turns': 19, 'controls': 19,", "'wire_lines': 44, 'turns': 22, 'controls': 22,"),
        ("if not ok or len(controls) > 19 or len(controls) != len(terminals) + 1:",
         "if not ok or len(controls) > 22 or len(controls) != len(terminals) + 1:"),
        ("if len(turn_admissions) > 19 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:",
         "if len(turn_admissions) > 22 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:"),
        (environment_block, NEW_ENVIRONMENT + "\n\n"),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise SystemExit(f"expected exactly one occurrence of: {old[:90]!r} "
                             f"(found {text.count(old)})")
        text = text.replace(old, new)
    for stale in ("C03-repair1033", "repair1033-directed", "repair1033-case-map",
                  "c03-repair1033-root-manifest"):
        if stale in text:
            raise SystemExit(f"stale reference to {stale} left in the derived runner")
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"runner: {TARGET}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")
    print("placeholders left for root: CLOCK_SEAL, CLOCK_REGISTRY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
