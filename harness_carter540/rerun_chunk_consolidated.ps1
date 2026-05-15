param(
    [string]$Tag = "rerun_consol",
    [string]$Quant = "Q6_K",
    [int]$Start,
    [int]$End,
    [string]$Label
)
$ErrorActionPreference = "Continue"
$llama = "C:\llamacpp-cuda\bin\llama-server.exe"
$root = "C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4"
$modelPath = "$root\models\E4B\gemma-4-E4B-it-Q6_K.gguf"
$mmprojPath = "$root\models\E4B\mmproj-F16.gguf"
$harness = "$root\harness_carter540"
$resDir = "$harness\results"

Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

$logFile = "$resDir\server_${Tag}_${Label}.log"
Start-Process -FilePath $llama -ArgumentList @(
    "-m", "`"$modelPath`"",
    "--mmproj", "`"$mmprojPath`"",
    "--jinja", "--port", "8080",
    "-ngl", "99", "-c", "16384",
    "--parallel", "1",
    "--ctx-checkpoints", "1",
    "--flash-attn", "on"
) -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" -NoNewWindow

$deadline = (Get-Date).AddMinutes(3)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:8080/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { break }
    } catch { Start-Sleep 2 }
}
Write-Host "Server ready, running [$Start..$End]" -ForegroundColor Green

Set-Location $harness
$output = "$resDir\${Tag}_${Quant}_${Label}.json"
python run_bench_consolidated.py --model "${Quant}_${Label}" --start $Start --end $End --output $output 2>&1 |
    Tee-Object -FilePath "$resDir\${Tag}_${Quant}_${Label}.log" |
    Select-String -Pattern "(MODELO|TOTAL|Pass rate|^  C\d+|========)" |
    Select-Object -Last 25

Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
