"""Keep H0040 open for the actual remaining prose defect after reference repair."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-update-survey632.py').read_text(encoding='utf-8')
source = source.replace('1ee9583ffc2255819fbf90f5faa40227950a04005965bb3fa9862921aff0f0f8', 'a1267bbc568e856a89d91da839f32efa9b71651db5bc5bec835be7463311f549')
source = source.replace('verification_reason_before632', 'verification_reason_before647')
start = source.index(" row['verification_reason']=")
end = source.index(" row['verification_evidence'].append", start)
source = source[:start]+" row['verification_reason']='646/647 repairs all four contextual named/pronominal reads and preserves16 application names/counts. H0040 remains open because the first published t15 draft adds running without a process observation. English focus language remains a separate defect.648 reconciles packaged window counts using later AUMID metadata with compatible process names/creation times; timing limitation explicit. No UI/voice credit.'\n row['generalization_status']='names_counts_and_references_verified647_unobserved_liveness_prose_open'\n"+source[end:]
source = source.replace('astra-window-evidence632', 'astra-context-product647').replace('C03-window-evidence632-private/evidence.json', 'C03-context-product647-private/adjudication.json').replace('read-only adjudication of541 plus current Python scope probe; no current English inference', 'Registered shared product646; exact20panel642 repeated:18 correct finals,2 failed; four contextual fresh reads repaired. First-draft unsupported running claim keeps requirement open.')
exec(compile(source, __file__, 'exec'))
