$ErrorActionPreference = 'Stop'
$selectorPython = 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe'
# Run only after the native reference queue has ended: no concurrent inference.
if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) { throw 'A model server is already running' }
& $selectorPython -X utf8 scratchpad/c03-k2-smoke696.py --selector-ablation --tag qwen-without-policy700 --family qwen --ctx-size 8192 --max-tokens 4096 *> "$env:TEMP/c03-k2-selector700-qwen-without-policy700.log"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $selectorPython -X utf8 scratchpad/c03-review-k2-panel696.py qwen-without-policy700 --ablation700
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output 'qwen-without-policy700 completed; manual adjudication pending'
& $selectorPython -X utf8 scratchpad/c03-k2-smoke696.py --selector-ablation --tag k2-without-policy700 --variant 3.7B-Q4_K_M --effort high --tool-format native --ctx-size 8192 --max-tokens 4096 --no-mmap --observe-template *> "$env:TEMP/c03-k2-selector700-k2-without-policy700.log"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $selectorPython -X utf8 scratchpad/c03-review-k2-panel696.py k2-without-policy700 --ablation700
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output 'k2-without-policy700 completed; manual adjudication pending'
