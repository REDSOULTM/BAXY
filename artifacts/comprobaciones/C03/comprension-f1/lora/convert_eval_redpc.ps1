param([string]$Tag)
$py = "D:\BAXYTrain\venv\Scripts\python.exe"
$env:PYTHONPATH = "D:\BAXYTrain\llama.cpp-b9980\gguf-py"
$env:PYTHONUTF8 = "1"
& $py D:\BAXYTrain\llama.cpp-b9980\convert_lora_to_gguf.py --base D:\BAXYTrain\qwen35-4b-hf-851bf6e8 --outtype f16 --outfile "D:\BAXYTrain\gguf\decider-$Tag.gguf" "D:\BAXYTrain\$Tag" *> "D:\BAXYTrain\convert-$Tag.out"
"convert exit $LASTEXITCODE" | Out-File -Append "D:\BAXYTrain\convert-$Tag.out"
if (-not (Test-Path "D:\BAXYTrain\gguf\decider-$Tag.gguf")) { exit 1 }
$srv = "D:\BAXYTrain\llama-b9980-cuda12.4\llama-server.exe"; $g = "D:\BAXYTrain\gguf\Qwen3.5-4B-Q4_K_M.gguf"
foreach ($s in @("DEV-A", "DEV-B")) {
  if (-not (Test-Path "D:\BAXYTrain\eval\base-$s.jsonl")) {
    & $py -X utf8 D:\BAXYTrain\eval\remote_eval.py --set "D:\BAXYTrain\eval\sets\$s.jsonl" --out "D:\BAXYTrain\eval\base-$s.jsonl" --server $srv --gguf $g *> "D:\BAXYTrain\eval\base-$s.log"
  }
  & $py -X utf8 D:\BAXYTrain\eval\remote_eval.py --set "D:\BAXYTrain\eval\sets\$s.jsonl" --out "D:\BAXYTrain\eval\$Tag-$s.jsonl" --server $srv --gguf $g --lora "D:\BAXYTrain\gguf\decider-$Tag.gguf" *> "D:\BAXYTrain\eval\$Tag-$s.log"
}
"EVAL_DONE" | Out-File -Append "D:\BAXYTrain\convert-$Tag.out"
