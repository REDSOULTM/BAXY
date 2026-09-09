"""Keep H0040 open after scoped reads expose a failing application variant."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-update-survey632.py').read_text(encoding='utf-8')
source=source.replace('1ee9583ffc2255819fbf90f5faa40227950a04005965bb3fa9862921aff0f0f8','6b09a8af1c44d52274c7dd97af5ed759637db4a9f46f276b22bdcef2514d92af')
source=source.replace('verification_reason_before632','verification_reason_before634')
start=source.index(" row['verification_reason']=");end=source.index(" row['verification_evidence'].append",start)
source=source[:start]+" row['verification_reason']='633/634 corrects application scope in all8 app queries, including H0040 ES and EN. Coverage remains open: Notepad variant reports no window, contradicted by window.active; packaged app inventory must be repaired. Focus English also has a separate language failure. No UI/voice acceptance.'\n"+source[end:]
source=source.replace('astra-window-evidence632','astra-window-product634').replace('C03-window-evidence632-private/evidence.json','C03-window-product634-private/adjudication.json').replace('read-only adjudication of541 plus current Python scope probe; no current English inference','registered shared product633:8application reads,2focus controls,2no-effect controls; individual observation and prose adjudication')
exec(compile(source,__file__,'exec'))
