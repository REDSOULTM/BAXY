"""Second bounded guard comparison: explicit request/completeness/count semantics."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-guard-boundary594.py').read_text(encoding='utf-8')
source = source.replace('594', '595').replace('guard-boundary595', 'guard-contract595')
start = source.index("old = 'incomplete_effect")
end = source.index('\ncases = ', start)
source = source[:start] + '''old = original['messages'][0]['content']
new = (
    "Classify the user's actual request, not actions merely mentioned. "
    "Choose request_type: stable_conversation for greetings, reactions, "
    "questions about the assistant's identity, explanations, hypothetical "
    "discussion, or instructions NOT to act. Informal language, insults and "
    "typos do not make conversation an incomplete action. external_read for "
    "a request to obtain current information, consult a named source, or "
    "read personal data or computer state. environment_change for a request "
    "to change the computer or the real world, regardless of whether the "
    "assistant can do it. HOWEVER, use incomplete_effect instead of either "
    "effect type when a requested effect lacks an essential target, value "
    "or resolved reference. Do not invent missing arguments. Count only "
    "requested positive atomic effects: zero for conversation or a prohibition, "
    "one for one outcome even with several modifiers, multiple for two or "
    "more independently requested outcomes. Incomplete effects still count. "
    "Do not select operations or answer the user."
)
candidate = new
''' + source[end:]
source = source.replace('replacing only incomplete-effect definition', 'replacing only the complete guard instruction')
source = source.replace('Ambiguous wording classifies conversational noise as an incomplete effect. Require an actual request for external reading/change before missing arguments can imply incomplete_effect.', '594 fixedH0012 without regression but retained five preregistered control failures. Second comparison gives the same classifier explicit positive-request, missing-argument and independent-outcome semantics; same16cases and greedy grammar. This is the final prompt comparison before changing strategy if the control gate still fails.')
exec(compile(source, __file__, 'exec'))
