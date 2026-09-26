# redpc: train a LoRA, then convert it and evaluate it on DEV-A/DEV-B (convert_eval.ps1). One hidden scheduled task.
param([string]$Tag, [int]$Max = 0, [double]$Epochs = 1.0, [string]$Data = "D:\BAXYTrain\data_v2")
& D:\BAXYTrain\scripts\run_train.ps1 -Tag $Tag -Max $Max -Epochs $Epochs -Data $Data
if (Test-Path "D:\BAXYTrain\$Tag\adapter_model.safetensors") { & D:\BAXYTrain\scripts\convert_eval.ps1 -Tag $Tag }
