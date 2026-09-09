"""Record the fresh English quantity read without granting follow-up coverage."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-update-survey632.py').read_text(encoding='utf-8')
source = source.replace('1ee9583ffc2255819fbf90f5faa40227950a04005965bb3fa9862921aff0f0f8', '1690681dedef92f03cb75afec5b4030f978acd0c9f5902de4d723d457d37caa1')
source = source.replace('verification_reason_before632', 'verification_reason_before642')
start = source.index(" row['verification_reason']=")
end = source.index(" row['verification_evidence'].append", start)
source = source[:start]+" row['verification_reason']='641/642 adds a fresh typed English quantity read. Twelve explicit named/count reads match independent unchanged Windows snapshots. H0040 remains open: four contextual follow-ups fail; English focus language is a separate defect. No UI/voice credit or coverage from explicit names alone.'\n row['generalization_status']='explicit_names_and_es_en_counts_verified642_followups_open'\n"+source[end:]
source = source.replace('astra-window-evidence632', 'astra-count-product642').replace('C03-window-evidence632-private/evidence.json', 'C03-count-product642-private/adjudication.json').replace('read-only adjudication of541 plus current Python scope probe; no current English inference', 'Registered shared product641; exact20panel640 repeated:15 verified,5 failed. Fresh English quantity observation and independent Win32 snapshots.')
exec(compile(source, __file__, 'exec'))
