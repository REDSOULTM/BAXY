# Sequential downloader - avoids the stack overflow we hit running 25 hf processes in parallel.
# hf download is resumable, so re-running this is safe.

$ErrorActionPreference = "Continue"

$targets = @(
    @{Repo="unsloth/gemma-4-E4B-it-GGUF";       File="gemma-4-E4B-it-Q4_K_M.gguf";              Dir="models\E4B"},
    @{Repo="unsloth/gemma-4-E4B-it-GGUF";       File="gemma-4-E4B-it-Q5_K_M.gguf";              Dir="models\E4B"},
    @{Repo="unsloth/gemma-4-E4B-it-GGUF";       File="gemma-4-E4B-it-Q6_K.gguf";                Dir="models\E4B"},
    @{Repo="unsloth/gemma-4-E4B-it-GGUF";       File="gemma-4-E4B-it-Q8_0.gguf";                Dir="models\E4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="mmproj-F16.gguf";                         Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="mmproj-F16.gguf";                         Dir="models\31B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-UD-IQ2_XXS.gguf";      Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-UD-IQ2_M.gguf";        Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf";      Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-UD-Q3_K_M.gguf";       Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf";      Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-MXFP4_MOE.gguf";       Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-UD-IQ4_XS.gguf";       Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-UD-Q4_K_M.gguf";       Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-UD-Q5_K_M.gguf";       Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-26B-A4B-it-GGUF";   File="gemma-4-26B-A4B-it-UD-Q6_K.gguf";         Dir="models\26B-A4B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-UD-IQ2_XXS.gguf";          Dir="models\31B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-UD-IQ2_M.gguf";            Dir="models\31B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-UD-Q2_K_XL.gguf";          Dir="models\31B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-Q3_K_M.gguf";              Dir="models\31B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-UD-Q3_K_XL.gguf";          Dir="models\31B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-IQ4_XS.gguf";              Dir="models\31B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-Q4_K_M.gguf";              Dir="models\31B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-UD-Q4_K_XL.gguf";          Dir="models\31B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-Q5_K_M.gguf";              Dir="models\31B"},
    @{Repo="unsloth/gemma-4-31B-it-GGUF";       File="gemma-4-31B-it-Q6_K.gguf";                Dir="models\31B"}
)

$total = $targets.Count
$i = 0
foreach ($t in $targets) {
    $i++
    $dest = Join-Path $t.Dir $t.File
    if (Test-Path $dest) {
        $sz = [math]::Round((Get-Item $dest).Length / 1GB, 2)
        # Skip only if file is plausibly complete (>50MB - mmprojs are ~1GB, models 3GB+)
        if ($sz -gt 0.5) {
            Write-Host "[$i/$total] SKIP (already have ${sz}GB): $($t.File)"
            continue
        }
    }
    Write-Host "[$i/$total] DL: $($t.File)"
    hf download $t.Repo $t.File --local-dir $t.Dir 2>&1 | Select-Object -Last 1
}

Write-Host "`nAll downloads attempted. Final inventory:"
Get-ChildItem -Path "models" -Recurse -Filter *.gguf | Select-Object @{N='GB';E={[math]::Round($_.Length/1GB,2)}}, FullName | Format-Table -AutoSize
