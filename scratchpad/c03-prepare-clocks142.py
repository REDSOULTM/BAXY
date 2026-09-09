from pathlib import Path
s = Path('scratchpad/c03-audio-clocks141.py').read_text(encoding='utf-8')
s = s.replace('astra-clocks141', 'astra-clocks142')
s = s.replace('with pa.PyAudio() as backend:', "wasapi = next(api for api in sd.query_hostapis() if api['name'] == 'Windows WASAPI')\nwith pa.PyAudio() as backend:")
s = s.replace("with sd.InputStream(samplerate=16000,channels=1,dtype='float32',blocksize=512,", "with sd.InputStream(device=wasapi['default_input_device'], extra_settings=sd.WasapiSettings(auto_convert=True),\n                            samplerate=16000,channels=1,dtype='float32',blocksize=512,")
s = s.replace('Diagnostic native callbacks; clocks only', 'WASAPI input on same default physical Realtek; shared auto_convert enabled; clocks only')
with Path('scratchpad/c03-audio-clocks142.py').open('x',encoding='utf-8') as f:
    f.write(s)
