param([int]$ExistingK2Pid = 29236)
$ErrorActionPreference = 'Stop'
$nativePython = 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe'
$nativeBase = 'artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699'
$nativeExisting = Get-Process -Id $ExistingK2Pid -ErrorAction SilentlyContinue
if ($null -ne $nativeExisting) {
    if ($nativeExisting.Path -ne 'D:\BAXYRuntime\build\llama-k2-horizon-35999d1\build-cuda13-sm86\bin\llama-server.exe') { throw 'Unexpected process identity' }
    Wait-Process -Id $ExistingK2Pid -ErrorAction SilentlyContinue
}
for ($nativeWait = 0; $nativeWait -lt 20; $nativeWait++) {
    if (Test-Path -LiteralPath "$nativeBase/run-09-bf16-high-reference699/RESOURCES.json") { break }
    Start-Sleep -Milliseconds 250
}
& $nativePython -X utf8 scratchpad/c03-review-neutral699.py 09-bf16-high-reference699 --seal-measurements
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output '09-bf16-high-reference699 completed and measured'
& $nativePython -X utf8 scratchpad/c03-k2-smoke696.py --neutral-panel --tag qwen-q4-reference699 --family qwen --ctx-size 20480 --max-tokens 16384 --no-kv-offload --no-mmap --observe-template *> "$env:TEMP/c03-k2-native699-qwen-q4-reference699.log"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $nativePython -X utf8 scratchpad/c03-review-neutral699.py qwen-q4-reference699 --seal-measurements
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output 'qwen-q4-reference699 completed and measured'
& $nativePython -X utf8 scratchpad/c03-k2-smoke696.py --neutral-panel --tag 37-q4-high-reference699 --variant 3.7B-Q4_K_M --effort high --tool-format native --ctx-size 36864 --max-tokens 32768 --no-kv-offload --no-mmap --observe-template *> "$env:TEMP/c03-k2-native699-37-q4-high-reference699.log"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $nativePython -X utf8 scratchpad/c03-review-neutral699.py 37-q4-high-reference699 --seal-measurements
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output '37-q4-high-reference699 completed and measured'
