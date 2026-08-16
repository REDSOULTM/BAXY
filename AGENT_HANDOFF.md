# BAXY private asset handoff

Use branch `codex/baxy-rebuild-v3`. The default branch has unrelated history.

This file has one purpose: restore ignored/private corpora and assets exactly.
It is not the current architecture, test baseline, debt register or general
onboarding guide. For those, read:

- `documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/README.md`;
- `documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md`.

App pins the Core child process and compares its compiled descriptor contract;
this is not a cryptographic signature of the hello. Catalog, installation and
validation snapshots are maintained only in the registry and their linked
attestations.

## Restore the canonical private bundle

The canonical data that previously blocked exhaustive `final17`/`final18`
certification is included in the private repository as the compressed,
hash-bound bundle `bootstrap/baxy-agent-assets-v1.zip`.

Restore it once from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\restore_agent_assets.ps1
```

The command validates the archive, every payload SHA-256, every byte count and
all JSONL row counts before installing anything. It restores:

- `artifacts/historical_exhaustive/all_executable_cases.jsonl` — 67,720 rows;
- `artifacts/historical_exhaustive/runtime_oracle.jsonl` — 14,845 rows;
- `artifacts/historical_exhaustive/runtime_language_scope.jsonl` — 14,845 rows;
- sibling `FunctionGemma/finetune_llm/curated/train_v3.jsonl` — 6,905 rows;
- `legacy/Experimentando/test_open_spotify.wav` — the historical voice sample.

If `FunctionGemma` must live elsewhere, pass its root explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\restore_agent_assets.ps1 `
  -FunctionGemmaRoot C:\path\to\FunctionGemma
```

An existing file with the expected hash is kept. A conflicting file fails
closed unless `-Force` is explicitly supplied.

After restoration, resume the existing exhaustive mission; do not reconstruct,
approximate or replace these canonical corpora. Start by checking the restored
inputs and the current branch state, then rerun the oracle audit, `final17` and
the remaining `final18` gates. Preserve the existing runtime installation and
model assets on the notebook.

The bundle intentionally does not redistribute the multi-gigabyte Gemma,
llama.cpp or Parakeet runtime assets. They remain separately licensed runtime
dependencies and were already installed on the target notebook according to
the installation report. This private bundle contains historical user-mission
data and a voice sample; do not mirror it to a public repository.

## Turn-evidence runtime corpus

`tests/data/turn_evidence_runtime.v1.jsonl` is intentionally ignored by Git
because its 25,156 rows combine 17,784 licensed public train rows with 7,372
privacy-screened historical rows. Its promoted SHA-256 is
`8abff5805a93615c6f5a655b9af5559063e34226cfc0db58c5547d97a70ee680`;
never use `git add -f` for it.

The current `baxy-agent-assets-v1.zip`, SHA-256
`543956a65bd11d68251b911964b3a240331c436776e8a3935733da5bdf90fe3a`,
does not contain this corpus. `restore_agent_assets.ps1` therefore cannot
restore it. Place an exact private backup at the ignored path and verify it
with the second block, or rebuild it from the official archives:

```powershell
$turnManifest = Get-Content `
  tests\data\turn_evidence_public_manifest.v1.json -Raw -Encoding UTF8 |
  ConvertFrom-Json
$prestoArchive = Join-Path $env:LOCALAPPDATA `
  'BAXYRuntime\datasets\presto-v1\presto_v1.zip'
$massiveArchive = Join-Path $env:LOCALAPPDATA `
  'BAXYRuntime\datasets\massive-v1.1\amazon-massive-dataset-1.1.tar.gz'

if ((Get-FileHash $prestoArchive -Algorithm SHA256).Hash.ToLowerInvariant() `
    -cne $turnManifest.sources.presto.archive.sha256) {
    throw 'PRESTO archive hash mismatch'
}
if ((Get-FileHash $massiveArchive -Algorithm SHA256).Hash.ToLowerInvariant() `
    -cne $turnManifest.sources.massive.archive.sha256) {
    throw 'MASSIVE archive hash mismatch'
}

experiments\mind_router_spike\.venv\Scripts\python.exe -X utf8 `
  scripts\build_public_turn_evidence.py `
  --archive $prestoArchive `
  --massive-archive $massiveArchive
if ($LASTEXITCODE -ne 0) { throw 'Turn-evidence rebuild failed' }
```

The builder uses the versioned source maps, the canonical private
`historical_messages.jsonl` and the closed product catalog. Verify all three
generated artifacts without printing corpus rows:

```powershell
$turnRuntime = Resolve-Path tests\data\turn_evidence_runtime.v1.jsonl
$turnPolicy = Get-Content `
  src\baxy_mind\data\turn_evidence_abstention_policy.v1.json `
  -Raw -Encoding UTF8 | ConvertFrom-Json
$turnHash = (Get-FileHash $turnRuntime -Algorithm SHA256).Hash.ToLowerInvariant()
$turnRows = ([IO.File]::ReadLines($turnRuntime) | Measure-Object).Count
$publicManifestHash = (Get-FileHash `
  tests\data\turn_evidence_public_manifest.v1.json `
  -Algorithm SHA256).Hash.ToLowerInvariant()
$publicHoldoutHash = (Get-FileHash `
  tests\data\turn_evidence_public_holdout.v1.jsonl `
  -Algorithm SHA256).Hash.ToLowerInvariant()

if ($turnHash -cne $turnPolicy.runtime_source_sha256 -or
    $turnRows -ne 25156 -or
    $publicManifestHash -cne `
      '933fd95e9699f434aa56edfe719094d3bd26b3163438194114dfd08f8782b296' -or
    $publicHoldoutHash -cne `
      'e1ee1746a3cb110799997367490def6199e09fa3bc9f900b2d2dd99dc9c174be') {
    throw 'Turn-evidence promotion artifacts do not match'
}
git check-ignore --quiet tests/data/turn_evidence_runtime.v1.jsonl
if ($LASTEXITCODE -ne 0) { throw 'Runtime corpus is no longer ignored' }
```

The public/versioned side consists of the two source maps, the data notice,
`turn_evidence_public_manifest.v1.json`, the 9,172-row public holdout, the
text-free final seal v2, the promoted policy and gate reports. The current
one-sided evaluation reports precision 0.994083, recall 0.42 and 0/400 false
actionable signals; family retrieval remains diagnostic only. The local E5 v4
cache contains no source text and is regenerated; neither it nor the ignored
runtime corpus belongs in Git or in the agent bundle.

The separate hierarchical E5 development v2 candidate is **not promoted**.
Its gate selected only 12/2,300 `supported_effect` utterances
(0.005217 < the preregistered 0.02 minimum), and two preregistered guard paths
did not resolve against the result schema. The paths were not repaired after
evaluation. No development weights or fast path may be loaded. The official
7,384-row MTOP test is still byte-sealed with `content_decoded:false`, and the
reserved public final holdout was not opened. Runtime therefore keeps the
existing LLM decision plus the one-sided advisory evidence.
