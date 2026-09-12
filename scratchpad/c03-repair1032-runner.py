"""Deriva el runner de REPAIR1032 del de REPAIR1031, sin tocar guardas heredadas.

Cambia rutas, sello, conteos y case_id, y endurece la comprobación de entorno con lo que invalidó
REPAIR1031: el runner se niega a arrancar si una ventana del sistema —ShellHost.exe— tiene el primer
plano, y exige que los destinos de lanzamiento no estén ya en ejecución.
"""
from __future__ import annotations

import hashlib
import pathlib

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
SOURCE = BASE / "C03-repair1031-proposal/runner.py"
TARGET = BASE / "C03-repair1032-proposal/runner.py"

OLD_IDS = "['H0015', 'H0055', 'H0134', 'H0136', 'H0391', 'H0418', 'H0653']"
NEW_IDS = ("['H0251', 'H0575', 'H0588', 'H0683', 'H0706', 'H0015', 'H0055', 'H0134', 'H0136', "
           "'H0391', 'H0418', 'H0653']")

OLD_COUNTS = ("{'cases': 17, 'historical_positive_open': 7, 'covered_regression_controls': 3, "
              "'failed_variant_reexecutions': 0, "
              "'original_development_variants': 4, 'boundaries': 3, 'wire_lines': 34, "
              "'controls': 17, 'session_new': 17, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 17, 'maximum_turn_admissions': 17, "
              "'maximum_reportable_terminals': 17, 'case_final_terminals': 17, "
              "'maximum_internal_confirmations': 0}")
NEW_COUNTS = ("{'cases': 23, 'historical_positive_open': 12, 'covered_regression_controls': 3, "
              "'failed_variant_reexecutions': 0, "
              "'original_development_variants': 5, 'boundaries': 3, 'wire_lines': 46, "
              "'controls': 23, 'session_new': 23, 'conditional_positive_commands': 0, "
              "'normal_diagnostic_commands': 23, 'maximum_turn_admissions': 23, "
              "'maximum_reportable_terminals': 23, 'case_final_terminals': 23, "
              "'maximum_internal_confirmations': 0}")

NEW_ENVIRONMENT = '''def declared_environment():
    """The sealed panel declares the desktop it needs. Verify it; REPAIR1031 died for not doing so."""

    import ctypes

    running = set()
    for process in psutil.process_iter(['name']):
        running.add((process.info['name'] or '').lower())
    seal = read(PANEL / 'SEAL.json')
    declared = seal['declared_environment']
    require(declared['already_running_before_batch'] == ['chrome', 'Discord', 'steam'],
            'declared environment changed')
    require(declared['not_running_before_batch'] == ['Calculator', 'SystemSettings', 'Paint', 'charmap'],
            'declared fresh targets changed')
    require(declared['no_system_flyout_in_foreground'] is True, 'foreground condition removed')
    require('steam.exe' in running, 'sealed environment says Steam is already running')
    for absent in ('calculatorapp.exe', 'systemsettings.exe', 'mspaint.exe', 'charmap.exe'):
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
    # app.open of REPAIR1031 into verification_failed with the apps visible on screen.
    require(name not in {'shellhost.exe', 'logonui.exe', 'lockapp.exe', 'unknown'},
            f'a system window holds the desktop foreground: {name}')
    return sorted(running & {'steam.exe', 'chrome.exe', 'discord.exe'})
'''

CONTROL_OLD = "== ['H0085', 'H0315', 'H0317'],"
CONTROL_NEW = "== ['H0085', 'H0315', 'H0317'],"


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("def declared_environment():")
    end = text.index("def preflight(")
    environment_block = text[start:end]
    replacements = [
        ('"""External repair1031 launcher;', '"""External repair1032 launcher;'),
        ("PRIVATE = BASE / 'C03-repair1031-private'", "PRIVATE = BASE / 'C03-repair1032-private'"),
        ("PANEL = BASE / 'C03-repair1031-proposal'", "PANEL = BASE / 'C03-repair1032-proposal'"),
        ("PROFILE = BASE / 'C03-repair1031-profile'", "PROFILE = BASE / 'C03-repair1032-profile'"),
        ("PUBLIC = ROOT / 'artifacts/comprobaciones/C03/REPAIR1031'",
         "PUBLIC = ROOT / 'artifacts/comprobaciones/C03/REPAIR1032'"),
        ("SEAL_SHA = 'a84fc0b050881939f9d6f1565065e80c48a8e34a24c0816fc79449f8fa970251'",
         "SEAL_SHA = '63bb65ef633886fefc6e752a36905e539db3ca42a65621d549567f0e0841833a'"),
        ("REGISTRY_SEALED_SHA = '1d8bc7f935243f5fd8e2e35397b517da98416133a37125a1222873825bf9f879'",
         "REGISTRY_SEALED_SHA = '621640c6adbd8b36669ee46ea6239a8da630c048d80508d7fc7b546605d5b14e'"),
        ("'wrong repair1031 panel seal'", "'wrong repair1032 panel seal'"),
        ("seal['schema'] == 'repair1031-directed-material-seal-v1'",
         "seal['schema'] == 'repair1032-directed-material-seal-v1'"),
        ("case_map['schema'] == 'repair1031-case-map-v1'",
         "case_map['schema'] == 'repair1032-case-map-v1'"),
        (f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {OLD_IDS}, 'selected IDs changed')",
         f"require(case_map['historical_case_ids'] == seal['historical_case_ids'] == {NEW_IDS}, 'selected IDs changed')"),
        (f"require(set(case_map['selected_registry_rows']) == set({OLD_IDS}), 'selected material missing')",
         f"require(set(case_map['selected_registry_rows']) == set({NEW_IDS}), 'selected material missing')"),
        (f"require(seal['counts'] == {OLD_COUNTS}, 'panel counts')",
         f"require(seal['counts'] == {NEW_COUNTS}, 'panel counts')"),
        ("require(len(panel) == len(entries) == 17 and len({case['case_id'] for case in panel}) == 17, 'expected 17 unique cases')",
         "require(len(panel) == len(entries) == 23 and len({case['case_id'] for case in panel}) == 23, 'expected 23 unique cases')"),
        ("require(len(wire) == len(positions) == 34, 'expected 34 wire lines')",
         "require(len(wire) == len(positions) == 46, 'expected 46 wire lines')"),
        ("['historical_literal'] * 7 + ['covered_regression_control'] * 3 "
         "+ ['original_development_variant'] * 4 + ['original_boundary'] * 3",
         "['historical_literal'] * 12 + ['covered_regression_control'] * 3 "
         "+ ['original_development_variant'] * 5 + ['original_boundary'] * 3"),
        ("candidate['schema'] == 'c03-repair1031-root-manifest-v1'",
         "candidate['schema'] == 'c03-repair1032-root-manifest-v1'"),
        ("'case_count': 17, 'limits': LIMITS", "'case_count': 23, 'limits': LIMITS"),
        ("'session': 'one product run; 17 sealed session.new controls each preceding its original turn',",
         "'session': 'one product run; 23 sealed session.new controls each preceding its original turn',"),
        ("'wire_lines': 34, 'turns': 17, 'controls': 17,", "'wire_lines': 46, 'turns': 23, 'controls': 23,"),
        ("if not ok or len(controls) > 17 or len(controls) != len(terminals) + 1:",
         "if not ok or len(controls) > 23 or len(controls) != len(terminals) + 1:"),
        ("if len(turn_admissions) > 17 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:",
         "if len(turn_admissions) > 23 or len(controls) != len(turn_admissions) or not controls[-1]['ok']:"),
        (environment_block, NEW_ENVIRONMENT + "\n\n"),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise SystemExit(f"expected exactly one occurrence of: {old[:90]!r} "
                             f"(found {text.count(old)})")
        text = text.replace(old, new)
    # Sólo cuentan como restos las rutas y los esquemas de la tanda anterior; nombrarla en un
    # comentario es memoria, no confusión de material.
    for stale in ("C03-repair1031", "repair1031-directed", "repair1031-case-map",
                  "c03-repair1031-root-manifest"):
        if stale in text:
            raise SystemExit(f"stale reference to {stale} left in the derived runner")
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"runner: {TARGET}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")
    print("placeholders left for root: SEAL1032, REGISTRY1032")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
