from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-evaluate176.py').read_text(encoding='utf-8')
source=source.replace('astra-linear176','astra-gain178').replace('voice/webrtc176','voice/webrtc178').replace('C03-linear176-private','C03-gain178-private')
source=source.replace("for name in ['near_only','physical_echo_plus_synthetic_near']:","for name in ['physical_echo','near_only','physical_echo_plus_synthetic_near']:")
source=source.replace("stt=Path(json.loads", "cases.append(('cold_silence',np.zeros(32000,np.float32),np.zeros(32000,np.float32)))\nstt=Path(json.loads")
source=source.replace("if name!='native_echo149':", "if name in {'near_only','physical_echo_plus_synthetic_near'}:")
source=source.replace('Local diagnostic build, not deployed','Experimental default echo-path gain0.1; same static library176; not deployed')
with (root/'scratchpad/c03-evaluate178.py').open('x',encoding='utf-8') as f:f.write(source)
print('178 evaluator prepared from176; all five174 controls, same settings.')
