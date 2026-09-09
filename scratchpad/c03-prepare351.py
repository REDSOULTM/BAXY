"""Prepare the same seven product requests with the previously available Qwen3.5 override."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
target=root/'scratchpad/c03-product351.py'
assert not target.exists()
text=(root/'scratchpad/c03-product345.py').read_text(encoding='utf-8').replace('345','351')
text=text.replace('default registered2507','diagnostic Qwen3.5-4B-Q4_K_M override, registered2507 unchanged')
text=text.replace('No classifier/model injection or sampling override.', 'No classifier/response injection or sampling override. The only model difference against345 is the previously available Qwen3.5-4B-Q4_K_M; all roles use the same override.')
text=text.replace('registered model/configuration unchanged.', 'registered manifest unchanged; diagnostic model override declared below. Source and sampling unchanged from345;350 native controls improved6/13 to10/13 without reaching acceptance.')
text=text.replace("manifest = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'", "manifest = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'\nmodel=Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')\nassert sha(model)=='00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'")
text=text.replace("'manifest_sha256':sha(manifest),", "'manifest_sha256':sha(manifest),\n    'diagnostic_model_override':{'path':str(model),'sha256':sha(model),'promotion':False},")
text=text.replace('env.update(BAXY_MIND_PYTHONPATH=', 'env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_PYTHONPATH=')
target.write_text(text,encoding='utf-8')
hook=root/'scratchpad/c03-owner351-hook'
hook.mkdir(exist_ok=False)
(hook/'sitecustomize.py').write_text((root/'scratchpad/c03-owner345-hook/sitecustomize.py').read_text(encoding='utf-8').replace('345','351'),encoding='utf-8')
print('351 same seven inputs prepared, Qwen3.5 override explicit; no runtime promotion.')
