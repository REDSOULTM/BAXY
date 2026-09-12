"""Deriva el runner de REPAIR1030 del de APPS1029, sin tocar sus guardas.

Cambian rutas, sello, conteos y case_id. Añade lo propio de esta tanda: los tres controles de no
regresión son filas **cubiertas**, así que el runner exige que sigan cubiertas y que no estén entre las
seleccionadas para crédito, y el entorno declarado cambia (Paint no en ejecución, Steam sí).
"""
from __future__ import annotations

import hashlib
import pathlib

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
SOURCE = BASE / "C03-apps1029-proposal/runner.py"
TARGET = BASE / "C03-repair1030-proposal/runner.py"

OLD_IDS = ("['H0251', 'H0497', 'H0575', 'H0588', 'H0683', 'H0085', 'H0706', 'H0015', 'H0055', "
           "'H0134', 'H0136', 'H0315', 'H0317', 'H0391', 'H0418', 'H0544', 'H0653']")
NEW_IDS = "['H0015', 'H0055', 'H0134', 'H0136', 'H0391', 'H0418', 'H0653']"

OLD_COUNTS = ("{'cases': 27, 'historical_positive_open': 17, 'failed_variant_reexecutions': 0, "
              "'original_development_variants': 5, 'boundaries': 5, 'wire_lines': 54, "
              "'controls': 27, 'session_new': 27, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 27, 'maximum_turn_admissions': 27, "
              "'maximum_reportable_terminals': 27, 'case_final_terminals': 27, "
              "'maximum_internal_confirmations': 0}")
NEW_COUNTS = ("{'cases': 17, 'historical_positive_open': 7, 'covered_regression_controls': 3, "
              "'failed_variant_reexecutions': 0, "
              "'original_development_variants': 4, 'boundaries': 3, 'wire_lines': 34, "
              "'controls': 17, 'session_new': 17, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 17, 'maximum_turn_admissions': 17, "
              "'maximum_reportable_terminals': 17, 'case_final_terminals': 17, "
              "'maximum_internal_confirmations': 0}")

NEW_ENVIRONMENT = '''def declared_environment():
    """The sealed panel declares which targets were already running. Verify it, do not assume it."""

    running = set()
    for process in psutil.process_iter(['name']):
        running.add((process.info['name'] or '').lower())
    seal = read(PANEL / 'SEAL.json')
    declared = seal['declared_environment']
    require(declared['already_running_before_batch'] == ['chrome', 'Discord', 'steam'],
            'declared environment changed')
    require(declared['not_running_before_batch'] == ['Paint'], 'declared fresh targets changed')
    require('steam.exe' in running, 'sealed environment says Steam is already running')
    require('mspaint.exe' not in running, 'sealed environment says Paint is not running')
    return sorted(running & {'steam.exe', 'chrome.exe', 'discord.exe'})
'''

CONTROL_CHECK = """    controls_declared = case_map['regression_control_case_ids']
    require(controls_declared == seal['regression_control_case_ids'] == ['H0085', 'H0315', 'H0317'],
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


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    # El bloque de entorno declarado se sustituye entero, no se parchea por líneas.
    start = text.index("def declared_environment():")
    end = text.index("def preflight(")
    environment_block = text[start:end]
    replacements = [
        ('"""External apps1029 launcher;', '"""External repair1030 launcher;'),
        ("PRIVATE = BASE / 'C03-apps1029-private'", "PRIVATE = BASE / 'C03-repair1030-private'"),
        ("PANEL = BASE / 'C03-apps1029-proposal'", "PANEL = BASE / 'C03-repair1030-proposal'"),
        ("PROFILE = BASE / 'C03-apps1029-profile'", "PROFILE = BASE / 'C03-repair1030-profile'"),
        ("PUBLIC = ROOT / 'artifacts/comprobaciones/C03/APPS1029'",
         "PUBLIC = ROOT / 'artifacts/comprobaciones/C03/REPAIR1030'"),
        ("SEAL_SHA = '652a0a409637f7fa15cb589786d37f3cc51a075d605912e17d32fee52825553b'",
         "SEAL_SHA = 'b206137d30efc43be04f2f63aece0a74b0ce1387acfb798bd15f887e8d8a057b'"),
        ("REGISTRY_SEALED_SHA = 'af5ccd83c2e6d567a9631b540f76fde011670fe9aba2de8f4777cb7cb3a0dccd'",
         "REGISTRY_SEALED_SHA = '3a5593f9948eb8ab260ce015750d4d801b0b2e288bfc03e0889ee62c4eb73f73'"),
        ("'wrong apps1029 panel seal'", "'wrong repair1030 panel seal'"),
        ("seal['schema'] == 'apps1029-directed-material-seal-v1'",
         "seal['schema'] == 'repair1030-directed-material-seal-v1'"),
        ("case_map['schema'] == 'apps1029-case-map-v1'",
         "case_map['schema'] == 'repair1030-case-map-v1'"),
        (f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {OLD_IDS}, 'selected IDs changed')",
         f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {NEW_IDS}, 'selected IDs changed')"),
        (f"require(set(case_map['selected_registry_rows']) == set({OLD_IDS}), 'selected material missing')",
         f"require(set(case_map['selected_registry_rows']) == set({NEW_IDS}), 'selected material missing')\n"
         + CONTROL_CHECK.rstrip("\n")),
        (f"require(seal['counts'] == {OLD_COUNTS}, 'panel counts')",
         f"require(seal['counts'] == {NEW_COUNTS}, 'panel counts')"),
        ("require(len(panel) == len(entries) == 27 and len({case['case_id'] for case in panel}) == 27, 'expected 27 unique cases')",
         "require(len(panel) == len(entries) == 17 and len({case['case_id'] for case in panel}) == 17, 'expected 17 unique cases')"),
        ("require(len(wire) == len(positions) == 54, 'expected 54 wire lines')",
         "require(len(wire) == len(positions) == 34, 'expected 34 wire lines')"),
        ("['historical_literal'] * 17 + ['original_development_variant'] * 5 + ['original_boundary'] * 5",
         "['historical_literal'] * 7 + ['covered_regression_control'] * 3 "
         "+ ['original_development_variant'] * 4 + ['original_boundary'] * 3"),
        ("candidate['schema'] == 'c03-apps1029-root-manifest-v1'",
         "candidate['schema'] == 'c03-repair1030-root-manifest-v1'"),
        ("'case_count': 27, 'limits': LIMITS", "'case_count': 17, 'limits': LIMITS"),
        ("'session': 'one product run; 27 sealed session.new controls each preceding its original turn',",
         "'session': 'one product run; 17 sealed session.new controls each preceding its original turn',"),
        ("'wire_lines': 54, 'turns': 27, 'controls': 27,", "'wire_lines': 34, 'turns': 17, 'controls': 17,"),
        ("if not ok or len(controls) > 27 or len(controls) != len(terminals) + 1:",
         "if not ok or len(controls) > 17 or len(controls) != len(terminals) + 1:"),
        ("if len(turn_admissions) > 27 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:",
         "if len(turn_admissions) > 17 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:"),
        (environment_block, NEW_ENVIRONMENT + "\n\n"),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise SystemExit(f"expected exactly one occurrence of: {old[:90]!r} "
                             f"(found {text.count(old)})")
        text = text.replace(old, new)
    for stale in ("apps1029", "APPS1029", "H0251", "H0706"):
        if stale in text:
            raise SystemExit(f"stale reference to {stale} left in the derived runner")
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"runner: {TARGET}\nsha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}\n"
          f"lines: {len(text.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
