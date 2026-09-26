# Launcher on the owner's main PC (redpc, D:\BAXYTrain), run as a hidden scheduled task over SSH: bf16 LoRA (D14).
param([string]$Tag, [int]$Max = 0, [double]$Epochs = 1.0, [int]$Rank = 16, [string]$Data = "D:\BAXYTrain\data")
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
$args = @("-X", "utf8", "D:\BAXYTrain\scripts\train_decider.py", "--out", "D:\BAXYTrain\$Tag", "--epochs", "$Epochs",
          "--rank", "$Rank", "--bf16", "--base", "D:\BAXYTrain\qwen35-4b-hf-851bf6e8", "--data", $Data)
if ($Max -gt 0) { $args += @("--max", "$Max") }
& D:\BAXYTrain\venv\Scripts\python.exe @args *> "D:\BAXYTrain\$Tag.out"
"exit $LASTEXITCODE" | Out-File -Append "D:\BAXYTrain\$Tag.out"
