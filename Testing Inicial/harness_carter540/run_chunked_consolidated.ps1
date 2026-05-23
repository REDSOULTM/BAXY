# Same as run_chunked.ps1 but uses run_bench_consolidated.py + tool_schemas_consolidated.json

param(
    [string]$Tag = "consolidated",
    [string]$Quant = "Q6_K"
)

$ErrorActionPreference = "Continue"
$llama = "C:\llamacpp-cuda\bin\llama-server.exe"
$root = "C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4"
$modelPath = "$root\models\E4B\gemma-4-E4B-it-Q6_K.gguf"
$mmprojPath = "$root\models\E4B\mmproj-F16.gguf"
$harness = "$root\harness_carter540"
$resDir = "$harness\results"

function Stop-LlamaServers {
    Get-Process -Name "llama-server" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

function Start-Server($logSuffix) {
    $logFile = "$resDir\server_${Tag}_${logSuffix}.log"
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
            $r = Invoke-WebRequest "http://127.0.0.1:8080/health" `
                -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { return $true }
        } catch { Start-Sleep 2 }
    }
    return $false
}

$chunks = @(
    @{ start = 0;   end = 90;  label = "C01-C03" },
    @{ start = 90;  end = 180; label = "C04-C06" },
    @{ start = 180; end = 270; label = "C07-C09" },
    @{ start = 270; end = 360; label = "C10-C12" },
    @{ start = 360; end = 450; label = "C13-C15" },
    @{ start = 450; end = 540; label = "C16-C18" }
)

Set-Location $harness
foreach ($c in $chunks) {
    Write-Host "`n========== CHUNK $($c.label) [$($c.start)-$($c.end)] ==========" -ForegroundColor Cyan
    Stop-LlamaServers
    if (-not (Start-Server $c.label)) {
        Write-Host "Server failed for chunk $($c.label). Skipping." -ForegroundColor Red
        continue
    }
    $output = "$resDir\${Tag}_${Quant}_$($c.label).json"
    python run_bench_consolidated.py --model "${Quant}_$($c.label)" `
        --start $c.start --end $c.end `
        --output $output 2>&1 | Tee-Object -FilePath "$resDir\${Tag}_${Quant}_$($c.label).log" |
        Select-String -Pattern "(MODELO|TOTAL|Pass rate|^  C\d+|========)" |
        Select-Object -Last 25
}

Stop-LlamaServers
Write-Host "`nAll chunks done." -ForegroundColor Green
