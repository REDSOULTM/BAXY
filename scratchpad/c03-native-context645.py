"""Single native-policy difference with identical diagnostic candidate sets."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-native-context644.py').read_text(encoding='utf-8')
source = source.replace('astra-native-context644', 'astra-native-context645').replace('C03-native-context644-private', 'C03-native-context645-private')
source = source.replace("for arm, selected in [('current', names), ('diagnostic_candidate', added)]:", "for arm, selected in [('candidate_only', added), ('context_contract', added)]:")
source = source.replace("panel.append({**case, 'arm': arm,", '''if arm == 'context_contract':
            client.payload['messages'][0]['content'] += (
                ' Use prior dialogue only to resolve what the current message refers to or leaves implicit.'
                ' A follow-up question about the current state of this computer or another named item'
                ' requires a new external read, even if an earlier answer reported a state.'
                ' Earlier observations are not current results. Do not repeat a prior action because'
                ' it appears in history, and do not read or act for acknowledgements or prohibitions.'
            )
        panel.append({**case, 'arm': arm,''')
source = source.replace('Only append missing window.application.status as last candidate replacing the last of28.', 'Both arms have the same diagnostic candidate set from644. Only the second appends the general current-read/context boundary to the native system policy; no examples or output literals.')
source = source.replace('643 contextual lexical query helps two followups but loses an independent network candidate; no global history concatenation adopted.', '644 candidate availability repairs three English selections but Spanish still recites prior results or refuses, and a prohibition triggers a read. The native policy lacks the contextual follow-up sentence present in TURN_POLICY_PROMPT. One rule difference, no source adoption.')
exec(compile(source, __file__, 'exec'))
