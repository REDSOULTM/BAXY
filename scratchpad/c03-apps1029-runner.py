"""Deriva el runner de APPS1029 del runner heredado de SYSTEM1028, sin tocar sus guardas.

La ley es heredar primero. El runner de 1028 ya trae la vinculación de candidato, los pines de fuente,
binarios y runtime, los muestreadores y la política de parada; lo que cambia en 1029 son las rutas, el
sello, los conteos y los case_id. Este script hace exactamente esas sustituciones, falla si alguna no
aparece —así una guarda no desaparece por un reemplazo silencioso— y añade la comprobación del entorno
declarado (Steam en ejecución, Calculator/Paint/Terminal no) que el panel sella.
"""
from __future__ import annotations

import hashlib
import pathlib

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
SOURCE = BASE / "C03-system1028-proposal/runner.py"
TARGET = BASE / "C03-apps1029-proposal/runner.py"

OLD_IDS = ("['H0532', 'H0539', 'H0655', 'H0146', 'H0442', 'H0219', 'H0607', 'H0508', 'H0076', "
           "'H0037', 'H0114', 'H0106', 'H0589', 'H0422']")
NEW_IDS = ("['H0251', 'H0497', 'H0575', 'H0588', 'H0683', 'H0085', 'H0706', 'H0015', 'H0055', "
           "'H0134', 'H0136', 'H0315', 'H0317', 'H0391', 'H0418', 'H0544', 'H0653']")

OLD_COUNTS = ("{'cases': 31, 'historical_positive_open': 14, 'failed_variant_reexecutions': 0, "
              "'original_development_variants': 12, 'boundaries': 5, 'wire_lines': 62, "
              "'controls': 31, 'session_new': 31, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 31, 'maximum_turn_admissions': 31, "
              "'maximum_reportable_terminals': 31, 'case_final_terminals': 31, "
              "'maximum_internal_confirmations': 0}")
NEW_COUNTS = ("{'cases': 27, 'historical_positive_open': 17, 'failed_variant_reexecutions': 0, "
              "'original_development_variants': 5, 'boundaries': 5, 'wire_lines': 54, "
              "'controls': 27, 'session_new': 27, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 27, 'maximum_turn_admissions': 27, "
              "'maximum_reportable_terminals': 27, 'case_final_terminals': 27, "
              "'maximum_internal_confirmations': 0}")

ENVIRONMENT_CHECK = '''
def declared_environment():
    """The sealed panel declares which targets were already running. Verify it, do not assume it."""

    running = set()
    for process in psutil.process_iter(['name']):
        running.add((process.info['name'] or '').lower())
    seal = read(PANEL / 'SEAL.json')
    declared = seal['declared_environment']
    require(declared['already_running_before_batch'] == ['chrome', 'Discord', 'steam',
            'SystemSettings', 'Notepad'], 'declared environment changed')
    require(declared['not_running_before_batch'] == ['Calculator', 'Paint', 'Windows Terminal'],
            'declared fresh targets changed')
    require('steam.exe' in running, 'sealed environment says Steam is already running')
    for absent in ('calculatorapp.exe', 'mspaint.exe', 'windowsterminal.exe'):
        require(absent not in running, f'sealed environment says {absent} is not running')
    return sorted(running & {'steam.exe', 'chrome.exe', 'discord.exe', 'systemsettings.exe',
                             'notepad.exe'})


'''

REPLACEMENTS = [
    ('"""External system1028 launcher; explicit preparation and measured run, never adjudication.',
     '"""External apps1029 launcher; explicit preparation and measured run, never adjudication.'),
    ("PRIVATE = BASE / 'C03-system1028-private'", "PRIVATE = BASE / 'C03-apps1029-private'"),
    ("PANEL = BASE / 'C03-system1028-proposal'", "PANEL = BASE / 'C03-apps1029-proposal'"),
    ("PROFILE = BASE / 'C03-system1028-profile'", "PROFILE = BASE / 'C03-apps1029-profile'"),
    ("PUBLIC = ROOT / 'artifacts/comprobaciones/C03/SYSTEM1028'",
     "PUBLIC = ROOT / 'artifacts/comprobaciones/C03/APPS1029'"),
    ("SEAL_SHA = 'eedb26881bdbf657992b43f869483a4a887e44805d700b4f9331b97e46fdda6f'",
     "SEAL_SHA = '652a0a409637f7fa15cb589786d37f3cc51a075d605912e17d32fee52825553b'"),
    ("REGISTRY_SEALED_SHA = '113e3b30a59395910996b7f4e4b31bb59f46a3276e68e2fda20024f52aa825cd'",
     "REGISTRY_SEALED_SHA = 'af5ccd83c2e6d567a9631b540f76fde011670fe9aba2de8f4777cb7cb3a0dccd'"),
    ("'wrong system1028 panel seal'", "'wrong apps1029 panel seal'"),
    ("seal['schema'] == 'system1028-directed-material-seal-v1'",
     "seal['schema'] == 'apps1029-directed-material-seal-v1'"),
    ("case_map['schema'] == 'system1028-case-map-v1'", "case_map['schema'] == 'apps1029-case-map-v1'"),
    (f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {OLD_IDS}, 'selected IDs changed')",
     f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {NEW_IDS}, 'selected IDs changed')"),
    (f"require(set(case_map['selected_registry_rows']) == set({OLD_IDS}), 'selected material missing')",
     f"require(set(case_map['selected_registry_rows']) == set({NEW_IDS}), 'selected material missing')"),
    (f"require(seal['counts'] == {OLD_COUNTS}, 'panel counts')",
     f"require(seal['counts'] == {NEW_COUNTS}, 'panel counts')"),
    ("require(len(panel) == len(entries) == 31 and len({case['case_id'] for case in panel}) == 31, 'expected 31 unique cases')",
     "require(len(panel) == len(entries) == 27 and len({case['case_id'] for case in panel}) == 27, 'expected 27 unique cases')"),
    ("require(len(wire) == len(positions) == 62, 'expected 62 wire lines')",
     "require(len(wire) == len(positions) == 54, 'expected 54 wire lines')"),
    ("['historical_literal'] * 14 + ['original_development_variant'] * 12 + ['original_boundary'] * 5",
     "['historical_literal'] * 17 + ['original_development_variant'] * 5 + ['original_boundary'] * 5"),
    ("candidate['schema'] == 'c03-system1028-root-manifest-v1'",
     "candidate['schema'] == 'c03-apps1029-root-manifest-v1'"),
    ("'case_count': 31, 'limits': LIMITS", "'case_count': 27, 'limits': LIMITS"),
    ("'session': 'one product run; 31 sealed session.new controls each preceding its original turn',",
     "'session': 'one product run; 27 sealed session.new controls each preceding its original turn',"),
    ("'wire_lines': 62, 'turns': 31, 'controls': 31,", "'wire_lines': 54, 'turns': 27, 'controls': 27,"),
    ("if not ok or len(controls) > 31 or len(controls) != len(terminals) + 1:",
     "if not ok or len(controls) > 27 or len(controls) != len(terminals) + 1:"),
    ("if len(turn_admissions) > 31 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:",
     "if len(turn_admissions) > 27 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:"),
    # The declared environment is part of the seal, so the runner verifies it in preflight.
    ("def preflight(seal_sha, expected_head, candidate_path, candidate_sha):",
     ENVIRONMENT_CHECK.lstrip("\n") + "def preflight(seal_sha, expected_head, candidate_path, candidate_sha):"),
    ("    require(check_pins(seal['read_source_pins']), 'historical panel evidence changed')",
     "    require(check_pins(seal['read_source_pins']), 'historical panel evidence changed')\n"
     "    declared_environment()"),
]


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if text.count(old) != 1:
            raise SystemExit(f"expected exactly one occurrence of: {old[:90]!r} "
                             f"(found {text.count(old)})")
        text = text.replace(old, new)
    for stale in ("system1028", "SYSTEM1028", "H0532", "H0442"):
        if stale in text:
            raise SystemExit(f"stale reference to {stale} left in the derived runner")
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    print(f"runner: {TARGET}\nsha256: {digest}\nlines: {len(text.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
