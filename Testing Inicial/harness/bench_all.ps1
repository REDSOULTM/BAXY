# Runs the EXTENDED harness (60 tests) on every viable GGUF using CUDA llama-server.
# Hardware target: RTX 4060 Ti 16GB. Backend: CUDA 13.1.

$ErrorActionPreference = "Continue"
$llama = "C:\llamacpp-cuda\bin\llama-server.exe"
$root = "C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4"

# Strict 16GB native: file size <= ~14GB so we leave room for KV cache + mmproj + overhead.
$models = @(
    @{Name="E2B-UD-Q2_K_XL";  Path="models\E2B\gemma-4-E2B-it-UD-Q2_K_XL.gguf";          Mmproj="models\E2B\mmproj-F16.gguf"},
    @{Name="E2B-Q3_K_M";      Path="models\E2B\gemma-4-E2B-it-Q3_K_M.gguf";              Mmproj="models\E2B\mmproj-F16.gguf"},
    @{Name="E2B-UD-Q3_K_XL";  Path="models\E2B\gemma-4-E2B-it-UD-Q3_K_XL.gguf";          Mmproj="models\E2B\mmproj-F16.gguf"},
    @{Name="E2B-Q4_K_M";      Path="models\E2B\gemma-4-E2B-it-Q4_K_M.gguf";              Mmproj="models\E2B\mmproj-F16.gguf"},
    @{Name="E2B-UD-Q4_K_XL";  Path="models\E2B\gemma-4-E2B-it-UD-Q4_K_XL.gguf";          Mmproj="models\E2B\mmproj-F16.gguf"},
    @{Name="E2B-Q5_K_M";      Path="models\E2B\gemma-4-E2B-it-Q5_K_M.gguf";              Mmproj="models\E2B\mmproj-F16.gguf"},
    @{Name="E4B-UD-IQ2_M";    Path="models\E4B\gemma-4-E4B-it-UD-IQ2_M.gguf";            Mmproj="models\E4B\mmproj-F16.gguf"},
    @{Name="E4B-Q4_K_M";      Path="models\E4B\gemma-4-E4B-it-Q4_K_M.gguf";              Mmproj="models\E4B\mmproj-F16.gguf"},
    @{Name="E4B-Q5_K_M";      Path="models\E4B\gemma-4-E4B-it-Q5_K_M.gguf";              Mmproj="models\E4B\mmproj-F16.gguf"},
    @{Name="E4B-Q6_K";        Path="models\E4B\gemma-4-E4B-it-Q6_K.gguf";                Mmproj="models\E4B\mmproj-F16.gguf"},
    @{Name="E4B-Q8_0";        Path="models\E4B\gemma-4-E4B-it-Q8_0.gguf";                Mmproj="models\E4B\mmproj-F16.gguf"},
    @{Name="31B-UD-IQ2_XXS";  Path="models\31B\gemma-4-31B-it-UD-IQ2_XXS.gguf";          Mmproj="models\31B\mmproj-F16.gguf"},
    @{Name="26B-UD-IQ2_XXS";  Path="models\26B-A4B\gemma-4-26B-A4B-it-UD-IQ2_XXS.gguf";  Mmproj="models\26B-A4B\mmproj-F16.gguf"},
    @{Name="26B-UD-IQ2_M";    Path="models\26B-A4B\gemma-4-26B-A4B-it-UD-IQ2_M.gguf";    Mmproj="models\26B-A4B\mmproj-F16.gguf"},
    @{Name="26B-UD-Q2_K_XL";  Path="models\26B-A4B\gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf";  Mmproj="models\26B-A4B\mmproj-F16.gguf"},
    @{Name="31B-UD-IQ2_M";    Path="models\31B\gemma-4-31B-it-UD-IQ2_M.gguf";            Mmproj="models\31B\mmproj-F16.gguf"},
    @{Name="31B-UD-Q2_K_XL";  Path="models\31B\gemma-4-31B-it-UD-Q2_K_XL.gguf";          Mmproj="models\31B\mmproj-F16.gguf"},
    @{Name="26B-UD-Q3_K_M";   Path="models\26B-A4B\gemma-4-26B-A4B-it-UD-Q3_K_M.gguf";   Mmproj="models\26B-A4B\mmproj-F16.gguf"},
    @{Name="26B-UD-Q3_K_XL";  Path="models\26B-A4B\gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf";  Mmproj="models\26B-A4B\mmproj-F16.gguf"},
    @{Name="26B-UD-IQ4_XS";   Path="models\26B-A4B\gemma-4-26B-A4B-it-UD-IQ4_XS.gguf";   Mmproj="models\26B-A4B\mmproj-F16.gguf"},
    @{Name="31B-Q3_K_M";      Path="models\31B\gemma-4-31B-it-Q3_K_M.gguf";              Mmproj="models\31B\mmproj-F16.gguf"}
)

function Stop-LlamaServers {
    Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

function Wait-ServerReady {
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/v1/models" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { return $true }
        } catch { Start-Sleep -Seconds 3 }
    }
    return $false
}

function Get-VramMiB {
    try {
        $out = & nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null
        return [int]$out.Trim()
    } catch { return -1 }
}

foreach ($m in $models) {
    $resultFile = Join-Path $root "results\extended_$($m.Name).json"
    if (Test-Path $resultFile) {
        Write-Host "`n========== $($m.Name) (SKIP - already done) ==========" -ForegroundColor Yellow
        continue
    }

    Write-Host "`n========== $($m.Name) ==========" -ForegroundColor Cyan
    Stop-LlamaServers

    $vramIdle = Get-VramMiB
    Write-Host "VRAM idle: $vramIdle MiB" -ForegroundColor DarkGray

    $logFile = Join-Path $root "results\server_$($m.Name).log"
    $modelPath = Join-Path $root $m.Path
    $mmprojPath = Join-Path $root $m.Mmproj

    Start-Process -FilePath $llama -ArgumentList @(
        "-m", "`"$modelPath`"",
        "--mmproj", "`"$mmprojPath`"",
        "--jinja",
        "--port", "8080",
        "-ngl", "99",
        "-c", "16384"
    ) -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" -NoNewWindow

    if (-not (Wait-ServerReady)) {
        Write-Host "Server failed to start for $($m.Name). Skipping." -ForegroundColor Red
        Stop-LlamaServers
        continue
    }
    Start-Sleep -Seconds 2  # let VRAM settle
    $vramLoaded = Get-VramMiB
    $vramDelta = $vramLoaded - $vramIdle
    Write-Host "VRAM after load: $vramLoaded MiB (delta: +$vramDelta MiB)" -ForegroundColor Green
    "$($m.Name),vram_idle_mib,$vramIdle,vram_loaded_mib,$vramLoaded,vram_delta_mib,$vramDelta" | Out-File -Append (Join-Path $root "results\vram_log.csv") -Encoding utf8

    Write-Host "Running extended bench..." -ForegroundColor Green
    & python (Join-Path $root "harness\run_bench_extended.py") $m.Name
    Stop-LlamaServers
}

Write-Host "`nAll done." -ForegroundColor Green
