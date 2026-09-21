# --- TYPEDWALLPAPER: el fondo de escritorio se cambia y se relee del registro — sobre el panel de VIDEO1955 (turnos ordinarios).
# Generado por make_typed_panels.py; se ejecuta dentro de derive_<new>.py (la variable s es el build).
# Cardinalidades: 1 literales, 3 variantes, 2 límites (N = 6).
# Preset/restore: preset: guardar HKCU\Control Panel\Desktop\Wallpaper; restore: SPI con el original
import subprocess as _sp
_NL = chr(10)

sub("    'disney_bare_request': 'Pedir algo en Disney+ sin decir qué ver, por transcripción cortada o mal oída (H0113 «on everybody en Disney.», H0130 «Toda la serie en Disney Plus», H0252 «Bueno, una serie East Plus.», H0270 «pon Una serie en Disney+»): el título es el único dato que falta y es lo único que se pregunta; cero operaciones —ni navegar al servicio ni elegir por la persona— y un final en el idioma del pedido que sea una sola pregunta por la serie o película que quiere ver, sin pedir confirmación de sí o no, sin preguntar por el servicio que ya nombró y sin negar la capacidad.',\n",
    "    'wallpaper_set': 'Fondo de pantalla (H0459 «cambiá el fondo de pantalla a azul»): exactamente una desktop.wallpaper.set completada y verificada (color liso escrito como imagen y aplicado por SPI, releído del registro), y un final que diga el color (o la imagen) aplicado; nada inventado.'," + _NL, 1)
sub("LITERALS = [('H0113', 'disney_bare_request'), ('H0130', 'disney_bare_request'), ('H0252', 'disney_bare_request'), ('H0270', 'disney_bare_request')]",
    "LITERALS = " + "[('H0459', 'wallpaper_set')]", 1)
sub("VARIANTS = [('video1955-dev-01', 'disney_bare_request', 'put something on Disney Plus'),"
    + _NL + "            ('video1955-dev-02', 'disney_bare_request', 'dale, prendé una peli en disney')]",
    "VARIANTS = " + "[('typedwallpaper-dev-01', 'wallpaper_set', 'set the wallpaper to red'),\n            ('typedwallpaper-dev-02', 'wallpaper_set', 'poné el fondo de escritorio verde'),\n            ('typedwallpaper-dev-03', 'wallpaper_set', 'cambiá el fondo a negro')]", 1)
sub("BOUNDARIES = [('video1955-boundary-01', 'No pongas nada en Disney+.',"
    + _NL + "               'Prohibición: reconocimiento, cero operaciones, sin pedir un título ni negar la capacidad.'),"
    + _NL + "              ('video1955-boundary-02', '¿Quién sos?',"
    + _NL + "               'Pregunta de identidad: respuesta propia, cero operaciones.')]",
    "BOUNDARIES = " + "[('typedwallpaper-boundary-01', 'no cambies el fondo', 'Prohibición: reconocimiento, cero operaciones.'),\n            ('typedwallpaper-boundary-02', 'cambiá el fondo a transparente', 'Color no soportado: límite honesto, cero operaciones.')]", 1)
sub("FIXTURE_APP = {}", "FIXTURE_APP = " + '{}', 1)
sub("ALLOWED = ['memory.status']" + _NL, "ALLOWED = " + "['memory.status', 'desktop.wallpaper.set']" + _NL, 1)
sub("ALLOWED_BY_GROUP = {'disney_bare_request': ['memory.status'], 'no_effect_boundary': ['memory.status']}",
    "ALLOWED_BY_GROUP = " + "{'wallpaper_set': ['memory.status', 'desktop.wallpaper.set'], 'no_effect_boundary': ['memory.status']}", 1)
sub("EXPECTED_BY_GROUP = {'disney_bare_request': []}", "EXPECTED_BY_GROUP = " + "{'wallpaper_set': ['desktop.wallpaper.set']}", 1)
# D13: the registry literal is measured with the owner's third party substituted; the panel records it.
sub("'fixture_app': FIXTURE_APP.get(c['case_id']),", "'fixture_app': FIXTURE_APP.get(c['case_id']), 'fixture_step': CASE_FIXTURE_STEPS.get(c['case_id']),", 1)
sub("LITERALS = ", "LITERAL_SUBSTITUTIONS = " + '{}' + _NL + "CASE_FIXTURE_STEPS = " + '{}' + _NL + "LITERALS = ", 1)
sub("'text': row['literal'], 'criterion': CRIT[group],", "'text': LITERAL_SUBSTITUTIONS.get(cid, row['literal']), 'literal_registry': row['literal'], 'literal_measured': cid in LITERAL_SUBSTITUTIONS, 'criterion': CRIT[group],", 1)
# The three registry bindings compare the registry literal, never the measured text (runner / prepare / adjudicate).
sub("runner_extra = (" + _NL, "runner_extra = (" + _NL + "    (\"require(registered['literal'] == case['text'] and case['expectation_kind'] == registered['expectation_kind']\", \"require(registered['literal'] == case.get('literal_registry', case['text']) and case['expectation_kind'] == registered['expectation_kind']\"),  # D13 literal_measured" + _NL, 1)
sub("rebind(P42 / 'root_prepare.py', P44 / 'root_prepare.py', consts + (" + _NL, "rebind(P42 / 'root_prepare.py', P44 / 'root_prepare.py', consts + (" + _NL + "    (\"require(literal_cases[case_id]['text'] == row['literal'], 'literal text changed: ' + case_id)\", \"require(literal_cases[case_id].get('literal_registry', literal_cases[case_id]['text']) == row['literal'], 'literal text changed: ' + case_id)\"),  # D13 literal_measured" + _NL, 1)
sub("rebind(P42 / 'root_adjudicate_from_decisions.py', P44 / 'root_adjudicate_from_decisions.py', consts + (" + _NL, "rebind(P42 / 'root_adjudicate_from_decisions.py', P44 / 'root_adjudicate_from_decisions.py', consts + (" + _NL + "    (\"require(row['literal'] == panel[decision['index']]['text'], 'Literal differs from registry')\", \"require(row['literal'] == panel[decision['index']].get('literal_registry', panel[decision['index']]['text']), 'Literal differs from registry')\"),  # D13 literal_measured" + _NL, 1)
# sin grupo revisado
assert 'disney_bare_request' not in s, 'restos del panel viejo'

# ------------------------------------------------ cardinalidades: 1 literales, 3 variantes, 2 límites
sub("counts = {'cases': N, 'historical_literals': 4, 'original_development_variants': 2, 'boundaries': 2, 'wire_lines': 2 * N,",
    "counts = {'cases': N, 'historical_literals': 1, 'original_development_variants': 3, 'boundaries': 2, 'wire_lines': 2 * N,", 1)
sub("kind_counts = {'historical_literal': 4, 'original_development_variant': 2, 'boundary': 2}",
    "kind_counts = {'historical_literal': 1, 'original_development_variant': 3, 'boundary': 2}", 1)
sub("'historical_literals': 4, 'original_development_variants': 2, 'boundaries': 2, 'wire_lines': 16, 'session_controls': 8, 'ordinary_turns': 8, 'reviewed_turns': 0, 'maximum_reportable_terminals': 8, 'maximum_internal_confirmations': 0}\"",
    "'historical_literals': 1, 'original_development_variants': 3, 'boundaries': 2, 'wire_lines': 12, 'session_controls': 6, 'ordinary_turns': 6, 'reviewed_turns': 0, 'maximum_reportable_terminals': 6, 'maximum_internal_confirmations': 0}\"", 1)
# turnos ordinarios

sub("== ['historical_literal'] * 4 + ['original_development_variant'] * 2 + ['boundary'] * 2,",
    "== ['historical_literal'] * 1 + ['original_development_variant'] * 3 + ['boundary'] * 2,", 1)
sub("{'historical_literal': 4, 'original_development_variant': 2, 'boundary': 2}, 'kind counts')",
    "{'historical_literal': 1, 'original_development_variant': 3, 'boundary': 2}, 'kind counts')", 1)
sub("panel[0:4]] == ids, 'literal order')", "panel[0:1]] == ids, 'literal order')", 1)
sub("and seal['kind_counts'] == {'historical_literal': 4, 'original_development_variant': 2, 'boundary': 2}, 'Material cardinalities changed')",
    "and seal['kind_counts'] == {'historical_literal': 1, 'original_development_variant': 3, 'boundary': 2}, 'Material cardinalities changed')", 1)
sub("need(seal['kind_counts'] == {'historical_literal':4, 'original_development_variant':2, 'boundary':2}, 'Wrong material kinds')",
    "need(seal['kind_counts'] == {'historical_literal':1, 'original_development_variant':3, 'boundary':2}, 'Wrong material kinds')", 1)

# ------------------------------------------------ transporte: efectos permitidos
_ALLOW_OLD = "\"require(transport['allowed_operations'] == ['memory.status'] and transport['maximum_confirmations'] == 0\""
_pair_old = "(" + _ALLOW_OLD + ", " + _ALLOW_OLD + ")"
_pair_new = "(" + _ALLOW_OLD + ", \"require(transport['allowed_operations'] == " + "['memory.status', 'desktop.wallpaper.set']" + " and transport['maximum_confirmations'] == 0\")"
n_allow = s.count(_pair_old)
assert n_allow >= 3, ('allowed_operations pairs', n_allow)
s = s.replace(_pair_old, _pair_new)
_TS_OLD = "\"require(read(TRANSPORT / 'TRANSPORT_SEAL.json')['allowed_operations'] == ['memory.status'], 'transport may only authorize isolated-profile note operations')\""
_ts_pair_old = "(" + _TS_OLD + ", \"require(read(TRANSPORT / 'TRANSPORT_SEAL.json')['allowed_operations'] == ['memory.status'], 'transport may only authorize the startup memory read')\")"
_ts_pair_new = "(" + _TS_OLD + ", \"require(read(TRANSPORT / 'TRANSPORT_SEAL.json')['allowed_operations'] == " + "['memory.status', 'desktop.wallpaper.set']" + ", 'transport may only authorize the startup memory read and the wallpaper operations')\")"
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
