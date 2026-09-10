$ErrorActionPreference = 'Stop'
$practicalPython = 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe'
if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) { throw 'A model server is already running' }
& $practicalPython -X utf8 scratchpad/c03-k2-smoke696.py --neutral-panel --tag qwen-q4-practical699 --family qwen --ctx-size 8192 --max-tokens 4096 --no-mmap --observe-template *> "$env:TEMP/c03-k2-native699-qwen-q4-practical699.log"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $practicalPython -X utf8 scratchpad/c03-review-neutral699.py qwen-q4-practical699 --seal-measurements
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output 'qwen-q4-practical699 completed; manual review pending'
& $practicalPython -X utf8 scratchpad/c03-k2-smoke696.py --neutral-panel --tag 37-q4-low-practical699 --variant 3.7B-Q4_K_M --effort low --tool-format native --ctx-size 8192 --max-tokens 4096 --no-mmap --observe-template *> "$env:TEMP/c03-k2-native699-37-q4-low-practical699.log"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $practicalPython -X utf8 scratchpad/c03-review-neutral699.py 37-q4-low-practical699 --seal-measurements
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output '37-q4-low-practical699 completed; manual review pending'
