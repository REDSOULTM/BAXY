"""Move H0040's remaining cause from provider observations to follow-up reading."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-update-survey632.py').read_text(encoding='utf-8')
source=source.replace('1ee9583ffc2255819fbf90f5faa40227950a04005965bb3fa9862921aff0f0f8','afba54e3c585a8c79224f729d9cb4defad426bb7cd601b4a9187b587c40f4c75')
source=source.replace('verification_reason_before632','verification_reason_before640')
start=source.index(" row['verification_reason']=");end=source.index(" row['verification_evidence'].append",start)
source=source[:start]+" row['verification_reason']='638/639/640 verifies packaged identity and visible HWND counts; WhatsApp positive ES/EN and Spanish quantity read pass. Still open: named and pronominal follow-ups lose context; English quantity returns a matching prior number without a new typed read. Focus English has a separate mixed-language classification defect. No coverage from explicit names alone or UI/voice credit.'\n row['generalization_status']='explicit_names_and_counts_verified639_640_followups_open'\n"+source[end:]
source=source.replace('astra-window-evidence632','astra-window-reference-product640').replace('C03-window-evidence632-private/evidence.json','C03-window-reference-product640-private/adjudication.json').replace('read-only adjudication of541 plus current Python scope probe; no current English inference','registered shared product638:20cases with packaged app, named/pronominal follow-ups and ES/EN quantities;14verified,6failed_or_unverified;639 independent HWND snapshots support scope/counts')
exec(compile(source,__file__,'exec'))
