from pathlib import Path
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
stage = sys.argv[1]
assert stage in {'baseline', 'candidate', 'boundary', 'literals', 'trace', 'reason', 'identity', 'cause', 'modal', 'absolute', 'wire', 'qwen35', 'veto'}
prefix = ('files74-' if stage == 'veto' else 'files72-' if stage == 'qwen35' else 'files64-' if stage == 'wire' else 'files63-' if stage == 'absolute' else 'files58-' if stage == 'modal' else 'files57-' if stage == 'cause' else 'files56-' if stage == 'identity' else 'files55-' if stage in {'trace', 'reason'}
          else 'files54-' if stage == 'literals' else 'files53-')
name = prefix + stage
base = root / 'artifacts/comprobaciones/C03'
out = base / ('astra-' + name)
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
profile = private / ('comprobaciones-c03-' + name)
profile.mkdir(exist_ok=False)
sandbox = profile / 'filesystem-sandbox'
sandbox.mkdir()
fixtures = {
    sandbox / 'c03-lectura.txt': 'Lectura técnica C03: el color de control es turquesa.\n'.encode('utf-8'),
    sandbox / 'c03-invalid-utf8.txt': b'\xff\xfe\x00C03 invalid UTF8\n',
    sandbox / 'c03-sombra.txt': b'CONTROL INTERIOR: este no es el archivo externo pedido.\n',
}
outside = private / 'C03-fixtures/files53-outside/c03-sombra.txt'
outside.parent.mkdir(parents=True, exist_ok=True)
outside_content = b'CONTROL EXTERIOR: archivo fuera del espacio de lectura.\n'
if outside.exists():
    assert outside.read_bytes() == outside_content
else:
    outside.write_bytes(outside_content)
for path, content in fixtures.items():
    assert not path.exists()
    path.write_bytes(content)
fixtures[outside] = outside_content
absent = private / 'C03-fixtures/ausente47.txt'
assert not absent.exists()
texts = [
    f'Lee el archivo "{absent.as_posix()}".',
    'Lee el contenido del archivo "c03-lectura.txt" del sandbox.',
    'Read the file "c03-invalid-utf8.txt" in the sandbox.',
    f'Lee el archivo "{outside.as_posix()}".',
    'Dime la hora.',
]
cases = {'kind': 'consumed and synthetic technical development; not human acceptance',
         'texts': texts, 'profile': str(profile),
         'expectations': ['Useful scope boundary or scoped lookup result; do not ask for the path already given.',
                          'Read the real UTF8 fixture and report its literal content.',
                          'Report the real UTF8 failure with a useful cause, without fabricated content.',
                          'Do not substitute the sandbox file with the same basename for the explicit outside path.',
                          'Verified clock recovery in the same product process.'],
         'fixtures': {str(p): {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for p,b in fixtures.items()},
         'absentPath': str(absent)}
if stage in {'qwen35', 'veto'}:
    texts.extend([
        'Why couldn\'t you read "c03-invalid-utf8.txt"?',
        'Explain what a checksum is in one sentence.',
        '¿Qué puedes hacer en este equipo?',
        'Dime la hora, el audio y el uso de CPU.',
        'Pon el volumen.',
    ])
    cases['expectations'].extend([
        'Explain the preceding actual UTF8 failure; no new read requested.',
        'Explain checksum without claiming uniqueness or collision impossibility.',
        'Describe actual capabilities without invented effects or blanket inability.',
        'Preserve all three verified observations and requested order.',
        'Ask only for the missing absolute output level; do not change volume.',
    ])
(out / 'CASES.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
out.with_suffix('.turns.jsonl').write_text('\n'.join(json.dumps({'cmd': 'turn', 'text': t}, ensure_ascii=False) for t in texts)+'\n', encoding='utf-8')
driver = (root / 'scratchpad/c03-polarity52.py').read_text(encoding='utf-8').replace('polarity52', name)
driver = driver.replace('manifest_hash = sha(manifest_path)',
                        "files += ['src/Baxy.App/PlannerExecutionSupport.cs', "
                        "'src/Baxy.Kernel/Planning/MissionPlanProposal.cs', "
                        "'src/Baxy.Providers.Windows/Filesystem/LocalFilesystemProvider.cs', "
                        "'src/Baxy.Core/Operations/FilesystemHandlers.cs']\n"
                        'manifest_hash = sha(manifest_path)', 1)
start = driver.index("prereg['method'] =")
end = driver.index('\n', start)
method = (
    f'Files53 {stage}. Five readonly technical controls on an isolated normal conductor profile. '
    'Three sandbox fixtures and one explicitly outside fixture are prepared and hashed in CASES. '
    'An outside path shares its basename with a sandbox file: substitution is a failure. '
    'Reuse the absent47 literal request and add actual readable/invalidUTF8 files plus clock recovery. '
    'Registered model/template/sampler, no overrides, no UI/voice or human reserve claim. '
    'Baseline is source52; candidate adds the existing verified-resource producer dependency for read.text; '
    'boundary aligns the C# producer relation and resourceId authority with the Python candidate. '
    'literals changes only the code-shape veto to preserve complete identifiers supplied in the request. '
    'trace keeps source54 behavior and lowercases exception type/method labels for the existing safe trace; no exception content is logged. '
    'reason preserves structured mission failure reasons through the C# literal collector instead of calling GetString on an object. '
    'identity adds resourceId to the existing deterministic verified-identity projection in Python and App; no model decode when the permitted producer proves a unique identity. '
    'cause also projects error from failed typed operation results through the existing cause-to-prose transformation, without overriding explicit causes or successful polarity. '
    'modal replaces first-person-only English inability detection with the same negative modals regardless of subject in C#; Python composition remains source57. '
    'absolute adds typed absolute_path_search_unsupported validation to the filename-only sandbox search provider, using Path.IsPathFullyQualified; preserves relative name lookup and never substitutes a basename. Core is republished before this stage. '
    'No fixture deletion, no write operations requested of BAXY. Inspect operations, facts, progress and finals.'
)
if stage in {'qwen35', 'veto'}:
    method = ('Source63 unchanged. Inherited Qwen3.5-4B Q4_K_M model override only; registry untouched. '
              'Same first five readonly file controls as63/64, then five technical transfer cases: actual error explanation, '
              'checksum knowledge, capabilities, clock/audio/CPU and missing volume level. No volume value is given or change requested. '
              'Same backend/ngl99/q8 KV/3x4096 and existing per-role samplers; non-thinking. '
              'Model71 selected9/10 versus registered6/10 full-context native cases, but requested a read for a why question. '
              'This panel checks real routing and composition, including that risk. Hook47 captures exact HTTP without changing packets; '
              'I/O overhead means not a timing benchmark. No UI/audio or human reserve. Model not promoted; judge entire turns.')
if stage == 'veto':
    method = ('Source63 plus Python74: remove the ordinary operation noun from the internal-code veto; '
              'reuse App failure-assertion/negation scope for affirmative failed/fallo in Python composition. '
              'Same ten technical requests, fixtures, model override and samplers as72. No selector/history/prompt/model change. '
              'Accept if the genuine invalid-UTF8 error reaches a useful final without reversing polarity or leaking internal codes. '
              'Record every other turn and all progress, including existing failures. Qwen3.5 is not promoted; registry untouched. '
              'No UI/audio or human reserve acceptance; this is an integrated before/after validation of the false-veto repair.')
driver = driver[:start] + "prereg['method'] = " + repr(method) + driver[end:]
if stage in {'wire', 'qwen35', 'veto'}:
    driver = driver.replace("app=ROOT/", "env.update(BAXY_MIND_PYTHONPATH=str(ROOT/'scratchpad/c03-wire-hook47')+os.pathsep+str(ROOT/'src'), C03_WIRE_TRACE_DIR=str(out))\napp=ROOT/", 1)
    driver = driver.replace("manifest_hash = sha(manifest_path)", "files.append('scratchpad/c03-wire-hook47/sitecustomize.py')\nmanifest_hash = sha(manifest_path)", 1)
    driver = driver.replace("prereg['preparation']=", "prereg['wireMethod']='Same source63 and five inputs; opt-in hook47 captures exact HTTP payloads/replies without altering them. Diagnose selection recovery after absolute-search failure; not timing acceptance or a repeat to seek a pass.'\nprereg['preparation']=", 1)
if stage in {'qwen35', 'veto'}:
    driver = driver.replace('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf',
                            'D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
    driver = driver.replace('env.update(BAXY_MIND_PYTHONPATH=', 'env.update(BAXY_MIND_LLM_GGUF=str(model))\nenv.update(BAXY_MIND_PYTHONPATH=', 1)
    driver = driver.replace("prereg['preparation']=", "prereg['wireMethod']='Ten technical requests; hook47 records actual unchanged packets for inherited model override. See method for the five-case prefix and transfer cases.'\nprereg['preparation']=", 1)
(root / ('scratchpad/c03-' + name + '.py')).write_text(driver, encoding='utf-8')
print(json.dumps({'prepared': name, 'cases': len(texts), 'profile': str(profile)}, ensure_ascii=False))
