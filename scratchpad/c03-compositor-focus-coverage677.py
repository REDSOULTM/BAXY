"""Repeat the exact17 integrated cases with requested-focus coverage676."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-compositor-focus-feedback675.py').read_text(encoding='utf-8')
source = source.replace('compositor-focus-feedback675', 'compositor-focus-coverage677').replace('compositor674', 'compositor676')
source = source.replace('Integrated source674 appends externally verified field contradiction to the existing retry; compare retry payloads to673.', 'Integrated source676 also checks explicitly requested single-window focus coverage and distinguishes missing answers from contradicted values. Same17 cases675; no new model, system instruction or answer template.')
exec(compile(source, __file__, 'exec'))
