"""Second controlled hypothesis: remove reference history, leave policy unchanged."""
from pathlib import Path
source = Path(__file__).with_name('c03-negative-current-selection.py').read_text(encoding='utf-8')
source = source.replace("base / 'astra-negative-current-selection'", "base / 'astra-negative-no-history'")
source = source.replace("for stage in ('baseline', 'current_request_policy'):", "for stage in ('without_history',):")
source = source.replace("contracts, history)", "contracts, [])")
source = source.replace("'history': history", "'history': [], 'removed_reference_history': history")
source = source.replace("'method': 'Same twelve", "'method': 'Only change from baseline of previous probe is removing the reference history. No policy clarification. The contextual Ponlo control explicitly tests the loss. Same twelve")
exec(compile(source, str(Path(__file__)), 'exec'))
