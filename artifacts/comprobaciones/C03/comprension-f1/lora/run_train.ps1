param([string]$Tag, [int]$Max = 0, [double]$Epochs = 1.0, [int]$Rank = 16)
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
$args = @("-X", "utf8", "D:\BAXYTrain\scripts\train_decider.py", "--out", "D:\BAXYTrain\$Tag", "--epochs", "$Epochs",
          "--rank", "$Rank", "--bf16", "--base", "D:\BAXYTrain\qwen35-4b-hf-851bf6e8", "--data", "D:\BAXYTrain\data")
if ($Max -gt 0) { $args += @("--max", "$Max") }
& D:\BAXYTrain\venv\Scripts\python.exe @args *> "D:\BAXYTrain\$Tag.out"
"exit $LASTEXITCODE" | Out-File -Append "D:\BAXYTrain\$Tag.out"
