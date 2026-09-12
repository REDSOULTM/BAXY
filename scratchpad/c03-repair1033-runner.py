"""Deriva el runner de REPAIR1033 del de REPAIR1032, sin tocar guardas heredadas.

Cambian rutas, sello, registro, conteos, case_id y los controles cubiertos —ahora cinco, de las dos
salidas—; la comprobación de entorno mantiene la negativa a arrancar con un flyout del sistema en primer
plano y añade Configuración a los destinos que deben empezar cerrados.
"""
from __future__ import annotations

import hashlib
import pathlib

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
SOURCE = BASE / "C03-repair1032-proposal/runner.py"
TARGET = BASE / "C03-repair1033-proposal/runner.py"

OLD_IDS = ("['H0251', 'H0575', 'H0588', 'H0683', 'H0706', 'H0015', 'H0055', 'H0134', 'H0136', "
           "'H0391', 'H0418', 'H0653']")
NEW_IDS = ("['H0015', 'H0055', 'H0134', 'H0136', 'H0391', 'H0418', 'H0653', 'H0575']")

OLD_COUNTS = ("{'cases': 23, 'historical_positive_open': 12, 'covered_regression_controls': 3, "
              "'failed_variant_reexecutions': 0, "
              "'original_development_variants': 5, 'boundaries': 3, 'wire_lines': 46, "
              "'controls': 23, 'session_new': 23, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 23, 'maximum_turn_admissions': 23, "
              "'maximum_reportable_terminals': 23, 'case_final_terminals': 23, "
              "'maximum_internal_confirmations': 0}")
NEW_COUNTS = ("{'cases': 19, 'historical_positive_open': 8, 'covered_regression_controls': 5, "
              "'failed_variant_reexecutions': 0, "
              "'original_development_variants': 4, 'boundaries': 2, 'wire_lines': 38, "
              "'controls': 19, 'session_new': 19, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 19, 'maximum_turn_admissions': 19, "
              "'maximum_reportable_terminals': 19, 'case_final_terminals': 19, "
              "'maximum_internal_confirmations': 0}")

NEW_ENVIRONMENT = '''def declared_environment():
    """The sealed panel declares the desktop it needs. Verify it, never assume it."""

    import ctypes

    running = set()
    for process in psutil.process_iter(['name']):
        running.add((process.info['name'] or '').lower())
    seal = read(PANEL / 'SEAL.json')
    declared = seal['declared_environment']
    require(declared['already_running_before_batch'] == ['chrome', 'Discord', 'steam'],
            'declared environment changed')
    require(declared['not_running_before_batch'] == ['Calculator', 'SystemSettings', 'Paint'],
            'declared fresh targets changed')
    require(declared['no_system_flyout_in_foreground'] is True, 'foreground condition removed')
    require('steam.exe' in running, 'sealed environment says Steam is already running')
    for absent in ('calculatorapp.exe', 'systemsettings.exe', 'mspaint.exe'):
        require(absent not in running, f'sealed environment says {absent} is not running')

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
    # A system flyout keeps the foreground and refuses the handoff; that is what turned every
    # app.open of the invalidated batch into verification_failed with the apps on screen.
    require(name not in {'shellhost.exe', 'logonui.exe', 'lockapp.exe', 'unknown'},
            f'a system window holds the desktop foreground: {name}')
    return sorted(running & {'steam.exe', 'chrome.exe', 'discord.exe'})
'''


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("def declared_environment():")
    end = text.index("def preflight(")
    environment_block = text[start:end]
    replacements = [
        ('"""External repair1032 launcher;', '"""External repair1033 launcher;'),
        ("PRIVATE = BASE / 'C03-repair1032-private'", "PRIVATE = BASE / 'C03-repair1033-private'"),
        ("PANEL = BASE / 'C03-repair1032-proposal'", "PANEL = BASE / 'C03-repair1033-proposal'"),
        ("PROFILE = BASE / 'C03-repair1032-profile'", "PROFILE = BASE / 'C03-repair1033-profile'"),
        ("PUBLIC = ROOT / 'artifacts/comprobaciones/C03/REPAIR1032'",
         "PUBLIC = ROOT / 'artifacts/comprobaciones/C03/REPAIR1033'"),
        ("SEAL_SHA = '63bb65ef633886fefc6e752a36905e539db3ca42a65621d549567f0e0841833a'",
         "SEAL_SHA = 'c146ea30cd56e01137cab5d16eacceca092f960658e4c33db0487ec3deb18e42'"),
        ("REGISTRY_SEALED_SHA = '621640c6adbd8b36669ee46ea6239a8da630c048d80508d7fc7b546605d5b14e'",
         "REGISTRY_SEALED_SHA = 'e9622300757b30a26fca21d84fbbde8afc85b5cec73aea1be03c9f600ef10ee3'"),
        ("'wrong repair1032 panel seal'", "'wrong repair1033 panel seal'"),
        ("seal['schema'] == 'repair1032-directed-material-seal-v1'",
         "seal['schema'] == 'repair1033-directed-material-seal-v1'"),
        ("case_map['schema'] == 'repair1032-case-map-v1'",
         "case_map['schema'] == 'repair1033-case-map-v1'"),
        (f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {OLD_IDS}, 'selected IDs changed')",
         f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {NEW_IDS}, 'selected IDs changed')"),
        (f"require(set(case_map['selected_registry_rows']) == set({OLD_IDS}), 'selected material missing')",
         f"require(set(case_map['selected_registry_rows']) == set({NEW_IDS}), 'selected material missing')"),
        ("== ['H0085', 'H0315', 'H0317'],",
         "== ['H0085', 'H0315', 'H0317', 'H0251', 'H0706'],"),
        (f"require(seal['counts'] == {OLD_COUNTS}, 'panel counts')",
         f"require(seal['counts'] == {NEW_COUNTS}, 'panel counts')"),
        ("require(len(panel) == len(entries) == 23 and len({case['case_id'] for case in panel}) == 23, 'expected 23 unique cases')",
         "require(len(panel) == len(entries) == 19 and len({case['case_id'] for case in panel}) == 19, 'expected 19 unique cases')"),
        ("require(len(wire) == len(positions) == 46, 'expected 46 wire lines')",
         "require(len(wire) == len(positions) == 38, 'expected 38 wire lines')"),
        ("['historical_literal'] * 12 + ['covered_regression_control'] * 3 "
         "+ ['original_development_variant'] * 5 + ['original_boundary'] * 3",
         "['historical_literal'] * 8 + ['covered_regression_control'] * 5 "
         "+ ['original_development_variant'] * 4 + ['original_boundary'] * 2"),
        ("candidate['schema'] == 'c03-repair1032-root-manifest-v1'",
         "candidate['schema'] == 'c03-repair1033-root-manifest-v1'"),
        ("'case_count': 23, 'limits': LIMITS", "'case_count': 19, 'limits': LIMITS"),
        ("'session': 'one product run; 23 sealed session.new controls each preceding its original turn',",
         "'session': 'one product run; 19 sealed session.new controls each preceding its original turn',"),
        ("'wire_lines': 46, 'turns': 23, 'controls': 23,", "'wire_lines': 38, 'turns': 19, 'controls': 19,"),
        ("if not ok or len(controls) > 23 or len(controls) != len(terminals) + 1:",
         "if not ok or len(controls) > 19 or len(controls) != len(terminals) + 1:"),
        ("if len(turn_admissions) > 23 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:",
         "if len(turn_admissions) > 19 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:"),
        (environment_block, NEW_ENVIRONMENT + "\n\n"),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise SystemExit(f"expected exactly one occurrence of: {old[:90]!r} "
                             f"(found {text.count(old)})")
        text = text.replace(old, new)
    for stale in ("C03-repair1032", "repair1032-directed", "repair1032-case-map",
                  "c03-repair1032-root-manifest"):
        if stale in text:
            raise SystemExit(f"stale reference to {stale} left in the derived runner")
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"runner: {TARGET}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
