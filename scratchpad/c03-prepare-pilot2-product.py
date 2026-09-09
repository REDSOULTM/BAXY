"""Reuse the completed warm integrated driver, changing only diagnostic adapter and observer bug."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
name='astra-lora-pilot2-product'
folder=ROOT/'artifacts/comprobaciones/C03'/name
assert not folder.exists()
(folder/'profile').mkdir(parents=True)
profile=(ROOT/'artifacts/comprobaciones/C03/astra-qwen2507-corpus-warm/profile/sitecustomize.py').read_text(encoding='utf-8')
profile=profile.replace('"component":"skill_registry", "encoderSupplied":kwargs.get("encoder") is not None',
                        '"component":"skill_registry", "encoderSupplied":getattr(self,"_encoder",None) is not None')
profile+='''

_original_server_command = LlmRuntime._server_command
def _adapter_server_command(self):
    command = _original_server_command(self)
    if Path(str(getattr(self, "_gguf", ""))).name.casefold() == "qwen3-4b-instruct-2507-q4_k_m.gguf":
        command.extend(["--lora", "D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/c03-pilot-lora-v2-f32.gguf"])
    return command
LlmRuntime._server_command = _adapter_server_command
'''
(folder/'profile/sitecustomize.py').write_text(profile,encoding='utf-8')
turns=ROOT/'artifacts/comprobaciones/C03/astra-qwen2507-corpus-warm.turns.jsonl'
(folder.parent/(name+'.turns.jsonl')).write_bytes(turns.read_bytes())
driver=(ROOT/'scratchpad/c03-qwen2507-corpus-warm.py').read_text(encoding='utf-8')
driver=driver.replace('astra-qwen2507-corpus-warm',name).replace('comprobaciones-c03-qwen2507-corpus-warm','comprobaciones-c03-lora-pilot2-product')
driver=driver.replace('scratchpad/c03-qwen2507-corpus-warm.py','scratchpad/c03-lora-pilot2-product.py')
driver=driver.replace('Missing calibrated runtime corpus caused TurnEvidenceService policy incompatibility. Inherit the exact corpus and verified existing vector cache from prior BAXY, with unchanged calibration, model and sampler. Retain original boolean audio projection after failed categorical experiment. Observe service/catalog readiness in the actual product and all 21 existing development replies.',
                       'Pilot2 improved direct compound facts and some mixed replies. Measure its effect across the existing integrated development requests and all LLM roles, including exact confirmation, cancellation and own fixture close. Add only the diagnostic LoRA; source, registry and validators unchanged. Correct the observer to read the actual SkillRegistry encoder.')
driver=driver.replace("manifest_hash = sha(manifest_path)","manifest_hash = sha(manifest_path)\nassert not (out/'PREREG.json').exists()\nadapter = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/c03-pilot-lora-v2-f32.gguf')")
driver=driver.replace("'profile': {'model': str(model), 'sha256': sha(model), 'ngl': 99,", "'profile': {'model': str(model), 'sha256': sha(model), 'adapter': str(adapter), 'adapterSha256': sha(adapter), 'ngl': 99,")
# The fixture is an empty owned window. Record whether BAXY closes it before any cleanup.
driver=driver.replace('released=False','''released=False
import win32gui
assert not win32gui.FindWindow(None, "Ventana C03 de prueba"), "Existing fixture title must be inspected, not reused blindly"
fixture=subprocess.Popen([str(ROOT/'scratchpad/C03TitleFixture.exe')],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'FIXTURE.json').write_text(json.dumps({'pid':fixture.pid,'path':str(ROOT/'scratchpad/C03TitleFixture.exe'),'sha256':sha(ROOT/'scratchpad/C03TitleFixture.exe')}),encoding='utf-8')
time.sleep(1)
assert fixture.poll() is None
''')
driver=driver.replace('    gpu.stop(); ram.stop()', '''    fixture_closed_by_product = fixture.poll() is not None
    fixture_cleanup_needed = not fixture_closed_by_product
    if fixture_cleanup_needed:
        fixture.terminate(); fixture.wait(timeout=10)
    gpu.stop(); ram.stop()''')
driver=driver.replace("'exitCode': process.returncode if process else None,", "'exitCode': process.returncode if process else None, 'fixtureClosedBeforeCleanup': fixture_closed_by_product, 'fixtureCleanupNeeded': fixture_cleanup_needed,")
target=ROOT/'scratchpad/c03-lora-pilot2-product.py'
assert not target.exists();target.write_text(driver,encoding='utf-8')
print(target)
