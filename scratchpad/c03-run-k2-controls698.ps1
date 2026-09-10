$ErrorActionPreference = 'Stop'
$k2Python = 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe'
$k2Profiles = @(
    @{tag='37-q4-high-parser698-1'; variant='3.7B-Q4_K_M'; effort='high'; format='native'},
    @{tag='37-q4-low-parser698-1'; variant='3.7B-Q4_K_M'; effort='low'; format='native'},
    @{tag='37-q4-medium-parser698-1'; variant='3.7B-Q4_K_M'; effort='medium'; format='native'},
    @{tag='09-q8-low-parser698-1'; variant='0.9B-Q8_0'; effort='low'; format='json'},
    @{tag='09-q8-medium-parser698-1'; variant='0.9B-Q8_0'; effort='medium'; format='json'}
)
$k2Plan = 'artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/CONTROLS698_PLAN.json'
if (Test-Path -LiteralPath $k2Plan) { throw 'Plan already exists; do not overwrite an experiment.' }
@{utc=[DateTime]::UtcNow.ToString('o'); profiles=$k2Profiles; panel=50; context=8192; max_tokens=4096;
  backend='BACKEND_BUILD698.json'; sequential=$true;
  purpose='Final corrected controls: high reference, practical low, and medium diagnostic after official implicit-tool-boundary fix. Preserve all errors and malformed effort outputs; no automatic C03 credit.'} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $k2Plan -Encoding UTF8
foreach ($k2Profile in $k2Profiles) {
    $k2Tag = $k2Profile.tag
    & $k2Python -X utf8 'scratchpad/c03-k2-smoke696.py' --panel --tag $k2Tag --variant $k2Profile.variant --effort $k2Profile.effort --tool-format $k2Profile.format --ctx-size 8192 --max-tokens 4096 --no-mmap --observe-template *> "$env:TEMP/c03-k2-run696-$k2Tag.log"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output "$k2Tag completed"
}
