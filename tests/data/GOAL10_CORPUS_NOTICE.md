# Goal 10 corpus freeze — privacy notice

`N10`, `M10` and `C10` are projections of observed user turns from the private
historical authorities `historical_messages.jsonl` and
`historical_message_mapping.jsonl`. They are local project data. They are not
a public dataset and must not be published as one.

Generated JSONL with user-text payload is **not versioned**:

- `tests/data/goal10_n10.v1.jsonl`
- `tests/data/goal10_m10.v1.jsonl`
- `tests/data/goal10_c10.v1.jsonl`

Rebuild them with `python -X utf8 scripts/freeze_goal10_corpus.py`. What Git
keeps is the freeze rules, schema, counts, hashes, the five repetition
families, per-partition publication, tests, and
`goal10_partition_index.v1.jsonl` (message_id plus owner/environment stamps,
never `text_literal`).

09.5.4 `residual_evidence` is not reparsed. The 1.947/626 turns and 808/281
missions from commit `a6cd673` remain the exact subset floor; any 09.5 user-turn
delta is counted from the live authorities only.
