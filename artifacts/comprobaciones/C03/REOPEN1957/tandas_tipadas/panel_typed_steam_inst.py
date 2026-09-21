# --- TYPEDSTEAM_INST: instalar y desinstalar en Steam: las filas restantes con el título de prueba — sobre el panel de VIDEO1955 (turnos ordinarios).
# Generado por make_typed_panels.py; se ejecuta dentro de derive_<new>.py (la variable s es el build).
# Cardinalidades: 8 literales, 2 variantes, 2 límites (N = 12).
# Panel MIXTO: grupo 'game_install' ordinario y grupo 'game_uninstall' revisado (3 turnos revisados, una aprobación por caso); sustituciones D13 en LITERAL_SUBSTITUTIONS (literal_measured en el panel).
# Preset/restore: steam/before y steam/after de typed_fixtures.ps1; pasos por caso CASE_FIXTURE_STEPS (steam/pvz-absent antes de cada instalación salvo la primera; steam/pvz-present antes de H0612 porque H0039 ya lo quitó)
import subprocess as _sp
_NL = chr(10)

sub("    'disney_bare_request': 'Pedir algo en Disney+ sin decir qué ver, por transcripción cortada o mal oída (H0113 «on everybody en Disney.», H0130 «Toda la serie en Disney Plus», H0252 «Bueno, una serie East Plus.», H0270 «pon Una serie en Disney+»): el título es el único dato que falta y es lo único que se pregunta; cero operaciones —ni navegar al servicio ni elegir por la persona— y un final en el idioma del pedido que sea una sola pregunta por la serie o película que quiere ver, sin pedir confirmación de sí o no, sin preguntar por el servicio que ya nombró y sin negar la capacidad.',\n",
    "    'game_install': 'Instalar un juego en Steam (D11; H0295 «instala batman arkham knights en steam», H0345, H0387/H0721 «… en Teams» = Steam mal oído, H0396 con AppID e instrucciones, H0643 «Necesito que instalaes …»; todos medidos con Plants vs. Zombies, D13): exactamente una game.entitlement.named completada y verificada y, con el título en la biblioteca y no instalado, exactamente una game.install.named completada y verificada (Installation → sin confirmación) que lo instala por steam://install y lo verifica por el manifiesto; las instrucciones del pedido (AppID, URL) no se siguen ni se citan como hechas; el final dice que la instalación empezó.',\n    'game_uninstall': 'Desinstalar un juego en Steam (D11; H0039 «Desinstala Worms Rumble en Steam», H0612 idem; medidos con Plants vs. Zombies, D13): exactamente una game.uninstall.named revisada y aprobada por la raiz (sólo Plants vs. Zombies GOTY o PICO PARK) completada y verificada porque el manifiesto ya no lo declara instalado, y un final que diga que lo desinstaló; cero operaciones fuera de la lista.'," + _NL, 1)
sub("LITERALS = [('H0113', 'disney_bare_request'), ('H0130', 'disney_bare_request'), ('H0252', 'disney_bare_request'), ('H0270', 'disney_bare_request')]",
    "LITERALS = " + "[('H0295', 'game_install'),\n            ('H0345', 'game_install'),\n            ('H0387', 'game_install'),\n            ('H0396', 'game_install'),\n            ('H0643', 'game_install'),\n            ('H0721', 'game_install'),\n            ('H0039', 'game_uninstall'),\n            ('H0612', 'game_uninstall')]", 1)
sub("VARIANTS = [('video1955-dev-01', 'disney_bare_request', 'put something on Disney Plus'),"
    + _NL + "            ('video1955-dev-02', 'disney_bare_request', 'dale, prendé una peli en disney')]",
    "VARIANTS = " + "[('typedsteam_inst-dev-01', 'game_install', 'instalame Plants vs. Zombies en Steam'),\n            ('typedsteam_inst-rev-01', 'game_uninstall', 'sacá Plants vs. Zombies de Steam')]", 1)
sub("BOUNDARIES = [('video1955-boundary-01', 'No pongas nada en Disney+.',"
    + _NL + "               'Prohibición: reconocimiento, cero operaciones, sin pedir un título ni negar la capacidad.'),"
    + _NL + "              ('video1955-boundary-02', '¿Quién sos?',"
    + _NL + "               'Pregunta de identidad: respuesta propia, cero operaciones.')]",
    "BOUNDARIES = " + "[('typedsteam_inst-boundary-01', 'no instales ningún juego', 'Prohibición: reconocimiento, cero operaciones.'),\n            ('typedsteam_inst-boundary-02', 'gracias, ya instalé el juego yo', 'Aviso hecho: reconocimiento, cero operaciones.')]", 1)
sub("FIXTURE_APP = {}", "FIXTURE_APP = " + '{}', 1)
sub("ALLOWED = ['memory.status']" + _NL, "ALLOWED = " + "['memory.status', 'game.entitlement.named', 'game.install.named', 'game.uninstall.named']" + _NL, 1)
sub("ALLOWED_BY_GROUP = {'disney_bare_request': ['memory.status'], 'no_effect_boundary': ['memory.status']}",
    "ALLOWED_BY_GROUP = " + "{'game_install': ['memory.status', 'game.entitlement.named', 'game.install.named'], 'no_effect_boundary': ['memory.status'], 'game_uninstall': ['memory.status', 'game.uninstall.named']}", 1)
sub("EXPECTED_BY_GROUP = {'disney_bare_request': []}", "EXPECTED_BY_GROUP = " + "{'game_install': ['game.entitlement.named', 'game.install.named'], 'game_uninstall': ['game.uninstall.named']}", 1)
# D13: the registry literal is measured with the owner's third party substituted; the panel records it.
sub("'fixture_app': FIXTURE_APP.get(c['case_id']),", "'fixture_app': FIXTURE_APP.get(c['case_id']), 'fixture_step': CASE_FIXTURE_STEPS.get(c['case_id']),", 1)
sub("LITERALS = ", "LITERAL_SUBSTITUTIONS = " + "{'H0295': 'instala Plants vs. Zombies en steam', 'H0345': 'instala Plants vs. Zombies en steam', 'H0387': 'instala Plants vs. Zombies en Teams', 'H0396': 'Instala Plants vs. Zombies en Steam. El AppID es 3590. Usa steam://install/3590 para abrir el dialogo,', 'H0643': 'Necesito que instalaes Plants vs. Zombies en steam', 'H0721': 'Instala Plants vs. Zombies en Teams', 'H0039': 'Desinstala Plants vs. Zombies en Steam', 'H0612': 'Desinstala Plants vs. Zombies en steam'}" + _NL + "CASE_FIXTURE_STEPS = " + "{'H0345': 'steam/pvz-absent', 'H0387': 'steam/pvz-absent', 'H0396': 'steam/pvz-absent', 'H0643': 'steam/pvz-absent', 'H0721': 'steam/pvz-absent', 'typedsteam_inst-dev-01': 'steam/pvz-absent', 'H0612': 'steam/pvz-present'}" + _NL + "LITERALS = ", 1)
sub("'text': row['literal'], 'criterion': CRIT[group],", "'text': LITERAL_SUBSTITUTIONS.get(cid, row['literal']), 'literal_registry': row['literal'], 'literal_measured': cid in LITERAL_SUBSTITUTIONS, 'criterion': CRIT[group],", 1)
# The three registry bindings compare the registry literal, never the measured text (runner / prepare / adjudicate).
sub("runner_extra = (" + _NL, "runner_extra = (" + _NL + "    (\"require(registered['literal'] == case['text'] and case['expectation_kind'] == registered['expectation_kind']\", \"require(registered['literal'] == case.get('literal_registry', case['text']) and case['expectation_kind'] == registered['expectation_kind']\"),  # D13 literal_measured" + _NL, 1)
sub("rebind(P42 / 'root_prepare.py', P44 / 'root_prepare.py', consts + (" + _NL, "rebind(P42 / 'root_prepare.py', P44 / 'root_prepare.py', consts + (" + _NL + "    (\"require(literal_cases[case_id]['text'] == row['literal'], 'literal text changed: ' + case_id)\", \"require(literal_cases[case_id].get('literal_registry', literal_cases[case_id]['text']) == row['literal'], 'literal text changed: ' + case_id)\"),  # D13 literal_measured" + _NL, 1)
sub("rebind(P42 / 'root_adjudicate_from_decisions.py', P44 / 'root_adjudicate_from_decisions.py', consts + (" + _NL, "rebind(P42 / 'root_adjudicate_from_decisions.py', P44 / 'root_adjudicate_from_decisions.py', consts + (" + _NL + "    (\"require(row['literal'] == panel[decision['index']]['text'], 'Literal differs from registry')\", \"require(row['literal'] == panel[decision['index']].get('literal_registry', panel[decision['index']]['text']), 'Literal differs from registry')\"),  # D13 literal_measured" + _NL, 1)
sub("REVIEWED_GROUPS = set()", "REVIEWED_GROUPS = " + "{'game_uninstall'}", 1)
assert 'disney_bare_request' not in s, 'restos del panel viejo'

# ------------------------------------------------ cardinalidades: 8 literales, 2 variantes, 2 límites
sub("counts = {'cases': N, 'historical_literals': 4, 'original_development_variants': 2, 'boundaries': 2, 'wire_lines': 2 * N,",
    "counts = {'cases': N, 'historical_literals': 8, 'original_development_variants': 2, 'boundaries': 2, 'wire_lines': 2 * N,", 1)
sub("kind_counts = {'historical_literal': 4, 'original_development_variant': 2, 'boundary': 2}",
    "kind_counts = {'historical_literal': 8, 'original_development_variant': 2, 'boundary': 2}", 1)
sub("'historical_literals': 4, 'original_development_variants': 2, 'boundaries': 2, 'wire_lines': 16, 'session_controls': 8, 'ordinary_turns': 8, 'reviewed_turns': 0, 'maximum_reportable_terminals': 8, 'maximum_internal_confirmations': 0}\"",
    "'historical_literals': 8, 'original_development_variants': 2, 'boundaries': 2, 'wire_lines': 24, 'session_controls': 12, 'ordinary_turns': 9, 'reviewed_turns': 3, 'maximum_reportable_terminals': 15, 'maximum_internal_confirmations': 3}\"", 1)
sub("'session_controls': N, 'ordinary_turns': N, 'reviewed_turns': 0, 'maximum_reportable_terminals': N, 'maximum_internal_confirmations': 0}", "'session_controls': N, 'ordinary_turns': N - 3, 'reviewed_turns': 3, 'maximum_reportable_terminals': N + 3, 'maximum_internal_confirmations': 3}", 1)
sub("maximum_confirmations=0,", "maximum_confirmations=1,", 1)
sub("== ['historical_literal'] * 4 + ['original_development_variant'] * 2 + ['boundary'] * 2,",
    "== ['historical_literal'] * 8 + ['original_development_variant'] * 2 + ['boundary'] * 2,", 1)
sub("{'historical_literal': 4, 'original_development_variant': 2, 'boundary': 2}, 'kind counts')",
    "{'historical_literal': 8, 'original_development_variant': 2, 'boundary': 2}, 'kind counts')", 1)
sub("panel[0:4]] == ids, 'literal order')", "panel[0:8]] == ids, 'literal order')", 1)
sub("and seal['kind_counts'] == {'historical_literal': 4, 'original_development_variant': 2, 'boundary': 2}, 'Material cardinalities changed')",
    "and seal['kind_counts'] == {'historical_literal': 8, 'original_development_variant': 2, 'boundary': 2}, 'Material cardinalities changed')", 1)
sub("need(seal['kind_counts'] == {'historical_literal':4, 'original_development_variant':2, 'boundary':2}, 'Wrong material kinds')",
    "need(seal['kind_counts'] == {'historical_literal':8, 'original_development_variant':2, 'boundary':2}, 'Wrong material kinds')", 1)

# ------------------------------------------------ transporte: efectos permitidos
_ALLOW_OLD = "\"require(transport['allowed_operations'] == ['memory.status'] and transport['maximum_confirmations'] == 0\""
_pair_old = "(" + _ALLOW_OLD + ", " + _ALLOW_OLD + ")"
_pair_new = "(" + _ALLOW_OLD + ", \"require(transport['allowed_operations'] == " + "['memory.status', 'game.entitlement.named', 'game.install.named', 'game.uninstall.named']" + " and transport['maximum_confirmations'] == 1\")"
n_allow = s.count(_pair_old)
assert n_allow >= 3, ('allowed_operations pairs', n_allow)
s = s.replace(_pair_old, _pair_new)
_TS_OLD = "\"require(read(TRANSPORT / 'TRANSPORT_SEAL.json')['allowed_operations'] == ['memory.status'], 'transport may only authorize isolated-profile note operations')\""
_ts_pair_old = "(" + _TS_OLD + ", \"require(read(TRANSPORT / 'TRANSPORT_SEAL.json')['allowed_operations'] == ['memory.status'], 'transport may only authorize the startup memory read')\")"
_ts_pair_new = "(" + _TS_OLD + ", \"require(read(TRANSPORT / 'TRANSPORT_SEAL.json')['allowed_operations'] == " + "['memory.status', 'game.entitlement.named', 'game.install.named', 'game.uninstall.named']" + ", 'transport may only authorize the startup memory read and the steam_inst operations')\")"
sub(_ts_pair_old, _ts_pair_new, 1)

# ------------------------------------------------ inventario: calculado del árbol fusionado (nunca fijado aquí)
import hashlib as _hl, json as _js, pathlib as _pl, re as _re
_R = _pl.Path('C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo')
_c42 = _js.loads(_pl.Path('C:/Users/usuario/AppData/Local/BAXY/C03-knowledge1144-instrument-v1/private/CANDIDATE_AUTHORIZED.json').read_text(encoding='utf-8-sig'))
_names = _sp.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', 'src', 'scripts', 'main.py'], cwd=_R, encoding='utf-8').split()
_sources = {n: _hl.sha256((_R / n).read_bytes()).hexdigest() for n in sorted(set(_names)) if (_R / n).is_file()}
_count = len(_sources)
_new_sources = sorted(set(_sources) - set(_c42['source_pins']))
_NEW2 = '{' + ', '.join(repr(n) for n in _new_sources) + '}'
sub("_new_source = 'src/Baxy.Providers.Windows/External/DesktopListVisible.ps1'" + _NL
    + "require(len(sources) == 585 and set(sources) == set(c42['source_pins']) | {_new_source},",
    "_new_sources = " + _NEW2 + _NL
    + "require(len(sources) == " + str(_count) + " and set(sources) == set(c42['source_pins']) | _new_sources,", 1)
sub("'counts': {'sources': 585, 'binaries': 12, 'runtime': 5}", "'counts': {'sources': " + str(_count) + ", 'binaries': 12, 'runtime': 5}", 1)
sub("'inherited_inventory_counts': {'sources': 585, 'runtime': 5, 'binaries': 12}", "'inherited_inventory_counts': {'sources': " + str(_count) + ", 'runtime': 5, 'binaries': 12}", 1)
sub("\"require(len(candidate['source_pins']) == 585, 'expected complete 585-source manifest')\"",
    "\"require(len(candidate['source_pins']) == " + str(_count) + ", 'expected complete " + str(_count) + "-source manifest')\"", 1)
sub("\"require(len(sources) == 585 and set(sources) == set(c['source_pins']) | {'src/Baxy.Providers.Windows/External/DesktopListVisible.ps1'} and sources == inventory['source_pins'], 'complete 585-source inventory changed')\"",
    "\"require(len(sources) == " + str(_count) + " and set(sources) == set(c['source_pins']) | " + _NEW2 + " and sources == inventory['source_pins'], 'complete " + str(_count) + "-source inventory changed')\"", 1)
sub("\"require(len(prep['sources']) == 585 and len(prep['binary_pins']) == 18, 'Candidate inventory cardinality changed')\"",
    "\"require(len(prep['sources']) == " + str(_count) + " and len(prep['binary_pins']) == 18, 'Candidate inventory cardinality changed')\"", 1)

# ------------------------------------------------ delta de fuente respecto del candidato 1142: calculado ahora
_delta = sorted(n for n in _sources if _sources[n] != _c42['source_pins'].get(n))
_literal = '{' + ', '.join(repr(n) for n in _delta) + '}'
s, _n = _re.subn(r"require\(set\(delta\) == \{[^\n]*?\}, 'unexpected source delta: ' \+ str\(sorted\(delta\)\)\)",
                 "require(set(delta) == " + _literal + ", 'unexpected source delta: ' + str(sorted(delta)))", s, count=1)
assert _n == 1, 'delta literal'
