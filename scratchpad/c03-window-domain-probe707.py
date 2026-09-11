"""Test one morphology hypothesis in memory while source705 stays frozen."""
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import effect_intent

out = root / 'artifacts/comprobaciones/C03/astra-window-domain-probe707'
out.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
positives = [
    'Enumera las ventanas.',
    'Muéstrame las ventanas.',
    'Lista mis ventanas.',
    'Dime cuántas ventanas hay abiertas.',
    '¿Cuáles son las ventanas abiertas?',
    'Las ventanas abiertas, muéstramelas.',
    'Quiero ver todas las ventanas del escritorio.',
    'Enséñame las ventanas que tengo abiertas.',
    '¿Qué ventanas están visibles ahora?',
    'Cuenta las ventanas de mi PC.',
    'Muestra las ventanas de Opera.',
    '¿Hay varias ventanas del navegador?',
    'Lista las ventanas y luego dime la hora.',
    '¿Cuántas ventanas de la aplicación están abiertas?',
    'Busca la ventana titulada "Atlas 42".',
    '¿Qué ventana está activa?',
    'Muéstrame la ventana actual.',
    'Lista las ventanas minimizadas.',
    'Necesito los títulos de las ventanas abiertas.',
    'Dime qué ventanas tengo en este escritorio.',
    'List my windows.',
    'Show all open windows.',
    'Which windows are open?',
    'How many windows are visible right now?',
    'List the windows and then tell me the time.',
    'Show the browser windows.',
    'Find the window titled "Cedar 73".',
    'Which window is active?',
    'What are the titles of my open windows?',
    'Show windows on this desktop.',
    'Baxy, lista mis windows.',
    'Muéstrame las open windows.',
    'Which ventanas tengo abiertas?',
    'Dime los titles de las ventanas abiertas.',
    'Las windows del navegador, list them.',
    'Show las ventanas del escritorio.',
    'Cuenta mis ventanas, please.',
    'List las ventanas y luego dime la hora.',
    'Find la ventana titulada "Maple 19".',
    'Qué window está active?',
]
negatives = [
    'Explica cómo sellar las ventanas de la cocina.',
    'Quiero pintar las ventanas de mi casa.',
    'Enumera los tipos de ventanas de aluminio.',
    '¿Por qué las ventanas de doble vidrio aíslan mejor?',
    'Cuenta las ventanas dibujadas en este plano arquitectónico.',
    '¿Qué significa una ventana de oportunidad?',
    'Describe las ventanas de oportunidad para una empresa.',
    'Explícame Windows 11, el sistema operativo.',
    '¿Cómo está la red neuronal?',
    'Haz una captura del ladrón.',
    'How do I clean the windows in my kitchen?',
    'List the windows shown on this house floor plan.',
    'What is a window of opportunity?',
    'Explain the Windows operating system.',
    'Why does glass fog up on house windows?',
    'Quiero clean las ventanas de mi cocina.',
    'Explain las ventanas de oportunidad en negocios.',
    'Lista los tipos de house windows para construir.',
    'Compare Windows 11 con Linux como sistemas operativos.',
    'Show me window insulation techniques for my house.',
]
cases = [{'id': f'P{i:02}', 'text': text, 'expected_domain': True} for i, text in enumerate(positives, 1)]
cases += [{'id': f'N{i:02}', 'text': text, 'expected_domain': False} for i, text in enumerate(negatives, 1)]
assert len(cases) == 60
source = inspect.getsource(effect_intent._window_domain)
candidate = source.replace('ventana|window', 'ventanas?|windows?')
candidate = candidate.replace(r'foreground\s+window\b', r'foreground\s+windows?\b')
assert candidate != source
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': sha(root / 'src/baxy_mind/effect_intent.py'),
          'operation': 'window.resolve', 'cases': cases,
          'hypothesis': 'Allow grammatical number in the existing window domain predicate, changing only that in an isolated module. Do not add surface aliases or bypass read-only gates.',
          'criterion': 'Compare false vetoes and false domains across the complete60; any remaining expected-positive failure or new expected-negative acceptance prevents treating the hypothesis as a complete correction.',
          'scope': 'Synthetic technical domain checks, not model decisions, provider execution, product acceptance or survey coverage. Other intent gates still own negation and action authority.'}
write(out / 'PREREG.json', prereg)
(out / 'IN_MEMORY_CANDIDATE.txt').write_text(candidate, encoding='utf-8')
before = [effect_intent.operation_domain_is_grounded(row['text'], 'window.resolve') for row in cases]
namespace = dict(vars(effect_intent))
exec(compile(candidate, '<isolated-window-domain-number>', 'exec'), namespace)
original = effect_intent._window_domain
try:
    effect_intent._window_domain = namespace['_window_domain']
    after = [effect_intent.operation_domain_is_grounded(row['text'], 'window.resolve') for row in cases]
finally:
    effect_intent._window_domain = original
assert sha(root / 'src/baxy_mind/effect_intent.py') == prereg['source_sha256']
rows = [{**row, 'before': old, 'after': new} for row, old, new in zip(cases, before, after)]
result = {'utc': datetime.now(timezone.utc).isoformat(), 'rows': rows, 'counts': {
    'cases': len(cases), 'positive': len(positives), 'negative': len(negatives),
    'baseline_correct': sum(row['before'] == row['expected_domain'] for row in rows),
    'candidate_correct': sum(row['after'] == row['expected_domain'] for row in rows),
    'gains': sum(row['before'] != row['expected_domain'] and row['after'] == row['expected_domain'] for row in rows),
    'losses': sum(row['before'] == row['expected_domain'] and row['after'] != row['expected_domain'] for row in rows),
    'remaining_false_vetoes': sum(row['expected_domain'] and row['after'] is not True for row in rows),
    'remaining_false_domains': sum(not row['expected_domain'] and row['after'] is not False for row in rows),
}, 'adopted': False, 'product_source_changed': False, 'model_inference': False, 'coverage_added': 0}
write(out / 'RESULT.json', result)
lines = ['# Diagnóstico de dominio de ventanas: número gramatical', '',
         'Sonda técnica aislada de 60 textos sintéticos. No ejecuta operaciones ni llama a un modelo.', '',
         json.dumps(result['counts'], ensure_ascii=False), '',
         '| Caso | Texto | Dominio esperado | Antes | Propuesta |', '|---|---|---|---|---|']
for row in rows:
    lines.append(f"| {row['id']} | {row['text']} | {row['expected_domain']} | {row['before']} | {row['after']} |")
lines += ['', 'La fuente productiva no cambia. Esta sonda no acredita cobertura ni respuesta veraz del producto.']
(out / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(result['counts'])
