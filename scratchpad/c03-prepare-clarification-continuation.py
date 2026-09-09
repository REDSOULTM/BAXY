from pathlib import Path
import json
import shutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
old='astra-clarification-error-qwen'
new='astra-clarification-continuation-qwen'
out=base/new
assert not out.exists()
(out/'profile').mkdir(parents=True)
shutil.copyfile(base/old/'profile/sitecustomize.py',out/'profile/sitecustomize.py')
requests=['¿Cómo está el audio?', 'Ajusta el volumen.', 'Déjalo al 80%.',
          '¿A qué volumen está?', 'Set the volume.', 'Set it to 60%.',
          'What is the volume?', 'Set the volume, por favor.', 'Al 40%, please.',
          '¿Cómo está el audio?', 'Pon el volumen al 100%.', '¿Cómo está el audio?']
(base/(new+'.turns.jsonl')).write_text(''.join(json.dumps({'cmd':'turn','text':q},ensure_ascii=False)+'\n' for q in requests),encoding='utf-8')
s=(root/'scratchpad/c03-clarification-error-qwen.py').read_text(encoding='utf-8')
s=s.replace(old,new).replace('c03-clarification-error-qwen.py','c03-clarification-continuation.py')
s=s.replace('comprobaciones-c03-clarification-error-qwen','comprobaciones-c03-clarification-continuation-qwen')
start=s.index(" 'method':")
end=s.index(" 'registrationSha256'",start)
s=s[:start]+" 'method':'Inherited conductor, 12 development turns to verify clarification continuation with real audio volume effects: ask incomplete adjustment then supply an absolute level in Spanish, English and mixed input. Read audio independently afterward. Restore volume to 100, the value observed in the immediately preceding diagnostic, and read again. No playback or mute changes requested. Qwen base without LoRA, explicit GGUF and q8 KV diagnostic overrides, native sampling and read-only observer. Not graphical UI nor fresh acceptance.',\n"+s[end:]
(root/'scratchpad/c03-clarification-continuation.py').write_text(s,encoding='utf-8')
print('Prepared clarification answers, actual volume effects and restoration to observed100.')
