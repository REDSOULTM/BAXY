from pathlib import Path

source = Path('scratchpad/c03-speex129.py').read_text(encoding='utf-8')
source = source.replace('astra-speex129', 'astra-speex130').replace('C03-speex129-private', 'C03-speex130-private')
source = source.replace('assert lib.speex_preprocess_ctl(pre, 0, c.byref(zero)) == 0', '# Default denoise enables all spectral gain, including echo suppression.')
source = source.replace('denoise and AGC disabled, echo suppression defaults unchanged', 'Default denoise enabled as upstream testecho.c; AGC off; echo suppression defaults unchanged.129 disabled all spectral gain unintentionally.')
source = source.replace("for method in ['raw', 'aec', 'aec_residual']:", "for method in ['aec_residual']:")
source = source.replace("'methods': ['raw', 'aec', 'aec_residual']", "'methods': ['aec_residual']")
with Path('scratchpad/c03-speex130.py').open('x', encoding='utf-8') as stream:
    stream.write(source)
