"""Resume550 after installing its missing ml_dtypes in the isolated tool directory."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-e5-avx2550.py').read_text(encoding='utf-8')
source=source.replace('astra-e5-avx2550','astra-e5-avx2551').replace('C03-e5-avx2550-private','C03-e5-avx2551-private').replace('reduce_range550.onnx','reduce_range551.onnx')
exec(compile(source,__file__,'exec'))
